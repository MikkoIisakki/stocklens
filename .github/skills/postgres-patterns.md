---
name: postgres-patterns
description: PostgreSQL schema conventions, indexing strategy, query patterns, and asyncpg usage for the pulse project.
---

# PostgreSQL Patterns

## Schema Conventions

- Every table has `created_at TIMESTAMPTZ DEFAULT NOW()`
- PKs: `BIGSERIAL` for append-heavy tables, `TEXT` for reference tables (symbols)
- `asset.symbol` is the universal FK — always `TEXT`, always uppercase (e.g. `'AAPL'`, `'NOKIA.HE'`)
- Snapshot tables have `UNIQUE (symbol, as_of_date)` — use `ON CONFLICT DO UPDATE` (upsert)
- Never store timezone-naive timestamps — always `TIMESTAMPTZ`

## Core Table Patterns

```sql
-- Reference table
CREATE TABLE asset (
    symbol      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    exchange    TEXT NOT NULL,   -- 'NASDAQ', 'NYSE', 'HSE' (Helsinki)
    market      TEXT NOT NULL,   -- 'US', 'FI'
    sector      TEXT,
    industry    TEXT,
    currency    TEXT NOT NULL DEFAULT 'USD',
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Append-heavy price table
CREATE TABLE daily_price (
    id          BIGSERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL REFERENCES asset(symbol),
    date        DATE NOT NULL,
    open        NUMERIC(14,4),
    high        NUMERIC(14,4),
    low         NUMERIC(14,4),
    close       NUMERIC(14,4) NOT NULL,
    volume      BIGINT,
    source      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, date)
);
CREATE INDEX ix_daily_price_symbol_date ON daily_price (symbol, date DESC);

-- Snapshot table pattern (factor, score)
CREATE TABLE factor_snapshot (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL REFERENCES asset(symbol),
    as_of_date      DATE NOT NULL,
    -- factor columns...
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, as_of_date)
);
CREATE INDEX ix_factor_snapshot_symbol_date ON factor_snapshot (symbol, as_of_date DESC);

-- Audit trail
CREATE TABLE raw_source_snapshot (
    id          BIGSERIAL PRIMARY KEY,
    symbol      TEXT,   -- nullable for non-asset data (macro)
    source      TEXT NOT NULL,   -- 'yfinance', 'alphavantage', 'fred', 'finnhub'
    endpoint    TEXT NOT NULL,   -- 'history', 'overview', 'T10Y2Y'
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload     JSONB NOT NULL
);
CREATE INDEX ix_raw_source_snapshot_symbol ON raw_source_snapshot (symbol, fetched_at DESC);
```

## Upsert Pattern

Always use `ON CONFLICT DO UPDATE` for snapshot tables:

```sql
INSERT INTO daily_price (symbol, date, open, high, low, close, volume, source)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (symbol, date) DO UPDATE SET
    open   = EXCLUDED.open,
    high   = EXCLUDED.high,
    low    = EXCLUDED.low,
    close  = EXCLUDED.close,
    volume = EXCLUDED.volume,
    source = EXCLUDED.source;
```

## asyncpg Usage

```python
import asyncpg

# Pool setup (in common/db.py)
async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=2, max_size=10)

# Query patterns
async def get_prices(conn: asyncpg.Connection, symbol: str, days: int):
    return await conn.fetch(
        "SELECT date, close, volume FROM daily_price "
        "WHERE symbol = $1 ORDER BY date DESC LIMIT $2",
        symbol, days
    )

# Bulk insert (use executemany for many rows)
async def insert_prices(conn: asyncpg.Connection, rows: list[dict]):
    await conn.executemany(
        "INSERT INTO daily_price (symbol, date, open, high, low, close, volume, source) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (symbol, date) DO UPDATE SET "
        "close = EXCLUDED.close, volume = EXCLUDED.volume, source = EXCLUDED.source",
        [(r['symbol'], r['date'], r['open'], r['high'], r['low'],
          r['close'], r['volume'], r['source']) for r in rows]
    )

# Transaction
async with conn.transaction():
    await conn.execute("INSERT INTO raw_source_snapshot ...", ...)
    await conn.executemany("INSERT INTO daily_price ...", rows)
```

## Useful Query Patterns

```sql
-- Latest snapshot per symbol
SELECT DISTINCT ON (symbol) symbol, as_of_date, score
FROM score_snapshot
ORDER BY symbol, as_of_date DESC;

-- Top N by score (for ranking endpoint)
SELECT s.symbol, a.name, s.score, s.action
FROM score_snapshot s
JOIN asset a ON a.symbol = s.symbol
WHERE s.as_of_date = CURRENT_DATE
  AND a.active = TRUE
  AND ($1::TEXT IS NULL OR a.market = $1)   -- optional market filter
ORDER BY s.score DESC
LIMIT $2 OFFSET $3;

-- Rolling 20-day average volume (for unusual volume detection)
SELECT symbol, date, volume,
       AVG(volume) OVER (
           PARTITION BY symbol
           ORDER BY date
           ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
       ) AS avg_volume_20d
FROM daily_price
WHERE symbol = $1
ORDER BY date DESC
LIMIT 30;
```

## Migration Convention

Files in `db/migrations/` named `NNN_description.sql`. Run in order. Keep migrations idempotent where possible (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`).
