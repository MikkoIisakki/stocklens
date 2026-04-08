"""Asset and price history endpoints.

GET /v1/assets                          — list active assets, filterable by market
GET /v1/assets/{symbol}/prices          — EOD price history for one symbol
"""

import logging
from datetime import date
from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.dependencies import Pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/assets", tags=["assets"])


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────


class AssetOut(BaseModel):
    id: int
    symbol: str
    name: str
    exchange: str
    market: str
    currency: str


class PriceOut(BaseModel):
    price_date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    adj_close: float | None
    volume: int | None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[AssetOut])
async def list_assets(
    pool: Pool,
    market: str | None = Query(default=None, description="Filter by market: US or FI"),
) -> list[dict[str, Any]]:
    """Return all active assets, optionally filtered by market."""
    async with pool.acquire() as conn:
        if market is not None:
            market_upper = market.upper()
            if market_upper not in ("US", "FI"):
                raise HTTPException(status_code=400, detail="market must be 'US' or 'FI'")
            rows = await conn.fetch(
                "SELECT id, symbol, name, exchange, market, currency"
                " FROM asset WHERE active = TRUE AND market = $1 ORDER BY symbol",
                market_upper,
            )
        else:
            rows = await conn.fetch(
                "SELECT id, symbol, name, exchange, market, currency"
                " FROM asset WHERE active = TRUE ORDER BY market, symbol"
            )
    return [dict(r) for r in rows]


@router.get("/{symbol}/prices", response_model=list[PriceOut])
async def get_price_history(
    symbol: str,
    pool: Pool,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=90, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Return EOD price history for one symbol.

    - ``from`` / ``to``: inclusive date bounds (ISO-8601)
    - ``limit``: max rows returned, default 90 (≈ 3 months), max 500
    - Results are ordered newest-first
    """
    async with pool.acquire() as conn:
        # Resolve asset — case-insensitive symbol match
        asset: asyncpg.Record | None = await conn.fetchrow(
            "SELECT id FROM asset WHERE upper(symbol) = upper($1) AND active = TRUE",
            symbol,
        )
        if asset is None:
            raise HTTPException(status_code=404, detail=f"Asset '{symbol}' not found")

        rows = await conn.fetch(
            """
            SELECT price_date, open, high, low, close, adj_close, volume
              FROM daily_price
             WHERE asset_id = $1
               AND ($2::date IS NULL OR price_date >= $2)
               AND ($3::date IS NULL OR price_date <= $3)
             ORDER BY price_date DESC
             LIMIT $4
            """,
            asset["id"],
            from_date,
            to_date,
            limit,
        )
    return [dict(r) for r in rows]
