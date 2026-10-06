"""Seed stage plans from facts the project already contains (no invented dates).

* every package gets the five standard stages (weights 10/20/40/20/10)
* a package with a signed contract has finished contractor selection (S2 done)
* the execution stage (S3) spans the contract: start = effective/signed date, end = contract end
Everything else stays empty for the team to fill in; see docs/OPEN_QUESTIONS.md.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contract, Package
from app.services.progress import ensure_stage_plans, recompute_package


async def seed_progress(session: AsyncSession) -> None:
    for package in (await session.execute(select(Package))).scalars().all():
        stages = {s.stage_code: s for s in await ensure_stage_plans(session, package)}
        contract = (
            (
                await session.execute(
                    select(Contract)
                    .where(Contract.package_id == package.id, Contract.deleted_at.is_(None))
                    .order_by(Contract.signed_date.nulls_last())
                )
            )
            .scalars()
            .first()
        )
        selection, execution = stages["S2_SELECTION"], stages["S3_EXECUTION"]
        if contract is not None:
            if selection.status == "not_started" and selection.progress_pct == 0:
                selection.status, selection.progress_pct = "done", Decimal(100)
            if execution.planned_start is None and execution.planned_end is None:
                execution.planned_start = contract.effective_date or contract.signed_date
                execution.planned_end = contract.extended_end_date or contract.planned_end_date
        elif selection.status == "not_started" and package.status == "bidding":
            selection.status = "in_progress"
        await recompute_package(session, package)
    await session.commit()
