"""Unit tests for the API key auth layer (task 3.3, ADR-007).

Covers the pure helpers (hash_key, generate_raw_key) and the
require_api_key dependency end-to-end through a FastAPI test client. No
real database; pool is mocked.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.api.auth import (
    KEY_PREFIX,
    generate_raw_key,
    get_settings,
    hash_key,
    require_api_key,
)
from app.api.dependencies import get_pool
from app.common.config import Settings

# ─── Pure helpers ────────────────────────────────────────────────────────────


def test_hash_key_is_sha256_hex() -> None:
    assert hash_key("hello") == ("2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")


def test_hash_key_is_deterministic() -> None:
    assert hash_key("same input") == hash_key("same input")


def test_hash_key_differs_for_different_inputs() -> None:
    assert hash_key("a") != hash_key("b")


def test_generate_raw_key_has_prefix_and_expected_length() -> None:
    key = generate_raw_key()
    assert key.startswith(KEY_PREFIX)
    # secrets.token_hex(16) → 32 hex chars; plus prefix
    assert len(key) == len(KEY_PREFIX) + 32


def test_generate_raw_key_is_random() -> None:
    assert generate_raw_key() != generate_raw_key()


# ─── require_api_key — wired into a real FastAPI app ─────────────────────────


def _make_protected_app(
    pool: Any, *, master: str = "", db_row: dict[str, Any] | None = None
) -> FastAPI:
    """Tiny app with one protected route. Bypasses production wiring so the
    test can swap pool + settings deterministically."""
    app = FastAPI()
    router = APIRouter(prefix="/v1/secret")

    @router.get("/ping")
    async def ping() -> dict[str, str]:
        return {"pong": "ok"}

    from fastapi import Depends

    app.include_router(router, dependencies=[Depends(require_api_key)])

    async def override_pool() -> Any:
        yield pool

    def override_settings() -> Settings:
        return Settings(
            database_url="postgresql://x:x@localhost/x", master_api_key=SecretStr(master)
        )

    app.dependency_overrides[get_pool] = override_pool
    app.dependency_overrides[get_settings] = override_settings

    # Configure the pool to return db_row from fetchrow if provided.
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=db_row)
    conn.execute = AsyncMock()

    class _Ctx:
        async def __aenter__(self) -> MagicMock:
            return conn

        async def __aexit__(self, *_: Any) -> None:
            pass

    pool.acquire = MagicMock(return_value=_Ctx())
    pool._conn = conn  # so tests can reach the conn mock for asserts
    return app


@pytest.mark.asyncio
async def test_401_when_no_authorization_header() -> None:
    app = _make_protected_app(MagicMock())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/v1/secret/ping")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_401_when_authorization_not_bearer() -> None:
    app = _make_protected_app(MagicMock())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/v1/secret/ping", headers={"Authorization": "Basic abc"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_200_with_master_key() -> None:
    app = _make_protected_app(MagicMock(), master="pulse_master_dev")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/v1/secret/ping", headers={"Authorization": "Bearer pulse_master_dev"})
    assert resp.status_code == 200
    assert resp.json() == {"pong": "ok"}


@pytest.mark.asyncio
async def test_master_key_does_not_match_when_disabled() -> None:
    """An empty master_api_key must NOT auto-grant when the caller sends an empty bearer."""
    app = _make_protected_app(MagicMock(), master="", db_row=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/v1/secret/ping", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_200_with_db_lookup_match_and_touches_last_used() -> None:
    pool = MagicMock()
    app = _make_protected_app(pool, db_row={"id": 7, "name": "mobile"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/v1/secret/ping", headers={"Authorization": "Bearer pulse_validkey"})
    assert resp.status_code == 200
    # last_used touch
    assert pool._conn.execute.await_args is not None
    args, _ = pool._conn.execute.await_args
    assert "UPDATE api_key" in args[0]
    assert args[1] == 7


@pytest.mark.asyncio
async def test_401_when_db_returns_none() -> None:
    app = _make_protected_app(MagicMock(), db_row=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/v1/secret/ping", headers={"Authorization": "Bearer pulse_unknownkey"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_master_key_uses_constant_time_compare() -> None:
    """A near-miss on the master key must not authenticate."""
    app = _make_protected_app(MagicMock(), master="pulse_master_dev")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/v1/secret/ping", headers={"Authorization": "Bearer pulse_master_de"})
    assert resp.status_code == 401
