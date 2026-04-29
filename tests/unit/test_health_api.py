"""Unit tests for GET /v1/health/ready (per-market freshness, task 2.9).

All database interactions are mocked — no live DB or network needed.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_pool
from app.api.routers.health import EXPECTED_INGEST_MARKETS, get_settings, router
from app.common.config import Settings


def _make_app(pool_mock: Any, max_ingest_age_hours: int = 25) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def override_pool() -> Any:
        yield pool_mock

    def override_settings() -> Settings:
        return Settings(
            database_url="postgresql://x:x@localhost/x", max_ingest_age_hours=max_ingest_age_hours
        )

    app.dependency_overrides[get_pool] = override_pool
    app.dependency_overrides[get_settings] = override_settings
    return app


def _pool_returning(per_market: dict[str, datetime | None]) -> MagicMock:
    """Build a pool mock whose fetch returns one row per provided market."""
    rows = [
        {"market": market, "last_finished": last_finished}
        for market, last_finished in per_market.items()
        if last_finished is not None
    ]
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=rows)

    class _Ctx:
        async def __aenter__(self) -> MagicMock:
            return conn

        async def __aexit__(self, *_: Any) -> None:
            pass

    pool = MagicMock()
    pool.acquire.return_value = _Ctx()
    return pool


def _pool_raising(exc: Exception) -> MagicMock:
    class _Ctx:
        async def __aenter__(self) -> None:
            raise exc

        async def __aexit__(self, *_: Any) -> None:
            pass

    pool = MagicMock()
    pool.acquire.return_value = _Ctx()
    return pool


def _all_fresh() -> dict[str, datetime | None]:
    fresh = datetime.now(UTC) - timedelta(hours=1)
    return {market: fresh for market in EXPECTED_INGEST_MARKETS}


@pytest.mark.asyncio
async def test_ok_when_every_market_fresh() -> None:
    app = _make_app(_pool_returning(_all_fresh()))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert set(body["markets"].keys()) == set(EXPECTED_INGEST_MARKETS)
    assert all(m["stale"] is False for m in body["markets"].values())


@pytest.mark.asyncio
async def test_degraded_when_energy_stale() -> None:
    """Task 2.9: ENERGY ingest staleness must surface in /v1/health/ready."""
    state = _all_fresh()
    state["ENERGY"] = datetime.now(UTC) - timedelta(hours=30)
    app = _make_app(_pool_returning(state))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert "ENERGY" in body["reason"]
    assert body["markets"]["ENERGY"]["stale"] is True
    assert body["markets"]["FI"]["stale"] is False
    assert body["markets"]["US"]["stale"] is False


@pytest.mark.asyncio
async def test_degraded_when_energy_never_ran() -> None:
    """An expected market with no successful run is treated as stale."""
    state = _all_fresh()
    state["ENERGY"] = None
    app = _make_app(_pool_returning(state))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["markets"]["ENERGY"]["last_finished"] is None
    assert body["markets"]["ENERGY"]["age_seconds"] is None
    assert body["markets"]["ENERGY"]["stale"] is True


@pytest.mark.asyncio
async def test_degraded_when_multiple_markets_stale() -> None:
    state: dict[str, datetime | None] = {
        "ENERGY": datetime.now(UTC) - timedelta(hours=40),
        "FI": datetime.now(UTC) - timedelta(hours=1),
        "US": None,
    }
    app = _make_app(_pool_returning(state))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health/ready")

    body = resp.json()
    assert body["status"] == "degraded"
    # Reason is alphabetised so it's stable
    assert body["reason"] == "stale or missing ingest: ENERGY, US"


@pytest.mark.asyncio
async def test_degraded_exactly_past_threshold() -> None:
    """A run finished max_ingest_age_hours+1s ago is degraded."""
    state = _all_fresh()
    state["FI"] = datetime.now(UTC) - timedelta(hours=25, seconds=1)
    app = _make_app(_pool_returning(state), max_ingest_age_hours=25)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health/ready")

    body = resp.json()
    assert body["status"] == "degraded"
    assert body["markets"]["FI"]["stale"] is True


@pytest.mark.asyncio
async def test_503_when_db_unreachable() -> None:
    app = _make_app(_pool_raising(ConnectionRefusedError("db down")))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health/ready")

    assert resp.status_code == 503
    assert resp.json()["status"] == "unavailable"
