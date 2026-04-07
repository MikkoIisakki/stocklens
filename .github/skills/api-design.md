---
name: api-design
description: REST API design conventions, versioning strategy, OpenAPI structure, error response format, and pagination contracts for the recommendator system. For architect use.
---

# API Design

## Conventions

- **Version prefix**: `/v1/` on all endpoints from day one — never break clients by changing unversioned paths
- **Resource naming**: plural nouns, lowercase, hyphen-separated (`/v1/score-snapshots`, not `/v1/scoreSnapshots`)
- **HTTP verbs**: GET (read), POST (create), PUT (full replace), PATCH (partial update), DELETE (deactivate)
- **Response format**: always JSON, always wrapped in a consistent envelope

## Response Envelope

All responses use a consistent structure:

```json
// Success — list
{
  "data": [...],
  "meta": {
    "total": 150,
    "limit": 20,
    "offset": 0
  }
}

// Success — single item
{
  "data": { ... }
}

// Error
{
  "error": {
    "code": "ASSET_NOT_FOUND",
    "message": "Asset 'INVALID' not found",
    "details": {}
  }
}
```

## Pagination

All list endpoints support `limit` and `offset`:

```
GET /v1/assets?limit=20&offset=0
GET /v1/recommendations?limit=10&offset=20&market=US&horizon=long_term
```

Default `limit`: 20. Max `limit`: 100. Always return `meta.total` so clients can paginate.

## Error Codes

Use machine-readable `code` strings alongside HTTP status codes:

| HTTP Status | Code | When |
|---|---|---|
| 400 | `INVALID_PARAMETER` | Bad query param type or value |
| 400 | `MISSING_PARAMETER` | Required param absent |
| 404 | `ASSET_NOT_FOUND` | Symbol doesn't exist in DB |
| 404 | `RULE_NOT_FOUND` | Alert rule ID not found |
| 422 | `VALIDATION_ERROR` | Request body fails Pydantic validation |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 503 | `DATABASE_UNAVAILABLE` | DB connection failed |

## Endpoint Catalogue

### Assets
```
GET  /v1/assets                           List assets (filterable: market, sector, active)
GET  /v1/assets/{symbol}                  Asset detail + latest score
GET  /v1/assets/{symbol}/prices           Price history (params: days, interval)
GET  /v1/assets/{symbol}/fundamentals     Latest fundamental snapshot
GET  /v1/assets/{symbol}/factors          Latest factor snapshot
GET  /v1/assets/{symbol}/score-history    Score over time (params: days, horizon)
```

### Screeners & Rankings
```
GET  /v1/screeners/rising-stocks          Top ranked by composite score
GET  /v1/screeners/value                  Ranked by valuation score
GET  /v1/screeners/momentum               Ranked by relative strength + volume
GET  /v1/screeners/custom                 Arbitrary filter (sector, min_score, market, horizon)
GET  /v1/rankings/daily                   Daily composite ranking snapshot
GET  /v1/rankings/weekly                  Weekly ranking snapshot
```

### Alerts
```
GET  /v1/alerts/rules                     List alert rules
POST /v1/alerts/rules                     Create alert rule
PUT  /v1/alerts/rules/{id}                Update alert rule
DEL  /v1/alerts/rules/{id}                Deactivate alert rule
GET  /v1/alerts/events                    List alert events (params: acknowledged, limit)
POST /v1/alerts/events/{id}/acknowledge   Acknowledge an alert event
```

### Watchlists
```
GET  /v1/watchlists                       List watchlists
POST /v1/watchlists                       Create watchlist
GET  /v1/watchlists/{id}                  Watchlist detail + items
POST /v1/watchlists/{id}/items            Add symbol to watchlist
DEL  /v1/watchlists/{id}/items/{symbol}   Remove symbol from watchlist
```

### System
```
GET  /v1/health                           Liveness: returns 200 if app is running
GET  /v1/health/ready                     Readiness: returns 200 if DB is reachable
GET  /v1/ingest-runs                      Recent ingestion run history + status
```

## OpenAPI / FastAPI Notes

FastAPI generates OpenAPI automatically. Ensure:
- Every endpoint has a `summary` and `description`
- All Pydantic response models have field descriptions
- Error responses documented via `responses={}` parameter
- Tags group endpoints by resource (`assets`, `screeners`, `alerts`, `watchlists`, `system`)

## Query Parameter Conventions

| Pattern | Example | Notes |
|---|---|---|
| Filter | `?market=US` | Exact match, optional |
| Multi-value filter | `?sector=Technology&sector=Energy` | FastAPI `List[str]` param |
| Date range | `?from=2024-01-01&to=2024-03-01` | ISO 8601 dates |
| Numeric range | `?min_score=25&max_score=100` | Inclusive bounds |
| Sorting | `?sort=score&order=desc` | Default sort documented per endpoint |
| Pagination | `?limit=20&offset=0` | Always supported on list endpoints |
