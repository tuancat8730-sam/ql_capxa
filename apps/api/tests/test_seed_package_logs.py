"""The Gói 05 pre-delivery inspection report lands in the package's site diary, once."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Package, ProgressLog
from app.seed.package_logs import seed_package_logs
from app.seed.project import seed_project
from app.seed.users import ensure_admin


async def test_package_05_inspection_is_logged_once(session: AsyncSession) -> None:
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
    assert "ĐẠT" in (log.summary or "") and "PHÙ HỢP" in (log.summary or "")
    assert "IP57" in (log.issues or "") and "BM-04" in (log.next_steps or "")
    total = (await session.execute(select(func.count()).select_from(ProgressLog))).scalar_one()
    assert total == 1
