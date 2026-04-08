"""Unit tests for /v1/assets endpoints.

Uses FastAPI's test client with the pool dependency overridden so no real
database is needed.
"""

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_pool
from app.api.routers.assets import router


def _make_app(pool_mock: Any) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def override_pool() -> Any:
        yield pool_mock

    app.dependency_overrides[get_pool] = override_pool
    return app


def _conn_mock(rows: list[dict[str, Any]]) -> MagicMock:
    """Return a pool mock whose connection returns *rows* from fetch/fetchrow."""
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=rows)
    conn.fetchrow = AsyncMock(return_value=rows[0] if rows else None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCtx(conn))
    return pool


class _AsyncCtx:
    def __init__(self, value: Any) -> None:
        self._value = value

    async def __aenter__(self) -> Any:
        return self._value

    async def __aexit__(self, *_: Any) -> None:
        pass


# ─── /v1/assets ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_assets_returns_200() -> None:
    rows = [
        {
            "id": 1,
            "symbol": "AAPL",
            "name": "Apple",
            "exchange": "NASDAQ",
            "market": "US",
            "currency": "USD",
        }
    ]
    app = _make_app(_conn_mock(rows))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/assets")

    assert resp.status_code == 200
    assert resp.json()[0]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_list_assets_invalid_market_returns_400() -> None:
    app = _make_app(_conn_mock([]))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/assets?market=XX")

    assert resp.status_code == 400


# ─── /v1/assets/{symbol}/prices ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_price_history_unknown_symbol_returns_404() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCtx(conn))
    app = _make_app(pool)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/assets/UNKNOWN/prices")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_price_history_returns_prices() -> None:
    asset_row = MagicMock()
    asset_row.__getitem__ = MagicMock(side_effect=lambda k: 42 if k == "id" else None)

    price_rows = [
        {
            "price_date": date(2024, 1, 2),
            "open": 150.0,
            "high": 155.0,
            "low": 148.0,
            "close": 152.0,
            "adj_close": 151.5,
            "volume": 1_000_000,
        }
    ]
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=asset_row)
    conn.fetch = AsyncMock(return_value=price_rows)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCtx(conn))
    app = _make_app(pool)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/assets/AAPL/prices")

    assert resp.status_code == 200
    assert resp.json()[0]["close"] == 152.0


@pytest.mark.asyncio
async def test_limit_too_large_returns_422() -> None:
    app = _make_app(_conn_mock([]))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/assets/AAPL/prices?limit=9999")

    assert resp.status_code == 422
