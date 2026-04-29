"""Unit tests for the electricity threshold alert engine.

Pure logic tests — no DB, no HTTP. Per ADR-005 prices are interval-based;
alerts record peak_interval_start, not peak_hour.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.alerts.energy import check_threshold_alerts

_REGION_CODE = "FI"
_PRICE_DATE = date(2025, 1, 15)
_DAY_START = datetime(2025, 1, 15, 0, 0, tzinfo=UTC)

_RULE = {
    "id": 1,
    "region_code": _REGION_CODE,
    "threshold_c_kwh": Decimal("30.00"),
    "active": True,
}


def _hourly_prices(peak_total_c_kwh: float, peak_hour: int = 14) -> list[dict]:
    """Build 24 hourly price rows (interval shape) with one configurable peak hour."""
    rows = []
    for h in range(24):
        rows.append(
            {
                "interval_start": _DAY_START + timedelta(hours=h),
                "interval_end": _DAY_START + timedelta(hours=h + 1),
                "interval_minutes": 60,
                "total_c_kwh": Decimal(str(peak_total_c_kwh))
                if h == peak_hour
                else Decimal("10.00"),
            }
        )
    return rows


def _quarter_hour_prices(peak_total_c_kwh: float, peak_index: int = 60) -> list[dict]:
    """Build 96 PT15M price rows with one configurable peak slot."""
    rows = []
    for i in range(96):
        start = _DAY_START + timedelta(minutes=15 * i)
        rows.append(
            {
                "interval_start": start,
                "interval_end": start + timedelta(minutes=15),
                "interval_minutes": 15,
                "total_c_kwh": Decimal(str(peak_total_c_kwh))
                if i == peak_index
                else Decimal("10.00"),
            }
        )
    return rows


def test_alert_fires_when_peak_exceeds_threshold() -> None:
    prices = _hourly_prices(peak_total_c_kwh=35.50, peak_hour=16)
    alerts = check_threshold_alerts(prices, rules=[_RULE], price_date=_PRICE_DATE)
    assert len(alerts) == 1
    assert alerts[0]["rule_id"] == 1
    assert alerts[0]["peak_c_kwh"] == Decimal("35.50")
    assert alerts[0]["peak_interval_start"] == _DAY_START + timedelta(hours=16)
    assert alerts[0]["threshold_c_kwh"] == Decimal("30.00")
    assert alerts[0]["price_date"] == _PRICE_DATE
    assert alerts[0]["region_code"] == _REGION_CODE


def test_no_alert_when_peak_below_threshold() -> None:
    prices = _hourly_prices(peak_total_c_kwh=25.00)
    alerts = check_threshold_alerts(prices, rules=[_RULE], price_date=_PRICE_DATE)
    assert alerts == []


def test_no_alert_when_peak_equals_threshold() -> None:
    prices = _hourly_prices(peak_total_c_kwh=30.00)
    alerts = check_threshold_alerts(prices, rules=[_RULE], price_date=_PRICE_DATE)
    assert alerts == []


def test_no_alert_when_prices_empty() -> None:
    alerts = check_threshold_alerts([], rules=[_RULE], price_date=_PRICE_DATE)
    assert alerts == []


def test_no_alert_when_no_active_rules() -> None:
    inactive_rule = {**_RULE, "active": False}
    prices = _hourly_prices(peak_total_c_kwh=50.00)
    alerts = check_threshold_alerts(prices, rules=[inactive_rule], price_date=_PRICE_DATE)
    assert alerts == []


def test_multiple_rules_each_evaluated_independently() -> None:
    low_rule = {**_RULE, "id": 1, "threshold_c_kwh": Decimal("20.00")}
    high_rule = {**_RULE, "id": 2, "threshold_c_kwh": Decimal("40.00")}
    prices = _hourly_prices(peak_total_c_kwh=35.00)
    alerts = check_threshold_alerts(prices, rules=[low_rule, high_rule], price_date=_PRICE_DATE)
    assert len(alerts) == 1
    assert alerts[0]["rule_id"] == 1


def test_negative_prices_do_not_trigger_alert() -> None:
    prices = [
        {
            "interval_start": _DAY_START + timedelta(hours=h),
            "interval_end": _DAY_START + timedelta(hours=h + 1),
            "interval_minutes": 60,
            "total_c_kwh": Decimal("-5.00"),
        }
        for h in range(24)
    ]
    alerts = check_threshold_alerts(prices, rules=[_RULE], price_date=_PRICE_DATE)
    assert alerts == []


def test_quarter_hourly_prices_resolve_peak_slot() -> None:
    """At PT15M cadence the peak is reported with the exact 15-min slot start."""
    prices = _quarter_hour_prices(peak_total_c_kwh=42.0, peak_index=70)
    alerts = check_threshold_alerts(prices, rules=[_RULE], price_date=_PRICE_DATE)
    assert len(alerts) == 1
    assert alerts[0]["peak_interval_start"] == _DAY_START + timedelta(minutes=15 * 70)
    assert alerts[0]["peak_c_kwh"] == Decimal("42.0")
