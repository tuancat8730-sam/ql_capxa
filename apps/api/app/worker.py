"""Background worker entrypoint: APScheduler jobs (alerts, text extraction) are registered here."""

import asyncio
import contextlib
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.alert_jobs import safe_digest, safe_refresh

logger = logging.getLogger("qlda.worker")


def register_jobs(scheduler: AsyncIOScheduler) -> AsyncIOScheduler:
    """Hourly engine pass (covers the 06:00 and 13:00 runs of SPEC 7 and the 4.10 AC of one
    hour) and the 08:00 e-mail digest, both in Vietnam time."""
    scheduler.add_job(
        safe_refresh, CronTrigger(minute=0), id="alerts_refresh", coalesce=True, max_instances=1
    )
    scheduler.add_job(safe_digest, CronTrigger(hour=8, minute=0), id="alerts_digest", coalesce=True)
    return scheduler


_HEALTH_REPLY = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"


async def _answer_health(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    with contextlib.suppress(TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
    writer.write(_HEALTH_REPLY)
    await writer.drain()
    writer.close()


async def serve_health(port: int) -> asyncio.Server:
    """Cloud Run only keeps a container that listens on $PORT, so the worker answers 200 there."""
    return await asyncio.start_server(_answer_health, "0.0.0.0", port)  # noqa: S104 - container


async def main() -> None:
    if port := os.environ.get("PORT"):
        await serve_health(int(port))
    scheduler = register_jobs(AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh"))
    scheduler.start()
    logger.info("worker started with %d jobs", len(scheduler.get_jobs()))
    await asyncio.Event().wait()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
