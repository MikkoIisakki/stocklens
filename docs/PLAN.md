# Pulse — White-label Screener Platform

**Platform concept**: One codebase, multiple domain-focused apps. Each app screens, ranks, and alerts on a specific data domain (electricity prices, stocks, crypto). Same pipeline architecture, same mobile shell, different configuration and data sources per domain.

**Deployment model**: Each domain is a separately branded app (own App Store listing, own domain/URL) built from the same repository via configuration.

**Current phase**: Phase 2 — Electricity Domain

---

## Phase 1 — Platform Foundation ✅ Complete

Goal: reliable daily data ingestion, storage with full audit trail, queryable via REST API. Built on stocks as the reference domain.

| # | Task | Status | Notes |
|---|---|---|---|
| 1.1 | Project structure + Docker Compose | ✅ Done | `backend/` layout, `docker-compose.yml`, `Makefile`, `pyproject.toml` |
| 1.2 | DB schema — core tables | ✅ Done | `asset`, `daily_price`, `raw_source_snapshot`, `ingest_run` |
| 1.3 | Ingest US EOD prices (yfinance) | ✅ Done | 50 US tickers |
| 1.4 | Ingest Finnish EOD prices (yfinance) | ✅ Done | 20 Helsinki exchange tickers |
| 1.5 | Daily ingest scheduler | ✅ Done | APScheduler cron; FI 17:00 UTC, US 21:30 UTC |
| 1.6 | REST API — assets + price history | ✅ Done | `GET /v1/assets`, `GET /v1/assets/{symbol}/prices` |
| 1.7 | Health check endpoint | ✅ Done | `GET /v1/health/ready` — ok / degraded / 503 |
| 1.8 | Architecture fitness function tests | ✅ Done | `tests/architecture/test_dependency_rules.py` |

---

## Phase 2 — Electricity Domain

**Goal**: daily Nordic electricity spot price ingestion, threshold alerts, first domain ready for public app release. Free Nordpool/ENTSO-E API — no licensing cost, no financial regulation concerns.

**Priority**: highest — this is the first domain viable for public App Store release.

| # | Task | Status | Notes |
|---|---|---|---|
| 2.1 | DB schema — electricity tables | ✅ Done | `energy_price` (interval-keyed per ADR-005), `energy_region`, extend `ingest_run`; seeds for 6 ENTSO-E bidding zones |
| 2.2 | Nordpool/ENTSO-E ingest | ✅ Done | ENTSO-E Transparency Platform (A44 day-ahead, PT15M/PT60M); `entsoe_client.py`, `energy_ingest.py`. Migrated from Nordpool 2026-04 — see ADR-004, ADR-005, RISK-014 |
| 2.3 | Price normalisation (VAT, currency) | ✅ Done | `normalization/energy_price.py`; spot_c_kwh + total_c_kwh with VAT+tax |
| 2.4 | Daily price scheduler | ✅ Done | `run_energy_job` at 11:30 UTC (13:30 CET) added to APScheduler |
| 2.5 | Threshold alert rules | ✅ Done | `alerts/energy.py`; `energy_alert_rule` + `energy_alert` tables; evaluated in job after ingest |
| 2.6 | REST API — electricity prices + alerts | ✅ Done | `GET /v1/energy/prices`, `GET /v1/energy/alerts` (interval shape per ADR-005) |
| 2.7 | "Cheap intervals" ranking | ✅ Done | `GET /v1/energy/cheap-intervals` returns intervals ranked ascending by total_c_kwh (renamed from cheap-hours in ADR-005) |
| 2.8 | Grafana energy dashboard | ✅ Done | `grafana/dashboards/energy.json`: 24h prices, peak/off-peak stat, 30-day trend, cheapest-interval table; Postgres datasource provisioning + docker-compose service |
| 2.9 | Health check extension | ✅ Done | `/v1/health/ready` now reports per-market freshness (ENERGY/FI/US); status=degraded if any market is stale (>25h) or has never run |

### Phase 2 Definition of Done

