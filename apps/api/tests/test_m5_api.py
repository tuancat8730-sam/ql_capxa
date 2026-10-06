"""M5: stage plans, tasks, daily logs, timeline (SPEC 3.13-3.15, 4.4, 15.7)."""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Package, ProgressLog, StagePlan
from app.seed.progress import seed_progress
from app.seed.project import seed_project
from app.services.storage import MemoryStorage
from tests.conftest import ALL_ROLES, make_user
from tests.test_documents_api import upload

TODAY = date(2026, 10, 6)
GHOST = "00000000-0000-0000-0000-000000000000"
READERS = {"admin", "director", "procurement", "technical", "cost", "onsite", "viewer"}  # not clerk
WRITERS = {"admin", "director", "technical", "onsite"}


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.progress.today_local", lambda: TODAY)


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[int, Package]:
    await seed_project(session)
    await seed_progress(session)
    return {p.number: p for p in (await session.execute(select(Package))).scalars().all()}


async def stages(c, package: Package) -> dict:
    resp = await c.get(f"/api/v1/packages/{package.id}/stages")
    assert resp.status_code == 200, resp.text
    return resp.json()


def stage(data: dict, code: str) -> dict:
    return next(s for s in data["stages"] if s["stage_code"] == code)


# --- stage plans -----------------------------------------------------------------------------


