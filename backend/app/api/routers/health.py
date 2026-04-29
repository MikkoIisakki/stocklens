"""Health check endpoints.

GET /v1/health/ready — returns 200 OK when every expected ingest market has
run within ``max_ingest_age_hours``, 200 with status=degraded when one or
more markets are stale or have never run, or 503 when the database is
unreachable.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app.api.dependencies import get_pool
from app.common.config import Settings
from app.common.config import settings as default_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/health", tags=["health"])

# Markets whose freshness counts toward overall readiness. Each corresponds to
# a scheduled APScheduler job (see app/jobs/scheduler.py).
EXPECTED_INGEST_MARKETS: tuple[str, ...] = ("ENERGY", "FI", "US")


def get_settings() -> Settings:
    """Dependency — allows override in tests."""
    return default_settings


@router.get("/ready")
async def readiness(
    response: Response,
    cfg: Annotated[Settings, Depends(get_settings)],
    pool: Annotated[Any, Depends(get_pool)],
) -> dict[str, Any]:
    """Return per-market readiness status.

    Status values:
    - ``ok``: database reachable and every expected market has a successful
      ingest within ``max_ingest_age_hours``.
    - ``degraded``: database reachable but at least one expected market is
      stale or has never run. The ``markets`` object lists each one.
    - ``unavailable``: database unreachable (HTTP 503).
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT market, MAX(finished_at) AS last_finished
                  FROM ingest_run
                 WHERE status = 'success'
                 GROUP BY market
                """
            )
    except Exception:
        logger.exception("Database unreachable during health check")
        response.status_code = 503
        return {"status": "unavailable"}

    last_by_market: dict[str, datetime | None] = {m: None for m in EXPECTED_INGEST_MARKETS}
    for r in rows:
        if r["market"] in last_by_market:
            last_by_market[r["market"]] = r["last_finished"]

    threshold = timedelta(hours=cfg.max_ingest_age_hours)
    now = datetime.now(UTC)

    markets: dict[str, dict[str, Any]] = {}
    stale_markets: list[str] = []
    for market, last_finished in last_by_market.items():
        if last_finished is None:
            markets[market] = {"last_finished": None, "age_seconds": None, "stale": True}
            stale_markets.append(market)
            continue
        age = now - last_finished
        is_stale = age > threshold
        markets[market] = {
            "last_finished": last_finished.isoformat(),
            "age_seconds": int(age.total_seconds()),
            "stale": is_stale,
        }
        if is_stale:
            stale_markets.append(market)

    if stale_markets:
        return {
            "status": "degraded",
            "reason": f"stale or missing ingest: {', '.join(sorted(stale_markets))}",
            "markets": markets,
        }

    return {"status": "ok", "markets": markets}
