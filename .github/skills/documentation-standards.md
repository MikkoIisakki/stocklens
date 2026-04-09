---
name: documentation-standards
description: Documentation responsibilities per agent role, ADR format, README standards, docstring conventions, API doc generation, and changelog process. Used by all agents.
---

# Documentation Standards

## Principle: Documentation as Code

Documentation lives in the repo, versioned alongside the code it describes. A doc that diverges from the code is worse than no doc — it misleads.

**Rules**:
- Every doc change ships in the same PR as the code change it documents
- Docs are reviewed like code — vague or stale docs are rejected in the DoD check
- No external wiki, no Confluence, no Google Docs — everything in `docs/` or inline

---

## Documentation by Agent Role

### Analyst → `docs/analysis/`
- Factor specification documents (one per factor)
- Algorithm design documents
- Backtest result summaries
- Market regime notes

### Architect → `decisions/`
- Architecture Decision Records (ADRs) — one file per decision
- System context, container, and component diagrams (Mermaid in `docs/architecture/`)
- Data model documents (`docs/architecture/data-model.md`)
- NFR matrix (`docs/architecture/nfr-matrix.md`)

### Engineer → inline + `docs/`
- Python docstrings on all public functions and classes
- Module-level `README.md` for complex modules
- `CHANGELOG.md` entries (auto-generated from Conventional Commits)

### DevOps → `docs/runbooks/`
- Operational runbooks (one per failure scenario)
- Deployment guide (`docs/runbooks/deployment.md`)
- Local setup guide (`docs/runbooks/local-setup.md`)

### Product Manager → `docs/requirements/`
- Requirement traceability matrix (`docs/requirements/traceability.md`)
- Change log (`docs/requirements/changes.md`)
- Phase retrospective notes

---

## Architecture Decision Records (ADRs)

ADRs live in `decisions/`. Every significant architecture or technology choice gets one. They are append-only — never edit a past ADR, write a new one that supersedes it.

### File naming
`decisions/NNN-short-title.md` — e.g. `decisions/001-modular-monolith.md`

### ADR template

```markdown
# ADR-NNN: <Title>

**Date**: YYYY-MM-DD
**Status**: Proposed | Accepted | Superseded by ADR-NNN
**Deciders**: architect, [orchestrator if cross-cutting]

## Context

What is the problem or situation that requires a decision?
What constraints apply (budget, timeline, existing stack, team size)?

## Options Considered

### Option 1: <Name>
- **Pros**: ...
- **Cons**: ...

### Option 2: <Name>
- **Pros**: ...
- **Cons**: ...

## Decision

Chose Option X because [specific reason tied to context and constraints].

## Consequences

**Positive**:
- ...

**Negative / trade-offs**:
- ...

**Revisit when**:
- [concrete trigger, not "if we need to"]
```

### When to write an ADR
- Technology choice (language, framework, database, queue)
- Architectural pattern (monolith vs services, CQRS, event sourcing)
- Data model decision with long-term implications
- Any decision that, if changed later, would require significant rework

Do NOT write an ADR for: implementation details, library internals, variable naming.

---

## Python Docstrings

All public functions, classes, and modules must have docstrings. Use Google style.

```python
def compute_rsi_signal(prices: pd.Series, length: int = 14) -> Signal:
    """Compute RSI signal from a price series.

    Args:
        prices: Closing prices in chronological order (oldest first).
        length: RSI lookback period in days. Defaults to 14.

    Returns:
        Signal with name='RSI', value=float, signal_type in
        ('bullish', 'neutral', 'bearish', 'unavailable').
        Returns signal_type='unavailable' with weight=0.0 if fewer
        than `length` prices are provided.

    Raises:
        ValueError: If prices is empty.
    """
```

**Module docstring** (top of every file):
```python
"""Technical signal computation for the pulse factor engine.

Computes RSI, MACD, Bollinger Band, EMA cross, and OBV signals from
daily price data. All functions return Signal objects — see common/types.py.

Factor thresholds and weights are defined by the analyst agent (analyst.md).
Do not change thresholds without analyst approval.
"""
```

