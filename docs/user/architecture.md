# Architecture

## Overview

Stocklens is a **modular monolith** — a single deployable unit organised into well-defined internal modules. This keeps operations simple (one image, one deploy) while enforcing the same boundaries a microservices design would require.

```
┌─────────────────────────────────────────────────────┐
│                    Docker Compose                    │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │   api    │  │ scheduler│  │      worker       │  │
│  │ :8000    │  │ (cron)   │  │  (job executor)   │  │
│  └────┬─────┘  └────┬─────┘  └────────┬──────────┘  │
│       │             │                 │              │
│       └─────────────┴─────────────────┘              │
│                       │                              │
│               ┌───────┴──────┐                       │
│               │  PostgreSQL  │                       │
│               │  :5432       │                       │
│               └──────────────┘                       │
└─────────────────────────────────────────────────────┘
```

All three application containers are built from the same `./backend` image — they differ only in their startup command.

## Internal modules

```
backend/app/
├── api/            ← FastAPI routers and dependencies (HTTP boundary)
├── ingestion/      ← Data fetching (yfinance client, US/FI ingest pipelines)
├── normalization/  ← Transform raw data into storage-ready format
├── storage/        ← Repository layer — all SQL lives here
├── jobs/           ← Scheduler and worker entry points
├── signals/        ← (Phase 2) Factor signal computation
├── scoring/        ← (Phase 2) Composite score calculation
├── ranking/        ← (Phase 2) Score materialisation and ranking
├── alerts/         ← (Phase 3) Alert rule engine
└── common/         ← Config, logging, shared types
```

### Dependency rule

Modules follow Clean Architecture — **inner modules do not import outer ones**:

```
api → storage → (nothing)
ingestion → storage, normalization
signals → storage
scoring → signals, storage
ranking → scoring, storage
alerts → ranking, storage
jobs → ingestion, (Phase 2) signals, scoring, ranking
```

This is enforced automatically by the architecture fitness function test:
`tests/architecture/test_dependency_rules.py`

## Data flow

```
yfinance (external)
      │
      ▼
ingestion/yfinance_client.py   ← async wrapper (thread pool)
      │
      ▼
normalization/price.py         ← validate, filter bad rows
      │
      ▼
storage/repository.py          ← upsert to daily_price
      │                           save to raw_source_snapshot
      ▼
PostgreSQL
      │
      ▼
api/routers/assets.py          ← serve via REST
```

## Key design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Package manager | uv | Fast, reproducible, replaces pip+venv |
| Web framework | FastAPI | Async, typed, auto-generates OpenAPI docs |
| Database driver | asyncpg | Fastest async PostgreSQL driver for Python |
| Scheduler | APScheduler | Simple cron-style scheduling without a broker |
| Data source | yfinance | Free EOD data for both US and Finnish markets |
| Validation | Pydantic v2 | Runtime type safety on all settings and API responses |
