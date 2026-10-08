"""M7 acceptance: dashboard blocks load fast, match the detail data and open from the source."""

import time
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ActionItem,
    Alert,
    ChecklistItem,
    Contract,
    DisbursementPlan,
    Guarantee,
    Package,
    Payment,
    Project,
    Risk,
)
from app.seed.checklists import seed_checklists
from app.seed.finance import seed_finance
from app.seed.progress import seed_progress
from app.seed.project import PACKAGES, seed_project
from app.seed.risks import seed_risks
from app.services.alert_engine import run_alerts
from app.services.finance import today_local
from tests.conftest import ALL_ROLES


@pytest.fixture
async def seeded(session: AsyncSession) -> None:
    await seed_project(session)
    await seed_finance(session)
    await seed_checklists(session)
    await seed_progress(session)
    await seed_risks(session)
    await run_alerts(session)


async def get(c, path: str) -> dict:
    r = await c.get(f"/api/v1/dashboard/{path}")
    assert r.status_code == 200, r.text
    return r.json()


async def test_every_block_requires_login_and_is_open_to_all_roles(
    session: AsyncSession, seeded: None, client, make_client_for
) -> None:
    blocks = ("summary", "cashflow", "top-risks", "alerts", "documents", "timeline")
    for block in blocks:
        assert (await client.get(f"/api/v1/dashboard/{block}")).status_code == 401
    for role in ALL_ROLES:
        c = await make_client_for(session, role)
        for block in blocks:
            assert (await c.get(f"/api/v1/dashboard/{block}")).status_code == 200, (role, block)