**When docstrings are NOT required**:
- Private functions (`_helper()`) — only if the logic is non-obvious
- Test functions — test name is the documentation
- Simple properties / dataclass fields — use field descriptions in Pydantic models instead

---

## Module README

Complex modules (more than 3 files or non-obvious design) get a `README.md`:

```markdown
# Module: signals/

Computes technical and fundamental signals from ingested market data.

## Responsibilities
- Reads from: `daily_price`, `factor_snapshot`, `fundamentals` (via storage/)
- Writes to: `factor_snapshot` (via storage/)
- Does NOT: access DB directly, call external APIs

## Files
- `technical.py` — RSI, MACD, Bollinger, EMA cross, OBV, ATR
- `fundamental.py` — EPS acceleration, margin expansion, valuation, quality
- `sentiment.py` — news sentiment rolling average

## Adding a New Signal
1. Get analyst approval (factor specification + weight proposal)
2. Add computation function to the appropriate file
3. Add unit tests in `tests/unit/signals/`
4. Add column to `factor_snapshot` table via migration
5. Update `scoring/rule_based.py` with the new weight
6. Update `docs/analysis/<factor-name>.md`
```

---

## API Documentation

FastAPI generates OpenAPI automatically from code. Ensure it stays accurate:

- Every router function has `summary=` and `description=` parameters
- Every Pydantic response model has `model_config` with `json_schema_extra` for examples
- Run `make docs` to regenerate `docs/api/openapi.json` — commit it with every API change

```python
@router.get(
    "/assets/{symbol}",
    summary="Get asset detail",
    description="Returns the latest metadata and score for a single asset.",
    response_model=AssetDetailResponse,
    responses={404: {"model": ErrorResponse, "description": "Asset not found"}},
)
async def get_asset(symbol: str, conn=Depends(get_conn)) -> AssetDetailResponse:
    ...
```

---

## Changelog

`CHANGELOG.md` lives at the repo root. Updated on every release (version tag).

Generated from Conventional Commits using `git-cliff` or `conventional-changelog`:

```bash
# Generate changelog for a new release
git cliff --tag v0.2.0 --output CHANGELOG.md
```

Format (Keep a Changelog standard):
```markdown
# Changelog

## [0.2.0] - 2026-05-01

### Added
- RSI signal with oversold/overbought thresholds (#12)
- Finnish market (.HE) ingestion support (#8)

### Fixed
- Helsinki market hours off by one hour during DST (#15)

### Changed
- Scoring weights rebalanced based on analyst review (#14)
```

---

## Docs Folder Structure

```
docs/
  analysis/               ← analyst: factor specs, algorithm docs
    rsi-factor.md
    eps-acceleration-factor.md
  architecture/           ← architect: diagrams, data model, NFR matrix
    system-context.md
    data-model.md
    nfr-matrix.md
  requirements/           ← product-manager: RTM, change log
    traceability.md
    changes.md
  runbooks/               ← devops: operational procedures
    local-setup.md
    deployment.md
    failed-migration.md
    stale-data.md
  api/                    ← auto-generated
    openapi.json

decisions/                ← architect: ADRs (repo root level)
  001-modular-monolith.md
  002-postgresql-over-timescaledb.md
  003-trunk-based-development.md

CHANGELOG.md              ← repo root
```

---

## Living Documentation Rules

1. **PR that changes behaviour must update the relevant doc in the same commit** — no "I'll update the docs later"
2. **Stale docs are bugs** — if you find a doc that contradicts the code, fix the doc (or the code) immediately
3. **ADRs are append-only** — mark old ones as `Superseded`, write a new one
4. **Grafana dashboards are docs** — they visualise system behaviour; keep them accurate and provisioned as code
5. **Test names are docs** — `test_rsi_below_30_returns_bullish` tells you the rule; write test names as specifications