- [ ] Tomorrow's interval prices ingested daily by 14:00 CET (PT15M or PT60M depending on zone)
- [ ] Prices stored in EUR/MWh and c/kWh (incl. VAT)
- [ ] Alert fires when peak price exceeds configured threshold
- [ ] `GET /v1/energy/prices?date=today|tomorrow` returns correct interval data with `interval_minutes`
- [ ] Grafana dashboard shows 24h price chart and cheap-interval ranking
- [ ] CI passes, coverage ≥ 70%

---

## Phase 3 — Multi-domain Platform Architecture

**Goal**: formal white-label infrastructure so adding a new domain requires only a config file and an ingestion module — not architectural changes.

| # | Task | Status | Notes |
|---|---|---|---|
| 3.1 | Domain config system | ✅ Done | `config/domains/energy.yaml` + typed loader `app.common.domain.load_domain_config`. Scheduler reads cron from config. Stocks/crypto YAMLs land with their phases. See ADR-006. |
| 3.2 | Expo white-label mobile app shell | ✅ Done | `mobile/` — Expo SDK 52 + Expo Router. `app.config.ts` loads `config/domains/<name>.yaml` at build time and injects via `Constants.expoConfig.extra`. Three screens (prices, cheap-intervals, alerts). API key is build-time bootstrap (see ADR-009 for the migration path to per-install tokens). Separate `mobile-ci.yml` workflow runs typecheck. |
| 3.3 | Auth layer (JWT / API key) | ✅ Done | API key (SHA-256 hashed) on `/v1/energy/*` and `/v1/assets/*`; `/v1/health/*` open. CLI: `python -m app.tools.create_api_key`. JWT-for-users deferred until per-user state exists. See ADR-007. |
| 3.4 | Push notification infrastructure | ⬜ Todo | FCM/APNs + device registration endpoint |
| 3.5 | Next.js white-label web shell | ✅ Done | `web/` — Next.js 15 + RSC + Tailwind. `PULSE_DOMAIN` env var picks the YAML; `PULSE_API_KEY` server-side only. Pages: prices (chart+table), cheap-intervals, alerts. Separate `web-ci.yml` workflow. See ADR-008. |
| 3.6 | EAS build pipeline (GHA) | ⬜ Todo | `eas build --profile energy` etc.; devops owns workflow |
| 3.7 | DigitalOcean deployment | ⬜ Todo | Stage B; CD pipeline; one Droplet per domain or shared |
| 3.8 | Lift interval triple into shared Pydantic base | ⬜ Todo | Trigger: when the second domain consumes intervals (stocks intraday or crypto). ~30 min of mechanical dedupe — `IntervalBase` in `app/api/schemas/interval.py`, domain models inherit. Per ADR-005, "rule of three" (don't extract before second user). |

---

## Phase 4 — Stock Factor Engine

**Goal**: compute all 8 signals per stock per day, produce composite score, expose ranked assets via API. Stocks-domain only.

| # | Task | Status | Notes |
|---|---|---|---|
| 4.1 | DB schema — factor and score tables | ⬜ Todo | `factor_snapshot`, `score_snapshot`, `ranking_snapshot` |
| 4.2 | Long-term signals (EPS acceleration, revenue growth, margins, ROE) | ⬜ Todo | Fundamental data via yfinance / Alpha Vantage |
| 4.3 | Short-term signals (RS, RSI, MACD, volume spike) | ⬜ Todo | Technical data via yfinance |
| 4.4 | Composite score (long + short horizon) | ⬜ Todo | Configurable weights in `config/domains/stocks.yaml` |
| 4.5 | Ranking materialisation | ⬜ Todo | Daily pre-computed ranking snapshot |
| 4.6 | REST API — rankings + score explanations | ⬜ Todo | `GET /v1/rankings`, factor contributions per asset |

---

## Phase 5 — Stock Screening + Alerts

**Goal**: threshold-based alert rules for stocks, Grafana dashboards. Internal / personal use only until app store gate clears.

| # | Task | Status | Notes |
|---|---|---|---|
| 5.1 | Alert rule engine + event generation | ⬜ Todo | Threshold rules on any signal or score |
| 5.2 | REST API — alerts | ⬜ Todo | `GET /v1/alerts`, `POST /v1/alerts/rules` |
| 5.3 | Grafana: pipeline health dashboard | ⬜ Todo | Ingest status, staleness, API errors |
| 5.4 | Grafana: market overview dashboard | ⬜ Todo | Top-ranked assets, RS heatmap, volume |
| 5.5 | Grafana: fundamentals dashboard | ⬜ Todo | EPS/revenue acceleration, margins, ROE |
| 5.6 | Grafana: alerts dashboard | ⬜ Todo | Unacknowledged alerts, breakouts |
| 5.7 | Backtest module | ⬜ Todo | Validate scoring weights against historical returns |

---

## Phase 6 — Crypto Domain

**Goal**: crypto screener using CoinGecko free API. Same pipeline as stocks, same technical signals, no licensing cost.

| # | Task | Status | Notes |
|---|---|---|---|
| 6.1 | DB schema extension for crypto | ⬜ Todo | Extend `asset` table; `market = 'CRYPTO'` |
| 6.2 | CoinGecko ingest | ⬜ Todo | Top 50 by market cap, OHLCV + market cap data |
| 6.3 | Crypto scoring model | ⬜ Todo | RS vs BTC, RSI, MACD, volume spike, market cap tier |
| 6.4 | REST API — crypto rankings | ⬜ Todo | Reuses `/v1/rankings?domain=crypto` |
| 6.5 | Crypto alert rules | ⬜ Todo | Price threshold, RSI overbought/oversold |

---

## Phase 7 — App Store Releases

**Goal**: public release of electricity and crypto domain apps. Stock app release gated on licensing + legal review.

| # | Task | Status | Notes |
|---|---|---|---|
| 7.1 | Electricity app — App Store + Google Play | ⬜ Todo | No gate beyond GDPR + privacy policy |
| 7.2 | Crypto app — App Store + Google Play | ⬜ Todo | MiCA screening check; "not financial advice" disclaimer |
| 7.3 | **Stock app gate** | ⬜ Todo | Blocks stock public release: licensed data source + MiFID II review |
| 7.4 | Stock app — App Store + Google Play | ⬜ Todo | Blocked by 7.3 |

### App store gate checklist (7.3 — stocks only)

| Prerequisite | Requirement |
|---|---|
| Data source licensing | Replace yfinance with licensed provider (Polygon.io) |
| MiFID II / FIN-FSA | Legal review of feature set framing |
| GDPR | Privacy policy, data retention, deletion mechanism |
| Wording | All copy uses screening/ranking language — no advice wording |
| App Store metadata | "Not investment advice" prominent in listing |

TestFlight/sideload for personal use does **not** require this gate.

---

## Key Decisions (settled)

| Decision | Choice | Revisit trigger |
|---|---|---|
| Platform model | White-label: one codebase, one app per domain | Never — this is the architecture |
| Architecture style | Modular monolith | Ingest/scoring/API need independent scaling |
| Language | Python 3.12 + FastAPI | Never |
| Database | PostgreSQL 16 | p99 latency > 200ms at scale |
| Job queue | APScheduler → Redis/RQ later | > 10 concurrent workers |
| Mobile | Expo / React Native (EAS build variants per domain) | Never |
| Web | Next.js (env-var configured per domain) | Never |
| Domain priority | Electricity (free) → Crypto (free) → Stocks (licensed) | Licensing costs change |
| Data sources | Free-first: Nordpool, CoinGecko, yfinance | Coverage gaps or ToS enforcement |
| Deployment | Local → DigitalOcean Droplet (Phase 3) → DOKS if load justifies | Real multi-user load |

## Open Risks (High)

| Risk | Status |
|---|---|
| RISK-001: yfinance API breaks | Mitigated |
| RISK-003: Scope creep | Open |
| RISK-004: Silent ingest failure | Mitigated |
| RISK-007: Scoring model produces misleading screening results | Open |
| RISK-009: Finnish stock fundamental data insufficient | Accepted |
| RISK-012: Data source ToS violation (stocks public release) | Open — gated by 7.3 |

Full risk register: [docs/risks/risk-register.md](risks/risk-register.md)
