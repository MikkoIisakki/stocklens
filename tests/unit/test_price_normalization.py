"""Unit tests for price normalization."""

from datetime import date

from app.normalization.price import normalize_price_rows


def _row(**kwargs):  # type: ignore[no-untyped-def]
    defaults = {
        "price_date": date(2024, 1, 2),
        "open": 150.0,
        "high": 155.0,
        "low": 148.0,
        "close": 152.0,
        "adj_close": 151.5,
        "volume": 1_000_000,
    }
    return {**defaults, **kwargs}


def test_valid_row_is_passed_through() -> None:
    result = normalize_price_rows([_row()], asset_id=1, ingest_run_id=7)
    assert len(result) == 1
    assert result[0]["close"] == 152.0
    assert result[0]["asset_id"] == 1
    assert result[0]["ingest_run_id"] == 7


def test_missing_close_is_skipped() -> None:
    result = normalize_price_rows([_row(close=None)], asset_id=1, ingest_run_id=1)
    assert result == []


def test_zero_close_is_skipped() -> None:
    result = normalize_price_rows([_row(close=0.0)], asset_id=1, ingest_run_id=1)
    assert result == []


def test_tiny_close_is_skipped() -> None:
    result = normalize_price_rows([_row(close=0.00001)], asset_id=1, ingest_run_id=1)
    assert result == []


def test_none_optional_fields_allowed() -> None:
    result = normalize_price_rows(
        [_row(open=None, high=None, low=None, adj_close=None, volume=None)],
        asset_id=2,
        ingest_run_id=3,
    )
    assert len(result) == 1
    assert result[0]["open"] is None
    assert result[0]["volume"] is None


def test_multiple_rows_mixed_validity() -> None:
    rows = [
        _row(price_date=date(2024, 1, 2), close=100.0),
        _row(price_date=date(2024, 1, 3), close=None),
        _row(price_date=date(2024, 1, 4), close=101.0),
    ]
    result = normalize_price_rows(rows, asset_id=1, ingest_run_id=1)
    assert len(result) == 2
    dates = [r["price_date"] for r in result]
    assert date(2024, 1, 2) in dates
    assert date(2024, 1, 4) in dates


def test_empty_input_returns_empty() -> None:
    assert normalize_price_rows([], asset_id=1, ingest_run_id=1) == []
