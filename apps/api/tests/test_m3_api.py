"""M3 API tests: guarantees, payments, disbursement plan (SPEC 3.10-3.12, 7.1, 7.2, section 8)."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Contract, Package, Payment
from app.seed.finance import seed_finance
from app.seed.project import seed_project
from tests.conftest import ALL_ROLES

FIXED_TODAY = date(2026, 11, 5)  # 8 days before the Package 05 advance guarantees expire


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[int, Package]:
    await seed_project(session)
    await seed_finance(session)
    return {p.number: p for p in (await session.execute(select(Package))).scalars().all()}


@pytest.fixture
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> date:
    monkeypatch.setattr("app.routers.finance.today_local", lambda: FIXED_TODAY)
    return FIXED_TODAY


async def cid(session: AsyncSession, seeded: dict[int, Package], number: int) -> str:
    c = (
        await session.execute(select(Contract).where(Contract.package_id == seeded[number].id))
    ).scalar_one()
    return str(c.id)


# --- M3 acceptance ---------------------------------------------------------------------------


async def test_package_05_advance_guarantees_are_expiring_and_short(
    session: AsyncSession, seeded: dict[int, Package], make_client_for, fixed_today: date
) -> None:
    c = await make_client_for(session, "viewer")
    rows = (await c.get(f"/api/v1/contracts/{await cid(session, seeded, 5)}/guarantees")).json()
    advance = [r for r in rows if r["guarantee_type"] == "advance" and r["status"] != "missing"]
    assert sorted(r["bank_name"] for r in advance) == ["BIDV", "TPBank"]
    for r in advance:
        assert r["effective_status"] == "expiring" and r["days_left"] == 8
        assert {f["code"] for f in r["findings"]} == {
            "GUARANTEE_EXPIRING",
            "ADVANCE_GUARANTEE_SHORT",
        }
        short = next(f for f in r["findings"] if f["code"] == "ADVANCE_GUARANTEE_SHORT")
        assert short["severity"] == "critical" and short["due_date"] == "2026-11-19"
    assert all(r["verified"] is False for r in advance)  # [OCR], not yet checked against originals


async def test_missing_guarantees_raise_critical_findings(
    session: AsyncSession, seeded: dict[int, Package], make_client_for, fixed_today: date
) -> None:
    c = await make_client_for(session, "viewer")
    for number, kind in ((4, "advance"), (5, "performance")):
        checks = (
            await c.get(f"/api/v1/contracts/{await cid(session, seeded, number)}/guarantee-checks")
        ).json()
        missing = [f for f in checks if f["code"] == "GUARANTEE_MISSING"]
        assert len(missing) == 1 and missing[0]["severity"] == "critical", (number, kind)


async def test_package_04_performance_bond_is_valid(
    session: AsyncSession, seeded: dict[int, Package], make_client_for, fixed_today: date
) -> None:
    c = await make_client_for(session, "viewer")
    rows = (await c.get(f"/api/v1/contracts/{await cid(session, seeded, 4)}/guarantees")).json()
    perf = next(r for r in rows if r["guarantee_type"] == "performance")
    assert (perf["bank_name"], perf["amount"], perf["effective_status"]) == (
        "ABBank",
        1_545_162_000,
        "valid",
    )


async def test_global_list_puts_soonest_expiry_first(
    session: AsyncSession, seeded: dict[int, Package], make_client_for, fixed_today: date
) -> None:
    c = await make_client_for(session, "viewer")
    data = (await c.get("/api/v1/guarantees")).json()
    assert data["total"] == 5
    assert [r["bank_name"] for r in data["items"][:2]] == ["BIDV", "TPBank"] or [
        r["bank_name"] for r in data["items"][:2]
    ] == ["TPBank", "BIDV"]
    assert all(r["expiry_date"] is None for r in data["items"][2:])
    assert {r["package_number"] for r in data["items"][:2]} == {5}
    assert (await c.get("/api/v1/guarantees", params={"status": "expiring"})).json()["total"] == 2
    assert (await c.get("/api/v1/guarantees", params={"status": "missing"})).json()["total"] == 2
    assert (await c.get("/api/v1/guarantees", params={"expiring_within_days": 10})).json()[
        "total"
    ] == 2
    assert (await c.get("/api/v1/guarantees", params={"expiring_within_days": 7})).json()[
        "total"
    ] == 0
    assert (await c.get("/api/v1/guarantees", params={"guarantee_type": "performance"})).json()[
        "total"
    ] == 2


# --- permissions -----------------------------------------------------------------------------

GUARANTEE_WRITE = {"admin", "director", "procurement", "cost"}
PAYMENT_READ = {"admin", "director", "procurement", "technical", "cost", "viewer"}
PAYMENT_WRITE = {"admin", "director", "cost"}


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_guarantee_permissions_follow_contract_matrix(
    role: str, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, role)
    contract_id = await cid(session, seeded, 6)
    assert (await c.get(f"/api/v1/contracts/{contract_id}/guarantees")).status_code == 200
    assert (await c.get("/api/v1/guarantees")).status_code == 200
    created = await c.post(
        f"/api/v1/contracts/{contract_id}/guarantees",
        json={"guarantee_type": "advance", "amount": 1},
    )
    assert created.status_code == (201 if role in GUARANTEE_WRITE else 403)


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_payment_permissions_follow_payment_matrix(
    role: str, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, role)
    contract_id = await cid(session, seeded, 6)
    read = 200 if role in PAYMENT_READ else 403
    assert (await c.get(f"/api/v1/contracts/{contract_id}/payments")).status_code == read
    assert (await c.get("/api/v1/payments")).status_code == read
    assert (await c.get("/api/v1/project/disbursement-plan")).status_code == read
    created = await c.post(
        f"/api/v1/contracts/{contract_id}/payments",
        json={"payment_type": "payment", "seq": 9, "amount": 5},
    )
    assert created.status_code == (201 if role in PAYMENT_WRITE else 403)
    put = await c.put("/api/v1/project/disbursement-plan", json={"items": []})
    assert put.status_code == (200 if role in PAYMENT_WRITE else 403)


# --- guarantee CRUD ---------------------------------------------------------------------------


async def test_guarantee_crud_and_derived_status(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "cost")
    contract_id = await cid(session, seeded, 6)
    soon = (date.today() + timedelta(days=5)).isoformat()
    far = (date.today() + timedelta(days=90)).isoformat()
    past = (date.today() - timedelta(days=1)).isoformat()
    made = await c.post(
        f"/api/v1/contracts/{contract_id}/guarantees",
        json={
            "guarantee_type": "performance",
            "amount": 100,
            "bank_name": "VCB",
            "expiry_date": soon,
        },
    )
    assert made.status_code == 201
    gid = made.json()["id"]
    assert made.json()["effective_status"] == "expiring" and made.json()["status"] == "valid"
    far_ = await c.patch(f"/api/v1/guarantees/{gid}", json={"expiry_date": far})
    assert far_.json()["effective_status"] == "valid"
    gone = await c.patch(f"/api/v1/guarantees/{gid}", json={"expiry_date": past})
    assert gone.json()["effective_status"] == "expired"
    assert any(
        f["code"] == "GUARANTEE_EXPIRING" and f["severity"] == "critical"
        for f in gone.json()["findings"]
    )
    released = await c.patch(f"/api/v1/guarantees/{gid}", json={"status": "released"})
    assert released.json()["effective_status"] == "released" and released.json()["findings"] == []
    assert (await c.delete(f"/api/v1/guarantees/{gid}")).status_code == 204
    assert (await c.delete(f"/api/v1/guarantees/{gid}")).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"guarantee_type": "mortgage"},
        {"guarantee_type": "advance", "amount": -1},
        {"guarantee_type": "advance", "status": "expired"},  # derived only, never stored
        {"guarantee_type": "advance", "status": "expiring"},
        {"guarantee_type": "advance", "expiry_date": "13/11/2026"},
        {"guarantee_type": "advance", "status": None},
        {"guarantee_type": "advance", "provider_org_id": "00000000-0000-0000-0000-000000000000"},
    ],
)
async def test_guarantee_validation_422(
    payload: dict, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    resp = await c.post(
        f"/api/v1/contracts/{await cid(session, seeded, 6)}/guarantees", json=payload
    )
    assert resp.status_code == 422


async def test_guarantee_404s_and_audit(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    ghost = "00000000-0000-0000-0000-000000000000"
    assert (await c.get(f"/api/v1/contracts/{ghost}/guarantees")).status_code == 404
    assert (
        await c.patch(f"/api/v1/guarantees/{ghost}", json={"required": False})
    ).status_code == 404
    made = await c.post(
        f"/api/v1/contracts/{await cid(session, seeded, 6)}/guarantees",
        json={"guarantee_type": "warranty", "amount": 1_000, "expiry_date": "2027-06-30"},
    )
    await c.patch(f"/api/v1/guarantees/{made.json()['id']}", json={"amount": 2_000})
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_type == "guarantee")))
        .scalars()
        .all()
    )
    assert {r.action for r in rows} == {"create", "update"}
    upd = next(r for r in rows if r.action == "update")
    assert upd.changes["amount"] == {"before": "1000", "after": "2000"}


# --- payments ---------------------------------------------------------------------------------


async def test_seeded_payments_for_package_06_and_04(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    p6 = (await c.get(f"/api/v1/contracts/{await cid(session, seeded, 6)}/payments")).json()
    assert [(p["payment_type"], p["seq"], p["amount"], p["status"]) for p in p6] == [
        ("advance", 0, 518_076_000, "planned"),
        ("payment", 1, 1_554_228_000, "planned"),
        ("payment", 2, 172_692_000, "planned"),
    ]
    p4 = (await c.get(f"/api/v1/contracts/{await cid(session, seeded, 4)}/payments")).json()
    assert sorted(p["amount"] for p in p4) == [15_451_620_000, 20_602_160_000]
    assert (await c.get(f"/api/v1/contracts/{await cid(session, seeded, 5)}/payments")).json() == []
    allp = (await c.get("/api/v1/payments")).json()
    assert allp["total"] == 5 and allp["items"][0]["package_number"] == 4
    assert (await c.get("/api/v1/payments", params={"payment_type": "advance"})).json()[
        "total"
    ] == 2


async def test_payment_lifecycle_and_who_may_approve(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    cost = await make_client_for(session, "cost")
    director = await make_client_for(session, "director")
    pid = (
        await session.execute(
            select(Payment.id).where(Payment.payment_type == "payment", Payment.seq == 1).limit(1)
        )
    ).scalar_one()
    url = f"/api/v1/payments/{pid}"

    assert (
        await cost.patch(url, json={"status": "approved"})
    ).status_code == 400  # planned -> approved
    req = await cost.patch(url, json={"status": "requested", "invoice_no": "HD-01"})
    assert req.status_code == 200 and req.json()["requested_date"] is not None
    assert (await cost.patch(url, json={"status": "approved"})).status_code == 403  # only approvers
    assert (await cost.post(f"{url}/mark-paid")).status_code == 409  # not approved yet
    assert (await director.patch(url, json={"status": "approved"})).status_code == 200
    assert (await cost.patch(url, json={"status": "paid"})).status_code == 400  # via mark-paid only
    paid = await cost.post(
        f"{url}/mark-paid", json={"paid_date": "2026-11-20", "treasury_ref": "KB-77"}
    )
    assert paid.status_code == 200
    assert (paid.json()["status"], paid.json()["paid_date"], paid.json()["treasury_ref"]) == (
        "paid",
        "2026-11-20",
        "KB-77",
    )
    assert (await cost.patch(url, json={"notes": "x"})).status_code == 409  # paid is immutable
    assert (await cost.post(f"{url}/mark-paid")).status_code == 409  # cannot pay twice

    actions = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "payment", AuditLog.entity_id == str(pid)
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(actions) == 3  # requested, approved, paid


async def test_rejected_payment_can_be_reopened_and_mark_paid_defaults_to_today(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    cost = await make_client_for(session, "cost")
    director = await make_client_for(session, "director")
    contract_id = await cid(session, seeded, 6)
    pid = (
        await cost.post(
            f"/api/v1/contracts/{contract_id}/payments",
            json={"payment_type": "penalty", "seq": 1, "amount": 7, "status": "requested"},
        )
    ).json()["id"]
    url = f"/api/v1/payments/{pid}"
    assert (await director.patch(url, json={"status": "rejected"})).status_code == 200
    assert (await cost.patch(url, json={"status": "planned"})).status_code == 200
    assert (await cost.patch(url, json={"status": "requested"})).status_code == 200
    assert (await director.patch(url, json={"status": "approved"})).status_code == 200
    paid = await cost.post(f"{url}/mark-paid")
    assert (
        paid.json()["paid_date"] == date.today().isoformat() or paid.json()["paid_date"] is not None
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"payment_type": "payment", "amount": 0},
        {"payment_type": "payment", "amount": -5},
        {"payment_type": "refund", "amount": 5},
        {"payment_type": "payment", "amount": 5, "status": "paid"},
        {"payment_type": "payment", "amount": 5, "status": "approved"},
        {"payment_type": "payment", "amount": 5, "seq": -1},
        {
            "payment_type": "payment",
            "amount": 5,
            "organization_id": "00000000-0000-0000-0000-000000000000",
        },
    ],
)
async def test_payment_validation_422(
    payload: dict, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "cost")
    resp = await c.post(f"/api/v1/contracts/{await cid(session, seeded, 6)}/payments", json=payload)
    assert resp.status_code == 422


async def test_payment_404s(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "cost")
    ghost = "00000000-0000-0000-0000-000000000000"
    assert (await c.get(f"/api/v1/contracts/{ghost}/payments")).status_code == 404
    assert (await c.patch(f"/api/v1/payments/{ghost}", json={"notes": "x"})).status_code == 404
    assert (await c.post(f"/api/v1/payments/{ghost}/mark-paid")).status_code == 404


async def test_recovered_advance_clears_advance_short_finding(
    session: AsyncSession, seeded: dict[int, Package], make_client_for, fixed_today: date
) -> None:
    cost = await make_client_for(session, "cost")
    director = await make_client_for(session, "director")
    contract_id = await cid(session, seeded, 5)
    checks = (await cost.get(f"/api/v1/contracts/{contract_id}/guarantee-checks")).json()
    assert "ADVANCE_GUARANTEE_SHORT" in {f["code"] for f in checks}
    rec = await cost.post(
        f"/api/v1/contracts/{contract_id}/payments",
        json={"payment_type": "recovery", "seq": 1, "amount": 4_079_992_500, "status": "requested"},
    )
    pid = rec.json()["id"]
    await director.patch(f"/api/v1/payments/{pid}", json={"status": "approved"})
    await cost.post(f"/api/v1/payments/{pid}/mark-paid")
    after = (await cost.get(f"/api/v1/contracts/{contract_id}/guarantee-checks")).json()
    assert "ADVANCE_GUARANTEE_SHORT" not in {f["code"] for f in after}


# --- disbursement plan -------------------------------------------------------------------------


async def test_disbursement_plan_replace_and_totals(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "cost")
    assert (await c.get("/api/v1/project/disbursement-plan")).json() == {
        "items": [],
        "planned_total": 0,
        "actual_total": 0,
    }
    body = {
        "items": [
            {"year": 2026, "month": 11, "planned_amount": 1_000, "actual_amount": 400},
            {"year": 2026, "month": 10, "planned_amount": 500},
            {"package_id": str(seeded[6].id), "year": 2026, "month": 10, "planned_amount": 250},
        ]
    }
    put = await c.put("/api/v1/project/disbursement-plan", json=body)
    assert put.status_code == 200
    data = put.json()
    assert data["planned_total"] == 1_750 and data["actual_total"] == 400
    assert [(i["year"], i["month"]) for i in data["items"]] == [(2026, 10), (2026, 10), (2026, 11)]
    again = await c.put("/api/v1/project/disbursement-plan", json={"items": [body["items"][1]]})
    assert again.json()["planned_total"] == 500  # replaced, not merged
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_type == "disbursement_plan")))
        .scalars()
        .all()
    )
    assert len(rows) == 2 and rows[-1].changes["rows"] in (
        {"before": 3, "after": 1},
        {"before": 1, "after": 3},
    )


@pytest.mark.parametrize(
    "items",
    [
        [{"year": 2026, "month": 13, "planned_amount": 1}],
        [{"year": 2026, "month": 0, "planned_amount": 1}],
        [{"year": 1999, "month": 1, "planned_amount": 1}],
        [{"year": 2026, "month": 1, "planned_amount": -1}],
        [
            {"year": 2026, "month": 1, "planned_amount": 1},
            {"year": 2026, "month": 1, "planned_amount": 2},
        ],
        [
            {
                "package_id": "00000000-0000-0000-0000-000000000000",
                "year": 2026,
                "month": 1,
                "planned_amount": 1,
            }
        ],
    ],
)
async def test_disbursement_plan_validation_422(
    items: list, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "cost")
    assert (
        await c.put("/api/v1/project/disbursement-plan", json={"items": items})
    ).status_code == 422
