"""M7 acceptance: the engine over the SPEC 14 seed raises the 14.7 alerts, never twice."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Contract, Guarantee, Package
from app.seed.checklists import seed_checklists
from app.seed.finance import seed_finance
from app.seed.progress import seed_progress
from app.seed.project import seed_project
from app.seed.risks import seed_risks
from app.services.alert_engine import RunResult, run_alerts

# 05/11/2026 10:00 in Vietnam (Thursday): TPBank/BIDV advance guarantees of Package 05 are 8 days
# from expiry (SPEC 14.7 scenario used by the M3 test as well).
NOW = datetime(2026, 11, 5, 3, 0, tzinfo=UTC)


@pytest.fixture
async def seeded(session: AsyncSession) -> None:
    await seed_project(session)
    await seed_finance(session)
    await seed_checklists(session)
    await seed_progress(session)
    await seed_risks(session)


async def alerts(session: AsyncSession, alert_type: str | None = None) -> list[Alert]:
    stmt = select(Alert).order_by(Alert.fingerprint).execution_options(populate_existing=True)
    if alert_type:
        stmt = stmt.where(Alert.alert_type == alert_type)
    return list((await session.execute(stmt)).scalars().all())


async def package(session: AsyncSession, number: int) -> Package:
    stmt = select(Package).where(Package.number == number).execution_options(populate_existing=True)
    return (await session.execute(stmt)).scalar_one()


async def test_seed_raises_the_expected_alerts(session: AsyncSession, seeded: None) -> None:
    result = await run_alerts(session, NOW)
    assert result.created > 0

    p5, p4, p7 = [await package(session, n) for n in (5, 4, 7)]

    short = await alerts(session, "ADVANCE_GUARANTEE_SHORT")
    assert short and all(a.severity == "critical" and a.package_id == p5.id for a in short)

    missing = {a.package_id: a for a in await alerts(session, "GUARANTEE_MISSING")}
    assert {p4.id, p5.id} <= set(missing)
    assert all(a.severity == "critical" for a in missing.values())

    (cross,) = await alerts(session, "CROSS_PKG_DEPENDENCY")
    assert cross.package_id == p7.id and cross.severity == "warning"

    expiring = await alerts(session, "GUARANTEE_EXPIRING")
    assert expiring and all(a.package_id == p5.id for a in expiring)


async def test_no_duplicate_fingerprints_and_second_run_changes_nothing(
    session: AsyncSession, seeded: None
) -> None:
    await run_alerts(session, NOW)
    first = {a.fingerprint: a.id for a in await alerts(session)}
    again = await run_alerts(session, NOW)
    assert (again.created, again.updated, again.reopened, again.resolved) == (0, 0, 0, 0)
    assert {a.fingerprint: a.id for a in await alerts(session)} == first
    total = (await session.execute(select(func.count(Alert.id)))).scalar_one()
    assert total == len(first)


async def test_package_health_follows_alerts(session: AsyncSession, seeded: None) -> None:
    await run_alerts(session, NOW)
    p3, p5 = await package(session, 3), await package(session, 5)
    assert (p3.health, p3.health_reason) == ("grey", "Chưa có hợp đồng")
    assert p5.health == "red"
    assert "nghiêm trọng" in (p5.health_reason or "")


async def test_fixing_the_data_closes_the_alert(session: AsyncSession, seeded: None) -> None:
    await run_alerts(session, NOW)
    guarantees = (
        await session.execute(select(Guarantee).where(Guarantee.guarantee_type == "advance"))
    ).scalars()
    for g in guarantees:
        if g.expiry_date is not None:
            g.expiry_date = date(2027, 6, 30)
    await session.commit()

    result = await run_alerts(session, NOW)
    assert result.resolved >= 1
    for kind in ("ADVANCE_GUARANTEE_SHORT", "GUARANTEE_EXPIRING"):
        rows = await alerts(session, kind)
        assert rows and all(a.status == "resolved" and a.resolved_at for a in rows)


async def test_resolved_alert_reopens_when_condition_returns(
    session: AsyncSession, seeded: None
) -> None:
    await run_alerts(session, NOW)
    (cross,) = await alerts(session, "CROSS_PKG_DEPENDENCY")
    seven = await package(session, 7)
    contract = (
        await session.execute(select(Contract).where(Contract.package_id == seven.id))
    ).scalar_one()
    original = contract.planned_end_date
    contract.planned_end_date = date(2028, 1, 1)
    await session.commit()
    await run_alerts(session, NOW)
    assert (await alerts(session, "CROSS_PKG_DEPENDENCY"))[0].status == "resolved"

    contract.planned_end_date = original
    await session.commit()
    result = await run_alerts(session, NOW)
    (again,) = await alerts(session, "CROSS_PKG_DEPENDENCY")
    assert again.id == cross.id and again.status == "open" and result.reopened >= 1


async def test_acknowledged_stays_until_severity_rises(session: AsyncSession, seeded: None) -> None:
    await run_alerts(session, NOW)
    a = (await alerts(session, "GUARANTEE_EXPIRING"))[0]
    a.status, a.acknowledged_at = "acknowledged", NOW
    await session.commit()
    await run_alerts(session, NOW)
    assert (await alerts(session, "GUARANTEE_EXPIRING"))[0].status == "acknowledged"

    # three days before expiry the warning becomes critical and must reach people again
    later = datetime(2026, 11, 10, 3, 0, tzinfo=UTC)
    await run_alerts(session, later)
    row = (await alerts(session, "GUARANTEE_EXPIRING"))[0]
    assert row.severity == "critical" and row.status == "open"


async def test_snooze_expires_and_critical_cannot_stay_snoozed(
    session: AsyncSession, seeded: None
) -> None:
    await run_alerts(session, NOW)
    warn = (await alerts(session, "CROSS_PKG_DEPENDENCY"))[0]
    warn.status, warn.snoozed_until = "suppressed", NOW + timedelta(days=2)
    crit = (await alerts(session, "GUARANTEE_MISSING"))[0]
    crit.status, crit.snoozed_until = "suppressed", NOW + timedelta(days=2)
    await session.commit()

    await run_alerts(session, NOW)
    by = {a.id: a for a in await alerts(session)}
    assert by[warn.id].status == "suppressed"  # still snoozed
    assert by[crit.id].status == "open"  # critical never stays snoozed

    await run_alerts(session, NOW + timedelta(days=3))
    assert {a.id: a for a in await alerts(session)}[warn.id].status == "open"


async def test_daily_log_missing_only_for_executing_packages(
    session: AsyncSession, seeded: None
) -> None:
    evening = datetime(2026, 11, 5, 11, 30, tzinfo=UTC)  # 18:30 Vietnam
    await run_alerts(session, evening)
    assert await alerts(session, "DAILY_LOG_MISSING") == []  # seed packages are contract_signed

    six = await package(session, 6)
    six.status = "executing"
    await session.commit()
    await run_alerts(session, evening)
    (log,) = await alerts(session, "DAILY_LOG_MISSING")
    assert log.package_id == six.id and log.severity == "info"

    await run_alerts(session, NOW)  # morning: the condition is gone, yesterday's closes
    assert (await alerts(session, "DAILY_LOG_MISSING"))[0].status == "resolved"


async def test_report_due_on_friday(session: AsyncSession, seeded: None) -> None:
    friday = datetime(2026, 11, 6, 3, 0, tzinfo=UTC)
    await run_alerts(session, friday)
    (weekly,) = await alerts(session, "REPORT_DUE")
    assert weekly.severity == "info" and weekly.package_id is None


def test_run_result_is_plain_data() -> None:
    assert RunResult().created == 0
