"""Electricity domain endpoints.

GET /v1/energy/prices?region={code}&date={YYYY-MM-DD|today|tomorrow}
GET /v1/energy/cheap-hours?region={code}&date={YYYY-MM-DD|today|tomorrow}&limit={int}
GET /v1/energy/alerts?region={code}
"""

import logging
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.dependencies import Pool
from app.storage import repository as repo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/energy", tags=["energy"])


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────


class HourlyPriceOut(BaseModel):
    hour: int
    price_eur_mwh: float
    spot_c_kwh: float
    total_c_kwh: float


class PricesResponse(BaseModel):
    region: str
    date: str
    prices: list[HourlyPriceOut]


class RankedHourOut(BaseModel):
    rank: int
    hour: int
    price_eur_mwh: float
    spot_c_kwh: float
    total_c_kwh: float


class CheapHoursResponse(BaseModel):
    region: str
    date: str
    hours: list[RankedHourOut]


class AlertOut(BaseModel):
    id: int
    price_date: date
    peak_c_kwh: float
    peak_hour: int
    threshold_c_kwh: float
    fired_at: str


class AlertsResponse(BaseModel):
    region: str
    alerts: list[AlertOut]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_date(date_str: str) -> date:
    """Resolve 'today', 'tomorrow', or ISO date string to a date object.

    Raises HTTPException(422) on unrecognised input.
    """
    if date_str == "today":
        return date.today()
    if date_str == "tomorrow":
        return date.today() + timedelta(days=1)
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid date '{date_str}'. Use YYYY-MM-DD, 'today', or 'tomorrow'.",
        ) from None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/prices", response_model=PricesResponse)
async def get_energy_prices(
    pool: Pool,
    region: str = Query(description="Nordpool bidding zone code, e.g. FI, SE3"),
    date: str = Query(description="Delivery date: YYYY-MM-DD, 'today', or 'tomorrow'"),
) -> dict[str, Any]:
    """Return hourly electricity prices for a region and date."""
    price_date = _resolve_date(date)
    region_upper = region.upper()

    async with pool.acquire() as conn:
        region_row = await conn.fetchrow(
            "SELECT code FROM energy_region WHERE code = $1 AND active = TRUE",
            region_upper,
        )
        if region_row is None:
            raise HTTPException(status_code=404, detail=f"Region '{region_upper}' not found")

        rows = await repo.get_energy_prices(conn, region_upper, price_date)

    return {
        "region": region_upper,
        "date": price_date.isoformat(),
        "prices": [dict(r) for r in rows],
    }


@router.get("/cheap-hours", response_model=CheapHoursResponse)
async def get_cheap_hours(
    pool: Pool,
    region: str = Query(description="Nordpool bidding zone code, e.g. FI, SE3"),
    date: str = Query(description="Delivery date: YYYY-MM-DD, 'today', or 'tomorrow'"),
    limit: int = Query(default=24, ge=1, le=48, description="Max number of hours to return"),
) -> dict[str, Any]:
    """Return the cheapest hours for a region/date, ranked ascending by total_c_kwh."""
    price_date = _resolve_date(date)
    region_upper = region.upper()

    async with pool.acquire() as conn:
        region_row = await conn.fetchrow(
            "SELECT code FROM energy_region WHERE code = $1 AND active = TRUE",
            region_upper,
        )
        if region_row is None:
            raise HTTPException(status_code=404, detail=f"Region '{region_upper}' not found")

        rows = await repo.get_cheap_hours(conn, region_upper, price_date, limit)

    return {
        "region": region_upper,
        "date": price_date.isoformat(),
        "hours": [{"rank": i + 1, **dict(r)} for i, r in enumerate(rows)],
    }


@router.get("/alerts", response_model=AlertsResponse)
async def get_energy_alerts(
    pool: Pool,
    region: str = Query(description="Nordpool bidding zone code, e.g. FI, SE3"),
) -> dict[str, Any]:
    """Return fired threshold alerts for a region, newest first."""
    region_upper = region.upper()

    async with pool.acquire() as conn:
        region_row = await conn.fetchrow(
            "SELECT code FROM energy_region WHERE code = $1 AND active = TRUE",
            region_upper,
        )
        if region_row is None:
            raise HTTPException(status_code=404, detail=f"Region '{region_upper}' not found")

        rows = await repo.get_energy_alerts(conn, region_upper)

    return {
        "region": region_upper,
        "alerts": [{**dict(r), "fired_at": r["fired_at"].isoformat()} for r in rows],
    }
