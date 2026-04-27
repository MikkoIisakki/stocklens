"""APScheduler entry point — dispatches daily ingest jobs.

Schedule (all times UTC, cron triggers):
  - Energy ingest: 11:30 UTC = 13:30 CET — after ENTSO-E publishes day-ahead prices (~13:00 CET)
  - FI ingest:     17:00 UTC = 19:00 EET — after Helsinki close (17:30 local)
  - US ingest:     21:30 UTC = 23:30 EET — after NYSE close (16:00 ET = 21:00 UTC)

Each job creates its own asyncpg pool, runs the async ingest pipeline, and
tears the pool down. Using per-run pools (rather than a long-lived one) keeps
the scheduler process simple — it runs once a day per job.
"""

import asyncio
import logging

import asyncpg
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.alerts.energy import check_threshold_alerts
from app.common.logging import configure_logging
from app.ingestion.energy_ingest import run_energy_ingest
from app.ingestion.fi_ingest import run_fi_ingest
from app.ingestion.us_ingest import run_us_ingest
from app.storage import repository as repo

logger = logging.getLogger(__name__)


async def _run_with_pool(coro_fn: object, *args: object) -> None:
    """Create a pool, call coro_fn(pool, *args), then close the pool."""
    from app.common.config import settings  # lazy — avoids import-time env validation

    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=3)
    if pool is None:
        raise RuntimeError("asyncpg.create_pool returned None")
    try:
        await coro_fn(pool, *args)  # type: ignore[operator]
    finally:
        await pool.close()


async def _run_energy_pipeline() -> None:
    """Ingest prices then evaluate threshold alerts — runs in a single pool."""
    from app.common.config import settings

    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=3)
    if pool is None:
        raise RuntimeError("asyncpg.create_pool returned None")
    try:
        await run_energy_ingest(pool)

        # Alert evaluation: jobs layer may import alerts layer (clean arch OK)
        async with pool.acquire() as conn:
            regions = await repo.get_active_energy_regions(conn)
            for region in regions:
                from datetime import date, timedelta

                target_date = date.today() + timedelta(days=1)
                prices = await conn.fetch(
                    "SELECT hour, total_c_kwh FROM energy_price WHERE region_code=$1 AND price_date=$2",
                    region["code"],
                    target_date,
                )
                if not prices:
                    continue
                rules = await repo.get_active_alert_rules(conn, region["code"])
                alerts = check_threshold_alerts(
                    [dict(r) for r in prices], rules=rules, price_date=target_date
                )
                if alerts:
                    await repo.save_energy_alerts(conn, alerts)
                    logger.info(
                        "Fired %d alert(s) for region=%s date=%s",
                        len(alerts),
                        region["code"],
                        target_date,
                    )
    finally:
        await pool.close()


def run_energy_job() -> None:
    """Synchronous wrapper — called by APScheduler at 11:30 UTC (13:30 CET)."""
    logger.info("Energy price ingest job triggered")
    asyncio.run(_run_energy_pipeline())


def run_us_job() -> None:
    """Synchronous wrapper — called by APScheduler."""
    logger.info("US ingest job triggered")
    asyncio.run(_run_with_pool(run_us_ingest))


def run_fi_job() -> None:
    """Synchronous wrapper — called by APScheduler."""
    logger.info("FI ingest job triggered")
    asyncio.run(_run_with_pool(run_fi_ingest))


def build_scheduler() -> BlockingScheduler:
    """Construct and return a configured scheduler (not yet started)."""
    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(
        run_energy_job,
        trigger=CronTrigger(hour=11, minute=30, timezone="UTC"),
        id="energy_price_ingest",
        name="ENTSO-E day-ahead price ingest",
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_fi_job,
        trigger=CronTrigger(hour=17, minute=0, timezone="UTC"),
        id="fi_eod_ingest",
        name="Finnish EOD ingest",
        misfire_grace_time=3600,
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
    logger.info("Scheduler starting — Energy at 11:30 UTC, FI at 17:00 UTC, US at 21:30 UTC")
    scheduler.start()


if __name__ == "__main__":
    main()
