"""Users for the Playwright run (SPEC 11). Refuses to touch anything but a database named *_e2e."""

import asyncio
import os
import sys

from sqlalchemy import select

from app.core.db import get_engine, get_sessionmaker
from app.core.security import hash_password
from app.models import Project, ProjectMember, User

PASSWORD = "E2e-Passw0rd!x"
ROLES = ("director", "technical", "onsite", "clerk", "viewer", "procurement", "cost")
# Works on both projects, as director in the commune project and as technician in SGD-HCM.
MULTI = "multi"


async def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url.rsplit("/", 1)[-1].endswith("_e2e"):
        sys.exit(
            f"refusing to seed e2e users into {url.rsplit('/', 1)[-1] or 'an unknown database'}"
        )
    async with get_sessionmaker()() as session:
        projects = {
            p.project_type: p for p in (await session.execute(select(Project))).scalars().all()
        }
        users: dict[str, User] = {}
        for role in (*ROLES, MULTI):
            users[role] = User(
                email=f"{role}@e2e.test",
                full_name=f"E2E {role}",
                role="director" if role == MULTI else role,
                is_active=True,
                password_hash=hash_password(PASSWORD),
                must_change_password=False,
            )
            session.add(users[role])
        await session.flush()
        for role in ROLES:  # everyone works on the commune project, like before
            session.add(
                ProjectMember(
                    project_id=projects["procurement"].id, user_id=users[role].id, role=role
                )
            )
        multi = users[MULTI]
        session.add(
            ProjectMember(project_id=projects["procurement"].id, user_id=multi.id, role="director")
        )
        session.add(
            ProjectMember(
                project_id=projects["software_delivery"].id, user_id=multi.id, role="technical"
            )
        )
        await session.commit()
    await get_engine().dispose()
    print(f"seeded {len(ROLES) + 1} e2e users")


if __name__ == "__main__":
    asyncio.run(main())
