"""Database access layer — all SQL lives here.

Each function accepts an asyncpg Connection (or PoolConnectionProxy) so callers
control transaction boundaries. No business logic — pure data access.
"""

import json
import logging
from datetime import date
from typing import Any

import asyncpg
import asyncpg.pool

logger = logging.getLogger(__name__)

# asyncpg.pool.acquire() returns a PoolConnectionProxy which is a subclass of
# Connection. Both share the same query interface; this union lets callers pass
# either without type errors.
AnyConn = asyncpg.Connection[asyncpg.Record] | asyncpg.pool.PoolConnectionProxy[asyncpg.Record]


# ─────────────────────────────────────────────────────────────────────────────
# Assets
# ─────────────────────────────────────────────────────────────────────────────


async def get_active_assets(conn: AnyConn, market: str) -> list[dict[str, Any]]:
    """Return all active assets for a given market (US | FI)."""
    rows = await conn.fetch(
        "SELECT id, symbol, exchange FROM asset WHERE market = $1 AND active = TRUE ORDER BY symbol",
        market,
    )
    return [dict(row) for row in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Ingest run lifecycle
# ─────────────────────────────────────────────────────────────────────────────


async def create_ingest_run(conn: AnyConn, market: str) -> int:
    """Insert a new ingest_run with status='running' and return its id."""
    run_id: int = await conn.fetchval(
        "INSERT INTO ingest_run (market) VALUES ($1) RETURNING id",
        market,
    )
    return run_id


async def finish_ingest_run(
    conn: AnyConn,
    run_id: int,
    *,
    status: str,
    assets_attempted: int,
    assets_succeeded: int,
    error_message: str | None = None,
) -> None:
    """Stamp finished_at and final status onto an existing ingest_run row."""
    await conn.execute(
        """
        UPDATE ingest_run
           SET finished_at      = now(),
               status           = $2,
               assets_attempted = $3,
               assets_succeeded = $4,
               error_message    = $5
         WHERE id = $1
        """,
        run_id,
        status,
        assets_attempted,
        assets_succeeded,
        error_message,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Prices
# ─────────────────────────────────────────────────────────────────────────────


async def upsert_daily_prices(conn: AnyConn, prices: list[dict[str, Any]]) -> int:
    """Upsert a batch of daily price rows. Returns the number of rows processed."""
    if not prices:
        return 0

    await conn.executemany(
        """
        INSERT INTO daily_price
               (asset_id, ingest_run_id, price_date, open, high, low, close, adj_close, volume)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (asset_id, price_date) DO UPDATE
               SET open          = EXCLUDED.open,
                   high          = EXCLUDED.high,
                   low           = EXCLUDED.low,
                   close         = EXCLUDED.close,
                   adj_close     = EXCLUDED.adj_close,
                   volume        = EXCLUDED.volume,
                   ingest_run_id = EXCLUDED.ingest_run_id
        """,
        [
            (
                p["asset_id"],
                p["ingest_run_id"],
                p["price_date"],
                p["open"],
                p["high"],
                p["low"],
                p["close"],
                p["adj_close"],
                p["volume"],
            )
            for p in prices
        ],
    )
    return len(prices)


# ─────────────────────────────────────────────────────────────────────────────
# Raw source snapshots
# ─────────────────────────────────────────────────────────────────────────────


async def save_raw_snapshot(
    conn: AnyConn,
    *,
    run_id: int,
    source: str,
    symbol: str,
    snapshot_date: date,
    payload: dict[str, Any],
) -> None:
    """Persist an immutable raw API response for audit and replay."""
    await conn.execute(
        """
        INSERT INTO raw_source_snapshot (ingest_run_id, source, symbol, snapshot_date, raw_payload)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        """,
        run_id,
        source,
        symbol,
        snapshot_date,
        json.dumps(payload),
    )
