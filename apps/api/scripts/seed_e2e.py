"""Users for the Playwright run (SPEC 11). Refuses to touch anything but a database named *_e2e."""

import asyncio
import os
import sys

from app.core.db import get_engine, get_sessionmaker
from app.core.security import hash_password
from app.models import User

PASSWORD = "E2e-Passw0rd!x"
ROLES = ("director", "technical", "onsite", "clerk", "viewer", "procurement", "cost")


async def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url.rsplit("/", 1)[-1].endswith("_e2e"):
        sys.exit(
            f"refusing to seed e2e users into {url.rsplit('/', 1)[-1] or 'an unknown database'}"
        )
    async with get_sessionmaker()() as session:
        for role in ROLES:
            session.add(
                User(
                    email=f"{role}@e2e.test",
                    full_name=f"E2E {role}",
                    role=role,
                    is_active=True,
                    password_hash=hash_password(PASSWORD),
                    must_change_password=False,
                )
            )
        await session.commit()
    await get_engine().dispose()
    print(f"seeded {len(ROLES)} e2e users")


if __name__ == "__main__":
    asyncio.run(main())
