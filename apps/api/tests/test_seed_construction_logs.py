"""The two weekly construction logs copied from the contractor's Word files."""

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ConstructionLog,
    ConstructionLogCarryover,
    ConstructionLogEntry,
    ConstructionLogMemberWork,
    Project,
    WbsTask,
)
from app.seed import sgd_hcm_logs_data as data
from app.seed.sgd_hcm import seed_sgd_hcm
from app.seed.sgd_hcm_logs import apply_logs, seed_sgd_hcm_logs

WEEK_1, WEEK_3 = date(2026, 9, 25), date(2026, 10, 9)


async def count(session: AsyncSession, model: type, project: Project | None = None) -> int:
    query = select(func.count()).select_from(model)
    if project is not None and model is ConstructionLog:
        query = query.where(ConstructionLog.project_id == project.id)
    return (await session.execute(query)).scalar_one()


async def log_of(session: AsyncSession, week: date) -> ConstructionLog:
    from app.services.construction_log import load_log

    project = (await session.execute(select(Project).where(Project.code == "SGD-HCM"))).scalar_one()
    log = await load_log(session, project.id, week)
    assert log is not None
    return log


async def test_the_full_seed_loads_both_weeks(session: AsyncSession, sgd_loaded: Project) -> None:
    assert await count(session, ConstructionLog, sgd_loaded) == 2
    one, three = await log_of(session, WEEK_1), await log_of(session, WEEK_3)
    assert (len(one.entries), len(one.carryovers), len(one.member_work)) == (11, 6, 0)
    assert (len(three.entries), len(three.carryovers), len(three.member_work)) == (16, 12, 2)
    assert one.report_date == date(2026, 10, 2) and three.report_date == date(2026, 10, 16)
    assert one.environment_note is None and three.environment_note is not None


async def test_the_plan_only_seed_leaves_the_logs_out(session: AsyncSession, sgd: Project) -> None:
    assert await count(session, ConstructionLog, sgd) == 0


async def test_entries_stay_inside_their_week_and_in_date_order(
    session: AsyncSession, sgd_loaded: Project
) -> None:
    for week in (WEEK_1, WEEK_3):
        log = await log_of(session, week)
        days = [e.entry_date for e in log.entries]
        assert days == sorted(days)
        assert all(week <= d <= week + timedelta(days=6) for d in days)
        # Saturday and Sunday carry no line in the source files
        assert all(d.weekday() < 5 for d in days)


async def test_task_codes_exist_and_sit_under_their_phase(
    session: AsyncSession, sgd_loaded: Project
) -> None:
    phase_of = {
        t.code: t.phase_code
        for t in (await session.execute(select(WbsTask).where(WbsTask.project_id == sgd_loaded.id)))
        .scalars()
        .all()
    }
    for week in (WEEK_1, WEEK_3):
        log = await log_of(session, week)
        for line in [*log.entries, *log.carryovers]:
            if line.task_code is not None:
                assert phase_of[line.task_code] == line.phase_code


async def test_the_delays_written_in_the_files_are_kept(
    session: AsyncSession, sgd_loaded: Project
) -> None:
    one, three = await log_of(session, WEEK_1), await log_of(session, WEEK_3)
    assert [e.delay_days for e in one.entries if e.delay_days] == [1]
    assert sorted(e.delay_days for e in three.entries if e.delay_days) == [2, 6, 8]


async def test_personnel_is_a_list_of_names(session: AsyncSession, sgd_loaded: Project) -> None:
    three = await log_of(session, WEEK_3)
    build = [e for e in three.entries if e.entry_date == date(2026, 10, 15) and e.task_code is None]
    assert build[0].personnel == [
        "Nguyễn Thành Tân",
        "Đỗ Thị Thu Hường",
        "Đỗ Ngọc Khánh",
        "Nguyễn Thị Thúy Hiệp",
    ]
    assert three.member_work[0].member_name == "VietFuture"
    assert len(three.member_work[1].personnel) == 2


async def test_running_the_seed_twice_adds_nothing(
    session: AsyncSession, sgd_loaded: Project
) -> None:
    await seed_sgd_hcm_logs(session)
    await seed_sgd_hcm(session)
    assert await count(session, ConstructionLog, sgd_loaded) == 2
    assert await count(session, ConstructionLogEntry) == 27
    assert await count(session, ConstructionLogCarryover) == 18
    assert await count(session, ConstructionLogMemberWork) == 2


async def test_a_log_edited_in_the_app_is_not_overwritten(
    session: AsyncSession, sgd_loaded: Project
) -> None:
    await session.execute(
        update(ConstructionLog)
        .where(ConstructionLog.week_start == WEEK_1)
        .values(issues="Đã sửa trong ứng dụng")
    )
    await session.commit()
    await seed_sgd_hcm_logs(session)
    assert (await log_of(session, WEEK_1)).issues == "Đã sửa trong ứng dụng"


async def test_a_deleted_week_comes_back_on_the_next_run(
    session: AsyncSession, sgd_loaded: Project
) -> None:
    log = await log_of(session, WEEK_3)
    await session.delete(log)
    await session.commit()
    assert await count(session, ConstructionLog, sgd_loaded) == 1
    await seed_sgd_hcm_logs(session)
    assert await count(session, ConstructionLog, sgd_loaded) == 2


async def test_apply_logs_without_the_project_does_nothing(session: AsyncSession) -> None:
    def run(sync_session) -> int:  # type: ignore[no-untyped-def]
        return apply_logs(sync_session.connection())

    assert await session.run_sync(run) == 0


@pytest.mark.parametrize("log", data.LOGS)
def test_every_line_of_the_source_is_complete(log: dict) -> None:  # type: ignore[type-arg]
    assert date.fromisoformat(log["week_start"]).weekday() == 4  # a reporting week starts on Friday
    assert all(entry[3].strip() for entry in log["entries"])
    assert all(len(entry) == 8 for entry in log["entries"])
    assert all(len(row) == 6 for row in log["carryovers"])
