"""Seed the SGD-HCM project: the baseline schedule of "Theo dõi tiến độ SGD-HCM".

Idempotent. Only the plan is seeded; progress, reports, risks and open decisions start empty and
are entered in the application. Nobody is seated in the project: system administrators see it
and add the others from the project page.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, WbsTask
from app.seed.project import _org
from app.seed.sgd_hcm_plan import PHASES

INVESTOR = "Sở Giáo dục và Đào tạo TP. Hồ Chí Minh"

PROJECT = {
    "code": "SGD-HCM",
    "short_name": "SGD-HCM",
    "project_type": "software_delivery",
    "name": (
        "Hệ thống quản lý dữ liệu cơ sở vật chất và thiết bị trường học "
        "— Sở Giáo dục và Đào tạo TP. Hồ Chí Minh"
    ),
    "location": "TP. Hồ Chí Minh",
    "start_year": 2026,
    "end_year": 2026,
    "description": (
        "Liên danh DVN thực hiện, Crystal giám sát. Kế hoạch 25/09 – 09/12/2026. "
        "Nguồn: Theo dõi tiến độ SGD-HCM.html (4.Kế hoạch tiến độ triển khai.xlsx)."
    ),
}


async def seed_sgd_hcm(session: AsyncSession) -> Project:
    investor = await _org(session, INVESTOR, "investor")
    project = (
        await session.execute(select(Project).where(Project.code == PROJECT["code"]))
    ).scalar_one_or_none()
    if project is None:
        project = Project(investor_org_id=investor.id, **PROJECT)
        session.add(project)
        await session.flush()

    have = set(
        (await session.execute(select(WbsTask.code).where(WbsTask.project_id == project.id)))
        .scalars()
        .all()
    )
    order = 0
    for phase in PHASES:
        for task in phase.tasks:
            order += 1
            if task.code in have:
                continue
            session.add(
                WbsTask(
                    project_id=project.id,
                    phase_code=phase.code,
                    phase_name=phase.name,
                    sort_order=order,
                    code=task.code,
                    name=task.name,
                    is_milestone=task.milestone,
                    plan_start=task.start,
                    plan_end=task.end,
                    plan_days=task.days,
                )
            )
    await session.commit()
    return project
