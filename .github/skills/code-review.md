---
name: code-review
description: Structured review rubric for correctness, regressions, test adequacy, migration safety, and security in pulse.
---

# Code Review Skill

Use this skill when performing independent review.

## Review Priorities

1. Correctness and regressions
2. Data safety and migration safety
3. Security and secret handling
4. Test adequacy
5. Maintainability and documentation alignment

## Checklist

- Behavior matches acceptance criteria and API contract.
- Existing behavior is not silently changed.
- Error handling is explicit and observable (logs + status codes).
- DB changes are idempotent and backward-safe.
- No secret values in repo files or examples beyond placeholders.
- New behavior is tested (unit/integration as appropriate).
- Docs/runbooks updated when operational behavior changed.

## Findings Format

Report only actionable findings. Order by severity.

```
- [High] Rankings endpoint returns stale data window
  File: services/api/routers/rankings.py:34
  Why: breaks ranking correctness and user trust
  Fix: filter latest rows by symbol after date window logic update
```

## Approval Criteria

Approve only when:

- No `Critical` or `High` findings remain
- Test coverage is adequate for changed risk areas
- CI checks pass

If you approve with residual risk, list it explicitly.
