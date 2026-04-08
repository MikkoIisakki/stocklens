"""Normalise raw yfinance rows into storage-ready dicts.

Keeps validation and transformation out of both the ingestion client
(which only fetches) and the repository (which only persists).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Minimum acceptable close price — filters out stale/zero rows
_MIN_CLOSE = 0.0001


def normalize_price_rows(
    raw_rows: list[dict[str, Any]],
    *,
    asset_id: int,
    ingest_run_id: int,
) -> list[dict[str, Any]]:
    """Convert raw yfinance rows to daily_price insert dicts.

    Skips rows where close is missing or implausibly small.
    Caller is responsible for deduplication (upsert handles it at DB level).
    """
    result = []
    for row in raw_rows:
        close = row.get("close")
        if close is None or close < _MIN_CLOSE:
            logger.warning("Skipping row with bad close=%s for asset_id=%d", close, asset_id)
            continue

        result.append(
            {
                "asset_id": asset_id,
                "ingest_run_id": ingest_run_id,
                "price_date": row["price_date"],
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": close,
                "adj_close": row.get("adj_close"),
                "volume": row.get("volume"),
            }
        )
    return result
