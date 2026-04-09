---
name: performance-testing
description: API load testing with k6, Python profiling, PostgreSQL query analysis, and performance benchmarking strategy for the pulse system. For engineer and devops use.
---

# Performance Testing

## When to Run Performance Tests

- Before deploying to the Droplet for the first time (Phase 3)
- After any change to a query in `storage/` that touches large tables
- When adding a new API endpoint used in screener or ranking queries
- After the ticker universe grows significantly (>200 tickers)

---

## API Load Testing with k6

k6 is the tool of choice — JavaScript-based, CLI-driven, CI-compatible.

### Install
```bash
brew install k6          # macOS
# or via Docker: docker run -i grafana/k6 run - <script.js
```

### Baseline script (`tests/performance/api_baseline.js`)

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '30s', target: 10 },   // ramp up
    { duration: '1m',  target: 10 },   // sustained load
    { duration: '15s', target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<200'],   // NFR: p95 < 200ms
    errors:            ['rate<0.01'],   // < 1% error rate
  },
};

const BASE = 'http://localhost:8000';

export default function () {
  // Test ranking endpoint — heaviest expected query
  let r = http.get(`${BASE}/v1/rankings/daily?limit=20`);
  check(r, { 'rankings 200': (res) => res.status === 200 });
  errorRate.add(r.status !== 200);

  sleep(0.5);

  // Test asset detail
  r = http.get(`${BASE}/v1/assets/AAPL`);
  check(r, { 'asset detail 200': (res) => res.status === 200 });

  sleep(0.5);

  // Test screener
  r = http.get(`${BASE}/v1/screeners/rising-stocks?market=US&limit=10`);
  check(r, { 'screener 200': (res) => res.status === 200 });

  sleep(1);
}
```

### Running
```bash
# Against local Docker Compose
k6 run tests/performance/api_baseline.js

# With HTML report
k6 run --out json=results.json tests/performance/api_baseline.js
```

### NFR Targets
| Metric | Target | Fail condition |
|---|---|---|
| p95 response time | < 200ms | > 200ms under 10 concurrent users |
| p99 response time | < 500ms | > 500ms |
| Error rate | < 1% | > 1% |
| Throughput | > 50 req/s | < 50 req/s for read endpoints |

---

## PostgreSQL Query Analysis

### Enable `pg_stat_statements`
```sql
-- Run once after DB init (add to migration)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

### Find slow queries
```sql
-- Top 10 slowest queries by mean execution time
SELECT
    left(query, 80)         AS query_snippet,
    calls,
    mean_exec_time::int     AS mean_ms,
    max_exec_time::int      AS max_ms,
    total_exec_time::int    AS total_ms
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### `EXPLAIN ANALYZE` for any suspicious query

```sql
-- Always use EXPLAIN ANALYZE on queries in storage/ before shipping
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT DISTINCT ON (symbol) symbol, score, action, as_of_date
FROM score_snapshot
WHERE as_of_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY symbol, as_of_date DESC;
```

**What to look for**:
- `Seq Scan` on large tables → missing index
- `rows=10000 actual rows=1` → stale statistics, run `ANALYZE`
- High `Buffers: shared hit` → good (cache hit); high `read` → cold cache or missing index
- Nested loops with large row estimates → consider a materialized view or pre-aggregation

### Index verification
```sql
-- Check indexes on key tables
SELECT indexname, indexdef FROM pg_indexes
WHERE tablename IN ('daily_price', 'factor_snapshot', 'score_snapshot')
ORDER BY tablename, indexname;

-- Check for sequential scans on large tables (run after load test)
SELECT relname, seq_scan, idx_scan, n_live_tup
FROM pg_stat_user_tables
ORDER BY seq_scan DESC;
```

---

## Python Profiling

### CPU profiling with `py-spy`
```bash
# Install
pip install py-spy

# Profile a running process (find PID with docker compose top)
py-spy top --pid <worker-pid>

# Generate flamegraph
py-spy record -o flamegraph.svg --pid <worker-pid> --duration 30
```

### Line profiling with `line_profiler`
```bash
pip install line_profiler
```

```python
# Decorate functions to profile
from line_profiler import profile

@profile
def compute_all_signals(factor_snapshot: FactorSnapshot) -> dict[str, Signal]:
    ...
```

```bash
kernprof -l -v backend/app/signals/technical.py
```

### Memory profiling with `memray`
```bash
pip install memray
memray run -o output.bin python -m app.jobs.worker
memray flamegraph output.bin
```

Use when worker RSS memory grows unexpectedly over time.

---

## Ingest Pipeline Benchmarking

Track ingest performance via `ingest_run` table — no external tool needed:

```sql
-- Ingest duration by source over last 30 days
SELECT
    source,
    job_type,
    COUNT(*)                                          AS runs,
    AVG(EXTRACT(EPOCH FROM (finished_at - started_at)))::int AS avg_seconds,
    MAX(EXTRACT(EPOCH FROM (finished_at - started_at)))::int AS max_seconds
FROM ingest_run
WHERE status = 'success'
  AND started_at > NOW() - INTERVAL '30 days'
GROUP BY source, job_type
ORDER BY avg_seconds DESC;
```

Target: full daily ingest (all sources, all tickers) completes in < 30 minutes.

---

## Performance Test in CI (Phase 3+)

Add a smoke performance test to CI that runs against the Docker Compose stack:

```yaml
# .github/workflows/performance.yml
name: Performance smoke test
on:
  push:
    branches: [main]

jobs:
  perf:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose up -d
      - run: docker compose exec db psql -U stocks -d stocks -f db/migrations/001_initial_schema.sql
      - run: sleep 10   # wait for API to be ready
      - uses: grafana/k6-action@v0.3.1
        with:
          filename: tests/performance/api_baseline.js
      - run: docker compose down
```
