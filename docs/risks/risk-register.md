# Risk Register

Last reviewed: 2026-04-07
Current phase: Pre-implementation (Phase 1 starting)

See `.github/skills/risk-management.md` for scoring methodology and process.

Score = Likelihood (1–5) × Impact (1–5). High ≥ 10, Critical ≥ 17.

---

## Project Risks

### RISK-001: yfinance API breaks or changes structure

| Field | Value |
|---|---|
| Category | Project / Technical |
| Likelihood | 3 |
| Impact | 4 |
| Score | 12 |
| Level | High |
| Status | Mitigated |
| Owner | architect, engineer |

**Description**: yfinance is an unofficial Yahoo Finance scraper, not a supported API. Yahoo could change their response format, rate-limit aggressively, or block the library at any time without notice.

**Consequences**: All US and Finnish price ingestion fails. Scores go stale. No recommendations until alternative is wired.

**Mitigation**:
- `raw_source_snapshot` stores every raw response — can replay normalization without re-fetching
- Data source layer is abstracted behind `ingestion/` with one file per source
- Alpha Vantage is a documented fallback for US price data
- `ingest_run` failures trigger Grafana staleness alerts within 24h

**Contingency**: If yfinance breaks, swap `ingestion/yfinance.py` implementation to Alpha Vantage or Polygon.io. The storage layer and downstream scoring are unaffected.

**Review trigger**: yfinance major version bump, or any `ingest_run` failure lasting > 2 days.

---

### RISK-002: Alpha Vantage free tier limit blocks fundamental ingestion

| Field | Value |
|---|---|
| Category | Project |
| Likelihood | 4 |
| Impact | 2 |
| Score | 8 |
| Level | Medium |
| Status | Mitigated |
| Owner | engineer |

**Description**: Alpha Vantage free tier allows 25 requests/day. With 65+ tickers needing fundamentals, full coverage takes 3+ days to rotate through.

**Consequences**: Fundamental factor data is stale for most tickers at any given time. Valuation and quality scores are less accurate.

**Mitigation**:
- Scheduler prioritises tickers by last-fetch date (oldest first)
- Daily counter tracked in Redis; stops publishing AV tasks at limit
- yfinance `.info` used as primary fundamentals source; AV as supplement
- `raw_source_snapshot` means if AV key is upgraded, historical gaps can be backfilled

**Contingency**: Upgrade to Alpha Vantage premium ($50/month) if fundamental data quality is materially impacting recommendation quality.

**Review trigger**: Phase 4 — if premium data is needed for production quality.

---

### RISK-003: Scope creep beyond current phase

| Field | Value |
|---|---|
| Category | Project |
| Likelihood | 4 |
| Impact | 3 |
| Score | 12 |
| Level | High |
| Status | Open |
| Owner | orchestrator, product-manager |

**Description**: Temptation to add features (ML scoring, Next.js UI, K8s, TimescaleDB) before the current phase is solid. Common in personal projects where there's no external accountability.

**Consequences**: Phase 1 never fully stabilizes. Data foundation is shaky. Later phases are built on untested ground.

**Mitigation**:
- Phase gates enforced by orchestrator — no Phase 2 work until Phase 1 DoD is fully met
- ADR-001/002/003 document deliberate deferral decisions with explicit revisit triggers
- product-manager backlog is MoSCoW-prioritised; future-phase items are labelled `Won't (this phase)`

**Contingency**: If scope creep is detected mid-task, orchestrator returns the task to product-manager to split or defer the out-of-scope portion.

**Review trigger**: Any task description that references technology or features not in the current phase plan.

---

## Technical Risks

### RISK-004: Silent ingest failure — scores go stale undetected

| Field | Value |
|---|---|
| Category | Technical / Operational |
| Likelihood | 3 |
| Impact | 5 |
| Score | 15 |
| Level | High |
| Status | Mitigated |
| Owner | devops, engineer |

**Description**: Ingestion job crashes or produces no rows without raising a detectable error. Scores remain at yesterday's values. Decisions made on stale data.

**Consequences**: Investment decisions based on outdated signals. This is the most dangerous failure mode for the system's purpose.

