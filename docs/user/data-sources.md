# Data Sources

## Yahoo Finance (via yfinance)

All EOD price data is fetched using the [yfinance](https://github.com/ranaroussi/yfinance) library.

| Property | Value |
|---|---|
| Coverage | US (NASDAQ, NYSE) and Finnish (OMX Helsinki) markets |
| Data type | End-of-day OHLCV + adjusted close |
| Frequency | Once daily after market close |
| Lookback per run | 5 days (upsert — no duplicates) |
| US schedule | 21:30 UTC (after NYSE close at 16:00 ET) |
| FI schedule | 17:00 UTC (after Helsinki close at 17:30 EET) |

### Asset universe

**US (50 tickers)** — S&P 500 top holdings + Nasdaq tech:
AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, LLY, JPM, V, XOM, UNH, MA, JNJ, PG, AVGO, MRK, HD, COST, ABBV, CVX, WMT, BAC, KO, PEP, TMO, MCD, CSCO, ACN, ADBE, CRM, NFLX, ABT, WFC, AMD, TXN, QCOM, INTU, ORCL, IBM, AMGN, RTX, HON, NEE, PM, DHR, LIN, INTC, UBER, PYPL

**Finnish (20 tickers)** — OMX Helsinki top names:
NOKIA.HE, NESTE.HE, KNEBV.HE, UPM.HE, STERV.HE, SAMPO.HE, ELISA.HE, WRT1V.HE, METSO.HE, KESKOB.HE, ORNBV.HE, TIE1V.HE, OUT1V.HE, FORTUM.HE, NORDEA.HE, NDA-FI.HE, PIHLIS.HE, QTCOM.HE, KAMUX.HE, REKA.HE

### Known limitations

!!! warning "Terms of service"
    yfinance scrapes Yahoo Finance without an official API key. This is
    acceptable for personal use but **must be reviewed before any commercial
    or SaaS deployment** (see RISK-012 in the risk register).

- **Data quality**: yfinance data may have occasional gaps, stale prices, or
  incorrect adjusted close values around corporate actions.
- **Rate limits**: Yahoo Finance may throttle aggressive polling. The ingest
  pipeline uses a concurrency limit (US: 5, FI: 3 simultaneous requests).
- **No intraday data**: EOD only. Real-time prices are out of scope.
- **Delisted tickers**: Assets marked `active = FALSE` in the database are
  skipped automatically.

### Raw snapshot storage

Every API response is stored verbatim in the `raw_source_snapshot` table
(as JSONB) before being normalised. This enables:

- **Audit trail** — know exactly what was received and when
- **Replay** — re-process historical data without re-fetching
- **Debugging** — diagnose data quality issues after the fact

## Planned future sources (Phase 4)

| Source | Purpose |
|---|---|
| Polygon.io or Alpha Vantage (premium) | Higher-quality OHLCV + fundamentals |
| FRED (fredapi) | Macro indicators (interest rates, inflation) |
| Finnhub | Earnings, analyst ratings |
