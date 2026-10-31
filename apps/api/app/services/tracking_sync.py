"""Sync the tracking workbook into the Lam Dong project: packages, contracts, milestones, risks.

The workbook is the source of truth. A dry run and a real run share one code path: both write
inside a transaction and the dry run rolls back, so the printed report is exactly what would change.
Fields the workbook leaves empty are never cleared.

Usage (from apps/api):
    uv run python -m app.services.tracking_sync --file <workbook.xlsx>          # dry run
    uv run python -m app.services.tracking_sync --file <workbook.xlsx> --apply  # write
"""

import argparse
import asyncio
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine, get_sessionmaker
from app.models import Contract, Package, Project, User
from app.seed.project import PROJECT
from app.services import audit
from app.services.tracking_changes import Change, set_fields
from app.services.tracking_details import DetailSnapshot, first_date, last_date, read_detail_sheets
from app.services.tracking_mapping import (
    contract_number,
    duration_days,
    organization_name,
    package_health,
    package_number,
    selection_form,
    selection_method,
)
from app.services.tracking_sync_items import sync_items
from app.services.tracking_workbook import (
    SEVERITY_ERROR,
    Finding,
    PackageRow,
    TrackingSnapshot,
    read_tracking_workbook,
)

EARLY_STATUSES = ("planning", "bidding", "negotiating")
SIGNED_STATUS = "contract_signed"


@dataclass(frozen=True)
class SyncReport:
    source: str
    changes: tuple[Change, ...]
    unmapped: tuple[str, ...]
    findings: tuple[Finding, ...]
    applied: bool

    @property
    def counts(self) -> dict[str, int]:
        return _counts(list(self.changes))


