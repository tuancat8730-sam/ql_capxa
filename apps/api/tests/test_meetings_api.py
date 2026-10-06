"""M6: meetings, action items, change requests (SPEC 3.20, 3.21, 4.11, 4.12)."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Organization, Package
from app.seed.project import seed_project
from tests.conftest import ALL_ROLES, make_user

GHOST = "00000000-0000-0000-0000-000000000000"
TODAY = date(2026, 10, 6)
MEETING_WRITERS = {"admin", "director", "procurement", "technical"}  # matrix "Họp, thay đổi"


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.meetings.today_local", lambda: TODAY)


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[int, Package]:
    await seed_project(session)
    return {p.number: p for p in (await session.execute(select(Package))).scalars().all()}


def meeting(**over) -> dict:
    return {
        "meeting_type": "weekly",
        "meeting_date": "2026-10-05",
        "location": "Phòng họp Sở KH&CN",
        "chair": "Giám đốc QLDA",
        "attendees": [{"name": "Nguyễn A", "organization": "TVQLDA"}, {"name": "Trần B"}],
        "minutes": "Thống nhất lịch giao hàng.",
        **over,
    }


# --- meetings ---------------------------------------------------------------------------------


async def test_meeting_crud_with_attendees(session: AsyncSession, seeded, make_client_for) -> None:
    c = await make_client_for(session, "technical")
    made = await c.post("/api/v1/meetings", json=meeting(package_id=str(seeded[4].id)))
    assert made.status_code == 201
    m = made.json()
    assert (m["meeting_type"], m["meeting_date"], m["open_actions"]) == ("weekly", "2026-10-05", 0)
    assert m["attendees"] == [
        {"name": "Nguyễn A", "organization": "TVQLDA"},
        {"name": "Trần B", "organization": None},
    ]
    url = f"/api/v1/meetings/{m['id']}"
    upd = (await c.patch(url, json={"minutes": "Đã sửa", "attendees": [{"name": "Lê C"}]})).json()
    assert upd["minutes"] == "Đã sửa" and [a["name"] for a in upd["attendees"]] == ["Lê C"]
    assert (await c.patch(url, json={"attendees": None})).json()["attendees"] == []
    assert (await c.get(url)).json()["id"] == m["id"]
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_type == "meeting")))
        .scalars()
        .all()
    )
    assert {r.action for r in rows} == {"create", "update"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        meeting(meeting_type="party"),
        meeting(meeting_date="05/10/2026"),
        meeting(attendees=[{"name": "  "}]),
        meeting(attendees=[{"organization": "thiếu tên"}]),
        meeting(package_id=GHOST),
        {"meeting_date": "2026-10-05"},
    ],
)
async def test_meeting_validation_422(
    payload: dict, session: AsyncSession, seeded, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    assert (await c.post("/api/v1/meetings", json=payload)).status_code == 422


async def test_meeting_patch_validation_and_404(
    session: AsyncSession, seeded, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    m = (await c.post("/api/v1/meetings", json=meeting())).json()
    url = f"/api/v1/meetings/{m['id']}"
    for bad in (
        {"meeting_date": None},
        {"meeting_type": None},
        {"meeting_type": "party"},
        {"package_id": GHOST},
    ):
        assert (await c.patch(url, json=bad)).status_code == 422, bad
    assert (await c.patch(f"/api/v1/meetings/{GHOST}", json={"minutes": "x"})).status_code == 404
    assert (await c.get(f"/api/v1/meetings/{GHOST}")).status_code == 404


async def test_meeting_listing_filters_and_order(
    session: AsyncSession, seeded, make_client_for
) -> None:
    c = await make_client_for(session, "director")
    await c.post(
        "/api/v1/meetings", json=meeting(meeting_date="2026-09-20", meeting_type="kickoff")
    )
    await c.post(
        "/api/v1/meetings", json=meeting(meeting_date="2026-10-05", package_id=str(seeded[4].id))
    )
    await c.post(
        "/api/v1/meetings", json=meeting(meeting_date="2026-10-01", meeting_type="issue_resolution")
    )
    api = "/api/v1/meetings"
    assert [m["meeting_date"] for m in (await c.get(api)).json()["items"]] == [
        "2026-10-05",
        "2026-10-01",
        "2026-09-20",
    ]
    assert (await c.get(api, params={"meeting_type": "kickoff"})).json()["total"] == 1
    assert (await c.get(api, params={"package_id": str(seeded[4].id)})).json()["total"] == 1
    assert (await c.get(api, params={"date_from": "2026-10-01"})).json()["total"] == 2
    assert (await c.get(api, params={"date_to": "2026-09-30"})).json()["total"] == 1
    assert (await c.get(api, params={"page_size": 101})).status_code == 422


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_meeting_permissions_follow_the_matrix(
    role: str, session: AsyncSession, seeded, make_client_for
) -> None:
    c = await make_client_for(session, role)
    assert (await c.get("/api/v1/meetings")).status_code == 200  # every role reads
    assert (await c.get("/api/v1/change-requests")).status_code == 200
    assert (await c.post("/api/v1/meetings", json=meeting())).status_code == (
        201 if role in MEETING_WRITERS else 403
    )
    assert (await c.get("/api/v1/action-items")).status_code == 200


# --- action items -----------------------------------------------------------------------------


async def test_action_items_belong_to_a_meeting_and_inherit_its_package(
    session: AsyncSession, seeded, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    m = (await c.post("/api/v1/meetings", json=meeting(package_id=str(seeded[4].id)))).json()
    me = (await c.get("/api/v1/auth/me")).json()
    due = (TODAY + timedelta(days=3)).isoformat()
    a = (
        await c.post(
            f"/api/v1/meetings/{m['id']}/action-items",
            json={"title": "Gửi lịch giao hàng", "owner_id": me["id"], "due_date": due},
        )
    ).json()
    assert (a["status"], a["package_id"], a["overdue"], a["meeting_id"]) == (
        "open",
        str(seeded[4].id),
        False,
        m["id"],
    )
    assert (await c.get(f"/api/v1/meetings/{m['id']}")).json()["open_actions"] == 1
    other = (
        await c.post(
            f"/api/v1/meetings/{m['id']}/action-items",
            json={"title": "Việc khác", "package_id": str(seeded[6].id)},
        )
    ).json()
    assert other["package_id"] == str(seeded[6].id)
    listed = (await c.get(f"/api/v1/meetings/{m['id']}/action-items")).json()
    assert [x["title"] for x in listed] == [
        "Gửi lịch giao hàng",
        "Việc khác",
    ]  # dated first, undated last
    assert (await c.patch(f"/api/v1/action-items/{a['id']}", json={"status": "done"})).json()[
        "status"
    ] == "done"
    assert (await c.get(f"/api/v1/meetings/{m['id']}")).json()["open_actions"] == 1


async def test_overdue_actions_for_the_dashboard(
    session: AsyncSession, seeded, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    m = (await c.post("/api/v1/meetings", json=meeting())).json()
    url = f"/api/v1/meetings/{m['id']}/action-items"
    late = (
        await c.post(
            url, json={"title": "Quá hạn", "due_date": (TODAY - timedelta(days=1)).isoformat()}
        )
    ).json()
    today = (await c.post(url, json={"title": "Hôm nay", "due_date": TODAY.isoformat()})).json()
    done = (
        await c.post(
            url, json={"title": "Xong", "due_date": (TODAY - timedelta(days=9)).isoformat()}
        )
    ).json()
    await c.patch(f"/api/v1/action-items/{done['id']}", json={"status": "done"})
    await c.post(url, json={"title": "Không hạn"})
    assert late["overdue"] is True and today["overdue"] is False  # due today is not yet late
    api = "/api/v1/action-items"
    assert [x["title"] for x in (await c.get(api, params={"overdue": "true"})).json()["items"]] == [
        "Quá hạn"
    ]
    assert (await c.get(api)).json()["total"] == 4
    assert (await c.get(api, params={"status": "done"})).json()["total"] == 1
    me = (await c.get("/api/v1/auth/me")).json()
    await c.patch(f"/api/v1/action-items/{late['id']}", json={"owner_id": me["id"]})
    assert (await c.get(api, params={"owner_id": me["id"]})).json()["total"] == 1


async def test_action_validation_delete_and_404(
    session: AsyncSession, seeded, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    m = (await c.post("/api/v1/meetings", json=meeting())).json()
    url = f"/api/v1/meetings/{m['id']}/action-items"
    gone = await make_user(session, "onsite", email="gone@example.test", is_active=False)
    for bad in (
        {},
        {"title": ""},
        {"title": "x", "status": "maybe"},
        {"title": "x", "owner_id": str(gone.id)},
        {"title": "x", "owner_id": GHOST},
        {"title": "x", "due_date": "1/1/2026"},
        {"title": "x", "package_id": GHOST},
    ):
        assert (await c.post(url, json=bad)).status_code == 422, bad
    a = (await c.post(url, json={"title": "Việc"})).json()
    for bad in ({"title": None}, {"status": None}, {"status": "maybe"}):
        assert (await c.patch(f"/api/v1/action-items/{a['id']}", json=bad)).status_code == 422
    assert (
        await c.post(f"/api/v1/meetings/{GHOST}/action-items", json={"title": "x"})
    ).status_code == 404
    assert (await c.get(f"/api/v1/meetings/{GHOST}/action-items")).status_code == 404
    assert (await c.patch(f"/api/v1/action-items/{GHOST}", json={"title": "x"})).status_code == 404
    assert (await c.delete(f"/api/v1/action-items/{a['id']}")).status_code == 204
    assert (await c.delete(f"/api/v1/action-items/{a['id']}")).status_code == 404


# --- change requests --------------------------------------------------------------------------


def change(package: Package, **over) -> dict:
    return {
        "package_id": str(package.id),
        "change_type": "model",
        "description": "Đổi model máy tính",
        **over,
    }


async def test_change_request_flow_review_decide_and_sign(
    session: AsyncSession, seeded, make_client_for
) -> None:
    tech = await make_client_for(session, "technical")
    director = await make_client_for(session, "director")
    org = (
        await session.execute(select(Organization).where(Organization.org_type == "investor"))
    ).scalar_one_or_none()
    org_id = str(org.id) if org else None
    made = (
        await tech.post(
            "/api/v1/change-requests",
            json=change(seeded[4], proposed_by_org_id=org_id, supervisor_opinion="TVGS đồng ý"),
        )
    ).json()
    assert (made["code"], made["status"], made["decided_at"]) == ("C-001", "proposed", None)
    url = f"/api/v1/change-requests/{made['id']}"
    reviewing = (
        await tech.patch(
            url, json={"status": "reviewing", "tvqlda_opinion": "Tương đương kỹ thuật"}
        )
    ).json()
    assert (reviewing["status"], reviewing["tvqlda_opinion"]) == (
        "reviewing",
        "Tương đương kỹ thuật",
    )
    assert (await tech.patch(url, json={"status": "reviewing"})).status_code == 200  # no-op is fine

    assert (
        await tech.post(f"{url}/decide", json={"decision": "approved"})
    ).status_code == 403  # W is not A
    decided = (
        await director.post(
            f"{url}/decide", json={"decision": "approved", "note": "Đồng ý, ký phụ lục"}
        )
    ).json()
    assert (decided["status"], decided["decision_note"]) == ("approved", "Đồng ý, ký phụ lục")
    assert decided["decided_at"] is not None and decided["decided_by"] is not None
    assert (await director.post(f"{url}/decide", json={"decision": "rejected"})).status_code == 409
    signed = (await tech.patch(url, json={"status": "appendix_signed"})).json()
    assert signed["status"] == "appendix_signed"
    assert (
        await tech.patch(url, json={"status": "proposed"})
    ).status_code == 400  # finished flows stay finished
    audit = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_type == "change_request")))
        .scalars()
        .all()
    )
    assert {a.action for a in audit} == {"create", "update"} and len(audit) >= 4


async def test_a_rejected_request_cannot_be_signed(
    session: AsyncSession, seeded, make_client_for
) -> None:
    tech = await make_client_for(session, "technical")
    director = await make_client_for(session, "director")
    made = (
        await tech.post("/api/v1/change-requests", json=change(seeded[5], change_type="origin"))
    ).json()
    url = f"/api/v1/change-requests/{made['id']}"
    assert (
        await director.post(
            f"{url}/decide", json={"decision": "rejected", "note": "Không tương đương"}
        )
    ).json()["status"] == "rejected"
    assert (await tech.patch(url, json={"status": "appendix_signed"})).status_code == 400
    assert (await tech.patch(url, json={"status": "reviewing"})).status_code == 400


async def test_the_status_cannot_jump_to_approved_through_patch(
    session: AsyncSession, seeded, make_client_for
) -> None:
    tech = await make_client_for(session, "technical")
    made = (await tech.post("/api/v1/change-requests", json=change(seeded[4]))).json()
    url = f"/api/v1/change-requests/{made['id']}"
    for status in ("approved", "rejected"):
        assert (
            await tech.patch(url, json={"status": status})
        ).status_code == 422  # decide() is the only way
    assert (
        await tech.patch(url, json={"status": "appendix_signed"})
    ).status_code == 400  # not approved yet


@pytest.mark.parametrize("role", ["admin", "procurement", "cost", "onsite", "clerk", "viewer"])
async def test_only_the_director_decides(
    role: str, session: AsyncSession, seeded, make_client_for
) -> None:
    tech = await make_client_for(session, "technical")
    made = (await tech.post("/api/v1/change-requests", json=change(seeded[4]))).json()
    c = await make_client_for(session, role)
    assert (
        await c.post(f"/api/v1/change-requests/{made['id']}/decide", json={"decision": "approved"})
    ).status_code == 403


@pytest.mark.parametrize(
    "payload_fn",
    [
        lambda p: {},
        lambda p: change(p, change_type="alien"),
        lambda p: change(p, description=""),
        lambda p: change(p, proposed_by_org_id=GHOST),
        lambda p: change(p, amendment_id=GHOST),
        lambda p: {**change(p), "package_id": GHOST},
        lambda p: {"change_type": "model", "description": "thiếu gói"},
    ],
)
async def test_change_validation_422(
    payload_fn, session: AsyncSession, seeded, make_client_for
) -> None:
    tech = await make_client_for(session, "technical")
    assert (
        await tech.post("/api/v1/change-requests", json=payload_fn(seeded[4]))
    ).status_code == 422


async def test_change_links_to_a_contract_amendment_and_lists_by_filters(
    session: AsyncSession, seeded, make_client_for
) -> None:
    admin = await make_client_for(session, "admin")
    contract_id = None
    # contracts exist only through the API here: create one for package 4, then an amendment
    contract = (
        await admin.post(f"/api/v1/packages/{seeded[4].id}/contracts", json={"contract_no": "71"})
    ).json()
    contract_id = contract["id"]
    amendment = (
        await admin.post(
            f"/api/v1/contracts/{contract_id}/amendments",
            json={"amendment_no": "PL01", "type": "scope"},
        )
    ).json()
    made = (
        await admin.post(
            "/api/v1/change-requests",
            json=change(seeded[4], amendment_id=amendment["id"], change_type="schedule"),
        )
    ).json()
    assert made["amendment_id"] == amendment["id"]
    await admin.post("/api/v1/change-requests", json=change(seeded[5]))
    api = "/api/v1/change-requests"
    assert (await admin.get(api)).json()["total"] == 2
    assert (await admin.get(api, params={"package_id": str(seeded[4].id)})).json()["total"] == 1
    assert (await admin.get(api, params={"change_type": "schedule"})).json()["total"] == 1
    assert (await admin.get(api, params={"status": "approved"})).json()["total"] == 0
    assert (await admin.get(f"{api}/{made['id']}")).json()["code"] == "C-001"
    assert (await admin.get(f"{api}/{GHOST}")).status_code == 404
    assert (await admin.patch(f"{api}/{GHOST}", json={"description": "x"})).status_code == 404
    assert (
        await admin.post(f"{api}/{GHOST}/decide", json={"decision": "approved"})
    ).status_code in {403, 404}
    for bad in (
        {"description": None},
        {"change_type": None},
        {"status": None},
        {"amendment_id": GHOST},
    ):
        assert (await admin.patch(f"{api}/{made['id']}", json=bad)).status_code == 422, bad
    assert (await admin.get(api, params={"page_size": 101})).status_code == 422