async def test_every_package_has_five_standard_stages_with_default_weights(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    for package in seeded.values():
        data = await stages(c, package)
        assert [s["stage_code"] for s in data["stages"]] == [
            "S1_START",
            "S2_SELECTION",
            "S3_EXECUTION",
            "S4_ACCEPTANCE",
            "S5_PAYMENT_SETTLEMENT",
        ]
        assert [s["weight"] for s in data["stages"]] == [10, 20, 40, 20, 10]


async def test_seed_uses_only_facts_from_the_contracts(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    p4 = await stages(c, seeded[4])  # contract signed 14/09/2026, end text 13/11/2026
    assert stage(p4, "S2_SELECTION")["status"] == "done"
    s3 = stage(p4, "S3_EXECUTION")
    assert (s3["planned_start"], s3["planned_end"]) == ("2026-09-14", "2026-11-13")
    assert stage(p4, "S1_START")["status"] == "not_started"  # unknown: left for the team
    assert (p4["package_progress"], p4["current_stage"]) == (
        20,
        "S1_START",
    )  # 20% x 100 / 100, S1 unfinished

    p3 = await stages(c, seeded[3])  # still bidding, no contract
    assert stage(p3, "S2_SELECTION")["status"] == "in_progress"
    assert (p3["package_progress"], stage(p3, "S3_EXECUTION")["planned_end"]) == (0, None)


async def test_package_progress_is_stored_on_the_package(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    row = (await c.get("/api/v1/packages")).json()["items"]
    assert {p["number"]: p["progress_pct"] for p in row}[4] == 20


async def test_stages_are_created_lazily_for_packages_without_them(
    session: AsyncSession, make_client_for
) -> None:
    await seed_project(session)  # no seed_progress
    c = await make_client_for(session, "viewer")
    package = (await session.execute(select(Package).where(Package.number == 6))).scalar_one()
    data = await stages(c, package)
    assert len(data["stages"]) == 5 and data["package_progress"] == 0
    assert (await stages(c, package))["stages"][0]["id"] == data["stages"][0]["id"]  # stable ids


async def test_updating_progress_recomputes_the_weighted_package_progress(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    data = await stages(c, seeded[4])
    s3 = stage(data, "S3_EXECUTION")
    resp = await c.patch(f"/api/v1/stage-plans/{s3['id']}", json={"progress_pct": 50})
    assert resp.status_code == 200
    body = resp.json()
    assert (
        body["stage"]["status"] == "in_progress" and body["stage"]["actual_start"] == "2026-10-06"
    )
    assert body["package_progress"] == 40  # (20 x 100 + 40 x 50) / 100
    done = await c.patch(f"/api/v1/stage-plans/{s3['id']}", json={"status": "done"})
    d = done.json()
    assert (d["stage"]["progress_pct"], d["stage"]["actual_end"]) == (100, "2026-10-06")
    assert d["package_progress"] == 60 and d["current_stage"] == "S1_START"
    s1 = stage(data, "S1_START")
    await c.patch(f"/api/v1/stage-plans/{s1['id']}", json={"status": "done"})
    after = (await c.patch(f"/api/v1/stage-plans/{s1['id']}", json={"notes": "x"})).json()
    assert after["current_stage"] == "S4_ACCEPTANCE" and after["package_progress"] == 70


async def test_full_progress_without_a_status_marks_the_stage_done(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    s4 = stage(await stages(c, seeded[4]), "S4_ACCEPTANCE")
    body = (await c.patch(f"/api/v1/stage-plans/{s4['id']}", json={"progress_pct": 100})).json()
    assert body["stage"]["status"] == "done" and body["stage"]["actual_end"] == "2026-10-06"


async def test_late_stages_show_as_delayed_but_keep_their_stored_status(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    s3 = stage(await stages(c, seeded[1]), "S3_EXECUTION")  # planned end 18/09/2026 < today
    assert (s3["status"], s3["effective_status"]) == ("not_started", "delayed")
    s3_pkg6 = stage(await stages(c, seeded[6]), "S3_EXECUTION")  # ends 22/01/2027
    assert s3_pkg6["effective_status"] == "not_started"


async def test_gantt_drag_changes_the_dates_and_the_timeline_follows(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "director")
    s3 = stage(await stages(c, seeded[4]), "S3_EXECUTION")
    moved = await c.patch(
        f"/api/v1/stage-plans/{s3['id']}",
        json={"planned_start": "2026-09-20", "planned_end": "2026-12-01"},
    )
    assert moved.status_code == 200
    tl = (await c.get("/api/v1/dashboard/timeline")).json()
    pkg = next(p for p in tl["packages"] if p["number"] == 4)
    bar = next(s for s in pkg["stages"] if s["stage_code"] == "S3_EXECUTION")
    assert (bar["planned_start"], bar["planned_end"]) == ("2026-09-20", "2026-12-01")
    assert tl["range_end"] == "2027-01-22" and tl["range_start"] == "2026-07-20"


@pytest.mark.parametrize(
    "payload",
    [
        {"planned_start": "2026-02-01", "planned_end": "2026-01-01"},
        {"actual_start": "2026-02-01", "actual_end": "2026-01-01"},
        {"progress_pct": 101},
        {"progress_pct": -1},
        {"progress_pct": None},
        {"weight": -5},
        {"name": None},
        {"status": "delayed"},  # derived, never stored
        {"status": "bogus"},
        {"planned_end": "01/01/2026"},
    ],
)
async def test_stage_validation_422(
    payload: dict, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    s3 = stage(await stages(c, seeded[4]), "S3_EXECUTION")
    assert (await c.patch(f"/api/v1/stage-plans/{s3['id']}", json=payload)).status_code == 422
    after = stage(await stages(c, seeded[4]), "S3_EXECUTION")
    assert (after["planned_start"], after["progress_pct"], after["weight"]) == (
        s3["planned_start"],
        s3["progress_pct"],
        s3["weight"],
    )  # nothing was half-applied


async def test_stage_404s_and_audit(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    assert (await c.patch(f"/api/v1/stage-plans/{GHOST}", json={"notes": "x"})).status_code == 404
    assert (await c.get(f"/api/v1/packages/{GHOST}/stages")).status_code == 404
    s3 = stage(await stages(c, seeded[4]), "S3_EXECUTION")
    await c.patch(f"/api/v1/stage-plans/{s3['id']}", json={"progress_pct": 10})
    row = (
        await session.execute(select(AuditLog).where(AuditLog.entity_type == "stage_plan"))
    ).scalar_one()
    assert row.changes["progress_pct"] == {"before": "0.00", "after": "10"} or row.changes[
        "progress_pct"
    ]["after"] in {"10", "10.00"}


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_progress_permissions_follow_the_matrix(
    role: str, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, role)
    pid = seeded[4].id
    assert (await c.get(f"/api/v1/packages/{pid}/stages")).status_code == (
        200 if role in READERS else 403
    )
    assert (await c.get(f"/api/v1/packages/{pid}/tasks")).status_code == (
        200 if role in READERS else 403
    )
    assert (await c.get(f"/api/v1/packages/{pid}/progress-logs")).status_code == (
        200 if role in READERS else 403
    )
    s3 = (
        await session.execute(
            select(StagePlan).where(
                StagePlan.package_id == pid, StagePlan.stage_code == "S3_EXECUTION"
            )
        )
    ).scalar_one()
    patch = await c.patch(f"/api/v1/stage-plans/{s3.id}", json={"notes": "n"})
    assert patch.status_code == (200 if role in WRITERS else 403)
    task = await c.post(f"/api/v1/packages/{pid}/tasks", json={"title": "Việc"})
    assert task.status_code == (201 if role in WRITERS else 403)
    log = await c.post(
        f"/api/v1/packages/{pid}/progress-logs", json={"log_date": "2026-10-05", "progress_pct": 10}
    )
    assert log.status_code == (201 if role in WRITERS else 403)


# --- tasks -----------------------------------------------------------------------------------


async def mk_task(c, package: Package, **body) -> dict:
    resp = await c.post(f"/api/v1/packages/{package.id}/tasks", json={"title": "Việc", **body})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_task_crud_defaults_and_filters(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    s3 = stage(await stages(c, seeded[4]), "S3_EXECUTION")
    t = await mk_task(
        c,
        seeded[4],
        title="Lắp đặt",
        stage_plan_id=s3["id"],
        priority="high",
        planned_end="2026-10-30",
    )
    assert (t["status"], t["priority"], t["weight"], t["depends_on"]) == ("todo", "high", 1, [])
    await mk_task(c, seeded[4], title="Khác")
    base = f"/api/v1/packages/{seeded[4].id}/tasks"
    assert len((await c.get(base)).json()) == 2
    assert [x["title"] for x in (await c.get(base, params={"stage_plan_id": s3["id"]})).json()] == [
        "Lắp đặt"
    ]
    assert len((await c.get(base, params={"status": "done"})).json()) == 0
    up = await c.patch(f"/api/v1/tasks/{t['id']}", json={"status": "doing", "notes": "Đang làm"})
    assert (up.json()["status"], up.json()["notes"]) == ("doing", "Đang làm")
    assert (await c.delete(f"/api/v1/tasks/{t['id']}")).status_code == 204
    assert (await c.delete(f"/api/v1/tasks/{t['id']}")).status_code == 404
    assert len((await c.get(base)).json()) == 1


async def test_finishing_every_task_of_a_stage_suggests_closing_it(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    s3 = stage(await stages(c, seeded[4]), "S3_EXECUTION")
    a = await mk_task(c, seeded[4], title="A", stage_plan_id=s3["id"])
    b = await mk_task(c, seeded[4], title="B", stage_plan_id=s3["id"])
    first = (await c.patch(f"/api/v1/tasks/{a['id']}", json={"status": "done"})).json()
    assert first["stage_all_done"] is False and first["actual_end"] == "2026-10-06"
    second = (await c.patch(f"/api/v1/tasks/{b['id']}", json={"status": "done"})).json()
    assert (
        second["stage_all_done"] is True
    )  # the user then confirms: the API never closes it silently
    counts = stage(await stages(c, seeded[4]), "S3_EXECUTION")
    assert (counts["task_count"], counts["tasks_done"], counts["status"]) == (2, 2, "not_started")


async def test_task_dependencies_and_cycles(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    a = await mk_task(c, seeded[4], title="A")
    b = await mk_task(c, seeded[4], title="B", depends_on=[a["id"]])
    d = await mk_task(c, seeded[4], title="C", depends_on=[b["id"]])
    assert b["depends_on"] == [a["id"]]
    assert (
        await c.patch(f"/api/v1/tasks/{a['id']}", json={"depends_on": [d["id"]]})
    ).status_code == 422  # loop
    assert (
        await c.patch(f"/api/v1/tasks/{a['id']}", json={"depends_on": [a["id"]]})
    ).status_code == 422  # itself
    assert (
        await c.patch(f"/api/v1/tasks/{a['id']}", json={"depends_on": [GHOST]})
    ).status_code == 422
    other = await mk_task(c, seeded[6], title="Gói khác")
    assert (
        await c.patch(f"/api/v1/tasks/{b['id']}", json={"depends_on": [other["id"]]})
    ).status_code == 422
    # deleting a prerequisite releases its dependants
    assert (await c.delete(f"/api/v1/tasks/{a['id']}")).status_code == 204
    after = {t["title"]: t for t in (await c.get(f"/api/v1/packages/{seeded[4].id}/tasks")).json()}
    assert after["B"]["depends_on"] == []


async def test_task_validation_422(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    url = f"/api/v1/packages/{seeded[4].id}/tasks"
    inactive = await make_user(session, "onsite", email="gone@example.test", is_active=False)
    other_stage = stage(await stages(c, seeded[6]), "S3_EXECUTION")
    for payload in (
        {},
        {"title": ""},
        {"title": "x", "status": "finished"},
        {"title": "x", "priority": "urgent"},
        {"title": "x", "weight": -1},
        {"title": "x", "planned_start": "2026-02-01", "planned_end": "2026-01-01"},
        {"title": "x", "stage_plan_id": other_stage["id"]},
        {"title": "x", "stage_plan_id": GHOST},
        {"title": "x", "assignee_id": str(inactive.id)},
        {"title": "x", "assignee_id": GHOST},
        {"title": None},
    ):
        assert (await c.post(url, json=payload)).status_code == 422, payload
    t = await mk_task(c, seeded[4])
    assert (await c.patch(f"/api/v1/tasks/{t['id']}", json={"title": None})).status_code == 422
    assert (await c.patch(f"/api/v1/tasks/{GHOST}", json={"title": "x"})).status_code == 404
    assert (await c.get(f"/api/v1/packages/{GHOST}/tasks")).status_code == 404
    assigned = await make_client_for(session, "onsite")  # an active user can be assigned
    me = (await assigned.get("/api/v1/auth/me")).json()
    ok = await c.patch(f"/api/v1/tasks/{t['id']}", json={"assignee_id": me["id"]})
    assert ok.json()["assignee_id"] == me["id"]
    assert len((await c.get(url, params={"assignee_id": me["id"]})).json()) == 1


# --- daily logs ------------------------------------------------------------------------------


def log_body(**over) -> dict:
    return {
        "log_date": "2026-10-05",
        "progress_pct": 35,
        "summary": "Lắp 3 xã",
        "workers": 12,
        "weather": "Nắng",
        **over,
    }


async def test_create_log_and_list_newest_first(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "onsite")
    url = f"/api/v1/packages/{seeded[4].id}/progress-logs"
    first = await c.post(url, json=log_body(log_date="2026-10-03", progress_pct=20))
    second = await c.post(url, json=log_body())
    assert first.status_code == second.status_code == 201
    body = second.json()
    assert (body["workers"], body["weather"], body["author_name"]) == (12, "Nắng", "User onsite")
    page = (await c.get(url)).json()
    assert [r["log_date"] for r in page["items"]] == ["2026-10-05", "2026-10-03"] and page[
        "total"
    ] == 2
    assert (await c.get(url, params={"date_from": "2026-10-04"})).json()["total"] == 1
    assert (await c.get(url, params={"date_to": "2026-10-04"})).json()["total"] == 1
    assert (await c.get(url, params={"page_size": 101})).status_code == 422


async def test_idempotency_key_makes_a_retried_send_return_the_first_result(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "onsite")
    url = f"/api/v1/packages/{seeded[4].id}/progress-logs"
    key = {"Idempotency-Key": str(uuid.uuid4())}
    first = await c.post(url, json=log_body(), headers=key)
    again = await c.post(url, json=log_body(summary="đã sửa trong khi chờ"), headers=key)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["id"] == first.json()["id"] and again.json()["summary"] == "Lắp 3 xã"
    count = len((await session.execute(select(ProgressLog))).scalars().all())
    assert count == 1
    # the body's client_id works the same way
    cid = {"client_id": str(uuid.uuid4())}
    one = await c.post(url, json=log_body(log_date="2026-10-04", **cid))
    two = await c.post(url, json=log_body(log_date="2026-10-04", **cid))
    assert (one.status_code, two.status_code, one.json()["id"] == two.json()["id"]) == (
        201,
        200,
        True,
    )


async def test_key_cannot_be_replayed_by_another_user_or_package(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    onsite = await make_client_for(session, "onsite")
    tech = await make_client_for(session, "technical")
    key = {"Idempotency-Key": str(uuid.uuid4())}
    await onsite.post(
        f"/api/v1/packages/{seeded[4].id}/progress-logs", json=log_body(), headers=key
    )
    assert (
        await tech.post(
            f"/api/v1/packages/{seeded[4].id}/progress-logs", json=log_body(), headers=key
        )
    ).status_code == 409
    assert (
        await onsite.post(
            f"/api/v1/packages/{seeded[6].id}/progress-logs", json=log_body(), headers=key
        )
    ).status_code == 409


async def test_one_log_per_package_day_and_author(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    onsite = await make_client_for(session, "onsite")
    tech = await make_client_for(session, "technical")
    url = f"/api/v1/packages/{seeded[4].id}/progress-logs"
    first = (await onsite.post(url, json=log_body())).json()
    dup = await onsite.post(url, json=log_body(summary="khác"))
    assert dup.status_code == 409
    err = dup.json()["error"]
    assert (
        err["code"] == "log_exists" and err["details"]["id"] == first["id"]
    )  # the client can offer merge/overwrite
    assert (
        await tech.post(url, json=log_body())
    ).status_code == 201  # another author, same day: fine
    assert (
        await onsite.post(f"/api/v1/packages/{seeded[6].id}/progress-logs", json=log_body())
    ).status_code == 201


async def test_log_validation_422(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "onsite")
    url = f"/api/v1/packages/{seeded[4].id}/progress-logs"
    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    assert (
        await c.post(url, json=log_body(log_date=tomorrow))
    ).status_code == 201  # timezone tolerance
    far = (TODAY + timedelta(days=2)).isoformat()
    for payload in (
        {},
        {"log_date": "2026-10-01"},
        log_body(progress_pct=101),
        log_body(progress_pct=-1),
        log_body(log_date=far),
        log_body(log_date="05/10/2026"),
        log_body(workers=-1),
        log_body(weather="x" * 101),
        log_body(attachments=[GHOST]),
        log_body(client_id="short"),
    ):
        assert (await c.post(url, json=payload)).status_code == 422, payload
    bad_key = await c.post(
        url, json=log_body(log_date="2026-10-02"), headers={"Idempotency-Key": "abc"}
    )
    assert bad_key.status_code == 422
    assert (
        await c.post(f"/api/v1/packages/{GHOST}/progress-logs", json=log_body())
    ).status_code == 404


async def test_attachments_must_be_documents_of_the_same_package(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    onsite = await make_client_for(session, "onsite")
    photo = (
        await upload(
            onsite, storage, seeded[4], doc_type="photo", title="Ảnh hiện trường", name="a.pdf"
        )
    ).json()
    elsewhere = (
        await upload(
            onsite, storage, seeded[6], doc_type="photo", title="Ảnh gói khác", name="b.pdf"
        )
    ).json()
    url = f"/api/v1/packages/{seeded[4].id}/progress-logs"
    ok = await onsite.post(url, json=log_body(attachments=[photo["id"]]))
    assert ok.status_code == 201 and ok.json()["attachments"] == [photo["id"]]
    bad = await onsite.post(
        url, json=log_body(log_date="2026-10-04", attachments=[elsewhere["id"]])
    )
    assert bad.status_code == 422


async def test_only_the_author_or_a_manager_may_edit_a_log(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    onsite = await make_client_for(session, "onsite")
    tech = await make_client_for(session, "technical")
    admin = await make_client_for(session, "admin")
    log = (
        await onsite.post(f"/api/v1/packages/{seeded[4].id}/progress-logs", json=log_body())
    ).json()
    url = f"/api/v1/progress-logs/{log['id']}"
    assert (await onsite.patch(url, json={"progress_pct": 40})).json()["progress_pct"] == 40
    assert (await tech.patch(url, json={"progress_pct": 50})).status_code == 403
    assert (await admin.patch(url, json={"summary": "đã duyệt"})).status_code == 200
    assert (await onsite.patch(url, json={"progress_pct": None})).status_code == 422
    assert (await onsite.patch(url, json={"progress_pct": 101})).status_code == 422
    assert (
        await onsite.patch(f"/api/v1/progress-logs/{GHOST}", json={"summary": "x"})
    ).status_code == 404
    rows = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "progress_log", AuditLog.action == "update"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2


# --- timeline --------------------------------------------------------------------------------


async def test_timeline_covers_all_packages_with_contract_bars(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    tl = (await c.get("/api/v1/dashboard/timeline")).json()
    assert tl["today"] == "2026-10-06" and [p["number"] for p in tl["packages"]] == list(
        range(1, 9)
    )
    assert all(len(p["stages"]) == 5 for p in tl["packages"])
    by = {p["number"]: p for p in tl["packages"]}
    assert by[3]["contract"] is None
    assert (
        by[6]["contract"]["end"] == "2027-01-22" and by[6]["contract"]["end_date_override"] is True
    )
    assert by[4]["contract"] == {
        "contract_no": "71",
        "start": "2026-09-14",
        "end": "2026-11-13",
        "end_date_override": False,
        "extended_end_date": None,
    }
    assert tl["range_start"] == "2026-07-20" and tl["range_end"] == "2027-01-22"


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_timeline_permissions_follow_the_package_matrix(
    role: str, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, role)
    assert (
        await c.get("/api/v1/dashboard/timeline")
    ).status_code == 200  # every role reads packages
