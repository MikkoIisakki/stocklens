"""APScheduler entry point — dispatches daily EOD ingest jobs.

Schedule (all times UTC, cron triggers):
  - FI ingest: 17:00 UTC = 19:00 EET — after Helsinki close (17:30 local)
  - US ingest: 21:30 UTC = 23:30 EET — after NYSE close (16:00 ET = 21:00 UTC)

Each job creates its own asyncpg pool, runs the async ingest pipeline, and
tears the pool down. Using per-run pools (rather than a long-lived one) keeps
the scheduler process simple — it runs once a day per market.
"""

import asyncio
import logging

import asyncpg
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.common.logging import configure_logging
from app.ingestion.fi_ingest import run_fi_ingest
from app.ingestion.us_ingest import run_us_ingest

logger = logging.getLogger(__name__)


async def _ingest(market: str) -> None:
    """Create a pool, run the ingest for *market*, and close the pool."""
    from app.common.config import settings  # lazy — avoids import-time env validation

    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=3)
    if pool is None:
        raise RuntimeError("asyncpg.create_pool returned None")
    try:
        if market == "US":
            await run_us_ingest(pool)
        else:
            await run_fi_ingest(pool)
    finally:
        await pool.close()


def run_us_job() -> None:
    """Synchronous wrapper — called by APScheduler."""
    logger.info("US ingest job triggered")
    asyncio.run(_ingest("US"))


def run_fi_job() -> None:
    """Synchronous wrapper — called by APScheduler."""
    logger.info("FI ingest job triggered")
    asyncio.run(_ingest("FI"))


def build_scheduler() -> BlockingScheduler:
    """Construct and return a configured scheduler (not yet started)."""
    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(
        run_fi_job,
        trigger=CronTrigger(hour=17, minute=0, timezone="UTC"),
        id="fi_eod_ingest",
        name="Finnish EOD ingest",
        misfire_grace_time=3600,  # tolerate up to 1h delay (e.g. container restart)
    )

    scheduler.add_job(
        run_us_job,
        trigger=CronTrigger(hour=21, minute=30, timezone="UTC"),
        id="us_eod_ingest",
        name="US EOD ingest",
        misfire_grace_time=3600,
    )

    return scheduler


def main() -> None:
    configure_logging()
    scheduler = build_scheduler()
    logger.info("Scheduler starting — FI ingest at 17:00 UTC, US ingest at 21:30 UTC")
    scheduler.start()


if __name__ == "__main__":
    main()
