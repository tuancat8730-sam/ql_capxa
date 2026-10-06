"""M6: three-level issues, SLA deadlines, escalation history (SPEC 3.17, 4.9, 7.4)."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Issue, Package
from app.seed.project import seed_project
from tests.conftest import ALL_ROLES, make_user

VN = ZoneInfo("Asia/Ho_Chi_Minh")
GHOST = "00000000-0000-0000-0000-000000000000"
READERS = {"admin", "director", "procurement", "technical", "cost", "onsite", "viewer"}
WRITERS = {"admin", "director", "procurement", "technical", "cost", "onsite"}


def vn(y: int, m: int, d: int, h: int = 10, minute: int = 0) -> datetime:
    return datetime(y, m, d, h, minute, tzinfo=VN).astimezone(UTC)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch):
    """Control 'now' for the issue router; default Thursday 08/10/2026 10:00 Vietnam time."""
    state = {"now": vn(2026, 10, 8)}
    monkeypatch.setattr("app.routers.issues._now", lambda: state["now"])
    return state


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[int, Package]:
    await seed_project(session)
    return {p.number: p for p in (await session.execute(select(Package))).scalars().all()}


def body(**over) -> dict:
    return {"issue_type": "operational", "title": "Lịch giao hàng chưa chốt", **over}


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# --- deadlines at creation ----------------------------------------------------------------------


async def test_level_1_is_due_two_days_after_creation(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "onsite")
    issue = (await c.post("/api/v1/issues", json=body(package_id=str(seeded[4].id)))).json()
    assert (issue["code"], issue["level"], issue["status"]) == ("V-001", 1, "open")
    assert parse(issue["due_at"]) == vn(2026, 10, 10)  # +2 calendar days (a Saturday)
    assert issue["overdue"] is False and issue["package_id"] == str(seeded[4].id)


async def test_level_2_is_three_working_days_and_honours_configured_holidays(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    admin = await make_client_for(session, "admin")
    c = await make_client_for(session, "technical")
    plain = (await c.post("/api/v1/issues", json=body(level=2, issue_type="contract"))).json()
    assert parse(plain["due_at"]) == vn(2026, 10, 13)  # Thu -> Fri, Mon, Tue
    await admin.post("/api/v1/admin/holidays", json={"day": "2026-10-12", "name": "Nghỉ bù"})
    with_holiday = (
        await c.post("/api/v1/issues", json=body(level=2, issue_type="contract"))
    ).json()
    assert parse(with_holiday["due_at"]) == vn(2026, 10, 14)  # Monday does not count
    assert with_holiday["escalated_at"] is not None


async def test_level_3_deadline_is_entered_by_hand(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "director")
    none = (await c.post("/api/v1/issues", json=body(level=3, issue_type="schedule"))).json()
    assert none["due_at"] is None and none["overdue"] is False
    manual = (
        await c.post("/api/v1/issues", json=body(level=3, due_at="2026-11-30T10:00:00+07:00"))
    ).json()
    assert parse(manual["due_at"]) == vn(2026, 11, 30)
    ignored = (
        await c.post("/api/v1/issues", json=body(level=1, due_at="2030-01-01T00:00:00Z"))
    ).json()
    assert parse(ignored["due_at"]) == vn(2026, 10, 10)  # a hand-typed date is only for level 3


@pytest.mark.parametrize("level", [1, 2, 3])
async def test_investor_requests_are_due_in_one_day_even_on_weekends(
    level: int, session: AsyncSession, seeded, clock, make_client_for
) -> None:
    clock["now"] = vn(2026, 10, 9, 17, 0)  # Friday evening
    c = await make_client_for(session, "onsite")
    issue = (
        await c.post("/api/v1/issues", json=body(issue_type="investor_request", level=level))
    ).json()
    assert parse(issue["due_at"]) == vn(2026, 10, 10, 17, 0)  # Saturday


# --- escalation ---------------------------------------------------------------------------------


async def test_escalation_moves_up_one_level_recomputes_the_deadline_and_keeps_history(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    issue = (await c.post("/api/v1/issues", json=body())).json()
    clock["now"] = vn(2026, 10, 9, 15, 0)  # Friday
    up = await c.post(
        f"/api/v1/issues/{issue['id']}/escalate", json={"note": "Cần chủ đầu tư quyết"}
    )
    assert up.status_code == 200
    out = up.json()
    assert (out["level"], out["status"]) == (2, "escalated")
    assert parse(out["due_at"]) == vn(2026, 10, 14, 15, 0)  # Fri + 3 working days = Wed
    clock["now"] = vn(2026, 10, 15, 9, 0)
    top = (
        await c.post(
            f"/api/v1/issues/{issue['id']}/escalate", json={"due_at": "2026-12-01T09:00:00+07:00"}
        )
    ).json()
    assert (top["level"], parse(top["due_at"])) == (3, vn(2026, 12, 1, 9, 0))
    detail = (await c.get(f"/api/v1/issues/{issue['id']}")).json()
    assert [(e["event"], e["from_level"], e["to_level"]) for e in detail["events"]] == [
        ("created", None, 1),
        ("escalated", 1, 2),
        ("escalated", 2, 3),
    ]
    assert detail["events"][1]["note"] == "Cần chủ đầu tư quyết"
    assert all(e["user_id"] for e in detail["events"])
    assert (
        await c.post(f"/api/v1/issues/{issue['id']}/escalate")
    ).status_code == 409  # already at the top


async def test_escalating_without_a_body_works_and_level_3_stays_without_deadline(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    issue = (await c.post("/api/v1/issues", json=body(level=2))).json()
    top = (await c.post(f"/api/v1/issues/{issue['id']}/escalate")).json()
    assert top["level"] == 3 and top["due_at"] is None


async def test_an_investor_request_keeps_its_fixed_deadline_when_escalated(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    issue = (await c.post("/api/v1/issues", json=body(issue_type="investor_request"))).json()
    clock["now"] = vn(2026, 10, 8, 14, 0)
    up = (await c.post(f"/api/v1/issues/{issue['id']}/escalate")).json()
    assert up["level"] == 2 and up["due_at"] == issue["due_at"]


async def test_finished_issues_cannot_be_escalated(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    issue = (await c.post("/api/v1/issues", json=body())).json()
    await c.post(f"/api/v1/issues/{issue['id']}/resolve", json={"resolution": "Đã xong"})
    assert (await c.post(f"/api/v1/issues/{issue['id']}/escalate")).status_code == 409
    assert (await c.post(f"/api/v1/issues/{GHOST}/escalate")).status_code == 404


# --- resolve and status moves -------------------------------------------------------------------


async def test_resolve_records_the_decision_and_blocks_a_second_resolution(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    issue = (await c.post("/api/v1/issues", json=body(level=2, issue_type="contract"))).json()
    url = f"/api/v1/issues/{issue['id']}/resolve"
    assert (await c.post(url, json={})).status_code == 422
    assert (await c.post(url, json={"resolution": ""})).status_code == 422
    clock["now"] = vn(2026, 10, 9, 9, 0)
    ok = (
        await c.post(url, json={"resolution": "Ký phụ lục", "decided_by": "Sở KH&CN, QĐ 123"})
    ).json()
    assert (ok["status"], ok["resolution"], ok["decided_by"]) == (
        "resolved",
        "Ký phụ lục",
        "Sở KH&CN, QĐ 123",
    )
    assert parse(ok["resolved_at"]) == vn(2026, 10, 9, 9, 0)
    assert ok["overdue"] is False
    assert (await c.post(url, json={"resolution": "lần hai"})).status_code == 409
    assert (
        await c.post(f"/api/v1/issues/{GHOST}/resolve", json={"resolution": "x"})
    ).status_code == 404


async def test_status_transitions_are_enforced(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    issue = (await c.post("/api/v1/issues", json=body())).json()
    url = f"/api/v1/issues/{issue['id']}"
    assert (await c.patch(url, json={"status": "in_progress"})).json()["status"] == "in_progress"
    assert (await c.patch(url, json={"status": "open"})).json()["status"] == "open"
    assert (
        await c.patch(url, json={"status": "closed"})
    ).status_code == 400  # must be resolved first
    for dedicated in ("resolved", "escalated"):
        assert (
            await c.patch(url, json={"status": dedicated})
        ).status_code == 422  # use /resolve, /escalate
    await c.post(f"{url}/resolve", json={"resolution": "ok"})
    reopened = (await c.patch(url, json={"status": "open"})).json()
    assert reopened["status"] == "open" and reopened["resolved_at"] is None
    await c.post(f"{url}/resolve", json={"resolution": "ok lần hai"})
    assert (await c.patch(url, json={"status": "closed"})).json()["status"] == "closed"
    events = [e["event"] for e in (await c.get(url)).json()["events"]]
    assert events == [
        "created",
        "status_changed",
        "status_changed",
        "resolved",
        "reopened",
        "resolved",
        "closed",
    ]


async def test_only_the_director_closes_level_3_issues(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    onsite = await make_client_for(session, "onsite")
    director = await make_client_for(session, "director")
    l3 = (await onsite.post("/api/v1/issues", json=body(level=3, issue_type="schedule"))).json()
    l1 = (await onsite.post("/api/v1/issues", json=body())).json()
    for issue in (l3, l1):
        await onsite.post(f"/api/v1/issues/{issue['id']}/resolve", json={"resolution": "xong"})
    assert (
        await onsite.patch(f"/api/v1/issues/{l3['id']}", json={"status": "closed"})
    ).status_code == 403
    assert (
        await director.patch(f"/api/v1/issues/{l3['id']}", json={"status": "closed"})
    ).status_code == 200
    assert (
        await onsite.patch(f"/api/v1/issues/{l1['id']}", json={"status": "closed"})
    ).status_code == 200


async def test_editing_the_deadline_needs_a_reason_and_is_recorded(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    issue = (await c.post("/api/v1/issues", json=body())).json()
    url = f"/api/v1/issues/{issue['id']}"
    assert (await c.patch(url, json={"due_at": "2026-10-20T10:00:00+07:00"})).status_code == 422
    assert (
        await c.patch(url, json={"due_at": "2026-10-20T10:00:00+07:00", "due_reason": "ab"})
    ).status_code == 422
    ok = await c.patch(
        url, json={"due_at": "2026-10-20T10:00:00+07:00", "due_reason": "Chủ đầu tư đồng ý gia hạn"}
    )
    assert parse(ok.json()["due_at"]) == vn(2026, 10, 20)
    events = (await c.get(url)).json()["events"]
    assert (
        events[-1]["event"] == "due_changed" and events[-1]["note"] == "Chủ đầu tư đồng ý gia hạn"
    )
    same = await c.patch(
        url, json={"due_at": "2026-10-20T10:00:00+07:00"}
    )  # unchanged: no reason needed
    assert same.status_code == 200
    audit = (
        (
            await session.execute(
                select(AuditLog).where(AuditLog.entity_type == "issue", AuditLog.action == "update")
            )
        )
        .scalars()
        .all()
    )
    assert any("due_at" in (a.changes or {}) for a in audit)


async def test_patch_other_fields_validation_and_404(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    issue = (await c.post("/api/v1/issues", json=body())).json()
    url = f"/api/v1/issues/{issue['id']}"
    gone = await make_user(session, "onsite", email="gone@example.test", is_active=False)
    for bad in (
        {"title": None},
        {"title": ""},
        {"status": None},
        {"issue_type": "weird"},
        {"assigned_to": str(gone.id)},
        {"assigned_to": GHOST},
    ):
        assert (await c.patch(url, json=bad)).status_code == 422, bad
    me = (await c.get("/api/v1/auth/me")).json()
    ok = (await c.patch(url, json={"assigned_to": me["id"], "description": "Chi tiết"})).json()
    assert (ok["assigned_to"], ok["description"]) == (me["id"], "Chi tiết")
    assert [e["event"] for e in (await c.get(url)).json()["events"]][-1] == "assigned"
    assert (await c.patch(f"/api/v1/issues/{GHOST}", json={"title": "x"})).status_code == 404
    assert (await c.get(f"/api/v1/issues/{GHOST}")).status_code == 404


# --- create validation --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {},
        body(title=""),
        body(level=0),
        body(level=4),
        body(issue_type="gossip"),
        body(package_id=GHOST),
        body(assigned_to=GHOST),
        {"title": "thiếu loại"},
    ],
)
async def test_create_validation_422(
    payload: dict, session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "onsite")
    assert (await c.post("/api/v1/issues", json=payload)).status_code == 422


async def test_codes_are_sequential(session: AsyncSession, seeded, clock, make_client_for) -> None:
    c = await make_client_for(session, "onsite")
    codes = [(await c.post("/api/v1/issues", json=body())).json()["code"] for _ in range(3)]
    assert codes == ["V-001", "V-002", "V-003"]


# --- overdue and listing ------------------------------------------------------------------------


async def test_overdue_flag_days_and_filters(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    late = (await c.post("/api/v1/issues", json=body(title="Quá hạn"))).json()
    fresh = (
        await c.post("/api/v1/issues", json=body(title="Còn hạn", package_id=str(seeded[6].id)))
    ).json()
    done = (await c.post("/api/v1/issues", json=body(title="Đã xong"))).json()
    await c.post(f"/api/v1/issues/{done['id']}/resolve", json={"resolution": "ok"})

    clock["now"] = vn(2026, 10, 10, 10, 0) + timedelta(
        hours=30
    )  # 1 day 6 h past the 10/10 10:00 deadline
    listing = (await c.get("/api/v1/issues")).json()
    by = {i["title"]: i for i in listing["items"]}
    assert (by["Quá hạn"]["overdue"], by["Quá hạn"]["overdue_days"]) == (True, 1)
    assert by["Đã xong"]["overdue"] is False  # finished issues are never overdue
    assert (await c.get("/api/v1/issues", params={"overdue": "true"})).json()[
        "total"
    ] == 2  # late + fresh (same deadline)
    assert {
        i["title"]
        for i in (await c.get("/api/v1/issues", params={"overdue": "false"})).json()["items"]
    } == {"Đã xong"}
    assert late["id"] and fresh["id"]


async def test_list_filters_search_and_ordering(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    me = (await c.get("/api/v1/auth/me")).json()
    await c.post(
        "/api/v1/issues",
        json=body(title="Mất điện tại xã A", package_id=str(seeded[4].id), assigned_to=me["id"]),
    )
    clock["now"] = vn(2026, 10, 8, 9, 0)
    await c.post(
        "/api/v1/issues", json=body(title="Điều khoản trọn gói", level=2, issue_type="contract")
    )
    await c.post("/api/v1/issues", json=body(title="Chậm tiến độ", level=3, issue_type="schedule"))
    api = "/api/v1/issues"
    assert (await c.get(api, params={"level": 2})).json()["total"] == 1
    assert (await c.get(api, params={"issue_type": "contract"})).json()["total"] == 1
    assert (await c.get(api, params={"package_id": str(seeded[4].id)})).json()["total"] == 1
    assert (await c.get(api, params={"assigned_to": me["id"]})).json()["total"] == 1
    assert (await c.get(api, params={"q": "mat dien"})).json()[
        "total"
    ] == 0  # plain ILIKE: no diacritic folding here
    assert (await c.get(api, params={"q": "Mất điện"})).json()["total"] == 1
    assert (await c.get(api, params={"q": "V-002"})).json()["total"] == 1
    titles = [i["title"] for i in (await c.get(api)).json()["items"]]
    assert titles[-1] == "Chậm tiến độ"  # no deadline sorts last
    for bad in ({"level": 4}, {"page_size": 101}):
        assert (await c.get(api, params=bad)).status_code == 422


# --- permissions and holidays -------------------------------------------------------------------


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_issue_permissions_follow_the_risk_matrix_row(
    role: str, session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, role)
    assert (await c.get("/api/v1/issues")).status_code == (200 if role in READERS else 403)
    created = await c.post("/api/v1/issues", json=body())
    assert created.status_code == (201 if role in WRITERS else 403)


@pytest.mark.parametrize("role", [r for r in ALL_ROLES if r != "admin"])
async def test_only_admin_manages_holidays(
    role: str, session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, role)
    assert (await c.get("/api/v1/admin/holidays")).status_code == 403
    assert (
        await c.post("/api/v1/admin/holidays", json={"day": "2026-09-02", "name": "Quốc khánh"})
    ).status_code == 403


async def test_holiday_crud_and_validation(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "admin")
    made = await c.post("/api/v1/admin/holidays", json={"day": "2026-09-02", "name": "Quốc khánh"})
    assert made.status_code == 201
    assert (
        await c.post("/api/v1/admin/holidays", json={"day": "2026-09-02", "name": "trùng"})
    ).status_code == 409
    await c.post(
        "/api/v1/admin/holidays", json={"day": "2026-04-30", "name": "Giải phóng miền Nam"}
    )
    assert [h["day"] for h in (await c.get("/api/v1/admin/holidays")).json()] == [
        "2026-04-30",
        "2026-09-02",
    ]
    for bad in ({}, {"day": "02/09/2026", "name": "x"}, {"day": "2026-09-03", "name": ""}):
        assert (await c.post("/api/v1/admin/holidays", json=bad)).status_code == 422
    assert (await c.delete(f"/api/v1/admin/holidays/{made.json()['id']}")).status_code == 204
    assert (await c.delete(f"/api/v1/admin/holidays/{made.json()['id']}")).status_code == 404
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_type == "holiday")))
        .scalars()
        .all()
    )
    assert {r.action for r in rows} == {"create", "delete"}


async def test_issue_creation_is_audited(
    session: AsyncSession, seeded, clock, make_client_for
) -> None:
    c = await make_client_for(session, "onsite")
    issue = (await c.post("/api/v1/issues", json=body())).json()
    row = (
        await session.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "issue", AuditLog.entity_id == issue["id"]
            )
        )
    ).scalar_one()
    assert row.action == "create" and row.changes["code"] == "V-001"
    stored = (await session.execute(select(Issue))).scalar_one()
    assert stored.reported_by is not None and isinstance(stored.due_at, datetime)
    assert date(2026, 10, 8) <= stored.reported_at.date() <= date(2026, 10, 9)