async def test_summary_project_card_and_package_strip(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    data = await get(c, "summary")
    project = data["project"]
    assert project["package_count"] == len(PACKAGES) == 8
    assert project["total_investment"] and project["investor_name"]
    # Package 06's contract ends 22/01/2027 (SPEC 14.3): the countdown follows it
    assert project["tvqlda_end_date"] == "2027-01-22"
    assert project["tvqlda_days_left"] == (date(2027, 1, 22) - today_local()).days

    strip = data["packages"]
    assert [p["number"] for p in strip] == list(range(1, 9))
    pkg3 = strip[2]
    assert (pkg3["health"], pkg3["health_reason"]) == ("grey", "Chưa có hợp đồng")
    assert pkg3["contractor"] is None
    pkg6 = strip[5]
    assert pkg6["contractor"] == "Sài Gòn Mới" and pkg6["winning_price"] == 1726920000
    assert {p["health"] for p in strip} <= {"green", "amber", "red", "grey"}


async def test_summary_finance_numbers_match_the_detail_rows(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    fin = (await get(c, "summary"))["finance"]

    expected = {
        "total_package_price": Package.package_price,
        "total_winning_price": Package.winning_price,
        "total_contract_value": Contract.value,
        "total_advance": Contract.advance_amount,
    }
    for key, column in expected.items():
        total = (await session.execute(select(func.coalesce(func.sum(column), 0)))).scalar_one()
        assert fin[key] == int(total), key
    assert fin["total_paid"] == 0  # nothing is paid in the seed
    assert fin["planned_total"] == 0 and fin["disbursement_rate_pct"] is None


async def test_disbursement_rate_is_paid_over_planned_to_date(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    project = (await session.execute(select(Project))).scalars().first()
    assert project
    today = today_local()
    last_month = today.replace(day=1) - timedelta(days=1)
    session.add_all(
        [
            DisbursementPlan(
                project_id=project.id,
                year=last_month.year,
                month=last_month.month,
                planned_amount=Decimal(1_000_000),
            ),
            DisbursementPlan(  # a future month counts towards the total but not "to date"
                project_id=project.id,
                year=today.year + 1,
                month=1,
                planned_amount=Decimal(5_000_000),
            ),
        ]
    )
    advance = select(Payment).where(Payment.payment_type == "advance")
    payment = (await session.execute(advance)).scalars().first()
    assert payment
    payment.status, payment.paid_date, payment.amount = "paid", today, Decimal(250_000)
    await session.commit()

    c = await make_client_for(session, "viewer")
    fin = (await get(c, "summary"))["finance"]
    assert fin["planned_total"] == 6_000_000 and fin["planned_to_date"] == 1_000_000
    assert fin["total_paid"] == 250_000 and fin["disbursement_rate_pct"] == 25


async def test_milestones_cover_the_next_30_days_in_date_order(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    today = today_local()
    dated = select(Guarantee).where(Guarantee.expiry_date.is_not(None)).order_by(Guarantee.id)
    soon, far = (await session.execute(dated)).scalars().all()[:2]
    soon.expiry_date = today + timedelta(days=5)
    far.expiry_date = today + timedelta(days=31)
    package_id = (await session.execute(select(Package.id).limit(1))).scalar_one()
    session.add(
        ActionItem(
            title="Gửi công văn",
            package_id=package_id,
            due_date=today + timedelta(days=2),
            status="open",
        )
    )
    await session.commit()

    c = await make_client_for(session, "viewer")
    items = (await get(c, "summary"))["milestones"]
    days = [m["days_left"] for m in items]
    assert days == sorted(days) and all(0 <= d <= 30 for d in days)
    guarantee = [m for m in items if m["kind"] == "guarantee_expiry"]
    assert [m["entity_id"] for m in guarantee] == [str(soon.id)]  # the 31-day one is out
    assert guarantee[0]["days_left"] == 5 and guarantee[0]["package_number"] is not None
    action = [m for m in items if m["kind"] == "action_due"]
    assert action and action[0]["days_left"] == 2 and "Gửi công văn" in action[0]["title"]


async def test_cashflow_planned_vs_actual_by_month(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    project = (await session.execute(select(Project))).scalars().first()
    assert project
    session.add_all(
        [
            DisbursementPlan(
                project_id=project.id, year=2026, month=10, planned_amount=Decimal(100)
            ),
            DisbursementPlan(
                project_id=project.id,
                year=2026,
                month=11,
                planned_amount=Decimal(200),
                actual_amount=Decimal(150),
            ),
            DisbursementPlan(
                project_id=project.id,
                year=2026,
                month=12,
                planned_amount=Decimal(300),
                actual_amount=Decimal(10),
            ),
        ]
    )
    advance = select(Payment).where(Payment.payment_type == "advance")
    payment = (await session.execute(advance)).scalars().first()
    assert payment
    payment.status, payment.paid_date, payment.amount = "paid", date(2026, 12, 3), Decimal(70)
    await session.commit()

    c = await make_client_for(session, "viewer")
    months = {(m["year"], m["month"]): m for m in (await get(c, "cashflow"))["months"]}
    assert list(months) == sorted(months)
    assert (months[(2026, 10)]["planned"], months[(2026, 10)]["actual"]) == (100, 0)
    assert months[(2026, 11)]["actual"] == 150  # typed actual, no paid payment that month
    assert months[(2026, 12)]["actual"] == 70  # a paid payment beats the typed figure


async def test_top_risks_are_the_five_worst_open_ones_with_the_matrix(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    risks = list((await session.execute(select(Risk))).scalars())
    closed = risks[0]
    closed.status = "closed"
    await session.commit()

    c = await make_client_for(session, "viewer")
    data = await get(c, "top-risks")
    assert len(data["items"]) == 5
    scores = [r["score"] for r in data["items"]]
    assert scores == sorted(scores, reverse=True)
    assert closed.code not in [r["code"] for r in data["items"]]
    assert data["matrix"]["total"] == len(risks) - 1 and len(data["matrix"]["cells"]) == 25
    assert sum(cell["count"] for cell in data["matrix"]["cells"]) == len(risks) - 1


async def test_alert_block_counts_match_the_alert_list(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    block = await get(c, "alerts")
    listing = (await c.get("/api/v1/alerts", params={"page_size": 100})).json()["items"]
    for severity in ("critical", "warning", "info"):
        assert block["counts"][severity] == sum(1 for a in listing if a["severity"] == severity)
    assert block["counts"]["total"] == len(listing)
    assert 0 < len(block["items"]) <= 10
    assert block["items"][0]["severity"] == "critical"  # worst first; each links via entity_id
    assert all(a["entity_type"] and a["entity_id"] for a in block["items"])

    row = (await session.execute(select(Alert).where(Alert.status == "open"))).scalars().first()
    assert row
    row.status = "resolved"
    await session.commit()
    assert (await get(c, "alerts"))["counts"]["total"] == len(listing) - 1


async def test_missing_documents_per_package(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    data = await get(c, "documents")
    assert data["packages"] and data["total_missing"] == sum(p["missing"] for p in data["packages"])
    db_missing = (
        await session.execute(
            select(func.count(ChecklistItem.id)).where(
                ChecklistItem.required.is_(True), ChecklistItem.status == "missing"
            )
        )
    ).scalar_one()
    assert data["total_missing"] == db_missing
    assert all(p["missing"] <= p["required"] for p in data["packages"])


async def test_summary_loads_under_two_seconds_with_seed_data(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    started = time.perf_counter()
    for block in ("summary", "cashflow", "top-risks", "alerts", "documents"):
        await get(c, block)
    assert time.perf_counter() - started < 2.0
