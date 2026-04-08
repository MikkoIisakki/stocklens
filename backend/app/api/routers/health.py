"""Health check endpoints.

GET /v1/health/ready — returns 200 OK when healthy, 200 with status=degraded
when the last ingest run is older than the configured threshold.
Returns 503 when the database is unreachable.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, Response

from app.common.config import Settings
from app.common.config import settings as default_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/health", tags=["health"])


def get_settings() -> Settings:
    """Dependency — allows override in tests."""
    return default_settings


@router.get("/ready")
async def readiness(
    response: Response,
    cfg: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Return system readiness status.

    Status values:
    - ok: database reachable, last ingest within threshold
    - degraded: database reachable but ingest is stale
    - unavailable: database unreachable (503)
    """
    try:
        conn = await asyncpg.connect(cfg.database_url)
        try:
            row = await conn.fetchrow(
                """
                SELECT MAX(started_at) AS last_run
                FROM ingest_run
                WHERE status = 'success'
                """
            )
        finally:
            await conn.close()
    except Exception:
        logger.exception("Database unreachable during health check")
        response.status_code = 503
        return {"status": "unavailable"}

    last_run: datetime | None = row["last_run"] if row else None
    threshold = timedelta(hours=cfg.max_ingest_age_hours)
    now = datetime.now(UTC)

    if last_run is None or (now - last_run.replace(tzinfo=UTC)) > threshold:
        # Degraded but still 200 — callers can detect via status field
        return {"status": "degraded", "reason": "ingest stale or never run"}

    return {"status": "ok"}
