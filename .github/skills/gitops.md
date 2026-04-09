---
name: gitops
description: GitOps principles, branch strategy, environment promotion, image tagging, rollback, and drift prevention for the stocklens project.
---

# GitOps

## Core Principle

**Git is the single source of truth for all system state.**

Every change to infrastructure, config, or application code flows through a Git commit. The running system must always reflect what is in the `main` branch. No out-of-band changes, no SSH-and-edit, no manual `docker compose up` in production.

```
Developer → PR → CI passes → Merge to main → CD applies automatically → System matches main
```

If the running system differs from `main`, that is a bug.

---

## Branch Strategy — Trunk-Based Development

Use trunk-based development, not GitFlow. `main` is always deployable.

```
main ──────────────────────────────────────────────────► (always deployable)
        │           │           │
    feature/x   feature/y   fix/z
     (short-lived, < 2 days ideally)
```

**Rules**:
- `main` is protected — no direct pushes, CI must pass before merge
- Feature branches are short-lived — avoid long-running branches that diverge
- One PR per logical change — don't batch unrelated work
- Squash merge to `main` to keep history readable
- Tags mark releases: `v0.1.0`, `v0.2.0` (semantic versioning)

**Branch naming**:
```
feature/<short-description>     feat/add-rsi-signal
fix/<short-description>         fix/missing-fi-prices
chore/<short-description>       chore/update-dependencies
docs/<short-description>        docs/update-api-design
```

---

## Environment Promotion

```
Local (Docker Compose)
    │  developer verifies manually
    ▼
main branch
    │  CI passes (tests + lint + coverage + migration check)
    ▼
Stage B: DigitalOcean Droplet   ← auto-deployed on merge to main (Phase 3)
    │  smoke tests pass
    ▼
(Phase C: DOKS production)      ← manual approval gate before prod
```

For Phase A & B (current): `local → main → Droplet`. No staging environment needed — personal use tolerates brief downtime.

For Phase C (multi-user): add a `staging` environment with a separate Droplet that auto-deploys; production requires manual approval in GHA.

---

## Image Tagging Strategy

Never deploy `latest` in production. Every deployed image is traceable to a Git commit.

```
# Tag format
ghcr.io/owner/stocklens-backend:<git-sha>      # primary, immutable
ghcr.io/owner/stocklens-backend:v0.2.0         # release tag
ghcr.io/owner/stocklens-backend:main           # branch tip (dev only)
```

**GHA build + push workflow** (`image-build.yml`, Phase 3):
```yaml
- name: Build and push
  uses: docker/build-push-action@v5
  with:
    context: ./backend
    target: prod
    push: true
    tags: |
      ghcr.io/${{ github.repository }}/backend:${{ github.sha }}
      ghcr.io/${{ github.repository }}/backend:${{ github.ref_name }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

---

## CD — Applying Changes

### Stage B (Droplet, Docker Compose)

CD workflow SSHes to the Droplet, updates the compose file, and runs `docker compose up -d`. The Droplet always runs whatever is in `main`.

```bash
# On the Droplet — CD script
cd /opt/stocklens
git fetch origin
git reset --hard origin/main          # Droplet matches main, always
docker compose pull                   # pull new image tags
docker compose up -d --build          # apply changes
psql $DATABASE_URL -f db/migrations/latest.sql  # apply pending migrations
```

**No drift allowed**: if someone SSH'd and made a manual change, `git reset --hard origin/main` eliminates it.

### Stage C (DOKS, Kubernetes)

Use Flux CD or Argo CD for GitOps reconciliation. The cluster continuously watches `k8s/` in `main` and applies any drift. Manual `kubectl apply` is forbidden.

---

## Rollback Strategy

**Rollback = revert the commit in Git, let CD re-apply.**

Never rollback by SSH-ing and running old commands.

```bash
# Rollback procedure
git revert <bad-commit-sha>    # creates a new revert commit
git push origin main           # triggers CD, which applies the revert
```

For a bad DB migration: write a new migration that undoes it. Never run `DROP TABLE` manually.

```sql
-- db/migrations/003_revert_bad_column.sql
ALTER TABLE factor_snapshot DROP COLUMN IF EXISTS bad_column;
```

---

## Drift Prevention

| Risk | Prevention |
|---|---|
| Manual infra changes | `git reset --hard origin/main` in every CD run |
| Untracked config | `.env.example` always kept in sync with required vars |
| Grafana dashboard click-ops | Dashboards provisioned from files; Grafana UI is read-only in prod |
| DB schema divergence | All migrations in `db/migrations/`, applied in CI and CD |
| Secrets in code | `git-secrets` or `gitleaks` in CI pre-check |

Add `gitleaks` as a GHA step to catch accidentally committed secrets:
```yaml
- name: Check for secrets
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## Pull Request Standards

Every PR must have:
- A descriptive title (`feat:`, `fix:`, `chore:`, `docs:` prefix)
- A description explaining **why**, not just what
- CI passing (tests + lint + coverage + migration check)
- At least self-review against the engineer/devops checklist

PR title format (Conventional Commits):
```
feat: add RSI signal to factor engine
fix: missing daily price for Helsinki close time
chore: bump yfinance to 0.2.38
docs: update API design for /v1/rankings endpoint
refactor: extract scoring weights to config file
test: add edge cases for insufficient RSI data
ci: add gitleaks secret scanning
```

These commit prefixes enable automated changelog generation.
