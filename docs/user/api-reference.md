# API Reference

Base URL: `http://localhost:8000` (local) — all endpoints are versioned under `/v1`.

Interactive docs (Swagger UI) are available at `http://localhost:8000/docs`.

---

## Health

### `GET /v1/health/ready`

Returns the readiness status of the system.

**Response**

| Status | HTTP | Meaning |
|---|---|---|
| `ok` | 200 | DB reachable, last ingest within 25 hours |
| `degraded` | 200 | DB reachable, but ingest is stale or has never run |
| `unavailable` | 503 | DB unreachable |

```json
{"status": "ok"}
```

```json
{"status": "degraded", "reason": "ingest stale or never run"}
```

---

## Assets

### `GET /v1/assets`

List all active assets.

**Query parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `market` | string | — | Filter by market: `US` or `FI` |

**Example**

```bash
curl "http://localhost:8000/v1/assets?market=US"
```

**Response** — array of asset objects:

```json
[
  {
    "id": 1,
    "symbol": "AAPL",
    "name": "Apple Inc.",
    "exchange": "NASDAQ",
    "market": "US",
    "currency": "USD"
  }
]
```

**Error responses**

| Code | Reason |
|---|---|
| 400 | `market` is not `US` or `FI` |

---

### `GET /v1/assets/{symbol}/prices`

Return end-of-day price history for one asset.

**Path parameters**

| Parameter | Description |
|---|---|
| `symbol` | Ticker symbol — case-insensitive. Use `NOKIA.HE` for Helsinki tickers. |

**Query parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `from` | date (ISO-8601) | — | Inclusive start date |
| `to` | date (ISO-8601) | — | Inclusive end date |
| `limit` | integer | 90 | Max rows returned. Range: 1–500 |

Results are ordered **newest first**.

**Example**

```bash
# Last 90 trading days
curl http://localhost:8000/v1/assets/AAPL/prices

# Specific date range
curl "http://localhost:8000/v1/assets/AAPL/prices?from=2024-01-01&to=2024-03-31&limit=500"

# Finnish ticker
curl http://localhost:8000/v1/assets/NOKIA.HE/prices
```

**Response** — array of price objects:

```json
[
  {
    "price_date": "2024-01-02",
    "open": 185.23,
    "high": 186.10,
    "low": 183.62,
    "close": 185.85,
    "adj_close": 185.85,
    "volume": 79763200
  }
]
```

| Field | Type | Notes |
|---|---|---|
| `price_date` | date | Trading date |
| `open` | float \| null | Opening price |
| `high` | float \| null | Day high |
| `low` | float \| null | Day low |
| `close` | float | Closing price (always present) |
| `adj_close` | float \| null | Adjusted for splits and dividends |
| `volume` | integer \| null | Number of shares traded |

**Error responses**

| Code | Reason |
|---|---|
| 404 | Symbol not found in the asset universe |
| 422 | `limit` out of range (1–500) |
