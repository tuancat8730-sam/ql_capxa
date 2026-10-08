"""The SGD-HCM project: schedule, weekly reports, open decisions, risks and alerts."""

from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Project, ProjectMember, User, WbsTask
from app.seed.sgd_hcm import seed_sgd_hcm
from app.seed.sgd_hcm_plan import PHASES
from app.services.alert_engine import run_alerts
from tests.test_multi_project import H, client_as, make_project, seat

BASE = "/api/v1/delivery"

RISK = {
    "title": "Dữ liệu cũ không đồng nhất",
    "category": "other",
    "probability": 5,
    "impact": 5,
    "group_name": "Dữ liệu",
    "owner_text": "CĐT, LD DVN",
    "mitigation": "Làm sạch trước khi chuyển đổi",
    "note": "Đã họp ngày 02/10",
    "due_date": "2026-10-30",
}


def freeze(monkeypatch: pytest.MonkeyPatch, day: str) -> None:
    """Pretend today is `day` for the delivery pages."""
    monkeypatch.setattr("app.routers.delivery.today_local", lambda: date.fromisoformat(day))


@pytest.fixture
async def sgd(session: AsyncSession) -> Project:
    return await seed_sgd_hcm(session)


async def member(
    storage,
    session: AsyncSession,
    sgd: Project,
    role: str = "director",
    email: str = "m@example.test",
) -> tuple[httpx.AsyncClient, User]:
    c, user = await client_as(storage, session, email, role)
    await seat(session, sgd, user, role)
    c.headers[H] = str(sgd.id)
    return c, user


async def task_id(c: httpx.AsyncClient, code: str) -> str:
    tasks = (await c.get(f"{BASE}/tasks")).json()
    return next(t["id"] for t in tasks if t["code"] == code)


# --- the seed ---------------------------------------------------------------------------------


async def test_the_seed_loads_the_baseline_plan(session: AsyncSession, sgd: Project) -> None:
    rows = (
        (await session.execute(select(WbsTask).where(WbsTask.project_id == sgd.id))).scalars().all()
    )
    assert len(rows) == sum(len(p.tasks) for p in PHASES) == 44
    assert sum(1 for r in rows if r.is_milestone) == 9
    assert {r.phase_code for r in rows} == {p.code for p in PHASES}
    assert min(r.plan_start for r in rows) == date(2026, 9, 25)
    assert max(r.plan_end for r in rows) == date(2026, 12, 9)
    assert not any(r.tracked for r in rows)
    assert sgd.project_type == "software_delivery"


async def test_seeding_twice_changes_nothing(session: AsyncSession, sgd: Project) -> None:
    again = await seed_sgd_hcm(session)
    count = (await session.execute(select(func.count()).select_from(WbsTask))).scalar_one()
    seats = (await session.execute(select(func.count()).select_from(ProjectMember))).scalar_one()
    assert again.id == sgd.id and count == 44
    assert seats == 0  # nobody is seated: system administrators add people later


# --- access -----------------------------------------------------------------------------------


async def test_the_pages_belong_to_software_projects_only(session: AsyncSession, storage) -> None:
    other = await make_project(session, "CX", "procurement")
    admin, _ = await client_as(storage, session, "root@example.test", "admin")
    assert (await admin.get(f"{BASE}/tasks", headers={H: str(other.id)})).status_code == 404


async def test_a_system_admin_sees_the_project_without_a_seat(
    session: AsyncSession, storage, sgd: Project
) -> None:
    admin, _ = await client_as(storage, session, "root@example.test", "admin")
    resp = await admin.get(f"{BASE}/tasks", headers={H: str(sgd.id)})
    assert resp.status_code == 200 and len(resp.json()) == 44


async def test_roles_decide_who_may_record_progress(
    session: AsyncSession, storage, sgd: Project
) -> None:
    viewer, _ = await member(storage, session, sgd, "viewer", "v@example.test")
    tech, _ = await member(storage, session, sgd, "technical", "t@example.test")
    tid = await task_id(viewer, "I.1")
    assert (await viewer.get(f"{BASE}/overview")).status_code == 200
    assert (await viewer.patch(f"{BASE}/tasks/{tid}", json={"pct": 10})).status_code == 403
    assert (await tech.patch(f"{BASE}/tasks/{tid}", json={"pct": 10})).status_code == 200
    assert (await viewer.put(f"{BASE}/reports/2026-09-25", json={})).status_code == 403
    assert (await viewer.post(f"{BASE}/decisions", json={"title": "x"})).status_code == 403


