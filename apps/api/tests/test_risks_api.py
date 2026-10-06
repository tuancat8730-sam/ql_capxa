"""M6: risk register, 5x5 matrix, review reminders (SPEC 3.16, 4.8)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Package, Risk
from app.seed.project import seed_project
from app.seed.risks import RISKS, seed_risks
from tests.conftest import ALL_ROLES, make_user

GHOST = "00000000-0000-0000-0000-000000000000"
READERS = {"admin", "director", "procurement", "technical", "cost", "onsite", "viewer"}  # not clerk
WRITERS = {"admin", "director", "procurement", "technical", "cost", "onsite"}


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[int, Package]:
    await seed_project(session)
    await seed_risks(session)
    return {p.number: p for p in (await session.execute(select(Package))).scalars().all()}


def body(**over) -> dict:
    return {"title": "Rủi ro mới", "category": "schedule", "probability": 3, "impact": 4, **over}


# --- seed (SPEC 14.6, M6 acceptance) -----------------------------------------------------------


async def test_seed_creates_the_ten_register_entries_with_computed_scores(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    data = (await c.get("/api/v1/risks", params={"page_size": 100})).json()
    assert data["total"] == len(RISKS) == 10
    assert [r["code"] for r in data["items"]].count("R-001") == 1
    for r in data["items"]:
        assert r["score"] == r["probability"] * r["impact"] and r["status"] == "open"
        assert r["owner_id"] is None and r["due_date"] is None  # unknown: not invented
    scores = [r["score"] for r in data["items"]]
    assert scores == sorted(scores, reverse=True)  # worst first
    top = data["items"][0]
    assert (top["score"], top["level"]) == (20, "high")


async def test_seed_risks_show_up_in_the_right_matrix_cells(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    matrix = (await c.get("/api/v1/risks/matrix")).json()
    assert matrix["total"] == 10 and len(matrix["cells"]) == 25
    cells = {(x["probability"], x["impact"]): x["count"] for x in matrix["cells"]}
    expected: dict[tuple[int, int], int] = {}
    for r in RISKS:
        expected[(r.probability, r.impact)] = expected.get((r.probability, r.impact), 0) + 1
    for cell, n in expected.items():
        assert cells[cell] == n, cell
    assert cells[(3, 4)] == 2  # two risks share this cell
    assert sum(cells.values()) == 10


async def test_seed_is_idempotent(session: AsyncSession, seeded: dict[int, Package]) -> None:
    await seed_risks(session)
    codes = (await session.execute(select(Risk.code).order_by(Risk.code))).scalars().all()
    assert codes == [f"R-{i:03d}" for i in range(1, 11)]


async def test_package_specific_risks_are_linked(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    p5 = (await c.get("/api/v1/risks", params={"package_id": str(seeded[5].id)})).json()
    assert [r["title"] for r in p5["items"]] == [
        "Bảo lãnh tạm ứng Gói 05 hết hạn trước hoặc sát hạn hợp đồng"
    ]
    matrix = (await c.get("/api/v1/risks/matrix", params={"package_id": str(seeded[5].id)})).json()
    assert matrix["total"] == 1


# --- permissions ------------------------------------------------------------------------------


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_risk_permissions_follow_the_matrix(
    role: str, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, role)
    assert (await c.get("/api/v1/risks")).status_code == (200 if role in READERS else 403)
    assert (await c.get("/api/v1/risks/matrix")).status_code == (200 if role in READERS else 403)
    created = await c.post("/api/v1/risks", json=body())
    assert created.status_code == (201 if role in WRITERS else 403)


async def test_only_the_director_closes_or_reopens_a_risk(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    admin = await make_client_for(session, "admin")
    director = await make_client_for(session, "director")
    risk = (await admin.post("/api/v1/risks", json=body())).json()
    url = f"/api/v1/risks/{risk['id']}"
    assert (await admin.patch(url, json={"status": "mitigating"})).status_code == 200
    denied = await admin.patch(url, json={"status": "closed"})
    assert denied.status_code == 403  # admin has W, not A
    assert (await director.patch(url, json={"status": "closed"})).json()["status"] == "closed"
    assert (
        await admin.patch(url, json={"status": "open"})
    ).status_code == 403  # reopening is also A
    assert (await director.patch(url, json={"status": "open"})).json()["status"] == "open"
    assert (await admin.patch(url, json={"title": "đổi tên khi đang đóng"})).status_code == 200


# --- create and update ------------------------------------------------------------------------


async def test_create_assigns_sequential_codes_and_computes_the_score(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    first = (
        await c.post("/api/v1/risks", json=body(probability=5, impact=5, source="analysis"))
    ).json()
    second = (await c.post("/api/v1/risks", json=body(probability=1, impact=2))).json()
    assert (first["code"], first["score"], first["level"], first["source"]) == (
        "R-011",
        25,
        "high",
        "analysis",
    )
    assert (second["code"], second["score"], second["level"], second["source"]) == (
        "R-012",
        2,
        "low",
        "manual",
    )
    cheating = await c.post("/api/v1/risks", json=body(probability=2, impact=2, score=25))
    assert cheating.json()["score"] == 4  # the client cannot set the score


async def test_update_recomputes_the_score_and_audits_the_change(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "cost")
    risk = (await c.post("/api/v1/risks", json=body(probability=2, impact=2))).json()
    upd = await c.patch(f"/api/v1/risks/{risk['id']}", json={"impact": 5, "mitigation": "Theo dõi"})
    assert (upd.json()["score"], upd.json()["level"]) == (10, "medium")
    rows = (
        (
            await session.execute(
                select(AuditLog).where(AuditLog.entity_type == "risk", AuditLog.action == "update")
            )
        )
        .scalars()
        .all()
    )
    assert rows[0].changes["impact"] == {"before": 2, "after": 5}
    assert rows[0].changes["score"] == {
        "before": 4,
        "after": 10,
    }  # history of the change (SPEC 4.8 AC)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        body(probability=0),
        body(probability=6),
        body(impact=0),
        body(impact=6),
        body(category="astrology"),
        body(title=""),
        body(source="rumour"),
        body(owner_id=GHOST),
        body(package_id=GHOST),
        body(due_date="31/12/2026"),
    ],
)
async def test_create_validation_422(
    payload: dict, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    assert (await c.post("/api/v1/risks", json=payload)).status_code == 422


async def test_owner_must_be_an_active_user_and_patch_validation(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    gone = await make_user(session, "onsite", email="gone@example.test", is_active=False)
    assert (await c.post("/api/v1/risks", json=body(owner_id=str(gone.id)))).status_code == 422
    me = (await c.get("/api/v1/auth/me")).json()
    risk = (
        await c.post("/api/v1/risks", json=body(owner_id=me["id"], package_id=str(seeded[4].id)))
    ).json()
    assert risk["owner_id"] == me["id"] and risk["package_id"] == str(seeded[4].id)
    url = f"/api/v1/risks/{risk['id']}"
    for bad in (
        {"title": None},
        {"category": None},
        {"probability": None},
        {"impact": 9},
        {"status": "done"},
    ):
        assert (await c.patch(url, json=bad)).status_code == 422
    assert (await c.patch(url, json={"owner_id": None})).json()[
        "owner_id"
    ] is None  # clearing is allowed
    assert (await c.patch(f"/api/v1/risks/{GHOST}", json={"title": "x"})).status_code == 404
    assert (await c.get(f"/api/v1/risks/{GHOST}")).status_code == 404


# --- listing and matrix -----------------------------------------------------------------------


async def test_list_filters_and_pagination(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    api = "/api/v1/risks"
    assert (await c.get(api, params={"level": "high"})).json()[
        "total"
    ] == 4  # scores 20, 20, 16, 15
    assert (await c.get(api, params={"level": "low"})).json()["total"] == 0
    assert {r["score"] for r in (await c.get(api, params={"level": "medium"})).json()["items"]} == {
        6,
        9,
        12,
    }
    assert (await c.get(api, params={"category": "contract"})).json()["total"] == 4
    assert (await c.get(api, params={"probability": 3, "impact": 4})).json()["total"] == 2
    assert (await c.get(api, params={"q": "tvgs"})).json()["total"] == 1
    assert (await c.get(api, params={"q": "R-002"})).json()["total"] == 1
    page = (await c.get(api, params={"page": 2, "page_size": 4})).json()
    assert len(page["items"]) == 4 and page["total"] == 10
    for bad in ({"level": "extreme"}, {"probability": 9}, {"page_size": 101}):
        assert (await c.get(api, params=bad)).status_code == 422


async def test_closed_risks_leave_the_matrix_unless_requested(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    director = await make_client_for(session, "director")
    risk = (await director.get("/api/v1/risks", params={"q": "R-001"})).json()["items"][0]
    await director.patch(f"/api/v1/risks/{risk['id']}", json={"status": "closed"})
    assert (await director.get("/api/v1/risks/matrix")).json()["total"] == 9
    assert (await director.get("/api/v1/risks/matrix", params={"include_closed": "true"})).json()[
        "total"
    ] == 10
    cell = next(
        x
        for x in (
            await director.get("/api/v1/risks/matrix", params={"include_closed": "true"})
        ).json()["cells"]
        if (x["probability"], x["impact"]) == (risk["probability"], risk["impact"])
    )
    assert risk["id"] in cell["risk_ids"]  # the UI filters the list by clicking the cell


# --- review reminder --------------------------------------------------------------------------


async def test_open_risks_not_reviewed_for_14_days_are_flagged_until_reviewed(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    risk = (await c.get("/api/v1/risks", params={"q": "R-003"})).json()["items"][0]
    assert risk["needs_review"] is False  # just created by the seed
    old = datetime.now(UTC) - timedelta(days=20)
    await session.execute(update(Risk).where(Risk.id == risk["id"]).values(created_at=old))
    await session.commit()
    assert (await c.get(f"/api/v1/risks/{risk['id']}")).json()["needs_review"] is True
    reviewed = await c.post(f"/api/v1/risks/{risk['id']}/review")
    assert reviewed.status_code == 200
    assert (
        reviewed.json()["needs_review"] is False and reviewed.json()["last_reviewed_at"] is not None
    )
    assert (await c.post(f"/api/v1/risks/{GHOST}/review")).status_code == 404


async def test_review_requires_write_access(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    viewer = await make_client_for(session, "viewer")
    risk_id = str(uuid.uuid4())
    assert (await viewer.post(f"/api/v1/risks/{risk_id}/review")).status_code == 403
