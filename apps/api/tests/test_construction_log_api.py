"""The construction log of a software-delivery project: one log per reporting week."""

from datetime import date

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Project
from tests.conftest import ALL_ROLES
from tests.test_delivery_api import member
from tests.test_multi_project import H, client_as, make_project, seat

BASE = "/api/v1/delivery/logs"
WEEK = "2026-09-25"


def body(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "report_date": "2026-10-02",
        "recipients": "Sở GD&ĐT TP.HCM (CĐT)",
        "reporter_org": "Liên danh DVN",
        "contract_ref": "Số 29/HĐKT-DVN ký ngày 21/9/2026",
        "coordinator": "Nguyễn Thị Thúy Hiệp",
        "environment_note": None,
        "overall_status": "Bám sát tiến độ",
        "key_results": "Đang phân tích yêu cầu",
        "issues": "Chưa có đầu mối",
        "coordination_requests": "- Ban hành Kế hoạch phối hợp khảo sát",
        "related_report": "BC tuần 25/9 – 01/10/2026",
        "entries": [
            {
                "entry_date": "2026-09-25",
                "phase_code": "I",
                "task_code": "I-1",
                "content": "Họp khởi động",
                "personnel": [],
                "note": "Cần CĐT xác nhận",
                "state": "done",
                "delay_days": None,
            },
            {
                "entry_date": "2026-09-28",
                "phase_code": "II",
                "task_code": "II-1",
                "content": "Lập kế hoạch khảo sát",
                "personnel": ["Nguyễn Duy Khánh"],
                "note": None,
                "state": "in_progress",
                "delay_days": 1,
            },
        ],
        "carryovers": [
            {
                "phase_code": "I",
                "task_code": "I-1",
                "title": "Kế hoạch chi tiết",
                "result_to_date": "Đã gửi, chờ CĐT xác nhận",
                "next_week": "Tiếp nhận ý kiến",
                "note": None,
            }
        ],
        "member_work": [
            {
                "member_name": "VietFuture",
                "item": "Mô-đun Quản lý mã định danh",
                "plan_ref": "5.4; 7.2",
                "personnel": ["Đỗ Ngọc Khánh"],
                "result": "Đang thực hiện",
                "next_plan": "Tiếp tục xây dựng",
                "issues_actions": None,
            }
        ],
    }
    base.update(over)
    return base


async def put(c: httpx.AsyncClient, week: str = WEEK, **over: object) -> httpx.Response:
    return await c.put(f"{BASE}/{week}", json=body(**over))


async def test_list_weeks_marks_the_weeks_with_a_log(storage, session: AsyncSession, sgd) -> None:
    c, _ = await member(storage, session, sgd)
    weeks = (await c.get(BASE)).json()
    assert weeks[0]["week_start"] == WEEK and weeks[0]["week_end"] == "2026-10-01"
    assert not any(w["has_log"] for w in weeks)

    assert (await put(c)).status_code == 200
    first = (await c.get(BASE)).json()[0]
    assert first["has_log"] is True
    assert first["entry_count"] == 2 and first["max_delay_days"] == 1
    assert first["has_report"] is False


async def test_save_then_read_back_in_order(storage, session: AsyncSession, sgd) -> None:
    c, _ = await member(storage, session, sgd)
    saved = (await put(c)).json()
    assert saved["week_start"] == WEEK and saved["id"]
    got = (await c.get(f"{BASE}/{WEEK}")).json()
    assert [e["entry_date"] for e in got["entries"]] == ["2026-09-25", "2026-09-28"]
    assert got["entries"][1]["personnel"] == ["Nguyễn Duy Khánh"]
    assert got["carryovers"][0]["title"] == "Kế hoạch chi tiết"
    assert got["member_work"][0]["personnel"] == ["Đỗ Ngọc Khánh"]
    assert got["environment_note"] is None


async def test_saving_again_replaces_the_children(storage, session: AsyncSession, sgd) -> None:
    c, _ = await member(storage, session, sgd)
    first = (await put(c)).json()
    entries = [body()["entries"][1]]  # type: ignore[index]
    second = await c.put(
        f"{BASE}/{WEEK}",
        json=body(entries=entries, carryovers=[], expected_updated_at=first["updated_at"]),
    )
    assert second.status_code == 200
    got = second.json()
    assert len(got["entries"]) == 1 and got["carryovers"] == []
    assert got["id"] == first["id"]


