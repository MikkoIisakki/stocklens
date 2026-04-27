"""Unit tests for the energy ingest pipeline orchestration.

All external dependencies (HTTP, DB) are mocked.
"""

from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from app.ingestion.energy_ingest import run_energy_ingest


def _fake_entsoe_response(delivery_date: date) -> dict[str, Any]:
    """ENTSO-E client returns the same shape the old Nordpool client did."""
    return {
        "deliveryDateCET": delivery_date.isoformat(),
        "currency": "EUR",
        "rows": [
            {
                "startTime": f"{delivery_date.isoformat()}T{h:02d}:00:00.000Z",
                "endTime": f"{delivery_date.isoformat()}T{h+1:02d}:00:00.000Z",
                "value": 80.0 + h,
            }
            for h in range(24)
        ],
    }


def _fake_region(code: str = "FI") -> dict[str, Any]:
    return {
        "code": code,
        "vat_rate": Decimal("0.255"),
        "electricity_tax_c_kwh": Decimal("2.24"),
        "active": True,
    }


def _mock_pool() -> MagicMock:
    """Pool mock whose acquire() acts as an async context manager."""
    conn = MagicMock()
    pool = MagicMock()

    class _AcquireCtx:
        async def __aenter__(self) -> MagicMock:
            return conn

        async def __aexit__(self, *_: Any) -> None:
            pass

    pool.acquire.return_value = _AcquireCtx()
    return pool


def _settings_with_token(token: str = "test-token") -> MagicMock:
    s = MagicMock()
    s.entsoe_api_token = SecretStr(token)
    return s


@pytest.mark.asyncio
async def test_successful_ingest_creates_run_and_upserts_prices() -> None:
    """Happy path: fetches 24 rows, upserts, finishes run with status=success."""
    target_date = date(2025, 1, 15)

    with (
        patch("app.ingestion.energy_ingest.settings", new=_settings_with_token()),
        patch("app.ingestion.energy_ingest.repo.create_ingest_run", new=AsyncMock(return_value=99)),
        patch(
            "app.ingestion.energy_ingest.repo.get_active_energy_regions",
            new=AsyncMock(return_value=[_fake_region()]),
        ),
        patch(
            "app.ingestion.energy_ingest.fetch_day_ahead",
            new=AsyncMock(return_value=_fake_entsoe_response(target_date)),
        ),
        patch(
            "app.ingestion.energy_ingest.repo.upsert_energy_prices", new=AsyncMock(return_value=24)
        ),
        patch("app.ingestion.energy_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_energy_ingest(_mock_pool(), target_date=target_date)

    mock_finish.assert_awaited_once()
    _, kwargs = mock_finish.call_args
    assert kwargs["status"] == "success"
    assert kwargs["assets_succeeded"] == 24


@pytest.mark.asyncio
async def test_passes_token_to_entsoe_client() -> None:
    """The ENTSOE_API_TOKEN setting is forwarded to fetch_day_ahead."""
    target_date = date(2025, 1, 15)
    fetch_mock = AsyncMock(return_value=_fake_entsoe_response(target_date))

    with (
        patch("app.ingestion.energy_ingest.settings", new=_settings_with_token("my-secret-token")),
        patch("app.ingestion.energy_ingest.repo.create_ingest_run", new=AsyncMock(return_value=1)),
        patch(
            "app.ingestion.energy_ingest.repo.get_active_energy_regions",
            new=AsyncMock(return_value=[_fake_region()]),
        ),
        patch("app.ingestion.energy_ingest.fetch_day_ahead", new=fetch_mock),
        patch(
            "app.ingestion.energy_ingest.repo.upsert_energy_prices", new=AsyncMock(return_value=24)
        ),
        patch("app.ingestion.energy_ingest.repo.finish_ingest_run", new=AsyncMock()),
    ):
        await run_energy_ingest(_mock_pool(), target_date=target_date)

    assert fetch_mock.await_args is not None
    assert fetch_mock.await_args.kwargs["token"] == "my-secret-token"


@pytest.mark.asyncio
async def test_missing_token_marks_run_failed() -> None:
    """An empty ENTSOE_API_TOKEN must fail fast with a clear ingest_run error message."""
    with (
        patch("app.ingestion.energy_ingest.settings", new=_settings_with_token("")),
        patch("app.ingestion.energy_ingest.repo.create_ingest_run", new=AsyncMock(return_value=1)),
        patch(
            "app.ingestion.energy_ingest.repo.get_active_energy_regions", new=AsyncMock()
        ) as mock_regions,
        patch("app.ingestion.energy_ingest.fetch_day_ahead", new=AsyncMock()) as mock_fetch,
        patch("app.ingestion.energy_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_energy_ingest(_mock_pool())

    mock_finish.assert_awaited_once()
    _, kwargs = mock_finish.call_args
    assert kwargs["status"] == "failed"
    assert "ENTSOE_API_TOKEN" in (kwargs["error_message"] or "")
    mock_regions.assert_not_called()
    mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_no_active_regions_marks_run_failed() -> None:
    """If no active energy regions exist, ingest_run is marked failed."""
    with (
        patch("app.ingestion.energy_ingest.settings", new=_settings_with_token()),
        patch("app.ingestion.energy_ingest.repo.create_ingest_run", new=AsyncMock(return_value=1)),
        patch(
            "app.ingestion.energy_ingest.repo.get_active_energy_regions",
            new=AsyncMock(return_value=[]),
        ),
        patch("app.ingestion.energy_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_energy_ingest(_mock_pool())

    mock_finish.assert_awaited_once()
    _, kwargs = mock_finish.call_args
    assert kwargs["status"] == "failed"


@pytest.mark.asyncio
async def test_entsoe_returns_no_rows_marks_run_failed() -> None:
    """If ENTSO-E returns an empty response, ingest_run is marked failed."""
    empty_response: dict[str, Any] = {
        "deliveryDateCET": "2025-01-15",
        "currency": "EUR",
        "rows": [],
    }

    with (
        patch("app.ingestion.energy_ingest.settings", new=_settings_with_token()),
        patch("app.ingestion.energy_ingest.repo.create_ingest_run", new=AsyncMock(return_value=1)),
        patch(
            "app.ingestion.energy_ingest.repo.get_active_energy_regions",
            new=AsyncMock(return_value=[_fake_region()]),
        ),
        patch(
            "app.ingestion.energy_ingest.fetch_day_ahead",
            new=AsyncMock(return_value=empty_response),
        ),
        patch("app.ingestion.energy_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_energy_ingest(_mock_pool())

    mock_finish.assert_awaited_once()
    _, kwargs = mock_finish.call_args
    assert kwargs["status"] == "failed"


@pytest.mark.asyncio
async def test_http_error_marks_run_failed() -> None:
    """If the ENTSO-E HTTP call raises, ingest_run is marked failed."""
    with (
        patch("app.ingestion.energy_ingest.settings", new=_settings_with_token()),
        patch("app.ingestion.energy_ingest.repo.create_ingest_run", new=AsyncMock(return_value=1)),
        patch(
            "app.ingestion.energy_ingest.repo.get_active_energy_regions",
            new=AsyncMock(return_value=[_fake_region()]),
        ),
        patch(
            "app.ingestion.energy_ingest.fetch_day_ahead",
            new=AsyncMock(side_effect=RuntimeError("HTTP 503")),
        ),
        patch("app.ingestion.energy_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_energy_ingest(_mock_pool())

    mock_finish.assert_awaited_once()
    _, kwargs = mock_finish.call_args
    assert kwargs["status"] == "failed"