# --- schedule ---------------------------------------------------------------------------------


async def test_tasks_come_in_plan_order_with_their_state(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-06")
    c, _ = await member(storage, session, sgd)
    tasks = (await c.get(f"{BASE}/tasks")).json()
    assert [t["code"] for t in tasks][:3] == ["I.1", "II.1", "II.2"]
    by_code = {t["code"]: t for t in tasks}
    assert by_code["I.1"]["state"] == "stale"  # ended 29/9, nothing recorded
    assert by_code["I.1"]["late_days"] == 5
    assert by_code["II.4"]["state"] == "stale"  # running today, nothing recorded
    assert by_code["IV.1"]["state"] == "todo"
    assert by_code["M1"]["is_milestone"] and by_code["M1"]["state"] == "todo"


async def test_recording_progress_follows_the_site_manager_rules(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-01")
    c, _ = await member(storage, session, sgd)
    tid = await task_id(c, "II.2")  # 1-5 Oct

    started = (await c.patch(f"{BASE}/tasks/{tid}", json={"pct": 40})).json()
    assert (started["status"], started["pct"], started["tracked"]) == ("in_progress", 40, True)
    assert started["actual_start"] == "2026-10-01" and started["actual_end"] is None

    done = (await c.patch(f"{BASE}/tasks/{tid}", json={"status": "done"})).json()
    assert (done["status"], done["pct"], done["state"]) == ("done", 100, "done")
    assert done["actual_end"] == "2026-10-01"

    bad_dates = {"actual_start": "2026-10-03", "actual_end": "2026-10-02"}
    assert (await c.patch(f"{BASE}/tasks/{tid}", json=bad_dates)).status_code == 422
    assert (await c.patch(f"{BASE}/tasks/{tid}", json={"pct": 101})).status_code == 422


async def test_a_milestone_is_reached_not_percent_complete(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-07")
    c, _ = await member(storage, session, sgd)
    mid = await task_id(c, "M1")
    got = (await c.patch(f"{BASE}/tasks/{mid}", json={"status": "done"})).json()
    assert got["status"] == "done" and got["pct"] == 0
    assert got["actual_end"] == "2026-10-07" and got["state"] == "done"


async def test_progress_can_be_reset_to_not_updated(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-02")
    c, _ = await member(storage, session, sgd)
    tid = await task_id(c, "II.2")
    await c.patch(f"{BASE}/tasks/{tid}", json={"pct": 60, "note": "Chờ biểu mẫu"})
    reset = (await c.post(f"{BASE}/tasks/{tid}/reset")).json()
    assert reset["tracked"] is False and reset["status"] == "not_started"
    assert reset["pct"] == 0 and reset["note"] is None


async def test_progress_is_audited_with_the_project(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-02")
    c, _ = await member(storage, session, sgd)
    tid = await task_id(c, "II.2")
    await c.patch(f"{BASE}/tasks/{tid}", json={"pct": 60})
    rows = (await c.get("/api/v1/audit-log?entity_type=wbs_task")).json()
    assert rows["total"] == 1 and rows["items"][0]["entity_id"] == tid


async def test_a_task_of_another_project_cannot_be_touched(
    session: AsyncSession, storage, sgd: Project
) -> None:
    c, user = await member(storage, session, sgd)
    tid = await task_id(c, "I.1")
    second = await make_project(session, "SW2", "software_delivery")
    await seat(session, second, user, "director")
    resp = await c.patch(f"{BASE}/tasks/{tid}", json={"pct": 5}, headers={H: str(second.id)})
    assert resp.status_code == 404


# --- overview ---------------------------------------------------------------------------------


async def test_overview_before_any_progress(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-09")
    c, _ = await member(storage, session, sgd)
    o = (await c.get(f"{BASE}/overview")).json()
    assert o["has_progress"] is False and o["actual_pct"] == 0
    assert 0 < o["plan_pct"] < 40
    assert o["diff"] == -round(o["plan_pct"])
    assert (o["project_start"], o["project_end"]) == ("2026-09-25", "2026-12-09")
    assert o["next_milestone"]["code"] == "M1"
    assert len(o["phases"]) == 11 and o["phases"][0]["code"] == "I"
    assert len(o["plan_curve"]) == 76 and o["plan_curve"][-1]["pct"] == 100
    assert o["weeks_ended"] == 2 and o["weeks_received"] == 0
    labels = [a["label"] for a in o["attention"]]
    assert "Cần cập nhật" in labels and labels.count("Báo cáo tuần") == 2
    assert [a["rank"] for a in o["attention"]] == sorted(a["rank"] for a in o["attention"])


async def test_overview_moves_with_progress(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-08")
    c, _ = await member(storage, session, sgd)
    before = (await c.get(f"{BASE}/overview")).json()
    for code in ("I.1", "II.1", "II.2", "II.3", "II.4", "V.1"):
        await c.patch(f"{BASE}/tasks/{await task_id(c, code)}", json={"status": "done"})
    await c.patch(f"{BASE}/tasks/{await task_id(c, 'M1')}", json={"status": "done"})
    after = (await c.get(f"{BASE}/overview")).json()
    assert after["has_progress"] and after["actual_pct"] > before["actual_pct"]
    assert after["next_milestone"]["code"] == "M2"
    assert after["stale_count"] < before["stale_count"]
    first = next(p for p in after["phases"] if p["code"] == "I")
    assert first["state"] == "done" and first["actual_pct"] == 100


# --- weekly reports ---------------------------------------------------------------------------


async def test_weeks_cover_the_plan_and_report_their_state(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-09")
    c, _ = await member(storage, session, sgd)
    weeks = (await c.get(f"{BASE}/weeks")).json()
    assert len(weeks) == 11
    assert (weeks[0]["start"], weeks[0]["end"]) == ("2026-09-25", "2026-10-01")
    assert [w["state"] for w in weeks[:4]] == ["missing", "missing", "current", "future"]
    assert weeks[-1]["suggested_planned_pct"] == 100
    assert weeks[0]["suggested_planned_pct"] < weeks[1]["suggested_planned_pct"]


async def test_a_report_is_saved_corrected_and_removed(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-08")
    c, _ = await member(storage, session, sgd)
    body = {
        "report_no": "BC-01",
        "submitted_on": "2026-10-02",
        "link": "https://drive.example.test/bc01",
        "planned_pct": 6,
        "actual_pct": 4,
        "done": "Họp khởi động",
        "next_plan": "Khảo sát",
    }
    saved = await c.put(f"{BASE}/reports/2026-09-25", json=body)
    assert saved.status_code == 200 and saved.json()["report_no"] == "BC-01"
    fixed = await c.put(f"{BASE}/reports/2026-09-25", json={**body, "status": "needs_more"})
    assert fixed.json()["status"] == "needs_more" and fixed.json()["id"] == saved.json()["id"]

    weeks = (await c.get(f"{BASE}/weeks")).json()
    assert weeks[0]["state"] == "needs_more" and weeks[0]["report"]["actual_pct"] == 4
    overview = (await c.get(f"{BASE}/overview")).json()
    assert overview["weeks_received"] == 1
    assert overview["report_points"] == [{"date": "2026-10-01", "pct": 4.0}]

    assert (await c.delete(f"{BASE}/reports/2026-09-25")).status_code == 204
    assert (await c.delete(f"{BASE}/reports/2026-09-25")).status_code == 404
    assert (await c.get(f"{BASE}/weeks")).json()[0]["state"] == "missing"


async def test_report_input_is_validated(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-08")
    c, _ = await member(storage, session, sgd)
    put = c.put
    assert (await put(f"{BASE}/reports/2026-09-26", json={})).status_code == 422  # not a start
    assert (await put(f"{BASE}/reports/2026-09-25", json={"link": "ftp://x"})).status_code == 422
    assert (await put(f"{BASE}/reports/2026-09-25", json={"actual_pct": 120})).status_code == 422
    nobody = {"risk_ids": ["00000000-0000-0000-0000-000000000001"]}
    assert (await put(f"{BASE}/reports/2026-09-25", json=nobody)).status_code == 422


async def test_a_report_can_name_the_risks_it_raises(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-08")
    c, _ = await member(storage, session, sgd)
    risk = (await c.post("/api/v1/risks", json=RISK)).json()
    saved = await c.put(f"{BASE}/reports/2026-09-25", json={"risk_ids": [risk["id"]]})
    assert saved.status_code == 200 and saved.json()["risk_ids"] == [risk["id"]]


# --- risks (shared table, free-text fields) ---------------------------------------------------


async def test_risks_keep_the_group_owner_and_running_note(
    session: AsyncSession, storage, sgd: Project
) -> None:
    c, _ = await member(storage, session, sgd)
    created = await c.post("/api/v1/risks", json=RISK)
    assert created.status_code == 201
    got = created.json()
    assert got["group_name"] == "Dữ liệu" and got["owner_text"] == "CĐT, LD DVN"
    assert got["note"] == "Đã họp ngày 02/10"
    patched = await c.patch(f"/api/v1/risks/{got['id']}", json={"note": "Đã chốt phương án"})
    assert patched.json()["note"] == "Đã chốt phương án"


# --- open decisions ---------------------------------------------------------------------------


async def test_decisions_are_numbered_decided_and_flagged_overdue(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-08")
    c, _ = await member(storage, session, sgd)
    old = {"title": "Chốt môi trường", "due_date": "2026-10-05"}
    first = (await c.post(f"{BASE}/decisions", json=old)).json()
    second = (await c.post(f"{BASE}/decisions", json={"title": "Chốt phạm vi"})).json()
    assert (first["no"], second["no"]) == (1, 2)
    assert first["overdue"] is True and second["overdue"] is False
    assert first["status"] == "pending"

    dup = await c.post(f"{BASE}/decisions", json={"title": "Trùng số", "no": 1})
    assert dup.status_code == 409

    close = {"status": "decided", "decision": "Dùng cloud"}
    decided = (await c.patch(f"{BASE}/decisions/{first['id']}", json=close)).json()
    assert decided["decided_on"] == "2026-10-08" and decided["overdue"] is False
    blank = await c.patch(f"{BASE}/decisions/{first['id']}", json={"title": None})
    assert blank.status_code == 422

    listing = (await c.get(f"{BASE}/decisions")).json()
    assert [d["no"] for d in listing] == [1, 2]
    overview = (await c.get(f"{BASE}/overview")).json()
    assert overview["pending_decisions"] == 1
    assert any(a["label"] == "Chờ CĐT" for a in overview["attention"])

    assert (await c.delete(f"{BASE}/decisions/{second['id']}")).status_code == 204
    assert (await c.get(f"{BASE}/decisions")).json()[0]["id"] == first["id"]


# --- alerts -----------------------------------------------------------------------------------


async def test_the_alert_engine_raises_delivery_alerts_for_this_project_only(
    session: AsyncSession, storage, sgd: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    freeze(monkeypatch, "2026-10-08")
    c, _ = await member(storage, session, sgd)
    ii2 = await task_id(c, "II.2")
    await c.patch(f"{BASE}/tasks/{ii2}", json={"pct": 50})  # past its end and still open
    await c.post("/api/v1/risks", json=RISK)  # 5 x 5
    await c.post(f"{BASE}/decisions", json={"title": "Chốt môi trường", "due_date": "2026-10-05"})
    other = await make_project(session, "CX", "procurement")

    now = datetime(2026, 10, 8, 3, 0, tzinfo=UTC)
    result = await run_alerts(session, now)
    assert result.created > 0

    alerts = (await session.execute(select(Alert))).scalars().all()
    assert {a.project_id for a in alerts} == {sgd.id}
    kinds = {a.alert_type for a in alerts}
    assert {"TASK_LATE", "WEEKLY_REPORT_MISSING", "DECISION_OVERDUE", "RISK_VERY_HIGH"} <= kinds
    assert "MILESTONE_SOON" in kinds  # M2 on 13 Oct is within a week
    late = next(a for a in alerts if a.alert_type == "TASK_LATE")
    assert late.severity == "warning" and "II.2" in late.title
    assert other.id not in {a.project_id for a in alerts}

    # solving the condition closes the alert on the next pass
    await c.patch(f"{BASE}/tasks/{ii2}", json={"status": "done"})
    await run_alerts(session, now)
    await session.refresh(late)
    assert late.status == "resolved"


async def test_the_alerts_page_of_the_project_lists_them(
    session: AsyncSession, storage, sgd: Project
) -> None:
    c, _ = await member(storage, session, sgd)
    await run_alerts(session, datetime(2026, 10, 8, 3, 0, tzinfo=UTC))
    page = (await c.get("/api/v1/alerts")).json()
    assert page["total"] > 0
    assert {a["alert_type"] for a in page["items"]} >= {"WEEKLY_REPORT_MISSING"}
