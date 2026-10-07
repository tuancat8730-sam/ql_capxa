"""Delivery plan API: upload with preview, replace keeping tracking, step updates, access."""

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Package, PlanItem, PlanStep
from app.seed.project import seed_project
from tests.conftest import ALL_ROLES
from tests.plan_docs import build_plan_docx

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
UPLOADERS = {"admin", "director", "procurement"}
TRACKERS = {"admin", "director", "technical", "onsite"}
GHOST = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
async def packages(session: AsyncSession) -> dict[int, Package]:
    await seed_project(session)
    return {p.number: p for p in (await session.execute(select(Package))).scalars().all()}


def upload(content: bytes | None = None, name: str = "ke-hoach.docx") -> dict:
    return {"file": (name, content if content is not None else build_plan_docx(), DOCX)}


def url(package: Package, tail: str = "plan") -> str:
    return f"/api/v1/packages/{package.id}/{tail}"


async def import_plan(client, package: Package, content: bytes | None = None, *, commit=True):
    return await client.post(
        url(package, "plan/import"),
        params={"commit": str(commit).lower()},
        files=upload(content),
    )


# --- reading and previewing ----------------------------------------------------------------------


async def test_a_package_without_a_plan_returns_null(
    session: AsyncSession, packages: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    r = await c.get(url(packages[4]))
    assert r.status_code == 200 and r.json() is None
    assert (await c.get(f"/api/v1/packages/{GHOST}/plan")).status_code == 404


async def test_preview_reads_the_file_and_saves_nothing(
    session: AsyncSession, packages: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "procurement")
    r = await import_plan(c, packages[4], commit=False)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["dry_run"] is True and data["replaces_existing"] is False
    assert (len(data["items"]), len(data["steps"]), data["total_quantity"]) == (2, 5, 9)
    assert data["contract_end"] == "2026-11-13" and data["locations"] == 2
    assert data["steps"][0]["summary"].startswith("- Kiểm tra hàng tại kho")
    codes = {f["code"] for f in data["findings"]}
    assert {"AFTER_CONTRACT_END", "AFTER_IMPLEMENT_END", "NO_TIME"} <= codes
    assert (await c.get(url(packages[4]))).json() is None
    assert (await session.execute(select(PlanStep))).first() is None


async def test_commit_saves_the_plan_and_the_tab_shows_everything(
    session: AsyncSession, packages: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "procurement")
    saved = await import_plan(c, packages[4])
    assert saved.status_code == 200 and saved.json()["dry_run"] is False

    viewer = await make_client_for(session, "viewer")
    data = (await viewer.get(url(packages[4]))).json()
    assert data["package_id"] == str(packages[4].id) and data["source_file_name"] == "ke-hoach.docx"
    assert data["addressee"].startswith("Sở Khoa học") and data["total_quantity"] == 9
    assert [i["line_no"] for i in data["items"]] == [1, 2]
    assert data["items"][1]["assignments"][0] == {"org": "Công ty TNHH A", "quantity": 1}
    assert [s["step_no"] for s in data["steps"]] == [1, 2, 3, 4, 5]
    assert data["steps"][1]["estimated"] is True and data["steps"][4]["start_date"] is None
    assert data["progress"] == {"done": 0, "total": 5, "pct": 0.0}
    assert data["locations"][0]["label"] == "Kiểm tra đầu vào"
    assert any(f["code"] == "AFTER_CONTRACT_END" for f in data["findings"])


async def test_a_plan_belongs_to_its_package_only(
    session: AsyncSession, packages: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    await import_plan(c, packages[4])
    assert (await c.get(url(packages[5]))).json() is None
    await import_plan(
        c, packages[5], build_plan_docx(items=[["1", "Máy", "Bộ", "1", "A", ""]], total="1")
    )
    assert (await c.get(url(packages[4]))).json()["total_quantity"] == 9
    assert (await c.get(url(packages[5]))).json()["total_quantity"] == 1


# --- replacing -----------------------------------------------------------------------------------


async def test_replacing_keeps_tracking_of_steps_with_the_same_wording(
    session: AsyncSession, packages: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "director")
    await import_plan(c, packages[4])
    plan = (await c.get(url(packages[4]))).json()
    first, second = plan["steps"][0], plan["steps"][1]
    await c.patch(
        f"/api/v1/plan-steps/{first['id']}",
        json={"status": "done", "actual_end": "2026-11-04", "tracking_note": "Đã nhập kho"},
    )
    await c.patch(f"/api/v1/plan-steps/{second['id']}", json={"status": "in_progress"})

    # a revised document: step 1 unchanged, step 2 reworded, a new step added
    revised = build_plan_docx(
        steps=[
            (
                "BƯỚC 1: KIỂM TRA",
                ["1", "- Kiểm tra hàng tại kho.\n- Lập biên bản.", "30/10/2026", "Nhà thầu"],
            ),
            (
                "",
                ["2", "- Gửi thiết bị đi hiệu chuẩn (đã đổi nội dung).", "06/11/2026", "Nhà thầu"],
            ),
            ("", ["3", "- Việc mới.", "20/11/2026", "Sở"]),
        ]
    )
    preview = (await import_plan(c, packages[4], revised, commit=False)).json()
    assert (
        preview["replaces_existing"] is True and preview["kept_tracking"] == 1
    )  # only step 1 keeps its wording
    assert [s["keeps_tracking"] for s in preview["steps"]] == [True, False, False]

    done = await import_plan(c, packages[4], revised)
    assert done.json()["plan_id"] == plan["id"]  # same plan, replaced in place
    new = (await c.get(url(packages[4]))).json()
    assert [s["step_no"] for s in new["steps"]] == [1, 2, 3]
    kept, reworded, added = new["steps"]
    assert (kept["status"], kept["actual_end"], kept["tracking_note"]) == (
        "done",
        "2026-11-04",
        "Đã nhập kho",
    )
    assert (reworded["status"], added["status"]) == ("not_started", "not_started")
    assert new["progress"]["done"] == 1 and len(new["items"]) == 2
    assert (await session.execute(select(PlanItem))).scalars().all().__len__() == 2  # no leftovers


async def test_importing_twice_the_same_file_changes_nothing_visible(
    session: AsyncSession, packages: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    await import_plan(c, packages[4])
    step = (await c.get(url(packages[4]))).json()["steps"][2]
    await c.patch(
        f"/api/v1/plan-steps/{step['id']}", json={"status": "blocked", "tracking_note": "Chờ"}
    )
    await import_plan(c, packages[4])
    again = (await c.get(url(packages[4]))).json()["steps"][2]
    assert (again["status"], again["tracking_note"]) == ("blocked", "Chờ")


# --- step tracking -------------------------------------------------------------------------------


async def test_status_changes_fill_the_actual_dates(
    session: AsyncSession, packages: dict[int, Package], make_client_for, monkeypatch
) -> None:
    monkeypatch.setattr("app.routers.plans.today_local", lambda: date(2026, 11, 9))
    c = await make_client_for(session, "technical")
    admin = await make_client_for(session, "admin")
    await import_plan(admin, packages[4])
    steps = (await c.get(url(packages[4]))).json()["steps"]

    started = (
        await c.patch(f"/api/v1/plan-steps/{steps[0]['id']}", json={"status": "in_progress"})
    ).json()
    assert (started["status"], started["actual_start"], started["actual_end"]) == (
        "in_progress",
        "2026-11-09",
        None,
    )
    finished = (
        await c.patch(f"/api/v1/plan-steps/{steps[0]['id']}", json={"status": "done"})
    ).json()
    assert (finished["actual_start"], finished["actual_end"]) == ("2026-11-09", "2026-11-09")
    # done straight away: both dates are today
    direct = (await c.patch(f"/api/v1/plan-steps/{steps[1]['id']}", json={"status": "done"})).json()
    assert (direct["actual_start"], direct["actual_end"]) == ("2026-11-09", "2026-11-09")
    plan = (await c.get(url(packages[4]))).json()
    assert plan["progress"] == {"done": 2, "total": 5, "pct": 40.0}


async def test_late_steps_are_marked_but_steps_without_time_never_are(
    session: AsyncSession, packages: dict[int, Package], make_client_for, monkeypatch
) -> None:
    monkeypatch.setattr("app.routers.plans.today_local", lambda: date(2026, 11, 20))
    c = await make_client_for(session, "admin")
    await import_plan(c, packages[4])
    steps = (await c.get(url(packages[4]))).json()["steps"]
    by_no = {s["step_no"]: s for s in steps}
    assert by_no[1]["effective_status"] == "delayed" and by_no[1]["days_late"] == 15  # ended 05/11
    assert by_no[3]["effective_status"] == "delayed" and by_no[3]["days_late"] == 5  # ended 15/11
    assert by_no[4]["effective_status"] == "not_started"  # ends 27/11: still ahead
    assert by_no[5]["effective_status"] == "not_started" and by_no[5]["days_late"] is None

    await c.patch(f"/api/v1/plan-steps/{by_no[1]['id']}", json={"status": "done"})
    done = {s["step_no"]: s for s in (await c.get(url(packages[4]))).json()["steps"]}
    assert done[1]["effective_status"] == "done" and done[1]["days_late"] is None


async def test_step_update_validation(
    session: AsyncSession, packages: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    await import_plan(c, packages[4])
    step = (await c.get(url(packages[4]))).json()["steps"][0]
    path = f"/api/v1/plan-steps/{step['id']}"
    assert (await c.patch(path, json={"status": "finished"})).status_code == 422
    backwards = {"actual_start": "2026-11-10", "actual_end": "2026-11-01"}
    r = await c.patch(path, json=backwards)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    assert (
        await c.patch(f"/api/v1/plan-steps/{GHOST}", json={"status": "done"})
    ).status_code == 404
    ok = await c.patch(path, json={"tracking_note": "  Ghi chú  "})
    assert ok.json()["tracking_note"] == "Ghi chú"
    assert (await c.patch(path, json={"tracking_note": "x" * 2001})).status_code == 422


# --- bad files -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "content", "fragment"),
    [
        ("ke-hoach.pdf", b"%PDF-1.4", "Chỉ nhận tệp Word"),
        ("ke-hoach.docx", b"not a word file", "không phải văn bản Word"),
        ("ke-hoach.docx", b"PK\x03\x04broken", "Không đọc được"),
    ],
)
async def test_unreadable_files_are_refused_and_nothing_is_saved(
    name: str,
    content: bytes,
    fragment: str,
    session: AsyncSession,
    packages: dict[int, Package],
    make_client_for,
) -> None:
    c = await make_client_for(session, "admin")
    r = await c.post(
        url(packages[4], "plan/import"), params={"commit": "true"}, files=upload(content, name)
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_plan_file"
    assert fragment in r.json()["error"]["message"]
    assert (await c.get(url(packages[4]))).json() is None


async def test_a_missing_file_is_a_validation_error(
    session: AsyncSession, packages: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    assert (await c.post(url(packages[4], "plan/import"))).status_code == 422


# --- delete and audit ----------------------------------------------------------------------------


async def test_delete_removes_the_plan_and_everything_under_it(
    session: AsyncSession, packages: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "director")
    assert (await c.delete(url(packages[4]))).status_code == 404  # nothing to delete yet
    await import_plan(c, packages[4])
    assert (await c.delete(url(packages[4]))).status_code == 204
    assert (await c.get(url(packages[4]))).json() is None
    assert (await session.execute(select(PlanStep))).first() is None
    assert (await session.execute(select(PlanItem))).first() is None


async def test_uploads_and_step_updates_are_audited(
    session: AsyncSession, packages: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    await import_plan(c, packages[4])
    step = (await c.get(url(packages[4]))).json()["steps"][0]
    await c.patch(f"/api/v1/plan-steps/{step['id']}", json={"status": "in_progress"})
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_type.like("%plan%"))))
        .scalars()
        .all()
    )
    by_type = {r.entity_type: r for r in rows}
    assert by_type["package_plan"].action == "create"
    assert (
        by_type["package_plan"].changes["steps"] == 5
        and by_type["package_plan"].changes["file"] == "ke-hoach.docx"
    )
    assert by_type["plan_step"].changes["status"] == {
        "before": "not_started",
        "after": "in_progress",
    }


# --- access --------------------------------------------------------------------------------------


async def test_role_matrix(
    session: AsyncSession, packages: dict[int, Package], make_client_for, client
) -> None:
    admin = await make_client_for(session, "admin")
    await import_plan(admin, packages[4])
    step_id = (await admin.get(url(packages[4]))).json()["steps"][0]["id"]
    assert (await client.get(url(packages[4]))).status_code == 401

    for role in ALL_ROLES:
        c = await make_client_for(session, role)
        assert (await c.get(url(packages[4]))).status_code == 200, role
        r = await import_plan(c, packages[5], commit=False)
        assert r.status_code == (200 if role in UPLOADERS else 403), ("import", role)
        t = await c.patch(f"/api/v1/plan-steps/{step_id}", json={"tracking_note": role})
        assert t.status_code == (200 if role in TRACKERS else 403), ("step", role)
    for role in sorted(set(ALL_ROLES) - UPLOADERS):
        c = await make_client_for(session, role)
        assert (await c.delete(url(packages[4]))).status_code == 403, ("delete", role)
