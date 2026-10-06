"""Progress rules (SPEC 4.4): weighted package progress, stage status, task dependencies."""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Package, StagePlan

STAGE_ORDER = (
    "S1_START",
    "S2_SELECTION",
    "S3_EXECUTION",
    "S4_ACCEPTANCE",
    "S5_PAYMENT_SETTLEMENT",
)
STAGE_NAMES = {
    "S1_START": "Khởi động",
    "S2_SELECTION": "Lựa chọn nhà thầu",
    "S3_EXECUTION": "Thực hiện hợp đồng",
    "S4_ACCEPTANCE": "Nghiệm thu bàn giao",
    "S5_PAYMENT_SETTLEMENT": "Thanh toán, thanh lý, quyết toán",
}
# SPEC 3.13: default weights 10/20/40/20/10 (editable).
DEFAULT_WEIGHTS = {
    "S1_START": Decimal(10),
    "S2_SELECTION": Decimal(20),
    "S3_EXECUTION": Decimal(40),
    "S4_ACCEPTANCE": Decimal(20),
    "S5_PAYMENT_SETTLEMENT": Decimal(10),
}

_TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class StageFacts:
    stage_code: str
    progress_pct: Decimal
    weight: Decimal
    status: str


def package_progress(stages: Iterable[StageFacts]) -> Decimal:
    """sum(progress x weight) / sum(weight); 0 when no stage carries weight (SPEC 4.4)."""
    items = list(stages)
    total_weight = sum((s.weight for s in items), Decimal(0))
    if total_weight == 0:
        return Decimal(0)
    weighted = sum((s.progress_pct * s.weight for s in items), Decimal(0))
    return (weighted / total_weight).quantize(_TWO_PLACES)


def current_stage(stages: Iterable[StageFacts]) -> str:
    """First stage that is not done; the last one once everything is done."""
    ordered = sorted(stages, key=lambda s: STAGE_ORDER.index(s.stage_code))
    for s in ordered:
        if s.status != "done":
            return s.stage_code
    return STAGE_ORDER[-1]


def effective_stage_status(
    status: str, planned_end: date | None, progress_pct: Decimal, today: date
) -> str:
    """A stage past its planned end and not finished shows as `delayed` (SPEC 7.1 STAGE_DELAYED)."""
    if status in {"done", "blocked"}:
        return status
    if planned_end is not None and planned_end < today and progress_pct < 100:
        return "delayed"
    return status


def stage_dates_valid(
    planned_start: date | None,
    planned_end: date | None,
    actual_start: date | None,
    actual_end: date | None,
) -> list[str]:
    """Names of the date pairs that run backwards (empty list means fine)."""
    bad: list[str] = []
    if planned_start and planned_end and planned_end < planned_start:
        bad.append("planned_end")
    if actual_start and actual_end and actual_end < actual_start:
        bad.append("actual_end")
    return bad


def would_create_cycle(
    edges: Mapping[uuid.UUID, Iterable[uuid.UUID]],
    task_id: uuid.UUID,
    new_deps: Iterable[uuid.UUID],
) -> bool:
    """True if making `task_id` depend on `new_deps` closes a loop (or points at itself)."""
    graph = {k: set(v) for k, v in edges.items()}
    graph[task_id] = set(new_deps)
    seen: set[uuid.UUID] = set()
    stack = list(graph[task_id])
    while stack:
        node = stack.pop()
        if node == task_id:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph.get(node, ()))
    return False


def all_tasks_done(statuses: Iterable[str]) -> bool:
    """SPEC 4.4: when every task of a stage is done, suggest marking the stage done."""
    items = list(statuses)
    return bool(items) and all(s == "done" for s in items)


# --- database helpers ---------------------------------------------------------------------------


def _stage_facts(rows: Iterable[StagePlan]) -> list[StageFacts]:
    return [StageFacts(r.stage_code, r.progress_pct, r.weight, r.status) for r in rows]


async def ensure_stage_plans(session: AsyncSession, package: Package) -> list[StagePlan]:
    """Every package owns the five standard stages (SPEC 3.13); create the missing ones."""
    rows = list(
        (await session.execute(select(StagePlan).where(StagePlan.package_id == package.id)))
        .scalars()
        .all()
    )
    have = {r.stage_code for r in rows}
    for code in STAGE_ORDER:
        if code not in have:
            row = StagePlan(
                package_id=package.id,
                stage_code=code,
                name=STAGE_NAMES[code],
                weight=DEFAULT_WEIGHTS[code],
                progress_pct=0,
                status="not_started",
            )
            session.add(row)
            rows.append(row)
    await session.flush()
    return sorted(rows, key=lambda r: STAGE_ORDER.index(r.stage_code))


async def recompute_package(session: AsyncSession, package: Package) -> None:
    """Refresh the package's progress and current stage from its stages."""
    rows = await ensure_stage_plans(session, package)
    facts = _stage_facts(rows)
    package.progress_pct = package_progress(facts)
    package.current_stage = current_stage(facts)
