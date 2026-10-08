"""M2 API contract tests: 200/201 correct, 403 per role (SPEC section 8), 422 on bad input."""

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Contract, Organization, Package
from app.seed.project import seed_project
from tests.conftest import ALL_ROLES

READ_OK = {
    "project": {"admin", "director", "procurement", "technical", "cost", "viewer"},
    "package": set(ALL_ROLES),
    "contract": set(ALL_ROLES),
}
WRITE_OK = {
    "project": {"admin"},
    "package": {"admin", "director", "procurement"},
    "contract": {"admin", "director", "procurement", "cost"},
}


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[int, Package]:
    await seed_project(session)
    return {p.number: p for p in (await session.execute(select(Package))).scalars().all()}


async def contract_id(session: AsyncSession, seeded: dict[int, Package], number: int) -> str:
    c = (
        await session.execute(select(Contract).where(Contract.package_id == seeded[number].id))
    ).scalar_one()
    return str(c.id)


# --- permissions ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_read_permissions(
    role: str, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, role)
    pid = str(seeded[4].id)
    cid = await contract_id(session, seeded, 4)
    expect = lambda res: 200 if role in READ_OK[res] else 403  # noqa: E731
    assert (await c.get("/api/v1/project")).status_code == expect("project")
    assert (await c.get("/api/v1/packages")).status_code == expect("package")
    assert (await c.get(f"/api/v1/packages/{pid}")).status_code == expect("package")
    assert (await c.get(f"/api/v1/packages/{pid}/overview")).status_code == expect("package")
    assert (await c.get(f"/api/v1/packages/{pid}/contracts")).status_code == expect("contract")
    assert (await c.get(f"/api/v1/contracts/{cid}")).status_code == expect("contract")


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_write_permissions(
    role: str, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, role)
    pid = str(seeded[4].id)
    cid = await contract_id(session, seeded, 4)
    code = lambda res: 200 if role in WRITE_OK[res] else 403  # noqa: E731
    assert (await c.patch("/api/v1/project", json={"location": "X"})).status_code == code("project")
    assert (await c.patch(f"/api/v1/packages/{pid}", json={"notes": "n"})).status_code == code(
        "package"
    )
    assert (
        await c.patch(f"/api/v1/contracts/{cid}", json={"copies_text": "6"})
    ).status_code == code("contract")
    created = await c.post(f"/api/v1/packages/{pid}/contracts", json={"contract_no": "99"})
    assert created.status_code == (201 if role in WRITE_OK["contract"] else 403)


async def test_unauthenticated_is_401(
    client: httpx.AsyncClient, seeded: dict[int, Package]
) -> None:
    for path in ("/api/v1/project", "/api/v1/packages", f"/api/v1/packages/{seeded[1].id}"):
        assert (await client.get(path)).status_code == 401


# --- project -------------------------------------------------------------------------------


