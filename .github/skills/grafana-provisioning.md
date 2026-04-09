---
name: grafana-provisioning
description: How to provision Grafana datasources and dashboards as code for the stocklens project.
---

# Grafana Provisioning

All Grafana configuration is code — no manual click-ops. Files live in `services/grafana/provisioning/`.

## Directory Structure

```
services/grafana/provisioning/
  datasources/
    postgres.yaml
  dashboards/
    dashboards.yaml        ← provider config
    pipeline.json
    market.json
    fundamentals.json
    alerts.json
```

## Datasource: PostgreSQL

`services/grafana/provisioning/datasources/postgres.yaml`:

```yaml
apiVersion: 1
datasources:
  - name: PostgreSQL
    type: postgres
    url: db:5432
    database: stocks
    user: stocks
    secureJsonData:
      password: "${DB_PASSWORD}"
    jsonData:
      sslmode: disable
      postgresVersion: 1600
      timescaledb: false
    isDefault: true
    editable: false
```

## Dashboard Provider

`services/grafana/provisioning/dashboards/dashboards.yaml`:

```yaml
apiVersion: 1
providers:
  - name: stocklens
    folder: Stocklens
    type: file
    disableDeletion: true
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
      foldersFromFilesStructure: true
```

## Dashboard JSON Structure

Minimum required fields for a valid dashboard JSON:

```json
{
  "__inputs": [],
  "__requires": [],
  "annotations": {"list": []},
  "description": "Dashboard description",
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [],
  "refresh": "5m",
  "schemaVersion": 39,
  "tags": ["stocklens"],
  "templating": {"list": []},
  "time": {"from": "now-30d", "to": "now"},
  "timepicker": {},
  "timezone": "browser",
  "title": "Dashboard Title",
  "uid": "unique-uid-here",
  "version": 1
}
```

## Panel SQL Examples

**Top recommendations table**:
```sql
SELECT
    a.symbol,
    a.name,
    s.score,
    s.action,
    s.confidence,
    s.as_of_date
FROM score_snapshot s
JOIN asset a ON a.symbol = s.symbol
WHERE s.as_of_date = CURRENT_DATE
  AND s.horizon = 'long_term'
ORDER BY s.score DESC
LIMIT 20
```

**Price chart** (time series panel):
```sql
SELECT
    date AS time,
    close
FROM daily_price
WHERE symbol = '$symbol'
  AND date >= NOW() - INTERVAL '90 days'
ORDER BY date
```

**RSI over time**:
```sql
SELECT
    as_of_date AS time,
    rsi_14
FROM factor_snapshot
WHERE symbol = '$symbol'
ORDER BY as_of_date
```

**Pipeline health**:
```sql
SELECT
    source,
    MAX(fetched_at) AS last_fetch,
    COUNT(*) AS snapshots_today
FROM raw_source_snapshot
WHERE fetched_at::date = CURRENT_DATE
GROUP BY source
ORDER BY source
```

## Template Variables

Add a `$symbol` variable backed by SQL:

```sql
SELECT DISTINCT symbol FROM asset WHERE active = TRUE ORDER BY symbol
```

Add a `$market` variable:
```sql
SELECT DISTINCT market FROM asset ORDER BY market
```

## Tips

- Set `"refresh": "5m"` on pipeline/alert dashboards, `"1h"` on market dashboards
- Use `"datasource": {"type": "postgres", "uid": "${DS_POSTGRESQL}"}` in panels
- Grafana reads provisioning files every 30s — no restart needed to pick up new dashboards
- `uid` must be unique per dashboard and stable — use a short descriptive slug