def _money(value: int | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _iso_date(text: str | None) -> date | None:
    return None if text is None else date.fromisoformat(text)


def _package_type(package: PackageRow) -> str:
    return "consulting" if package.is_preparation or "Tư vấn" in package.name else "goods"


def _package_values(package: PackageRow) -> dict[str, Any]:
    return {
        "name": package.name or None,
        "scope_summary": package.scope or None,
        "package_type": _package_type(package),
        "package_price": _money(package.price or None),
        "selection_form": selection_form(package.selection),
        "selection_method": selection_method(package.selection),
        "approved_duration_days": duration_days(package.duration),
        "winning_price": _money(package.contract_value),
        "winning_org_text": organization_name(package.contractor)
        if package.contract_value
        else None,
        "status": SIGNED_STATUS if package.contract_value else None,
        "health": package_health(package.status),
        "health_reason": package.status or None,
    }


def _contract_values(package: PackageRow) -> dict[str, Any]:
    planned_end = last_date(package.contract_term)
    return {
        "contract_no": contract_number(package.contract_ref),
        "signed_date": _iso_date(first_date(package.contract_ref)),
        "duration_days": duration_days(package.contract_term),
        "planned_end_date": _iso_date(planned_end),
        "end_date_override": True if planned_end else None,
        "value": _money(package.contract_value),
        "advance_amount": _money(package.advance),
        "status": "signed",
    }


async def _find_project(session: AsyncSession) -> Project:
    project = (
        await session.execute(select(Project).where(Project.code == PROJECT["code"]))
    ).scalar_one_or_none()
    if project is None:
        raise RuntimeError(f"Chưa có dự án {PROJECT['code']}: chạy seed trước")
    return project


async def _sync_package(
    session: AsyncSession, project: Project, package: PackageRow
) -> tuple[Package, Change]:
    number = package_number(package.code)
    if number is None:
        raise ValueError(f"Mã gói không hợp lệ: {package.code}")
    key = f"gói {package.code}"
    values = _package_values(package)
    existing = (
        await session.execute(
            select(Package).where(Package.project_id == project.id, Package.number == number)
        )
    ).scalar_one_or_none()
    if existing is None:
        obj = Package(
            project_id=project.id, number=number, current_stage="S1_START", status="planning"
        )
        session.add(obj)
        created = set_fields(obj, values)
        await session.flush()
        return obj, Change("package", key, "create", created)
    if package.contract_value and existing.status in EARLY_STATUSES:
        values["status"] = SIGNED_STATUS
    changed = (*set_fields(existing, values), *_clear_unsigned(existing, package))
    return existing, Change("package", key, "update" if changed else "unchanged", changed)


def _clear_unsigned(obj: Package, package: PackageRow) -> tuple[str, ...]:
    """A package with no workbook contract must not keep a winner or price from an old row."""
    if package.contract_value is not None:
        return ()
    cleared: list[str] = []
    for name in ("winning_price", "winning_org_text"):
        if getattr(obj, name) is not None:
            setattr(obj, name, None)
            cleared.append(name)
    return tuple(cleared)


async def _has_contract(session: AsyncSession, package_id: Any) -> bool:
    found = await session.scalar(
        select(Contract.id)
        .where(Contract.package_id == package_id, Contract.deleted_at.is_(None))
        .limit(1)
    )
    return found is not None


async def _sync_contract(
    session: AsyncSession, package_row: Package, package: PackageRow
) -> Change | Finding:
    key = f"hợp đồng {package.code}"
    existing = list(
        (
            await session.execute(
                select(Contract).where(
                    Contract.package_id == package_row.id, Contract.deleted_at.is_(None)
                )
            )
        ).scalars()
    )
    if len(existing) > 1:
        return Finding(
            SEVERITY_ERROR,
            "multiple_contracts",
            f"Gói {package.code} có {len(existing)} hợp đồng; cần xử lý tay",
        )
    values = _contract_values(package)
    if not existing:
        obj = Contract(package_id=package_row.id, contract_no=values.pop("contract_no") or "")
        session.add(obj)
        created = set_fields(obj, values)
        await session.flush()
        return Change("contract", key, "create", created)
    changed = set_fields(existing[0], values)
    return Change("contract", key, "update" if changed else "unchanged", changed)


async def _relocate_cbdt(
    session: AsyncSession, project: Project, workbook: TrackingSnapshot
) -> list[Change]:
    """Move a package seeded under the QĐ 239 number to its CBĐT number (101..103).

    The seed numbers the three preparation packages 1..3, which collides with execution packages
    01..03. A package is moved only when its contractor name matches the workbook's CBĐT row, and
    only once: when the CBĐT number already exists the move is already done.
    """
    changes: list[Change] = []
    for cbdt in workbook.preparation_packages:
        target = package_number(cbdt.code)
        if target is None:
            continue
        contractor = organization_name(cbdt.contractor)
        candidate = (
            await session.execute(
                select(Package).where(
                    Package.project_id == project.id,
                    Package.winning_org_text == contractor,
                    Package.number < 100,
                )
            )
        ).scalar_one_or_none()
        if candidate is None:
            continue
        already_moved = (
            await session.execute(
                select(Package.id).where(Package.project_id == project.id, Package.number == target)
            )
        ).scalar_one_or_none()
        if already_moved is not None:
            continue
        old_number = candidate.number
        candidate.number = target
        changes.append(
            Change("package", f"gói {cbdt.code}", "update", (f"number {old_number}->{target}",))
        )
    return changes


async def run_sync(
    session: AsyncSession,
    workbook: TrackingSnapshot,
    details: DetailSnapshot,
    actor: User,
    apply: bool,
) -> SyncReport:
    """Write the workbook to the database unless `apply` is off or an error was found."""
    if workbook.has_errors:
        return SyncReport(workbook.source, (), (), workbook.findings, applied=False)
    project = await _find_project(session)
    changes: list[Change] = []
    findings: list[Finding] = list(workbook.findings)
    changes.extend(await _relocate_cbdt(session, project, workbook))
    packages: dict[str, Package] = {}
    for package in workbook.packages:
        package_row, change = await _sync_package(session, project, package)
        packages[package.code] = package_row
        changes.append(change)
        if package.contract_value and package.contract_ref:
            outcome = await _sync_contract(session, package_row, package)
            if isinstance(outcome, Finding):
                findings.append(outcome)
            else:
                changes.append(outcome)
        elif await _has_contract(session, package_row.id):
            findings.append(
                Finding(
                    SEVERITY_ERROR,
                    "contract_not_in_workbook",
                    f"Gói {package.code} có hợp đồng trong DB, workbook không ghi HĐ; xử lý tay",
                )
            )
    item_changes, unmapped, item_findings = await sync_items(session, project, packages, details)
    changes.extend(item_changes)
    findings.extend(item_findings)
    can_apply = apply and not any(f.severity == SEVERITY_ERROR for f in findings)
    if can_apply:
        audit.record(
            session,
            action="update",
            entity_type="project",
            entity_id=project.id,
            user_id=actor.id,
            changes={"tracking_sync": {"source": workbook.source, "counts": _counts(changes)}},
        )
        await session.commit()
    else:
        await session.rollback()
    return SyncReport(workbook.source, tuple(changes), tuple(unmapped), tuple(findings), can_apply)


def _counts(changes: list[Change]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for change in changes:
        key = f"{change.entity}:{change.action}"
        counts[key] = counts.get(key, 0) + 1
    return counts


async def _actor(session: AsyncSession, email: str) -> User:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        raise RuntimeError(f"Không có người dùng {email}: chạy seed admin trước")
    return user


async def _main_async(file: Path, apply: bool, actor_email: str) -> SyncReport:
    workbook = read_tracking_workbook(file)
    details = read_detail_sheets(file)
    async with get_sessionmaker()() as session:
        actor = await _actor(session, actor_email)
        return await run_sync(session, workbook, details, actor, apply)


async def _run_cli(file: Path, apply: bool, actor_email: str) -> SyncReport:
    try:
        return await _main_async(file, apply, actor_email)
    finally:
        await get_engine().dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Đồng bộ workbook theo dõi gói thầu vào web app")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="ghi vào DB (mặc định: chỉ chạy thử)")
    parser.add_argument(
        "--actor",
        default=os.environ.get("SEED_ADMIN_EMAIL", "admin@qlda.local"),
        help="tài khoản ghi nhận người thực hiện đồng bộ",
    )
    args = parser.parse_args()
    print_report(asyncio.run(_run_cli(args.file, args.apply, args.actor)))


def print_report(report: SyncReport) -> None:
    mode = "ĐÃ GHI" if report.applied else "CHẠY THỬ (không ghi)"
    print(f"Nguồn: {report.source} | {mode}")
    for key, count in sorted(report.counts.items()):
        print(f"  {key}: {count}")
    for change in report.changes:
        if change.action in ("create", "update") and change.fields:
            print(f"  {change.entity} {change.key} [{change.action}]: {', '.join(change.fields)}")
    for finding in report.findings:
        print(f"  [{finding.severity}] {finding.code}: {finding.message}")
    for text in report.unmapped:
        print(f"  [chưa ánh xạ] {text}")


if __name__ == "__main__":
    main()
