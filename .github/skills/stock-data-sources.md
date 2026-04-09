---
name: stock-data-sources
description: API quirks, rate limits, and usage patterns for all free data sources used in the pulse project.
---

# Stock Data Sources

Reference for all free data sources. Check here before writing any ingestion code.

## yfinance (primary price source)

No API key required. Unofficial Yahoo Finance wrapper.

```python
import yfinance as yf

# Single ticker
ticker = yf.Ticker("AAPL")

# OHLCV history
df = ticker.history(period="1y", interval="1d")
# Returns DataFrame with: Open, High, Low, Close, Volume, Dividends, Stock Splits
# Index is DatetimeIndex (timezone-aware, US/Eastern for US, Europe/Helsinki for .HE)

# Fundamentals
info = ticker.info          # dict with 100+ fields — inconsistent, check for None
financials = ticker.financials      # quarterly income statement (DataFrame)
balance_sheet = ticker.balance_sheet
cash_flow = ticker.cashflow

# Multiple tickers at once (more efficient)
data = yf.download(["AAPL", "MSFT"], period="1y", interval="1d")
```

**Rate limits**: Unofficial, no documented limit. ~2000 requests/hour observed safe. Add 0.5s sleep between bulk downloads.

**Known quirks**:
- `ticker.info` returns empty dict silently on unknown tickers — always check `info.get('regularMarketPrice')` is not None
- Finnish tickers use `.HE` suffix: `"NOKIA.HE"`, `"STERV.HE"`
- Dividends and splits are included in `history()` — exclude with `auto_adjust=True` (default) or handle separately
- Delisted tickers return empty DataFrame, not an error

## Alpha Vantage (fundamentals + technicals supplement)

Free tier: **25 requests/day** (no key) or **500 requests/day** (free API key).
Get key at: https://www.alphavantage.co/support/#api-key

```python
import requests

BASE = "https://www.alphavantage.co/query"

# Company overview (P/E, EPS, revenue, etc.)
r = requests.get(BASE, params={
    "function": "OVERVIEW",
    "symbol": "AAPL",
    "apikey": API_KEY
})
data = r.json()
# Key fields: PERatio, EPS, RevenuePerShareTTM, ProfitMargin, ReturnOnEquityTTM
# All values are strings — cast to float, handle "None" string

# Income statement
r = requests.get(BASE, params={
    "function": "INCOME_STATEMENT",
    "symbol": "AAPL",
    "apikey": API_KEY
})
```

**Rate limit enforcement**: Track daily usage in a counter. Prioritize most-changed assets.

**Known quirks**:
- All numeric values returned as strings, including `"None"` for missing data
- Finnish tickers not supported — US only
- `OVERVIEW` endpoint is the most useful for fundamentals screening

## FRED (Federal Reserve Economic Data)

Free, requires API key. 120 requests/minute.
Get key at: https://fred.stlouisfed.org/docs/api/api_key.html

```python
from fredapi import Fred

fred = Fred(api_key=FRED_KEY)

# Key series for macro context
series = {
    "T10Y2Y":    "10Y-2Y yield spread (recession indicator)",
    "UNRATE":    "Unemployment rate",
    "CPIAUCSL":  "CPI (inflation)",
    "FEDFUNDS":  "Fed funds rate",
    "SP500":     "S&P 500 index level",
    "VIXCLS":    "VIX volatility index",
}

df = fred.get_series("T10Y2Y", observation_start="2020-01-01")
# Returns pandas Series with DatetimeIndex
```

**Update frequency**: Most series update monthly or weekly — fetch weekly, not daily.

## Finnhub (news + sentiment)

Free tier: 60 requests/minute.
Get key at: https://finnhub.io/register

```python
import finnhub

client = finnhub.Client(api_key=FINNHUB_KEY)

# Company news (last 7 days)
news = client.company_news("AAPL",
    _from="2024-01-01",
    to="2024-01-07"
)
# Returns list of dicts: headline, summary, url, datetime, sentiment (if available)

# Basic financials
metrics = client.company_basic_financials("AAPL", "all")
```

**Known quirks**:
- Finnish stocks have limited coverage
- Sentiment field is not always present — fall back to lexicon-based scoring
- News deduplication needed — same story appears multiple times

## Data Source Priority

| Data type | Primary | Fallback |
|---|---|---|
| US OHLCV EOD | yfinance | Alpha Vantage |
| Finnish OHLCV | yfinance (.HE) | None (yfinance only) |
| Fundamentals | yfinance `.info` | Alpha Vantage OVERVIEW |
| Income statement | yfinance `.financials` | Alpha Vantage INCOME_STATEMENT |
| News | Finnhub | yfinance `.news` |
| Macro indicators | FRED | None |
