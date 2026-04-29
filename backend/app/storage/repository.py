"""Database access layer — all SQL lives here.

Each function accepts an asyncpg Connection (or PoolConnectionProxy) so callers
control transaction boundaries. No business logic — pure data access.
"""

import json
import logging
from datetime import date
from typing import TYPE_CHECKING, Any

import asyncpg
import asyncpg.pool

logger = logging.getLogger(__name__)

# asyncpg.Connection is not subscriptable at runtime in asyncpg 0.30.
# TYPE_CHECKING guard gives mypy the generic form; at runtime the bare Union
# is used (Connection and PoolConnectionProxy share the same query interface).
if TYPE_CHECKING:
    AnyConn = asyncpg.Connection[asyncpg.Record] | asyncpg.pool.PoolConnectionProxy[asyncpg.Record]
else:
    AnyConn = asyncpg.Connection | asyncpg.pool.PoolConnectionProxy


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
# Energy
# ─────────────────────────────────────────────────────────────────────────────


async def get_active_energy_regions(conn: AnyConn) -> list[dict[str, Any]]:
    """Return all active energy regions with their VAT and tax parameters."""
    rows = await conn.fetch(
        "SELECT code, vat_rate, electricity_tax_c_kwh, active FROM energy_region WHERE active = TRUE ORDER BY code"
    )
    return [dict(row) for row in rows]


async def get_active_alert_rules(conn: AnyConn, region_code: str) -> list[dict[str, Any]]:
    """Return active alert rules for a given energy region."""
    rows = await conn.fetch(
        "SELECT id, region_code, threshold_c_kwh, active FROM energy_alert_rule WHERE region_code = $1 AND active = TRUE",
        region_code,
    )
    return [dict(row) for row in rows]


async def save_energy_alerts(conn: AnyConn, alerts: list[dict[str, Any]]) -> int:
    """Upsert fired alert events. Returns number of rows processed."""
    if not alerts:
        return 0
    await conn.executemany(
        """
        INSERT INTO energy_alert
               (rule_id, region_code, price_date, peak_c_kwh, peak_interval_start, threshold_c_kwh)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (rule_id, price_date) DO NOTHING
        """,
        [
            (
                a["rule_id"],
                a["region_code"],
                a["price_date"],
                a["peak_c_kwh"],
                a["peak_interval_start"],
                a["threshold_c_kwh"],
            )
            for a in alerts
        ],
    )
    return len(alerts)


async def get_energy_prices(
    conn: AnyConn, region_code: str, price_date: date
) -> list[dict[str, Any]]:
    """Return interval price rows for a region whose UTC date matches *price_date*.

    Returned rows are ordered by ``interval_start`` ascending. Resolution is
    whatever the upstream provider published — typically PT60M (24 rows) or
    PT15M (96 rows) for ENTSO-E zones.
    """
    rows = await conn.fetch(
        """
        SELECT interval_start, interval_end, interval_minutes,
               price_eur_mwh, spot_c_kwh, total_c_kwh
          FROM energy_price
         WHERE region_code = $1
           AND (interval_start AT TIME ZONE 'UTC')::date = $2
         ORDER BY interval_start
        """,
        region_code,
        price_date,
    )
    return [dict(row) for row in rows]


async def get_cheap_intervals(
    conn: AnyConn, region_code: str, price_date: date, limit: int
) -> list[dict[str, Any]]:
    """Return interval price rows for a region/date sorted ascending by total_c_kwh.

    Caller passes ``limit`` to cap the result; the SQL applies it server-side.
    Ranking (1 = cheapest) is derived in the API layer from ordering.
    """
    rows = await conn.fetch(
        """
        SELECT interval_start, interval_end, interval_minutes,
               price_eur_mwh, spot_c_kwh, total_c_kwh
          FROM energy_price
         WHERE region_code = $1
           AND (interval_start AT TIME ZONE 'UTC')::date = $2
         ORDER BY total_c_kwh ASC, interval_start ASC
         LIMIT $3
        """,
        region_code,
        price_date,
        limit,
    )
    return [dict(row) for row in rows]


async def get_energy_alerts(conn: AnyConn, region_code: str) -> list[dict[str, Any]]:
    """Return all fired alerts for a region, newest first."""
    rows = await conn.fetch(
        """
        SELECT ea.id, ea.price_date, ea.peak_c_kwh, ea.peak_interval_start,
               ea.threshold_c_kwh, ea.fired_at
          FROM energy_alert ea
          JOIN energy_alert_rule ear ON ear.id = ea.rule_id
         WHERE ea.region_code = $1
         ORDER BY ea.fired_at DESC
        """,
        region_code,
    )
    return [dict(row) for row in rows]


async def upsert_energy_prices(conn: AnyConn, prices: list[dict[str, Any]]) -> int:
    """Upsert a batch of interval-keyed energy price rows. Returns rows processed."""
    if not prices:
        return 0

    await conn.executemany(
        """
        INSERT INTO energy_price
               (region_code, ingest_run_id, interval_start, interval_end, interval_minutes,
                price_eur_mwh, spot_c_kwh, total_c_kwh)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (region_code, interval_start) DO UPDATE
               SET interval_end     = EXCLUDED.interval_end,
                   interval_minutes = EXCLUDED.interval_minutes,
                   price_eur_mwh    = EXCLUDED.price_eur_mwh,
                   spot_c_kwh       = EXCLUDED.spot_c_kwh,
                   total_c_kwh      = EXCLUDED.total_c_kwh,
                   ingest_run_id    = EXCLUDED.ingest_run_id,
                   fetched_at       = now()
        """,
        [
            (
                p["region_code"],
                p["ingest_run_id"],
                p["interval_start"],
                p["interval_end"],
                p["interval_minutes"],
                p["price_eur_mwh"],
                p["spot_c_kwh"],
                p["total_c_kwh"],
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
