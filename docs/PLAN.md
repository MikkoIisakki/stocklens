# Recommendator — Project Plan

**Current phase**: Phase 1 — Data Foundation  
**Status**: Not started (agent team setup complete, no application code written)

---

## Phase 1 — Data Foundation

Goal: reliable daily price ingestion for US + Finnish markets, stored with full audit trail, queryable via REST API.

### Tasks

| # | Task | Status | Notes |
|---|---|---|---|
| 1.1 | Project structure + Docker Compose | ✅ Done | `backend/` layout, `docker-compose.yml`, `Makefile`, `pyproject.toml`, `.env.example` |
| 1.2 | DB schema — core tables | ✅ Done | `asset`, `daily_price`, `raw_source_snapshot`, `ingest_run`; seed: 50 US + 20 FI tickers |
| 1.3 | Ingest US EOD prices (yfinance) | ⬜ Todo | Top 50 S&P 500 + Nasdaq tech tickers |
| 1.4 | Ingest Finnish EOD prices (yfinance, .HE) | ✅ Done | Helsinki exchange tickers; reuses full 1.3 pipeline |
| 1.5 | Daily ingest scheduler | ✅ Done | APScheduler cron: FI 17:00 UTC, US 21:30 UTC; misfire_grace_time=3600 |
| 1.6 | REST API — assets + price history | ⬜ Todo | `GET /v1/assets`, `GET /v1/assets/{symbol}/prices` |
| 1.7 | Health check endpoint | ⬜ Todo | `GET /v1/health/ready` — returns `degraded` if last ingest > 25h ago |
| 1.8 | Architecture fitness function tests | ⬜ Todo | `tests/architecture/test_dependency_rules.py` — enforce Clean Architecture boundaries in CI |

### Phase 1 Definition of Done

- [ ] All 8 tasks complete with all ACs passing
- [ ] `make up && make migrate && make seed` leaves system fully working from a clean clone
- [ ] CI passes (ruff, mypy, bandit, radon, pytest ≥ 80% coverage, gitleaks)
- [ ] US + Finnish prices ingested and queryable
- [ ] Staleness alert fires if ingest hasn't run in 25h
- [ ] No hardcoded values, secrets, or magic numbers anywhere

---

## Phase 2 — Factor Engine

Goal: compute all 8 signals per asset per day, produce a composite score, expose ranked buy candidates via API.

| # | Task | Status |
|---|---|---|
| 2.1 | DB schema — factor and score tables | ⬜ Todo |
| 2.2 | Long-term signals (EPS acceleration, revenue growth, margins, ROE) | ⬜ Todo |
| 2.3 | Short-term signals (RS, RSI, MACD, volume spike) | ⬜ Todo |
| 2.4 | Composite score (long + short horizon) | ⬜ Todo |
| 2.5 | Ranking materialization | ⬜ Todo |
| 2.6 | REST API — rankings + score explanations | ⬜ Todo |

---

## Phase 3 — Recommendations + Alerts

Goal: threshold-based alert rules, Grafana dashboards for pipeline health and market overview.

| # | Task | Status |
|---|---|---|
| 3.1 | Alert rule engine + event generation | ⬜ Todo |
| 3.2 | REST API — alerts | ⬜ Todo |
| 3.3 | Grafana: pipeline health dashboard | ⬜ Todo |
| 3.4 | Grafana: market overview dashboard | ⬜ Todo |
| 3.5 | Grafana: fundamentals dashboard | ⬜ Todo |
| 3.6 | Grafana: alerts dashboard | ⬜ Todo |
| 3.7 | DigitalOcean deployment (Stage B) | ⬜ Todo |

---

## Phase 4 — Polish

| # | Task | Status |
|---|---|---|
| 4.1 | Backtest module — validate scoring weights against historical returns | ⬜ Todo |
| 4.2 | Premium data source integration (Polygon.io or Alpha Vantage premium) | ⬜ Todo |
| 4.3 | Next.js watchlist + screener UI | ⬜ Todo |
| 4.4 | DOKS deployment (if load justifies it) | ⬜ Todo |

---

## Key Decisions (settled)

| Decision | Choice | Revisit trigger |
|---|---|---|
| Architecture | Modular monolith | Ingest/scoring/API need independent scaling |
| Language | Python 3.12 + FastAPI | Never |
| Database | PostgreSQL 16 (plain) | p99 latency > 200ms at scale |
| Job queue | APScheduler → Redis/RQ later | > 10 concurrent workers |
| Data sources | yfinance (primary), Alpha Vantage (fundamentals supplement) | Coverage gaps block decisions |
| Deployment | Local → DigitalOcean Droplet (Phase 3) → DOKS (Phase 4 if needed) | Real load |

## Open Risks (High)

| Risk | Status |
|---|---|
| RISK-002: Alpha Vantage free tier limits fundamental coverage | Mitigated |
| RISK-003: Scope creep beyond current phase | Open |
| RISK-004: Silent ingest failure — scores go stale | Mitigated |
| RISK-007: Scoring model produces misleading recommendations | Open |
| RISK-009: Finnish market fundamental data insufficient | Accepted |
| RISK-012: yfinance ToS violation at SaaS scale | Accepted (personal use) |

Full risk register: [docs/risks/risk-register.md](risks/risk-register.md)
