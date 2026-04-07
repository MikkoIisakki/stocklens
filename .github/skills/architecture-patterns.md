---
name: architecture-patterns
description: C4 diagramming conventions, CQRS pattern, module boundary rules, and criteria for splitting a modular monolith into services. For architect use.
---

# Architecture Patterns

## C4 Model — Diagram Levels

Use C4 for all architecture diagrams. Use Mermaid for version-controllable text diagrams.

### Level 1 — System Context
Shows the system, its users, and external systems it interacts with. No internal detail.

```mermaid
graph TD
    User([Investor])
    System[Recommendator System]
    YF[Yahoo Finance API]
    AV[Alpha Vantage API]
    FRED[FRED API]
    FH[Finnhub API]

    User -->|views recommendations & alerts| System
    System -->|fetches OHLCV + fundamentals| YF
    System -->|fetches fundamentals + technicals| AV
    System -->|fetches macro indicators| FRED
    System -->|fetches news + sentiment| FH
```

### Level 2 — Container Diagram
Shows deployable units (containers), their responsibilities, and communication.

```mermaid
graph TD
    subgraph Docker Compose
        API[FastAPI\nREST API\n:8000]
        Worker[Worker\nFactor computation]
        Scheduler[Scheduler\nJob dispatch]
        DB[(PostgreSQL\nstocks DB)]
        Grafana[Grafana\nDashboards\n:3000]
        Caddy[Caddy\nReverse Proxy\n:80/:443]
    end

    Scheduler -->|publishes jobs| Worker
    Worker -->|reads/writes| DB
    API -->|reads pre-computed| DB
    Grafana -->|SQL reads| DB
    Caddy -->|proxies| API
    Caddy -->|proxies| Grafana
```

### Level 3 — Component Diagram
Shows internal structure of a container. Use for complex modules.

```mermaid
graph TD
    subgraph Backend App
        Router[API Routers]
        Ingest[Ingestion\nper source]
        Norm[Normalization]
        Signals[Signals\ntechnical/fundamental]
        Scoring[Scoring\nrule-based]
        Ranking[Ranking]
        Alerts[Alerts]
        Storage[Storage\nall SQL]
        Common[Common\nconfig/logging/types]
    end

    Router --> Storage
    Ingest --> Norm --> Storage
    Signals --> Storage
    Scoring --> Storage
    Ranking --> Storage
    Alerts --> Storage
    Router --> Common
    Ingest --> Common
```

---

## CQRS — Command Query Responsibility Segregation

The recommendator uses a simplified CQRS pattern:

- **Write path** (Command): ingestion jobs write raw data → normalization → factor computation → score materialization
- **Read path** (Query): API and Grafana read only from pre-computed tables

**Rule**: Nothing on the read path triggers computation. All reads are against materialized state.

**Why**: Decouples read performance from write complexity. Pre-computed results mean consistent, fast API responses regardless of how complex the scoring logic becomes.

---

## Module Boundary Rules

1. **`storage/` is the only module that touches the database.** No other module imports `asyncpg` or writes SQL.
2. **`api/` routers contain no business logic.** They call `storage/` and return. Logic goes in domain modules.
3. **Domain modules (`signals/`, `scoring/`, `alerts/`) do not import from each other.** They share only `common/` types.
4. **`common/` contains only infrastructure concerns.** No business rules in config or logging modules.
5. **`ingestion/` writes to `raw_source_snapshot` first, always.** Normalization happens after the raw record is persisted.

Violations are architectural debt. Raise them with the architect before implementing.

---

## When to Split the Monolith

Splitting into microservices is justified only when at least one of these is true:

| Trigger | Example |
|---|---|
| Independent scaling is required | Ingestion load spikes, but API must stay responsive |
| Different deployment cadences | ML model updated hourly, API deployed weekly |
| Isolation for multi-tenancy | Per-customer data boundaries required |
| Team ownership boundaries | Different teams own different bounded contexts |
| A component's failure must not cascade | Scoring failure must not affect API availability |

**Not** justified by: "it seems cleaner", "microservices are modern", "we might need it later".

Current state: all triggers are absent → monolith is correct.

---

## Technology Decision Record (TDR) Format

Use this structure when documenting any technology choice:

```markdown
## TDR-NNN: <Decision Title>

**Date**: YYYY-MM-DD
**Status**: Accepted / Superseded by TDR-NNN

### Context
What problem are we solving? What constraints apply?

### Options Considered
1. **Option A** — pros / cons
2. **Option B** — pros / cons
3. **Option C** — pros / cons

### Decision
Chose Option X because...

### Consequences
- Positive: ...
- Negative / trade-offs: ...
- Revisit when: ...
```
