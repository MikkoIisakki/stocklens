"""Unit tests for energy price normalisation.

Tests pure functions only — no DB, no HTTP. Per ADR-005 the normalised rows
carry interval_start/interval_end/interval_minutes (not hour/price_date).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.normalization.energy_price import normalize_day_ahead_response

# ─── Fixtures ─────────────────────────────────────────────────────────────────

_REGION_FI = {
    "code": "FI",
    "vat_rate": Decimal("0.255"),
    "electricity_tax_c_kwh": Decimal("2.24"),
}


def _hourly_response(prices: list[float]) -> dict[str, object]:
    base = datetime(2025, 1, 15, 0, 0, tzinfo=UTC)
    return {
        "deliveryDate": "2025-01-15",
        "currency": "EUR",
        "rows": [
            {
                "interval_start": base + timedelta(hours=h),
                "interval_end": base + timedelta(hours=h + 1),
                "interval_minutes": 60,
                "value": v,
            }
            for h, v in enumerate(prices)
        ],
    }


def _quarter_hourly_response(prices: list[float]) -> dict[str, object]:
    rows = []
    for i, v in enumerate(prices):
        start = datetime(2025, 1, 15, 0, 0, tzinfo=UTC) + timedelta(minutes=15 * i)
        end = start + timedelta(minutes=15)
        rows.append(
            {
                "interval_start": start,
                "interval_end": end,
                "interval_minutes": 15,
                "value": v,
            }
        )
    return {"deliveryDate": "2025-01-15", "currency": "EUR", "rows": rows}


_VALID_HOURLY_RESPONSE = _hourly_response([80.00 + h for h in range(24)])


# ─── Tests ────────────────────────────────────────────────────────────────────


def test_returns_24_rows_for_full_hourly_day() -> None:
    prices = normalize_day_ahead_response(
        _VALID_HOURLY_RESPONSE, region=_REGION_FI, ingest_run_id=1
    )
    assert len(prices) == 24


def test_interval_fields_passed_through() -> None:
    prices = normalize_day_ahead_response(
        _VALID_HOURLY_RESPONSE, region=_REGION_FI, ingest_run_id=1
    )
    first = prices[0]
    assert first["interval_start"] == datetime(2025, 1, 15, 0, 0, tzinfo=UTC)
    assert first["interval_end"] == datetime(2025, 1, 15, 1, 0, tzinfo=UTC)
    assert first["interval_minutes"] == 60


def test_spot_c_kwh_is_eur_mwh_divided_by_10() -> None:
    prices = normalize_day_ahead_response(
        _VALID_HOURLY_RESPONSE, region=_REGION_FI, ingest_run_id=1
    )
    first = prices[0]
    expected_spot = Decimal("80.00") / Decimal("10")
    assert first["spot_c_kwh"] == expected_spot


def test_total_c_kwh_includes_tax_and_vat() -> None:
    prices = normalize_day_ahead_response(
        _VALID_HOURLY_RESPONSE, region=_REGION_FI, ingest_run_id=1
    )
    first = prices[0]
    spot = Decimal("80.00") / Decimal("10")
    tax = Decimal("2.24")
    vat = Decimal("0.255")
    expected_total = ((spot + tax) * (1 + vat)).quantize(Decimal("0.0001"))
    assert first["total_c_kwh"] == expected_total


def test_negative_price_produces_valid_row() -> None:
    response = _hourly_response([-15.00])
    prices = normalize_day_ahead_response(response, region=_REGION_FI, ingest_run_id=1)
    assert len(prices) == 1
    assert prices[0]["price_eur_mwh"] == Decimal("-15.00")
    assert prices[0]["spot_c_kwh"] == Decimal("-1.50")


def test_region_code_copied_to_each_row() -> None:
    prices = normalize_day_ahead_response(
        _VALID_HOURLY_RESPONSE, region=_REGION_FI, ingest_run_id=1
    )
    assert all(p["region_code"] == "FI" for p in prices)


def test_ingest_run_id_copied_to_each_row() -> None:
    prices = normalize_day_ahead_response(
        _VALID_HOURLY_RESPONSE, region=_REGION_FI, ingest_run_id=42
    )
    assert all(p["ingest_run_id"] == 42 for p in prices)


def test_empty_rows_returns_empty_list() -> None:
    response = {"deliveryDate": "2025-01-15", "currency": "EUR", "rows": []}
    prices = normalize_day_ahead_response(response, region=_REGION_FI, ingest_run_id=1)
    assert prices == []


def test_pt15m_response_preserves_interval_minutes() -> None:
    """A PT15M provider response normalises to 96 rows with interval_minutes=15."""
    response = _quarter_hourly_response([10.0] * 96)
    prices = normalize_day_ahead_response(response, region=_REGION_FI, ingest_run_id=1)
    assert len(prices) == 96
    assert all(p["interval_minutes"] == 15 for p in prices)
    # First and last slots cover the whole 24h window
    assert prices[0]["interval_start"] == datetime(2025, 1, 15, 0, 0, tzinfo=UTC)
    assert prices[-1]["interval_end"] == datetime(2025, 1, 16, 0, 0, tzinfo=UTC)
