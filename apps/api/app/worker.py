"""Background worker entrypoint: APScheduler jobs (alerts, text extraction) are registered here."""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger("qlda.worker")


async def main() -> None:
    scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")
    scheduler.start()
    logger.info("worker started with %d jobs", len(scheduler.get_jobs()))
    await asyncio.Event().wait()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