async def test_project_card(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    body = (await c.get("/api/v1/project")).json()
    assert body["package_count"] == 8
    assert body["total_investment"] == 219_000_000_000
    assert body["treasury_account"] == "9552.2.8200685"
    assert body["investor_name"] == "Sở Khoa học và Công nghệ tỉnh Lâm Đồng"


async def test_project_patch_validation_and_audit(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    assert (await c.patch("/api/v1/project", json={"name": None})).status_code == 422
    assert (await c.patch("/api/v1/project", json={"start_year": 1900})).status_code == 422
    assert (await c.patch("/api/v1/project", json={"total_investment": -1})).status_code == 422
    ok = await c.patch("/api/v1/project", json={"location": "Lâm Đồng 2"})
    assert ok.status_code == 200 and ok.json()["location"] == "Lâm Đồng 2"
    row = (
        await session.execute(select(AuditLog).where(AuditLog.entity_type == "project"))
    ).scalar_one()
    assert row.changes["location"] == {"before": "Tỉnh Lâm Đồng", "after": "Lâm Đồng 2"}


# --- packages ------------------------------------------------------------------------------


async def test_list_packages_returns_all_eight_in_order(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    data = (await c.get("/api/v1/packages")).json()
    assert data["total"] == 8 and [i["number"] for i in data["items"]] == list(range(1, 9))
    by = {i["number"]: i for i in data["items"]}
    assert by[3]["contract_no"] == "41/2026/SKH&CNLĐ-BTA" and by[3]["contract_value"] == 430_000_000
    assert by[4]["contract_value"] == 51_505_400_000
    assert by[4]["needs_review"] is True and by[5]["needs_review"] is False
    assert by[6]["needs_review"] is False  # info-level override does not need review


async def test_list_packages_filters_and_pagination(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    assert (await c.get("/api/v1/packages", params={"status": "bidding"})).json()["total"] == 0
    signed = await c.get("/api/v1/packages", params={"status": "contract_signed"})
    assert signed.json()["total"] == 8
    assert (await c.get("/api/v1/packages", params={"q": "nguyên luân"})).json()["total"] == 1
    page2 = (await c.get("/api/v1/packages", params={"page": 2, "page_size": 3})).json()
    assert [i["number"] for i in page2["items"]] == [4, 5, 6]
    assert (await c.get("/api/v1/packages", params={"page_size": 101})).status_code == 422


async def test_package_not_found_and_bad_uuid(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "viewer")
    assert (await c.get("/api/v1/packages/00000000-0000-0000-0000-000000000000")).status_code == 404
    assert (await c.get("/api/v1/packages/not-a-uuid")).status_code == 422


async def test_package_patch(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "procurement")
    pid = str(seeded[7].id)
    ok = await c.patch(
        f"/api/v1/packages/{pid}",
        json={"name": "TVGS", "winning_price": 500_000_000, "status": "executing"},
    )
    assert ok.status_code == 200
    assert (ok.json()["name"], ok.json()["winning_price"], ok.json()["status"]) == (
        "TVGS",
        500_000_000,
        "executing",
    )
    for bad in (
        {"status": "bogus"},
        {"name": None},
        {"package_price": -5},
        {"approved_duration_days": 0},
    ):
        assert (await c.patch(f"/api/v1/packages/{pid}", json=bad)).status_code == 422
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_type == "package")))
        .scalars()
        .all()
    )
    assert len(rows) == 1 and rows[0].changes["winning_price"]["after"] == "500000000"


