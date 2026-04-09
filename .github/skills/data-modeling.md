---
name: data-modeling
description: Conceptual, logical, and physical data modeling approach for the pulse system. Schema evolution strategy and normalization trade-offs. For architect use.
---

# Data Modeling

## Three Levels of Data Modeling

### Conceptual Model
Business entities and their relationships — no technical detail, no column types.

```
Asset ──< DailyPrice          (one asset has many daily prices)
Asset ──< FactorSnapshot      (one asset has many factor snapshots, one per day)
Asset ──< ScoreSnapshot       (one asset has many score snapshots, one per day per horizon)
Asset ──< Fundamental         (one asset has many quarterly fundamental snapshots)
Asset ──< NewsItem            (one asset has many news items)
Asset ──< AlertEvent          (one asset triggers many alert events)
AlertRule ──< AlertEvent      (one rule generates many events)
IngestRun ──< RawSourceSnapshot (one run produces many raw snapshots)
```

### Logical Model
Entities with attributes and relationships — database-agnostic, no implementation types yet.

| Entity | Key Attributes | Relationships |
|---|---|---|
| Asset | symbol (PK), name, exchange, market, sector, currency, active | Parent of all market data |
| DailyPrice | (symbol, date) PK, OHLCV, source | Belongs to Asset |
| RawSourceSnapshot | id PK, symbol, source, endpoint, fetched_at, payload | Audit trail for all ingested data |
| IngestRun | id PK, source, started_at, finished_at, status, assets_processed | Operational log |
| FactorSnapshot | (symbol, as_of_date) PK, all factor columns, computed_at | Belongs to Asset, one per day |
| ScoreSnapshot | (symbol, as_of_date, horizon) PK, score, action, confidence, factor_contributions | Belongs to Asset, one per day per horizon |
| Fundamental | (symbol, report_date) PK, income/balance/cash flow fields | Belongs to Asset, one per quarter |
| EarningsEvent | id PK, symbol, event_date, reported_eps, estimated_eps, surprise_pct | Belongs to Asset |
| InsiderTrade | id PK, symbol, trade_date, insider_name, trade_type, shares, value | Belongs to Asset |
| AnalystRevision | id PK, symbol, revision_date, analyst, old_target, new_target, rating | Belongs to Asset |
| NewsItem | id PK, symbol, published_at, headline, url, sentiment_score, source | Belongs to Asset (nullable for market news) |
| MacroIndicator | (series_id, date) PK, value | No asset relationship |
| AlertRule | id PK, name, symbol (nullable), market, metric, operator, threshold, active | Parent of AlertEvent |
| AlertEvent | id PK, rule_id, symbol, triggered_at, value, threshold, message, acknowledged | Belongs to AlertRule + Asset |
| Watchlist | id PK, name, created_at | — |
| WatchlistItem | (watchlist_id, symbol) PK | Belongs to Watchlist + Asset |

### Physical Model
PostgreSQL-specific implementation. See `postgres-patterns` skill for SQL DDL conventions.

---

## Normalization Strategy

**Normalize** reference and transactional data (asset master, daily prices, fundamentals) to avoid update anomalies.

**Denormalize deliberately** for read-heavy snapshot tables (`factor_snapshot`, `score_snapshot`) — pre-join data so the read path needs no joins.

**JSONB for flexibility** in two places:
- `raw_source_snapshot.payload` — stores full API response; structure varies per source
- `score_snapshot.factor_contributions` — stores per-factor breakdown; schema evolves as factors are added

---

## Schema Evolution Strategy

### Additive changes (safe, no migration risk)
- Adding nullable columns to existing tables
- Adding new tables
- Adding indexes

### Breaking changes (require migration plan)
- Renaming columns (requires dual-write period or coordinated deploy)
- Changing column types
- Removing columns
- Changing unique constraints

### Migration conventions
- Files in `db/migrations/` named `NNN_description.sql`
- Each migration is idempotent (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`)
- Never modify a past migration — always add a new one
- Migrations run in CI against a clean DB to verify they apply cleanly

---

## Key Design Decisions

### Why `(symbol, as_of_date)` as snapshot PK
Snapshot tables are written once per day per asset. The composite key enforces exactly-one-row-per-day and enables efficient `DISTINCT ON (symbol) ORDER BY as_of_date DESC` queries for "latest snapshot per asset" without a subquery.

### Why `horizon` in `score_snapshot`
Long-term and short-term scores use different factor weights and serve different user intents. Storing both allows the API to filter by horizon and lets the user see both views of the same asset.

### Why `raw_source_snapshot` is non-negotiable
External APIs change without notice (field renames, value format changes, data gaps). Storing the raw payload means:
1. Any normalization bug can be fixed by re-processing stored payloads without re-fetching
2. Full audit trail: every derived value can be traced to its source

### Why `factor_contributions` in `score_snapshot` is JSONB
The set of factors evolves as new signals are added. JSONB avoids schema migration every time a factor is added or renamed. The trade-off is no column-level indexing on individual factors — acceptable because factor breakdown is a display concern, not a query filter.
