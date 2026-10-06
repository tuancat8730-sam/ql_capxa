"""`python -m app.seed.run` — idempotent seed entrypoint (grows with each milestone)."""

import asyncio
import os

from app.core.db import get_engine, get_sessionmaker
from app.seed.checklists import seed_checklists
from app.seed.finance import seed_finance
from app.seed.progress import seed_progress
from app.seed.project import seed_project
from app.seed.users import ensure_admin


async def main() -> None:
    email = os.environ.get("SEED_ADMIN_EMAIL", "admin@qlda.local")
    async with get_sessionmaker()() as session:
        result = await ensure_admin(session, email, os.environ.get("SEED_ADMIN_PASSWORD"))
    if result.created:
        # Shown once on the operator's terminal; the account must change it at first login.
        print(f"Created admin {result.email} with temporary password: {result.password}")
    else:
        print(f"Admin {result.email} already exists; left unchanged")
    async with get_sessionmaker()() as session:
        await seed_project(session)
        await seed_finance(session)
        await seed_checklists(session)
        await seed_progress(session)
    print("Seeded project, packages, contracts, finance, checklists and stages (idempotent)")
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
