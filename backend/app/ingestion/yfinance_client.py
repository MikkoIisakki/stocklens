"""Thin async wrapper around yfinance.

yfinance is synchronous and CPU-bound (network + pandas). We run it in a
thread pool executor so it doesn't block the event loop.
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 5  # fetch a small window — we upsert so duplicates are fine


def _fetch_sync(symbol: str, start: date, end: date) -> dict[str, Any]:
    """Download OHLCV history for one symbol. Runs in a thread."""
    ticker = yf.Ticker(symbol)
    df = ticker.history(
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=False,  # keep separate Adj Close column
        actions=False,
    )
    if df.empty:
        return {"symbol": symbol, "rows": []}

    # DatetimeIndex → plain date objects for serialisability
    df.index = df.index.date
    rows = []
    for price_date, row in df.iterrows():
        rows.append(
            {
                "price_date": price_date,
                "open": float(row["Open"]) if row["Open"] == row["Open"] else None,
                "high": float(row["High"]) if row["High"] == row["High"] else None,
                "low": float(row["Low"]) if row["Low"] == row["Low"] else None,
                "close": float(row["Close"]),
                "adj_close": float(row["Adj Close"]) if "Adj Close" in row else None,
                "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else None,
            }
        )
    return {"symbol": symbol, "rows": rows}


async def fetch_eod(
    symbol: str,
    *,
    lookback_days: int = _LOOKBACK_DAYS,
) -> dict[str, Any]:
    """Fetch recent EOD prices for *symbol* and return a serialisable dict.

    Returns ``{"symbol": symbol, "rows": [...]}``.  The ``rows`` list may be
    empty if the symbol returned no data (e.g. non-trading day, bad ticker).
    """
    end = date.today()
    start = end - timedelta(days=lookback_days)
    loop = asyncio.get_running_loop()
    result: dict[str, Any] = await loop.run_in_executor(None, _fetch_sync, symbol, start, end)
    logger.debug("yfinance %s: %d rows", symbol, len(result["rows"]))
    return result
