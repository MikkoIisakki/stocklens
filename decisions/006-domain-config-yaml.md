# ADR-006: Domain config lives in `config/domains/<name>.yaml`

**Date**: 2026-04-29
**Status**: Accepted
**Deciders**: architect, orchestrator

## Context

Pulse is a white-label platform: one codebase, one app per domain
(energy, stocks, crypto). Until task 3.1, each domain's metadata was
spread across multiple files with no single source of truth:

- Region list and VAT/tax: `db/seeds/002_energy_regions.sql` (SQL).
- Default alert thresholds: `db/seeds/003_energy_alert_rules.sql` (SQL).
- Scheduler cron times: hardcoded in `backend/app/jobs/scheduler.py`.
- Display names, branding placeholders: nowhere — mentioned in PLAN.md prose.

Adding a new domain (stocks in Phase 4, crypto in Phase 6) would mean
duplicating this scattering. EAS build profiles (task 3.6) and the
white-label web/mobile shells (3.5/3.2) need a structured place to read
"what is *this* app's name, which API endpoints does it expose, what
defaults does it ship with."

## Decision

Adopt one YAML file per domain at `config/domains/<name>.yaml`, loaded
through a typed Pydantic model in `backend/app/common/domain.py`.

Schema (minimal, matches what energy actually needs today):

```yaml
name: energy
display_name: Pulse Energy
description: ...

schedule:
  ingest_cron:
    hour: 11
    minute: 30
    timezone: UTC
  job_id: energy_price_ingest
  job_name: ENTSO-E day-ahead price ingest

regions:
  - code: FI
    name: Finland
    country: FI
    vat_rate: 0.2550
    electricity_tax_c_kwh: 2.2400
  # ... five more

alert_thresholds_c_kwh:
  FI: 30.00
```

Loaded via `load_domain_config("energy")`, returning a typed
`DomainConfig` with `lru_cache` so repeated calls are free.

## Conventions

1. **One file per domain.** No `domains.yaml` mega-file; one file per app
   keeps EAS build profiles and white-label shells reading the slice
   they care about.
2. **Schema is per-need, not pre-designed.** When stocks lands in Phase
   4, add fields used by stocks (`assets`, `factor_weights`); do not
   pre-add empty `assets: []` to energy. Validate via Pydantic.
3. **YAML is the source of truth, SQL seeds and Python constants are
   downstream.** Today the energy seed is hand-written and matches the
   YAML by convention; a fitness-function test (task 3.1's
   `test_energy_fi_matches_seed_values`) verifies this. Future work may
   generate the seed from the YAML, but generation isn't required to
   adopt the convention.
4. **Cross-field validation lives in the Pydantic model.**
   `model_validator` rejects `alert_thresholds_c_kwh` keys that don't
   match a region code, etc.
5. **Tests load fixture YAML from `tmp_path`** rather than mutating the
   production cache. Production calls take no arg; tests pass
   `config_dir=tmp_path`.
6. **No env-var interpolation in the YAML.** Secrets live in `.env` and
   `Settings`; YAML carries only public config. If a domain needs a
   secret (provider tokens), it goes in `Settings`, not the YAML.

## Alternatives considered

### One mega `domains.yaml` with all domains nested

Rejected: EAS builds and white-label shells should be able to load just
"their" config without parsing unrelated domains. Diffs are also clearer
when each domain's history is its own file.

### TOML / JSON instead of YAML

Rejected: the file is human-edited (operations, branding, cron times);
YAML wins on readability for nested structures. PyYAML is already a
transitive dep (lxml, mkdocs); making it explicit costs nothing.

### Database table (`domain_config`) as the source of truth

Rejected for now: would couple "what app are we building?" to a running
DB. EAS builds happen in CI without a DB; mobile branding would need an
API call before first launch. Files in the repo make this trivial.
Revisit if domain config needs to be runtime-mutable per tenant
(multi-tenant SaaS scenario, not our current trajectory).

## Consequences

**Positive**:

- New domains add a YAML file; the loader pattern is unchanged.
- `scheduler.py` reads cron from YAML — operators tune ingest times
  without code review.
- White-label web/mobile shells (tasks 3.2, 3.5) and EAS pipeline (3.6)
  have a documented contract to read.
- Tests can synthesise fixture YAML for edge cases without touching the
  production file.

**Negative / trade-offs**:

- Two sources of truth in transition (YAML and SQL seed) until a
  generator is added — mitigated by the
  `test_energy_fi_matches_seed_values` fitness test.
- Pydantic schema migrations as the model evolves require updating
  every domain file in the same PR.

**Revisit when**:

- A domain needs config that varies per deployed tenant (then DB-backed
  config makes sense alongside the file-backed defaults).
- The YAML grows large enough that nested files (`config/domains/energy/`
  with `regions.yaml`, `branding.yaml`, etc.) become more readable than
  one file.

## References

- Task 3.1 in `docs/PLAN.md`.
- ADR-001 (modular monolith): the loader is a common-layer module
  importable from any domain slice.
