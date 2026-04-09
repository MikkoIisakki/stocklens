---
name: requirements-management
description: Requirements traceability, NFR ownership, change management, and MoSCoW prioritization for the stocklens project. Owned by the product-manager agent.
---

# Requirements Management

## Requirements Hierarchy

```
Vision
  └── Project Objective
        └── Phase Goal  (Phase 1: Data Foundation, etc.)
              └── Epic  (e.g. "US stock ingestion")
                    └── User Story  (e.g. "ingest EOD prices for top 50 S&P")
                          └── Acceptance Criteria  (Given/When/Then)
                                └── Test  (pytest test case)
```

Every item traces up and down. A change at any level must be evaluated for impact on all levels below it.

---

## Functional vs Non-Functional Requirements

### Functional Requirements (FR)
What the system does. Captured as user stories with Given/When/Then AC.
Owner: **product-manager**

### Non-Functional Requirements (NFR)
How well the system does it. Must have explicit acceptance criteria just like FRs.
Owner: **architect** (defines targets) + **product-manager** (validates they are met)

| NFR | Target | Acceptance Criterion | Measured by |
|---|---|---|---|
| API response time | p95 < 200ms | All list endpoints respond < 200ms under normal load | Grafana + pg timing |
| Data freshness | Scores within 1h of market close | `score_snapshot.as_of_date` = today by 19:00 ET/EET | Grafana pipeline dashboard |
| Ingest reliability | > 99% daily success rate | No more than 1 failed `ingest_run` per week | `ingest_run` table |
| Test coverage | ≥ 80% per module | CI fails below 80% | `--cov-fail-under=80` |
| Onboarding | New dev setup < 15 min | `git clone → make up → working system` | Manual verification |
| Migration safety | All migrations idempotent | CI migration-check workflow passes | GHA |
| Secret exposure | Zero secrets in git history | `gitleaks` CI scan passes | GHA |

NFRs must be tested just like FRs. If an NFR cannot be verified automatically, add it to the CI pipeline.

---

## Requirement Traceability Matrix (RTM)

Maintain `docs/requirements/traceability.md`. Format:

```markdown
| ID | User Story | Phase | AC Count | Design Artifact | Test File(s) | Status |
|----|---|---|---|---|---|---|
| US-01 | Ingest EOD prices for US top 50 | 1 | 4 | data-model-v1.md | test_storage_prices.py | Done |
| US-02 | Ingest Finnish (.HE) prices | 1 | 3 | data-model-v1.md | test_storage_prices.py | Done |
| US-03 | Schedule daily ingestion | 1 | 2 | sequence-ingest.md | test_scheduler.py | In Progress |
| NFR-01 | API p95 < 200ms | 1 | 1 | api-design.md | test_api_performance.py | Pending |
```

Update the RTM when:
- A story is added, changed, or completed
- A design artifact is produced
- A test file is created

The RTM is the source of truth for what has been built and what remains.

---

## MoSCoW Prioritization

Use MoSCoW within each phase to decide what ships vs what defers when time pressure occurs:

| Priority | Meaning | Rule |
|---|---|---|
| **Must** | Required for the phase to be considered complete | Cannot defer — blocks next phase |
| **Should** | High value, expected to ship | Defer only under explicit time pressure, log the decision |
| **Could** | Nice to have, adds value | First to defer when scope is tight |
| **Won't** | Deliberately excluded from this phase | Documented so it's not re-debated |

Every story in the backlog has a MoSCoW label. When a Must is threatened, escalate to orchestrator before deferring.

---

## Change Management

### When a requirement changes mid-phase:

1. **Document the change** — what changed, why, who requested it
2. **Impact assessment** — which design artifacts, tests, and implementations are affected?
3. **MoSCoW check** — does this change a Must? If so, what Must is being dropped to make room?
4. **Orchestrator approval** — changes affecting scope, design, or phase completion require orchestrator sign-off
5. **Update RTM** — reflect the change in the traceability matrix

### Change log format (in `docs/requirements/changes.md`):

```markdown
## YYYY-MM-DD — <short description>

**Requested by**: <user/analyst/architect>
**Change**: <what changed>
**Reason**: <why>
**Impact**: <which stories, artifacts, tests affected>
**Decision**: Approved / Deferred / Rejected
**Approved by**: orchestrator
```

### What never changes without explicit approval:
- Phase scope (adding stories to a phase already in progress)
- NFR targets (relaxing coverage or latency targets)
- Factor definitions or scoring weights (analyst must approve via `factor-research` process)

---

## Requirements Smells

Flag these to the orchestrator immediately:

| Smell | Example | Problem |
|---|---|---|
| Ambiguous AC | "should be fast" | Not testable — quantify |
| Missing error case | Only happy path AC | Incomplete coverage |
| Implementation in story | "use asyncpg to fetch prices" | Story dictates how, not what |
| Untraceable story | Story with no test file | Can't verify it was built |
| Orphan test | Test with no linked story | Unknown what requirement it validates |
| Gold plating | Engineer adds unasked features | Scope creep — remove or log as new story |
