---
name: risk-management
description: Risk identification, classification, mitigation, and tracking for the pulse project. Covers project, technical, domain, and operational risk categories. Used by orchestrator, architect, product-manager, and analyst.
---

# Risk Management

## Risk Classification

Every risk is rated on two dimensions:

**Likelihood**: How probable is the risk materializing?
| Rating | Label | Meaning |
|---|---|---|
| 1 | Rare | Unlikely under normal conditions |
| 2 | Unlikely | Could happen, not expected |
| 3 | Possible | Might happen at some point |
| 4 | Likely | Will probably happen |
| 5 | Almost certain | Expected to happen |

**Impact**: What is the effect if it materializes?
| Rating | Label | Meaning |
|---|---|---|
| 1 | Negligible | Minor inconvenience, no data loss |
| 2 | Minor | Small delay, easily recovered |
| 3 | Moderate | Significant effort to recover, some data loss possible |
| 4 | Major | Phase delayed, meaningful data/time loss |
| 5 | Critical | System unusable, investment decisions compromised |

**Risk Score** = Likelihood × Impact

| Score | Level | Action |
|---|---|---|
| 1–4 | Low | Monitor |
| 5–9 | Medium | Mitigate |
| 10–16 | High | Mitigate urgently |
| 17–25 | Critical | Stop and address before proceeding |

---

## Risk Register Format

Each risk in `docs/risks/risk-register.md` follows this format:

```markdown
### RISK-NNN: <Title>

| Field | Value |
|---|---|
| Category | Project / Technical / Domain / Operational |
| Likelihood | 1–5 |
| Impact | 1–5 |
| Score | L × I |
| Level | Low / Medium / High / Critical |
| Status | Open / Mitigated / Accepted / Closed |
| Owner | Which agent monitors this |

**Description**: What could go wrong and why.

**Consequences**: What happens if this risk materializes.

**Mitigation**: Concrete steps taken or planned to reduce likelihood or impact.

**Contingency**: What to do if it materializes despite mitigation.

**Review trigger**: Condition that should prompt re-evaluation of this risk.
```

---

## Risk Categories

### Project Risks
Threaten delivery timeline, scope, or quality.

Common risks for this project:
- **Scope creep** — adding features beyond the current phase
- **Over-engineering** — building infrastructure for future needs that never materialize
- **External API deprecation** — yfinance, Alpha Vantage, or Finnhub changing terms or structure
- **Learning curve** — new technologies slowing delivery (K8s, TimescaleDB added prematurely)

### Technical Risks
Threaten system correctness, reliability, or performance.

Common risks for this project:
- **Data quality** — yfinance returning stale, incorrect, or missing data without indication
- **Schema migration failure** — a bad migration corrupts or loses data
- **DB performance degradation** — query latency grows as data accumulates
- **Missing index** — a slow query in production that wasn't caught in testing
- **Silent scoring failure** — processor crashes without alert; scores go stale unnoticed

### Domain / Algorithm Risks
Threaten the quality of screening results.

Common risks for this project:
- **Factor decay** — a signal that worked historically stops working (crowding, regime change)
- **Data snooping bias** — backtest optimizes for past data, doesn't generalize
- **Look-ahead bias** — using data in scoring that wouldn't have been available at decision time
- **Market regime change** — momentum/growth factors underperform in value/defensive environments
- **Finnish market data gaps** — yfinance coverage for .HE tickers is incomplete for fundamentals
- **Screening results acting as advice** — treating scores as certainty rather than probabilistic signal

### Operational Risks
Threaten the running system in production.

Common risks for this project:
- **Secret exposure** — API key committed to git or logged
- **Droplet data loss** — PostgreSQL on a single node with no backup
- **Ingest failure undetected** — scores go stale but no alert fires
- **Caddy TLS expiry** — cert renewal fails, HTTPS breaks
- **Manual infra drift** — someone SSH's and changes something not in git

---

## Failure Mode and Effects Analysis (FMEA)

For critical components, the architect produces an FMEA table:

```markdown
## FMEA: <Component Name>

| Failure Mode | Effect | Likelihood | Severity | Detection | RPN | Mitigation |
|---|---|---|---|---|---|---|
| yfinance returns empty DataFrame | No price data ingested for asset | 3 | 4 | Low (silent) | 48 | Check df.empty after fetch; log + raise NoDataError |
| DB connection pool exhausted | API returns 503 | 2 | 4 | Medium (health check) | 32 | Pool size tuning; circuit breaker on DB calls |
| Scoring worker crashes mid-run | Partial scores; some assets missing today's score | 2 | 3 | Low (stale score alert) | 24 | Idempotent scoring; Grafana staleness alert |
| Redis OOM (cache full) | Cache misses; all reads hit DB | 2 | 2 | Low | 16 | maxmemory + allkeys-lru; DB handles load |
```

**Risk Priority Number (RPN)** = Likelihood × Severity × (6 - Detection rating)
Detection: 1 = immediate, 5 = never detected

---

## Risk Review Process

### Before starting a new phase
1. Review the risk register — re-score open risks
2. Identify new risks introduced by the upcoming phase work
3. Ensure all High/Critical risks have mitigations in place before proceeding

### Before a significant design decision
- Architect includes a risk section in every ADR
- Any new external dependency gets a risk entry

### Before adding a new factor (analyst)
- Analyst documents factor failure conditions in the factor specification
- Backtesting criteria address look-ahead bias explicitly

### Ongoing
- Grafana pipeline dashboard surfaces operational risks automatically (stale data, failed ingest)
- `ingest_run` failures auto-populate as observable events

---

## Risk Response Strategies

| Strategy | When to use | Example |
|---|---|---|
| **Avoid** | Risk is too high; change the approach | Don't use a single-node DB for critical data → use Managed PostgreSQL |
| **Mitigate** | Reduce likelihood or impact | Add staleness alerts to detect silent ingest failures |
| **Transfer** | Move risk to a third party | Use DigitalOcean Managed PostgreSQL (backup is their responsibility) |
| **Accept** | Risk is low enough; cost of mitigation exceeds benefit | Accept yfinance unofficial API risk — free tier, easy to swap |
| **Contingency** | Plan for if it happens | If yfinance breaks: fall back to Alpha Vantage; if both break: serve stale data with warning |

---

## Risk Escalation

| Level | Action |
|---|---|
| Low | Log in risk register, monitor |
| Medium | Define mitigation steps, assign to relevant agent |
| High | Block current phase task until mitigation is in place; document in ADR |
| Critical | Stop work, escalate to orchestrator, do not proceed until resolved |