async def test_package_overview_has_contracts_and_flags(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    ov = (await c.get(f"/api/v1/packages/{seeded[4].id}/overview")).json()
    assert ov["project"]["code"] == "8200685" and ov["needs_review"] is True
    codes = {i["code"] for i in ov["contracts"][0]["consistency"]}
    assert codes == {"END_DATE_MISMATCH"}
    ov4 = (await c.get(f"/api/v1/packages/{seeded[4].id}/overview")).json()
    assert [p["role"] for p in ov4["contracts"][0]["parties"]] == ["lead", "member"]
    assert ov4["contracts"][0]["parties"][0]["organization_name"] == "Nguyên Luân"
    ov3 = (await c.get(f"/api/v1/packages/{seeded[3].id}/overview")).json()
    assert len(ov3["contracts"]) == 1 and ov3["needs_review"] is False
    assert ov3["contracts"][0]["parties"][0]["role"] == "sole"


# --- contracts -----------------------------------------------------------------------------


async def test_create_contract_computes_end_date_and_runs_checks(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "procurement")
    resp = await c.post(
        f"/api/v1/packages/{seeded[3].id}/contracts",
        json={
            "contract_no": "100",
            "signed_date": "2026-10-01",
            "duration_days": 30,
            "value": 430_000_000,
            "advance_pct": 30,
            "advance_amount": 129_000_001,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["planned_end_date"] == "2026-10-30"  # start + duration - 1
    assert body["status"] == "signed"
    assert {i["code"] for i in body["consistency"]} == {"ADVANCE_NE_PCT_X_VALUE"} or body[
        "consistency"
    ] == []  # 1 dong tolerance: 129_000_001 vs 129_000_000 is allowed
    bad = await c.patch(f"/api/v1/contracts/{body['id']}", json={"advance_amount": 135_000_000})
    assert "ADVANCE_NE_PCT_X_VALUE" in {i["code"] for i in bad.json()["consistency"]}
    assert bad.json()["needs_review"] is True


async def test_update_recomputes_end_date_unless_overridden(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "procurement")
    cid = await contract_id(session, seeded, 5)  # 14/09 + 60 - 1 = 12/11
    up = await c.patch(f"/api/v1/contracts/{cid}", json={"duration_days": 70})
    assert up.json()["planned_end_date"] == "2026-11-22"  # 14/09 + 70 - 1
    pinned = await c.patch(
        f"/api/v1/contracts/{cid}",
        json={"planned_end_date": "2026-12-31", "end_date_override": True},
    )
    assert pinned.json()["planned_end_date"] == "2026-12-31"
    still = await c.patch(f"/api/v1/contracts/{cid}", json={"duration_days": 90})
    assert still.json()["planned_end_date"] == "2026-12-31"
    assert {i["severity"] for i in still.json()["consistency"]} == {"info"}
    assert still.json()["needs_review"] is False


async def test_contract_validation_422(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    pid = str(seeded[3].id)
    cid = await contract_id(session, seeded, 4)
    for payload in (
        {},  # contract_no missing
        {"contract_no": ""},
        {"contract_no": "1", "value": -1},
        {"contract_no": "1", "advance_pct": 101},
        {"contract_no": "1", "contract_type": "weird"},
        {"contract_no": "1", "duration_days": 0},
        {"contract_no": "1", "signed_date": "31/12/2026"},
        {"contract_no": "1", "status": None},
    ):
        assert (await c.post(f"/api/v1/packages/{pid}/contracts", json=payload)).status_code == 422
    assert (
        await c.patch(f"/api/v1/contracts/{cid}", json={"contract_no": None})
    ).status_code == 422
    assert (
        await c.patch(f"/api/v1/contracts/{cid}", json={"price_adjustment": None})
    ).status_code == 422


async def test_contract_404s(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "admin")
    ghost = "00000000-0000-0000-0000-000000000000"
    assert (await c.get(f"/api/v1/contracts/{ghost}")).status_code == 404
    assert (await c.get(f"/api/v1/packages/{ghost}/contracts")).status_code == 404
    assert (
        await c.post(f"/api/v1/packages/{ghost}/contracts", json={"contract_no": "1"})
    ).status_code == 404
    assert (
        await c.patch(f"/api/v1/contracts/{ghost}", json={"copies_text": "x"})
    ).status_code == 404


async def test_contract_changes_are_audited_with_json_safe_values(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "cost")
    cid = await contract_id(session, seeded, 4)
    await c.patch(f"/api/v1/contracts/{cid}", json={"value": 51_505_400_001})
    row = (
        await session.execute(
            select(AuditLog).where(AuditLog.entity_type == "contract", AuditLog.entity_id == cid)
        )
    ).scalar_one()
    assert row.action == "update"
    assert row.changes["value"] == {"before": "51505400000", "after": "51505400001"}


# --- children ------------------------------------------------------------------------------


async def test_parties_crud(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "procurement")
    cid = await contract_id(session, seeded, 4)
    org = (
        await session.execute(select(Organization).where(Organization.name == "BSN"))
    ).scalar_one()
    created = await c.post(
        f"/api/v1/contracts/{cid}/parties",
        json={"organization_id": str(org.id), "role": "member", "share_amount": 1},
    )
    assert created.status_code == 201 and created.json()["organization_name"] == "BSN"
    pid = created.json()["id"]
    assert len((await c.get(f"/api/v1/contracts/{cid}/parties")).json()) == 3
    # shares now exceed the contract value -> flag
    flags = {i["code"] for i in (await c.get(f"/api/v1/contracts/{cid}")).json()["consistency"]}
    assert "PARTY_SHARE_SUM_NE_VALUE" in flags
    upd = await c.patch(f"/api/v1/contract-parties/{pid}", json={"share_amount": 5})
    assert upd.json()["share_amount"] == 5
    assert (
        await c.patch(f"/api/v1/contract-parties/{pid}", json={"role": None})
    ).status_code == 422
    assert (await c.delete(f"/api/v1/contract-parties/{pid}")).status_code == 204
    assert (await c.delete(f"/api/v1/contract-parties/{pid}")).status_code == 404
    bad_org = await c.post(
        f"/api/v1/contracts/{cid}/parties",
        json={"organization_id": "00000000-0000-0000-0000-000000000000", "role": "member"},
    )
    assert bad_org.status_code == 422
    assert (
        await c.post(
            f"/api/v1/contracts/{cid}/parties",
            json={"organization_id": str(org.id), "role": "boss"},
        )
    ).status_code == 422


async def test_items_crud(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "procurement")
    cid = await contract_id(session, seeded, 4)
    created = await c.post(
        f"/api/v1/contracts/{cid}/items",
        json={
            "line_no": 1,
            "name": "Máy tính để bàn",
            "unit": "bộ",
            "quantity": 10.5,
            "unit_price": 12_000_000,
            "amount": 126_000_000,
            "warranty_months": 24,
            "requires_calibration": True,
        },
    )
    assert created.status_code == 201
    item = created.json()
    assert item["quantity"] == 10.5 and item["requires_calibration"] is True
    listing = (await c.get(f"/api/v1/contracts/{cid}/items")).json()
    assert [i["line_no"] for i in listing] == [1]
    up = await c.patch(f"/api/v1/contract-items/{item['id']}", json={"warranty_months": 36})
    assert up.json()["warranty_months"] == 36
    for bad in (
        {"line_no": 0, "name": "x"},
        {"line_no": 2},
        {"line_no": 2, "name": "x", "quantity": -1},
    ):
        assert (await c.post(f"/api/v1/contracts/{cid}/items", json=bad)).status_code == 422
    assert (await c.delete(f"/api/v1/contract-items/{item['id']}")).status_code == 204
    assert (await c.get(f"/api/v1/contracts/{cid}/items")).json() == []


async def test_amendments_crud(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "procurement")
    cid = await contract_id(session, seeded, 1)
    created = await c.post(
        f"/api/v1/contracts/{cid}/amendments",
        json={
            "amendment_no": "PL01",
            "type": "duration",
            "signed_date": "2026-09-01",
            "new_end_date": "2026-10-15",
            "description": "Gia hạn",
        },
    )
    assert created.status_code == 201 and created.json()["new_end_date"] == "2026-10-15"
    aid = created.json()["id"]
    assert [
        a["amendment_no"] for a in (await c.get(f"/api/v1/contracts/{cid}/amendments")).json()
    ] == ["PL01"]
    assert (
        await c.patch(f"/api/v1/contract-amendments/{aid}", json={"type": "value", "new_value": 5})
    ).json()["type"] == "value"
    assert (
        await c.post(
            f"/api/v1/contracts/{cid}/amendments", json={"amendment_no": "PL02", "type": "bogus"}
        )
    ).status_code == 422
    assert (
        await c.patch(f"/api/v1/contract-amendments/{aid}", json={"type": None})
    ).status_code == 422
    assert (await c.delete(f"/api/v1/contract-amendments/{aid}")).status_code == 204


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_child_write_permissions_follow_contract_matrix(
    role: str, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, role)
    cid = await contract_id(session, seeded, 4)
    allowed = role in WRITE_OK["contract"]
    item = await c.post(f"/api/v1/contracts/{cid}/items", json={"line_no": 1, "name": "x"})
    amend = await c.post(
        f"/api/v1/contracts/{cid}/amendments", json={"amendment_no": "1", "type": "other"}
    )
    assert item.status_code == (201 if allowed else 403)
    assert amend.status_code == (201 if allowed else 403)
    assert (await c.get(f"/api/v1/contracts/{cid}/items")).status_code == 200