**Mitigation**:
- `ingest_run` table records every job attempt with status and timestamps
- Grafana pipeline dashboard: query for assets with `daily_price.date < CURRENT_DATE` alerts visually
- Grafana alert rule fires if any asset has no price data by 19:00 ET/EET
- `GET /v1/health/ready` returns `degraded` if last ingest > 25h ago

**Contingency**: On alert, check `ingest_run` for error messages. Re-run manually via `make migrate && docker compose restart worker`.

**Review trigger**: Any `ingest_run.status = 'failed'` entry.

---

### RISK-005: DB schema migration corrupts or loses data

| Field | Value |
|---|---|
| Category | Technical |
| Likelihood | 2 |
| Impact | 5 |
| Score | 10 |
| Level | High |
| Status | Mitigated |
| Owner | engineer, devops |

**Description**: A poorly written migration drops a column, changes a type incorrectly, or runs non-idempotently causing duplicate data or constraint violations.

**Consequences**: Data loss requires restore from backup. Downtime. Potential loss of historical factor data.

**Mitigation**:
- All migrations tested in CI against a clean DB (`migration-check.yml` workflow)
- Migrations are idempotent (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`)
- No destructive operations (DROP COLUMN, DROP TABLE) without explicit `-- DESTRUCTIVE` comment and manual review
- DigitalOcean Managed PostgreSQL provides daily automated backups (Phase B)
- Local: `make fresh` tested before any migration is committed

**Contingency**: Restore from DigitalOcean backup. Replay `raw_source_snapshot` to rebuild derived data.

**Review trigger**: Any migration containing `DROP`, `ALTER COLUMN TYPE`, or `TRUNCATE`.

---

### RISK-006: Architecture fitness functions not maintained

| Field | Value |
|---|---|
| Category | Technical |
| Likelihood | 3 |
| Impact | 3 |
| Score | 9 |
| Level | Medium |
| Status | Open |
| Owner | engineer |

**Description**: Dependency rule violations (e.g. signals/ importing storage/ directly) accumulate over time if `tests/architecture/` tests are not written and maintained.

**Consequences**: Clean Architecture boundaries erode. Code becomes harder to test and reason about. Domain logic becomes coupled to infrastructure.

**Mitigation**:
- Architecture fitness function tests required as part of Phase 1 setup (`tests/architecture/test_dependency_rules.py`)
- CI runs these tests on every push — violations fail the build

**Contingency**: If tests are missing, add them before merging the next PR.

**Review trigger**: Any PR that crosses module boundaries.

---

## Domain / Algorithm Risks

### RISK-007: Scoring model produces misleading recommendations

| Field | Value |
|---|---|
| Category | Domain |
| Likelihood | 3 |
| Impact | 4 |
| Score | 12 |
| Level | High |
| Status | Open |
| Owner | analyst |

**Description**: The rule-based scoring model with current weights has not been validated against historical returns. Weights are evidence-informed but not empirically tested on this universe.

**Consequences**: High-scored stocks underperform; low-scored stocks outperform. Recommendations actively mislead rather than help.

**Mitigation**:
- Analyst documents failure conditions and market regimes where each factor breaks (in `analyst.md`)
- Factor weights are configurable — can be adjusted as evidence accumulates
- `score_snapshot` stores `factor_contributions` — every recommendation is explainable and auditable
- Backtest module (Phase 4) will validate weights against historical data before increasing trust in the model
- User (Mikko) treats recommendations as one input to research, not as trade signals

**Contingency**: If observation shows consistent underperformance, analyst reviews factor weights and proposes rebalancing. Backtest validates before deploying new weights.

**Review trigger**: After 3 months of data, review top-20 recommendations vs actual returns. After Phase 4 backtest is available.

---

### RISK-008: Look-ahead bias in factor computation

| Field | Value |
|---|---|
| Category | Domain |
| Likelihood | 2 |
| Impact | 4 |
| Score | 8 |
| Level | Medium |
| Status | Open |
| Owner | analyst, engineer |

**Description**: A factor accidentally uses data that wouldn't have been available at the time of the signal (e.g. using Q3 earnings data when computing a signal dated before Q3 was reported).

**Consequences**: Backtest results are overstated. Live signals underperform expectations set by backtest.

**Mitigation**:
- All factor snapshots use `as_of_date` — engineer must verify data used for that date was available before that date
- Analyst factor specifications explicitly state reporting lag (e.g. "use earnings reported at least 2 days ago")
- Backtest criteria include look-ahead bias check as a required validation step

**Contingency**: If look-ahead bias is discovered in a factor, recompute historical `factor_snapshot` values using correctly time-stamped data.

**Review trigger**: When the backtesting module is built (Phase 4).

---

### RISK-009: Finnish market data quality insufficient for scoring

| Field | Value |
|---|---|
| Category | Domain |
| Likelihood | 4 |
| Impact | 3 |
| Score | 12 |
| Level | High |
| Status | Accepted |
| Owner | analyst |

**Description**: yfinance fundamentals coverage for Helsinki-listed stocks is incomplete, especially for mid/small-cap companies. Fundamental signals (EPS acceleration, valuation score, quality score) may be unavailable for many FI tickers.

**Consequences**: FI recommendations are weighted more heavily on technical signals (RS, RSI, volume) and less on fundamentals — a less complete picture. Scoring confidence will be lower.

**Mitigation**:
- `Signal` type includes `signal_type='unavailable'` with `weight=0.0` — missing factors are excluded from scoring, not zeroed
- `score_snapshot.confidence` field reflects proportion of factors available — low-confidence scores are clearly flagged
- Analyst specifications note reduced coverage expectations for FI mid/small-cap

**Contingency**: If FI fundamental coverage is too thin to be useful, restrict Finnish recommendations to large-caps (Nokia, Neste, Kone, Sampo) where coverage is reliable.

**Review trigger**: After first full ingest cycle — check what % of FI tickers have usable fundamental data.

---

## Operational Risks

### RISK-010: Secret exposure — API key in git history

| Field | Value |
|---|---|
| Category | Operational / Security |
| Likelihood | 2 |
| Impact | 5 |
| Score | 10 |
| Level | High |
| Status | Mitigated |
| Owner | devops |

**Description**: An API key (Alpha Vantage, Finnhub, FRED) or password is accidentally committed to the repository.

**Consequences**: Key is compromised. If it's a paid service, unauthorized usage incurs cost. If it's a DB password, data is at risk.

**Mitigation**:
- `gitleaks` scans every commit in CI — fails the build if a secret is detected
- Pre-commit hook runs gitleaks locally before push
- `.env` is in `.gitignore`; `.env.example` contains only placeholder values
- All config via `pydantic-settings` — no `os.environ.get()` scattered in code

**Contingency**: If a secret is exposed: immediately revoke it at the source (Alpha Vantage dashboard, etc.), generate a new one, update GitHub Secrets and `.env`. Use `git filter-repo` to remove from history and force-push (coordinate with any collaborators).

**Review trigger**: Any `gitleaks` CI failure.

---

### RISK-011: Single-point-of-failure — local Droplet data loss

| Field | Value |
|---|---|
| Category | Operational |
| Likelihood | 2 |
| Impact | 4 |
| Score | 8 |
| Level | Medium |
| Status | Open (Phase A) → Mitigated (Phase B) |
| Owner | devops |

**Description**: In Phase A (local only), all data lives on one machine with no backup. In Phase B with a single Droplet and self-managed PostgreSQL, disk failure means total data loss.

**Consequences**: Loss of all historical price data, factor snapshots, and scores. Must re-ingest from scratch (prices can be re-fetched; derived data must be recomputed).

**Mitigation (Phase A)**: Accepted — local dev, data is re-fetchable from free APIs.

**Mitigation (Phase B)**: Use DigitalOcean Managed PostgreSQL (daily automated backups, PITR). Do not self-host PostgreSQL on the Droplet in production.

**Contingency**: Restore from Managed PostgreSQL backup. Re-run scoring pipeline to rebuild derived data from restored raw prices.

**Review trigger**: Phase B deployment — confirm Managed PostgreSQL is active before going live.

---
*Add new risks as they are identified. Re-score existing risks at each phase boundary.*
