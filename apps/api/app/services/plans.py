"""Saving, merging and presenting a package's delivery plan."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contract, Package, PackagePlan, PlanItem, PlanStep
from app.schemas.plan import (
    FindingOut,
    PlanItemOut,
    PlanOut,
    PlanStepOut,
    ProgressOut,
)
from app.services.plan_parser import (
    Finding,
    ParsedItem,
    ParsedPlan,
    ParsedStep,
    plan_findings,
)

_TRACKED = ("status", "actual_start", "actual_end", "tracking_note")


def effective_step_status(
    status: str, end_date: date | None, today: date
) -> tuple[str, int | None]:
    """A step past its end date and not finished is `delayed`; one without a date never is."""
    if status in {"not_started", "in_progress"} and end_date is not None and end_date < today:
        return "delayed", (today - end_date).days
    return status, None


def progress_of(steps: list[PlanStep]) -> ProgressOut:
    done = sum(1 for s in steps if s.status == "done")
    total = len(steps)
    return ProgressOut(done=done, total=total, pct=round(done * 100 / total, 1) if total else 0.0)


async def package_contract_end(session: AsyncSession, package_id: uuid.UUID) -> date | None:
    contract = (
        (
            await session.execute(
                select(Contract)
                .where(Contract.package_id == package_id, Contract.deleted_at.is_(None))
                .order_by(Contract.signed_date.nulls_last())
            )
        )
        .scalars()
        .first()
    )
    if contract is None:
        return None
    return contract.extended_end_date or contract.planned_end_date


def _as_parsed(plan: PackagePlan, items: list[PlanItem], steps: list[PlanStep]) -> ParsedPlan:
    """The stored plan in the shape the consistency rules read."""
    return ParsedPlan(
        contract_start=plan.contract_start,
        contract_end=plan.contract_end,
        implement_start=plan.implement_start,
        implement_end=plan.implement_end,
        declared_total=plan.declared_total,
        items=[
            ParsedItem(
                line_no=i.line_no,
                name=i.name,
                quantity=i.quantity,
                assignments=list(i.assignments),
            )
            for i in items
        ],
        steps=[
            ParsedStep(
                step_no=s.step_no,
                content=s.content,
                start_date=s.start_date,
                end_date=s.end_date,
            )
            for s in steps
        ],
    )


def finding_out(f: Finding) -> FindingOut:
    return FindingOut(code=f.code, severity=f.severity, message=f.message)


async def load_plan(
    session: AsyncSession, package_id: uuid.UUID
) -> tuple[PackagePlan, list[PlanItem], list[PlanStep]] | None:
    plan = (
        await session.execute(select(PackagePlan).where(PackagePlan.package_id == package_id))
    ).scalar_one_or_none()
    if plan is None:
        return None
    items = list(
        (
            await session.execute(
                select(PlanItem).where(PlanItem.plan_id == plan.id).order_by(PlanItem.line_no)
            )
        )
        .scalars()
        .all()
    )
    steps = list(
        (
            await session.execute(
                select(PlanStep)
                .where(PlanStep.plan_id == plan.id)
                .order_by(PlanStep.step_no, PlanStep.created_at)
            )
        )
        .scalars()
        .all()
    )
    return plan, items, steps


def present(
    plan: PackagePlan,
    items: list[PlanItem],
    steps: list[PlanStep],
    contract_end: date | None,
    today: date,
) -> PlanOut:
    step_out: list[PlanStepOut] = []
    for s in steps:
        out = PlanStepOut.model_validate(s)
        out.effective_status, out.days_late = effective_step_status(  # type: ignore[assignment]
            s.status, s.end_date, today
        )
        step_out.append(out)
    findings = plan_findings(_as_parsed(plan, items, steps), contract_end=contract_end)
    return PlanOut(
        id=plan.id,
        package_id=plan.package_id,
        addressee=plan.addressee,
        legal_basis=plan.legal_basis,
        contract_text=plan.contract_text,
        contract_start=plan.contract_start,
        contract_end=plan.contract_end,
        implement_text=plan.implement_text,
        implement_start=plan.implement_start,
        implement_end=plan.implement_end,
        locations=list(plan.locations),
        signer=plan.signer,
        declared_total=plan.declared_total,
        total_quantity=sum(i.quantity or 0 for i in items),
        source_file_name=plan.source_file_name,
        imported_at=plan.imported_at,
        items=[PlanItemOut.model_validate(i) for i in items],
        steps=step_out,
        progress=progress_of(steps),
        findings=[finding_out(f) for f in findings],
    )


def match_tracking(old_steps: list[PlanStep], new_steps: list[ParsedStep]) -> dict[int, PlanStep]:
    """Index in `new_steps` -> the old step with the same wording whose tracking is kept.

    Each old step is used at most once, in order, so repeated wording is paired one to one.
    """
    pool: dict[str, list[PlanStep]] = {}
    for old in old_steps:
        pool.setdefault(old.content_hash, []).append(old)
    matched: dict[int, PlanStep] = {}
    for index, new in enumerate(new_steps):
        candidates = pool.get(new.content_hash)
        if candidates:
            matched[index] = candidates.pop(0)
    return matched


async def save_plan(
    session: AsyncSession,
    package: Package,
    parsed: ParsedPlan,
    *,
    file_name: str,
    user_id: uuid.UUID,
) -> tuple[PackagePlan, int, bool]:
    """Create or replace the package's plan. Returns (plan, kept tracking count, replaced)."""
    existing = await load_plan(session, package.id)
    replaced = existing is not None
    kept: dict[int, dict[str, Any]] = {}
    if existing is not None:
        plan, _old_items, old_steps = existing
        for index, old in match_tracking(old_steps, parsed.steps).items():
            kept[index] = {k: getattr(old, k) for k in _TRACKED}
        await session.execute(delete(PlanStep).where(PlanStep.plan_id == plan.id))
        await session.execute(delete(PlanItem).where(PlanItem.plan_id == plan.id))
    else:
        plan = PackagePlan(package_id=package.id, created_by=user_id)
        session.add(plan)
    plan.updated_by = user_id
    for field in (
        "addressee",
        "legal_basis",
        "contract_start",
        "contract_end",
        "implement_start",
        "implement_end",
        "signer",
        "declared_total",
    ):
        setattr(plan, field, getattr(parsed, field))
    plan.contract_text = parsed.contract_text
    plan.implement_text = parsed.implement_text
    plan.locations = list(parsed.locations)
    plan.source_file_name = file_name
    plan.imported_at = datetime.now(UTC)
    plan.imported_by = user_id
    await session.flush()

    for item in parsed.items:
        session.add(
            PlanItem(
                plan_id=plan.id,
                line_no=item.line_no,
                name=item.name,
                details=item.details,
                unit=item.unit,
                quantity=item.quantity,
                assignments=list(item.assignments),
                note=item.note,
            )
        )
    for index, step in enumerate(parsed.steps):
        session.add(
            PlanStep(
                plan_id=plan.id,
                group_no=step.group_no,
                group_title=step.group_title,
                step_no=step.step_no,
                content=step.content,
                content_hash=step.content_hash,
                time_text=step.time_text,
                start_date=step.start_date,
                end_date=step.end_date,
                estimated=step.estimated,
                time_note=step.time_note,
                participants=list(step.participants),
                **kept.get(index, {}),
            )
        )
    await session.flush()
    return plan, len(kept), replaced