async def test_a_stale_copy_is_refused(storage, session: AsyncSession, sgd) -> None:
    c, _ = await member(storage, session, sgd)
    first = (await put(c)).json()
    ok = await c.put(
        f"{BASE}/{WEEK}", json=body(issues="Đã sửa", expected_updated_at=first["updated_at"])
    )
    assert ok.status_code == 200
    stale = await c.put(
        f"{BASE}/{WEEK}", json=body(issues="Ghi đè", expected_updated_at=first["updated_at"])
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "log_changed"
    assert (await c.get(f"{BASE}/{WEEK}")).json()["issues"] == "Đã sửa"


async def test_the_week_must_start_on_a_reporting_day(storage, session: AsyncSession, sgd) -> None:
    c, _ = await member(storage, session, sgd)
    assert (await put(c, "2026-09-26")).status_code == 422
    assert (await put(c, "2026-01-02")).status_code == 422


async def test_entries_must_fall_inside_the_week(storage, session: AsyncSession, sgd) -> None:
    c, _ = await member(storage, session, sgd)
    late = {**body()["entries"][0], "entry_date": "2026-10-02"}  # type: ignore[index]
    assert (await put(c, entries=[late])).status_code == 422


async def test_task_codes_must_exist_and_match_the_phase(
    storage, session: AsyncSession, sgd
) -> None:
    c, _ = await member(storage, session, sgd)
    entry = body()["entries"][0]  # type: ignore[index]
    unknown = await put(c, entries=[{**entry, "task_code": "Z-9"}])
    assert unknown.status_code == 422
    wrong_phase = await put(c, entries=[{**entry, "phase_code": "II"}])
    assert wrong_phase.status_code == 422
    no_task = await put(c, entries=[{**entry, "task_code": None}])
    assert no_task.status_code == 200


async def test_unknown_state_and_negative_delay_are_refused(
    storage, session: AsyncSession, sgd
) -> None:
    c, _ = await member(storage, session, sgd)
    entry = body()["entries"][0]  # type: ignore[index]
    assert (await put(c, entries=[{**entry, "state": "weird"}])).status_code == 422
    assert (await put(c, entries=[{**entry, "delay_days": -1}])).status_code == 422
    assert (await put(c, entries=[{**entry, "content": ""}])).status_code == 422


async def test_a_missing_log_is_404(storage, session: AsyncSession, sgd) -> None:
    c, _ = await member(storage, session, sgd)
    assert (await c.get(f"{BASE}/{WEEK}")).status_code == 404
    assert (await c.delete(f"{BASE}/{WEEK}")).status_code == 404


async def test_delete_removes_the_log_and_is_audited(storage, session: AsyncSession, sgd) -> None:
    c, _ = await member(storage, session, sgd)
    await put(c)
    assert (await c.delete(f"{BASE}/{WEEK}")).status_code == 204
    assert (await c.get(f"{BASE}/{WEEK}")).status_code == 404
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_type == "construction_log")))
        .scalars()
        .all()
    )
    assert [r.action for r in rows] == ["create", "delete"]
    assert all(r.project_id == sgd.id for r in rows)


async def test_the_matrix_decides_who_may_write(storage, session: AsyncSession, sgd) -> None:
    viewer, _ = await member(storage, session, sgd, "viewer", "v@example.test")
    cost, _ = await member(storage, session, sgd, "cost", "c@example.test")
    technical, _ = await member(storage, session, sgd, "technical", "t@example.test")
    assert (await viewer.get(BASE)).status_code == 200
    assert (await viewer.put(f"{BASE}/{WEEK}", json=body())).status_code == 403
    assert (await cost.put(f"{BASE}/{WEEK}", json=body())).status_code == 403
    assert (await technical.put(f"{BASE}/{WEEK}", json=body())).status_code == 200
    assert (await viewer.delete(f"{BASE}/{WEEK}")).status_code == 403


async def test_a_procurement_project_has_no_construction_log(
    storage, session: AsyncSession
) -> None:
    other = await make_project(session, "PROC")
    c, user = await client_as(storage, session, "p@example.test", "director")
    await seat(session, other, user, "director")
    c.headers[H] = str(other.id)
    assert (await c.get(BASE)).status_code == 404
    assert (await c.put(f"{BASE}/{WEEK}", json=body())).status_code == 404


