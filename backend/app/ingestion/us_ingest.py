"""US EOD price ingest — fetches the top S&P 500 + Nasdaq tech universe.

Entry point: ``run_us_ingest(pool)``

Flow:
  1. Open ingest_run (status=running)
  2. Load active US assets from DB
  3. For each asset: fetch yfinance → save raw snapshot → normalise → upsert prices
  4. Close ingest_run (status=success | failed)

Each asset is attempted independently — a single bad ticker does not abort
the whole run.  The ingest_run row records how many succeeded so the health
check and dashboards can reflect partial failures.
"""

import asyncio
import logging
from datetime import date
from typing import Any

import asyncpg

from app.ingestion.yfinance_client import fetch_eod
from app.normalization.price import normalize_price_rows
from app.storage import repository as repo
from app.storage.repository import AnyConn

logger = logging.getLogger(__name__)

_MARKET = "US"
_CONCURRENCY = 5  # simultaneous yfinance requests (they are HTTP under the hood)


async def _ingest_asset(
    conn: AnyConn,
    *,
    asset_id: int,
    symbol: str,
    run_id: int,
    snapshot_date: date,
) -> bool:
    """Ingest one asset. Returns True on success, False on any error."""
    try:
        raw = await fetch_eod(symbol)
    except Exception:
        logger.exception("yfinance fetch failed for %s", symbol)
        return False

    try:
        await repo.save_raw_snapshot(
            conn,
            run_id=run_id,
            source="yfinance",
            symbol=symbol,
            snapshot_date=snapshot_date,
            payload={
                "rows": [{**r, "price_date": r["price_date"].isoformat()} for r in raw["rows"]]
            },
        )
    except Exception:
        logger.exception("Failed to save raw snapshot for %s", symbol)
        # Non-fatal — we still try to persist prices

    if not raw["rows"]:
        logger.warning("No price rows returned for %s", symbol)
        return False

    prices = normalize_price_rows(raw["rows"], asset_id=asset_id, ingest_run_id=run_id)
    if not prices:
        logger.warning("All rows filtered out for %s", symbol)
        return False

    try:
        await repo.upsert_daily_prices(conn, prices)
    except Exception:
        logger.exception("DB upsert failed for %s", symbol)
        return False

    logger.info("Ingested %d price rows for %s", len(prices), symbol)
    return True


async def run_us_ingest(pool: asyncpg.Pool[asyncpg.Record]) -> None:
    """Run the full US EOD ingest pipeline against *pool*."""
    snapshot_date = date.today()

    async with pool.acquire() as conn:
        run_id = await repo.create_ingest_run(conn, _MARKET)
        logger.info("Started US ingest run id=%d", run_id)

        assets = await repo.get_active_assets(conn, _MARKET)
        if not assets:
            logger.warning("No active US assets found — nothing to ingest")
            await repo.finish_ingest_run(
                conn,
                run_id,
                status="failed",
                assets_attempted=0,
                assets_succeeded=0,
                error_message="No active assets in DB",
            )
            return

        # Bounded concurrency via semaphore — avoids hammering yfinance
        sem = asyncio.Semaphore(_CONCURRENCY)
        attempted = len(assets)

        async def guarded(asset: dict[str, Any]) -> bool:
            async with sem:
                return await _ingest_asset(
                    conn,
                    asset_id=asset["id"],
                    symbol=asset["symbol"],
                    run_id=run_id,
                    snapshot_date=snapshot_date,
                )

        results = await asyncio.gather(*[guarded(a) for a in assets])
        succeeded = sum(results)

        status = "success" if succeeded > 0 else "failed"
        error = None if succeeded > 0 else "All assets failed to ingest"

        await repo.finish_ingest_run(
            conn,
            run_id,
            status=status,
            assets_attempted=attempted,
            assets_succeeded=succeeded,
            error_message=error,
        )
        logger.info(
            "US ingest run id=%d finished: %s (%d/%d assets succeeded)",
            run_id,
            status,
            succeeded,
            attempted,
        )
