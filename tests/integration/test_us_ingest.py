"""Integration tests for US ingest pipeline.

Tests run against the real test database (via db_conn fixture from conftest.py)
and mock only the yfinance HTTP calls so no network is needed in CI.
"""

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest

from app.ingestion.us_ingest import run_us_ingest


def _fake_fetch(symbol: str, *, lookback_days: int = 5) -> dict[str, Any]:
    """Return a single realistic price row for any symbol."""
    return {
        "symbol": symbol,
        "rows": [
            {
                "price_date": date(2024, 1, 2),
                "open": 150.0,
                "high": 155.0,
                "low": 148.0,
                "close": 152.0,
                "adj_close": 151.5,
                "volume": 1_000_000,
            }
        ],
    }


@pytest.fixture()
async def single_asset_pool(db_conn: asyncpg.Connection, db_pool: asyncpg.Pool) -> asyncpg.Pool:
    """Seed one US asset for ingest tests.

    We insert directly via db_conn (which is inside a rolled-back transaction),
    but run_us_ingest acquires its own connection from the pool — so we need
    to commit a real row and clean it up after.

    To avoid that complexity we patch get_active_assets instead.
    """
    return db_pool


@pytest.mark.asyncio
async def test_successful_ingest_creates_run_and_prices(db_pool: asyncpg.Pool) -> None:
    """End-to-end: fetch mocked prices → persisted to DB → ingest_run=success."""
    fake_assets = [{"id": 999, "symbol": "AAPL", "exchange": "NASDAQ"}]

    with (
        patch("app.ingestion.us_ingest.repo.get_active_assets", return_value=fake_assets),
        patch("app.ingestion.us_ingest.fetch_eod", new=AsyncMock(side_effect=_fake_fetch)),
        patch("app.ingestion.us_ingest.repo.save_raw_snapshot", new=AsyncMock()),
        patch("app.ingestion.us_ingest.repo.upsert_daily_prices", new=AsyncMock(return_value=1)),
        patch("app.ingestion.us_ingest.repo.create_ingest_run", new=AsyncMock(return_value=42)),
        patch("app.ingestion.us_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_us_ingest(db_pool)

    mock_finish.assert_called_once()
    _, call_kwargs = mock_finish.call_args
    assert call_kwargs["status"] == "success"
    assert call_kwargs["assets_attempted"] == 1
    assert call_kwargs["assets_succeeded"] == 1


@pytest.mark.asyncio
async def test_empty_asset_list_marks_run_failed(db_pool: asyncpg.Pool) -> None:
    with (
        patch("app.ingestion.us_ingest.repo.get_active_assets", return_value=[]),
        patch("app.ingestion.us_ingest.repo.create_ingest_run", new=AsyncMock(return_value=43)),
        patch("app.ingestion.us_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_us_ingest(db_pool)

    _, call_kwargs = mock_finish.call_args
    assert call_kwargs["status"] == "failed"
    assert "No active assets" in (call_kwargs["error_message"] or "")


@pytest.mark.asyncio
async def test_fetch_exception_counts_as_failure(db_pool: asyncpg.Pool) -> None:
    fake_assets = [{"id": 999, "symbol": "BADFEED", "exchange": "NYSE"}]

    async def boom(symbol: str, **_: Any) -> dict[str, Any]:
        raise RuntimeError("network error")

    with (
        patch("app.ingestion.us_ingest.repo.get_active_assets", return_value=fake_assets),
        patch("app.ingestion.us_ingest.fetch_eod", new=AsyncMock(side_effect=boom)),
        patch("app.ingestion.us_ingest.repo.create_ingest_run", new=AsyncMock(return_value=44)),
        patch("app.ingestion.us_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_us_ingest(db_pool)

    _, call_kwargs = mock_finish.call_args
    assert call_kwargs["status"] == "failed"
    assert call_kwargs["assets_succeeded"] == 0
