"""Entry points that own their DB session: scheduler jobs, the manual refresh and write hooks."""

import asyncio
import logging
from collections.abc import Callable

from sqlalchemy import text

from app.core.db import get_engine, get_sessionmaker
from app.services.alert_engine import RunResult, run_alerts
from app.services.mailer import Mailer, build_mailer
from app.services.notify import send_critical_notifications, send_daily_digest

logger = logging.getLogger("qlda.alerts")

# One engine pass at a time: concurrent write hooks would race on the unique fingerprint.
_lock = asyncio.Lock()
# ... and one across processes (several API tasks plus the worker): a Postgres advisory lock.
ENGINE_LOCK_KEY = 7_700_001


async def refresh_alerts(mailer: Mailer | None = None) -> tuple[RunResult, int]:
    """Evaluate every rule, then e-mail new critical alerts. Returns (result, e-mails sent)."""
    mailer = mailer or build_mailer()
    async with _lock, get_engine().connect() as lock_conn:
        # session-level lock on its own connection: held through the engine pass and the mails,
        # so two processes never evaluate or e-mail the same alerts at once
        await lock_conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": ENGINE_LOCK_KEY})
        try:
            async with get_sessionmaker()() as session:
                result = await run_alerts(session)
                sent = await send_critical_notifications(session, mailer)
        finally:
            await lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ENGINE_LOCK_KEY})
            await lock_conn.commit()
    return result, sent


async def morning_digest(mailer: Mailer | None = None) -> int:
    mailer = mailer or build_mailer()
    async with get_sessionmaker()() as session:
        return await send_daily_digest(session, mailer)


async def safe_refresh(mailer: Mailer | None = None) -> None:
    """For schedulers and background hooks: a failing run is logged, never raised."""
    try:
        await refresh_alerts(mailer)
    except Exception:
        logger.exception("alert refresh failed")


async def safe_digest(mailer: Mailer | None = None) -> None:
    try:
        await morning_digest(mailer)
    except Exception:
        logger.exception("daily digest failed")


class WriteRefresh:
    """Re-run the engine after a write (SPEC 7), merging bursts of writes into one more pass."""

    def __init__(self, mailer: Callable[[], Mailer | None]) -> None:
        self._mailer = mailer
        self._task: asyncio.Task[None] | None = None
        self._dirty = False

    def trigger(self) -> None:
        self._dirty = True
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while self._dirty:
            self._dirty = False
            await safe_refresh(self._mailer())

    async def drain(self) -> None:
        """Wait for the pending pass; used by tests and at shutdown."""
        while self._task is not None and not self._task.done():
            await self._task
