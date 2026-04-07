---
name: observability
description: Logging standards, health check design, pipeline staleness detection, and what "the system is healthy" means for each component. For architect and devops use.
---

# Observability

## What "Healthy" Means Per Component

| Component | Healthy when | Unhealthy signal |
|---|---|---|
| **API** | Responds to `/v1/health/ready` in < 500ms | DB unreachable, response > 2s |
| **Scheduler** | Ingest jobs published within 5 min of scheduled time | No jobs published for > 1h during market hours |
| **Worker** | Processes jobs with < 30 min lag | Job queue grows, no completions in > 1h |
| **Ingestion** | `ingest_run` row written with `status=success` within 2h of market close | `status=failed` or no row for today |
| **Scoring** | `score_snapshot` rows written for all active assets by 19:00 local | Missing rows or `as_of_date` = yesterday |
| **Database** | `pg_isready` passes, query latency < 50ms | Connection refused, slow queries |
| **Data freshness** | `daily_price.date` = today for all active assets by 19:00 | Stale dates — data source may be down |

## Logging Standards

Use structured JSON logging in all services. Never use `print()`.

```python
import logging
import json

# Standard fields in every log record
{
  "timestamp": "2026-04-07T10:00:00Z",   # ISO 8601 UTC
  "level": "INFO",                         # DEBUG / INFO / WARNING / ERROR / CRITICAL
  "service": "worker",                     # service name
  "module": "ingestion.yfinance",          # Python module path
  "event": "price_ingestion_complete",     # snake_case event name
  "symbol": "AAPL",                        # domain context fields
  "rows_written": 252,
  "duration_ms": 430,
  "source": "yfinance"
}
```

**Log levels**:
- `DEBUG` — per-row detail, timing internals (off in production)
- `INFO` — job started/completed, rows written, scores computed
- `WARNING` — recoverable issues: missing data field, API rate limit approaching, stale data detected
- `ERROR` — failed ingest for a specific asset, unexpected API response, DB write failed
- `CRITICAL` — total pipeline failure, DB unreachable, scheduler crashed

**Never log**: API keys, passwords, personal data, raw API response payloads (those go in `raw_source_snapshot`)

## Pipeline Staleness Detection

The Grafana pipeline dashboard queries these to detect staleness:

```sql
-- Assets with no price data today
SELECT a.symbol, a.market, MAX(dp.date) AS last_price_date
FROM asset a
LEFT JOIN daily_price dp ON dp.symbol = a.symbol
WHERE a.active = TRUE
GROUP BY a.symbol, a.market
HAVING MAX(dp.date) < CURRENT_DATE
ORDER BY last_price_date ASC NULLS FIRST;

-- Missing score snapshots for today
SELECT a.symbol
FROM asset a
WHERE a.active = TRUE
  AND NOT EXISTS (
    SELECT 1 FROM score_snapshot ss
    WHERE ss.symbol = a.symbol
      AND ss.as_of_date = CURRENT_DATE
  );

-- Recent ingest run failures
SELECT source, started_at, status, error_message
FROM ingest_run
WHERE started_at > NOW() - INTERVAL '24 hours'
  AND status = 'failed'
ORDER BY started_at DESC;
```

## Health Check Endpoints

```
GET /v1/health
→ 200 always (liveness — is the process running?)
→ {"status": "ok"}

GET /v1/health/ready
→ 200 if DB reachable + last ingest_run < 25h ago
→ 503 if DB unreachable
→ {"status": "ok" | "degraded" | "unavailable", "checks": {...}}
```

Readiness response body:
```json
{
  "status": "degraded",
  "checks": {
    "database": "ok",
    "last_ingest_us": "2026-04-06T17:30:00Z",
    "last_ingest_fi": "2026-04-06T19:15:00Z",
    "stale_assets": 3
  }
}
```

## `ingest_run` Table

Every scheduled job writes an `ingest_run` record:

```sql
CREATE TABLE ingest_run (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,           -- 'yfinance_us', 'yfinance_fi', 'alphavantage', 'fred', 'finnhub'
    job_type        TEXT NOT NULL,           -- 'daily_prices', 'fundamentals', 'macro', 'news'
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running',  -- 'running', 'success', 'partial', 'failed'
    assets_attempted INT,
    assets_succeeded INT,
    assets_failed    INT,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Grafana Alert Rules (System Health)

Configure in Grafana (not application alert_rule table — these are infra alerts):

| Alert | Query | Threshold |
|---|---|---|
| Stale US prices | Count assets with last price > 1 day ago | > 0 after 19:00 ET |
| Failed ingest run | Count failed ingest_runs in last 24h | > 0 |
| Missing scores | Count assets with no score today | > 0 after 20:00 ET |
| API slow | `/v1/health/ready` response time | > 1000ms |
