"""Electricity domain ingest — ENTSO-E Transparency Platform day-ahead prices.

Entry point: ``run_energy_ingest(pool, target_date)``

Fetches hourly day-ahead spot prices from the ENTSO-E Transparency Platform for
all active energy regions, normalises them (EUR/MWh -> c/kWh with VAT+tax), and
upserts into energy_price. Designed to run once daily at ~13:30 CET after
ENTSO-E publishes tomorrow's prices (~13:00 CET).

Provider migrated from Nordpool to ENTSO-E in 2026-04 (RISK-014, ADR-004) after
Nordpool's unauthenticated dataportal endpoint started returning 401.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import asyncpg

from app.common.config import settings
from app.ingestion.entsoe_client import fetch_day_ahead
from app.normalization.energy_price import normalize_nordpool_response
from app.storage import repository as repo
from app.storage.repository import AnyConn

logger = logging.getLogger(__name__)

_MARKET = "ENERGY"


async def _ingest_region(
    conn: AnyConn,
    *,
    region: dict[str, Any],
    target_date: date,
    run_id: int,
    token: str,
) -> int:
    """Ingest one bidding zone for *target_date*. Returns number of rows stored."""
    region_code = region["code"]
    try:
        raw = await fetch_day_ahead(target_date, region=region_code, token=token)
    except Exception:
        logger.exception("ENTSO-E fetch failed for region=%s date=%s", region_code, target_date)
        return 0

    prices = normalize_nordpool_response(raw, region=region, ingest_run_id=run_id)
    if not prices:
        logger.warning("No price rows returned for region=%s date=%s", region_code, target_date)
        return 0

    try:
        count = await repo.upsert_energy_prices(conn, prices)
    except Exception:
        logger.exception("DB upsert failed for region=%s date=%s", region_code, target_date)
        return 0

    logger.info("Ingested %d hourly prices for region=%s date=%s", count, region_code, target_date)
    return count


async def run_energy_ingest(
    pool: asyncpg.Pool[asyncpg.Record],
    *,
    target_date: date | None = None,
) -> None:
    """Run the full energy ingest pipeline for all active regions.

    Args:
        pool: asyncpg connection pool.
        target_date: The delivery date to fetch prices for. Defaults to
            tomorrow (ENTSO-E publishes tomorrow's prices at ~13:00 CET).
    """
    if target_date is None:
        target_date = date.today() + timedelta(days=1)

    token = settings.entsoe_api_token.get_secret_value()
    if not token:
        logger.error(
            "ENTSOE_API_TOKEN is not set — register at transparency.entsoe.eu and set in .env"
        )

    async with pool.acquire() as conn:
        run_id = await repo.create_ingest_run(conn, _MARKET)
        logger.info("Started energy ingest run id=%d date=%s", run_id, target_date)

        if not token:
            await repo.finish_ingest_run(
                conn,
                run_id,
                status="failed",
                assets_attempted=0,
                assets_succeeded=0,
                error_message="ENTSOE_API_TOKEN is not configured",
            )
            return

        regions = await repo.get_active_energy_regions(conn)
        if not regions:
            logger.warning("No active energy regions — nothing to ingest")
            await repo.finish_ingest_run(
                conn,
                run_id,
                status="failed",
                assets_attempted=0,
                assets_succeeded=0,
                error_message="No active energy regions in DB",
            )
            return

        total_rows = 0
        for region in regions:
            rows = await _ingest_region(
                conn,
                region=region,
                target_date=target_date,
                run_id=run_id,
                token=token,
            )
            total_rows += rows

        status = "success" if total_rows > 0 else "failed"
        error = None if total_rows > 0 else f"No prices ingested for {target_date}"

        await repo.finish_ingest_run(
            conn,
            run_id,
            status=status,
            assets_attempted=len(regions),
            assets_succeeded=total_rows,
            error_message=error,
        )
        logger.info(
            "Energy ingest run id=%d finished: %s (%d rows across %d regions)",
            run_id,
            status,
            total_rows,
            len(regions),
        )
