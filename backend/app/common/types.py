"""Shared domain types used across module boundaries.

Only primitive building blocks belong here. Domain-specific types live
in their own modules (e.g. storage/models.py, signals/models.py).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import NewType

AssetSymbol = NewType("AssetSymbol", str)


@dataclass(frozen=True)
class EnergyRegion:
    """Nordpool bidding zone with country-specific tax and VAT parameters."""

    code: str  # e.g. "FI", "SE3"
    name: str
    country: str  # ISO 3166-1 alpha-2
    vat_rate: Decimal  # e.g. Decimal("0.255")
    electricity_tax_c_kwh: Decimal  # government excise tax in c/kWh; 0 if not applicable
    active: bool = True


@dataclass(frozen=True)
class EnergyPrice:
    """Hourly day-ahead electricity spot price for a Nordpool bidding zone."""

    region_code: str
    price_date: date
    hour: int  # 0-23 (local delivery hour)
    price_eur_mwh: Decimal  # raw Nordpool spot price; can be negative
    spot_c_kwh: Decimal  # price_eur_mwh / 10, spot only, excl. tax + VAT
    total_c_kwh: Decimal  # (spot + electricity_tax) x (1 + vat_rate); excl. distribution/margin
