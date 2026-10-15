"""The Gói 05 handover record lands in the package's site diary, once."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Package, ProgressLog
from app.seed.package_logs import seed_package_logs
from app.seed.project import seed_project
from app.seed.users import ensure_admin


async def test_package_05_handover_is_logged_once(session: AsyncSession) -> None:
    await ensure_admin(session, "admin@qlda.local", "S3cure-pass-for-tests!")
    await seed_project(session)
    await seed_package_logs(session)
    await seed_package_logs(session)

    p5 = (await session.execute(select(Package).where(Package.number == 5))).scalar_one()
    logs = (
        (await session.execute(select(ProgressLog).where(ProgressLog.package_id == p5.id)))
        .scalars()
        .all()
    )
    assert len(logs) == 1
    log = logs[0]
    assert log.log_date.isoformat() == "2026-10-13"
    assert "1310/BBBG-G05/TVGS-SGM" in (log.summary or "")
    assert "BKCA2020101" in (log.issues or "") and "ký biên bản" in (log.next_steps or "")
    total = (await session.execute(select(func.count()).select_from(ProgressLog))).scalar_one()
    assert total == 1
