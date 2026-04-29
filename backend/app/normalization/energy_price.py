"""Normalise raw day-ahead price API responses into storage-ready dicts.

Anti-corruption layer: translates provider payloads (currently ENTSO-E) into
the interval-based ``energy_price`` row shape. No I/O. Pure transformation.
"""

from decimal import Decimal
from typing import Any


def normalize_day_ahead_response(
    raw: dict[str, Any],
    *,
    region: dict[str, Any],
    ingest_run_id: int,
) -> list[dict[str, Any]]:
    """Convert a day-ahead price response to ``energy_price`` insert dicts.

    Expects the provider-agnostic shape produced by
    ``ingestion.entsoe_client.fetch_day_ahead``:

        {
            "deliveryDate": "YYYY-MM-DD",
            "currency": "EUR",
            "rows": [
                {"interval_start": <datetime UTC>,
                 "interval_end":   <datetime UTC>,
                 "interval_minutes": 15 | 60 | ...,
                 "value": <float EUR/MWh>},
                ...
            ]
        }

    Args:
        raw: Provider response in the shape above.
        region: ``energy_region`` row dict with ``code``, ``vat_rate``,
            ``electricity_tax_c_kwh``.
        ingest_run_id: FK for the audit trail.

    Returns:
        List of dicts ready for ``repo.upsert_energy_prices``.
        Empty list if the response contains no rows.
    """
    rows = raw.get("rows", [])
    if not rows:
        return []

    region_code: str = region["code"]
    vat_rate = Decimal(str(region["vat_rate"]))
    electricity_tax = Decimal(str(region["electricity_tax_c_kwh"]))

    result = []
    for row in rows:
        price_eur_mwh = Decimal(str(row["value"])).quantize(Decimal("0.0001"))
        spot_c_kwh = (price_eur_mwh / Decimal("10")).quantize(Decimal("0.0001"))
        total_c_kwh = ((spot_c_kwh + electricity_tax) * (1 + vat_rate)).quantize(Decimal("0.0001"))

        result.append(
            {
                "region_code": region_code,
                "ingest_run_id": ingest_run_id,
                "interval_start": row["interval_start"],
                "interval_end": row["interval_end"],
                "interval_minutes": row["interval_minutes"],
                "price_eur_mwh": price_eur_mwh,
                "spot_c_kwh": spot_c_kwh,
                "total_c_kwh": total_c_kwh,
            }
        )

    return result
