"""Electricity threshold alert engine.

Pure domain logic — no I/O. Given a list of interval price rows and a list of
alert rules, returns alert dicts for any rules whose threshold is breached.

Callers (ingest pipeline) are responsible for persisting the returned dicts
via repo.save_energy_alerts() and for loading active rules from the DB.
"""

from datetime import date
from decimal import Decimal
from typing import Any


def check_threshold_alerts(
    prices: list[dict[str, Any]],
    *,
    rules: list[dict[str, Any]],
    price_date: date,
) -> list[dict[str, Any]]:
    """Evaluate threshold rules against interval price data for one date.

    Args:
        prices: Interval price dicts with at least ``interval_start`` and
            ``total_c_kwh`` keys (any cadence — 15-min, hourly, daily).
        rules:  Active energy_alert_rule rows (must have id, region_code,
                threshold_c_kwh, active).
        price_date: The delivery date the prices belong to.

    Returns:
        List of alert dicts ready for ``repo.save_energy_alerts()``.
        Empty list if no rules are breached or prices is empty.
    """
    if not prices or not rules:
        return []

    peak_row = max(prices, key=lambda r: r["total_c_kwh"])
    peak_c_kwh: Decimal = peak_row["total_c_kwh"]
    peak_interval_start = peak_row["interval_start"]

    alerts = []
    for rule in rules:
        if not rule.get("active", True):
            continue
        threshold: Decimal = Decimal(str(rule["threshold_c_kwh"]))
        if peak_c_kwh > threshold:
            alerts.append(
                {
                    "rule_id": rule["id"],
                    "region_code": rule["region_code"],
                    "price_date": price_date,
                    "peak_c_kwh": peak_c_kwh,
                    "peak_interval_start": peak_interval_start,
                    "threshold_c_kwh": threshold,
                }
            )

    return alerts