async def test_logs_do_not_cross_projects(storage, session: AsyncSession, sgd: Project) -> None:
    c, _ = await member(storage, session, sgd)
    await put(c)
    second = await make_project(session, "SW2", "software_delivery")
    d, user = await client_as(storage, session, "o@example.test", "director")
    await seat(session, second, user, "director")
    d.headers[H] = str(second.id)
    assert (await d.get(f"{BASE}/{WEEK}")).status_code == 404


async def test_the_week_list_links_the_weekly_report(storage, session: AsyncSession, sgd) -> None:
    c, _ = await member(storage, session, sgd)
    report = {"status": "received", "submitted_on": "2026-10-02", "risk_ids": []}
    assert (await c.put(f"/api/v1/delivery/reports/{WEEK}", json=report)).status_code == 200
    first = (await c.get(BASE)).json()[0]
    assert first["has_report"] is True and first["has_log"] is False


async def test_task_history_lists_the_entries_of_one_task(
    storage, session: AsyncSession, sgd
) -> None:
    c, _ = await member(storage, session, sgd)
    await put(c)
    got = (await c.get("/api/v1/delivery/tasks/II-1/log-history")).json()
    assert [(h["entry_date"], h["delay_days"]) for h in got] == [("2026-09-28", 1)]
    assert got[0]["week_start"] == WEEK
    assert (await c.get("/api/v1/delivery/tasks/Z-9/log-history")).status_code == 404


async def test_saving_an_existing_log_needs_the_version_it_was_loaded_at(
    storage, session: AsyncSession, sgd
) -> None:
    c, _ = await member(storage, session, sgd)
    await put(c)
    again = await put(c, issues="Không gửi phiên bản")
    assert again.status_code == 409 and again.json()["error"]["code"] == "log_changed"
    assert (await c.get(f"{BASE}/{WEEK}")).json()["issues"] == "Chưa có đầu mối"


async def test_an_edit_to_the_text_of_a_line_is_audited(
    storage, session: AsyncSession, sgd
) -> None:
    c, _ = await member(storage, session, sgd)
    first = (await put(c)).json()
    entries = [dict(e) for e in body()["entries"]]  # type: ignore[union-attr]
    entries[0]["content"] = "Họp khởi động (đã sửa chữ)"
    second = await c.put(
        f"{BASE}/{WEEK}", json=body(entries=entries, expected_updated_at=first["updated_at"])
    )
    assert second.status_code == 200
    rows = (
        (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.entity_type == "construction_log")
                .order_by(AuditLog.ts)
            )
        )
        .scalars()
        .all()
    )
    assert [r.action for r in rows] == ["create", "update"]
    assert "entries_digest" in rows[1].changes


async def test_a_phase_outside_the_plan_is_refused(storage, session: AsyncSession, sgd) -> None:
    c, _ = await member(storage, session, sgd)
    entry = {**body()["entries"][0], "phase_code": "ZZ", "task_code": None}  # type: ignore[index]
    assert (await put(c, entries=[entry])).status_code == 422
    carry = {**body()["carryovers"][0], "phase_code": "ZZ", "task_code": None}  # type: ignore[index]
    assert (await put(c, carryovers=[carry])).status_code == 422


async def test_another_project_cannot_write_delete_or_read_history(
    storage, session: AsyncSession, sgd: Project
) -> None:
    c, _ = await member(storage, session, sgd)
    await put(c)
    second = await make_project(session, "SW2", "software_delivery")
    d, user = await client_as(storage, session, "o2@example.test", "director")
    await seat(session, second, user, "director")
    d.headers[H] = str(second.id)
    assert (await d.put(f"{BASE}/{WEEK}", json=body())).status_code == 422
    assert (await d.delete(f"{BASE}/{WEEK}")).status_code == 404
    assert (await d.get("/api/v1/delivery/tasks/II-1/log-history")).status_code == 404
    assert (await c.get(f"{BASE}/{WEEK}")).status_code == 200


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_every_role_follows_the_matrix(
    storage, session: AsyncSession, sgd, role: str
) -> None:
    c, _ = await member(storage, session, sgd, role, f"{role}@example.test")
    allowed = role in {"admin", "director", "procurement", "technical", "clerk"}
    assert (await c.get(BASE)).status_code == 200
    assert (await c.put(f"{BASE}/{WEEK}", json=body())).status_code == (200 if allowed else 403)


def test_the_first_reporting_day_is_a_friday() -> None:
    assert date.fromisoformat(WEEK).weekday() == 4
