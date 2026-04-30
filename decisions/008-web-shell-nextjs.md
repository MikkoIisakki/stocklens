# ADR-008: White-label web shell — Next.js 15 App Router

**Date**: 2026-04-30
**Status**: Accepted
**Deciders**: architect, frontend, orchestrator

## Context

Phase 3 calls for a white-label web shell (task 3.5) — one Next.js
codebase that ships as multiple branded apps (energy first, crypto and
stocks later). The shell must:

1. Read its branding from a domain-specific config so a single `next
   build` produces the same artefact regardless of brand, with the brand
   picked at deploy time via env var.
2. Talk to the existing Pulse REST API using the API key auth shape
   from ADR-007 — without leaking the key to the browser.
3. Render today's prices, the cheapest intervals, and the alert list
   for the configured default region — enough to validate the white-label
   pattern before committing to a mobile shell.

Out of scope for this ADR: user accounts, dark mode, i18n, design
system. Each is a future, additive change.

## Decision

### Framework

**Next.js 15 with App Router**, TypeScript strict mode, Tailwind v3.
Reasons:

- React Server Components allow API calls to run on the server; the
  `PULSE_API_KEY` never ships to the browser.
- App-Router `searchParams` give us per-request region/date selection
  without a state-management library.
- File-system routing maps cleanly to one page per domain feature.
- Tailwind requires no design-system commitment; a deeper component
  library can land later when there's enough surface to justify one.

### Domain config consumption

The shell reads `config/domains/<name>.yaml` (the same files the backend
consumes per ADR-006) at server-component boundaries:

```ts
const cfg = loadDomainConfig();   // reads PULSE_DOMAIN env var
cfg.display_name                  // "Pulse Energy"
cfg.default_region                // first region in the list
```

`loadDomainConfig` is `import "server-only"` so any accidental import
from a client component fails at build time. The Next.js
`outputFileTracingIncludes` config copies the YAML into the build
output so containerised deployments don't need to mount the repo.

### Branding

Today: `display_name`, `description`, region list, default region come
from the YAML. CSS custom properties (`--brand-primary`,
`--brand-foreground`) are defined in `globals.css` and consumed by
`tailwind.config.ts` via `rgb(var(--brand-primary))`. Domains tweak
colors by overriding the variable values (future enhancement; not
required to ship). No domain-specific JS logic exists in this PR — the
shell is genuinely identical across domains.

### API auth

Server components import a `lib/api.ts` helper that reads
`PULSE_API_BASE_URL` and `PULSE_API_KEY` from env vars and sends
`Authorization: Bearer <key>` on every fetch. The key never appears in
client bundles. Errors surface as a typed `PulseApiError` so pages can
render a friendly panel instead of crashing.

### Pages

- `/` — today's interval prices for the default region. Recharts line
  chart + raw table.
- `/cheap-intervals` — top-N cheapest slots, ranked.
- `/alerts` — fired threshold alerts, newest first.

All three accept `?region=...` and `?date=...` query params so the same
deployment can render any seeded region without redeploying. Default
region comes from the YAML.

### CI

A new `.github/workflows/web-ci.yml` runs `npm install && npm run lint &&
npm run typecheck && npm run build` on changes under `web/` or
`config/domains/`. The backend CI workflow is unchanged. Build env vars
are placeholders — `next build` doesn't make API calls.

## Alternatives considered

### Plain React with Vite

Rejected. SPA means the API key has to live somewhere the browser can
reach, which means a backend-for-frontend would be required anyway —
and at that point we want Next.js's RSC support, not Vite + Express.

### Astro

Rejected. Astro's island architecture is great for static-first sites
but the energy app is mostly dynamic data fetched per request; RSC fits
better. Revisit when there are static marketing pages to colocate with
the app.

### One Next.js codebase per domain (no white-label)

Rejected. Three near-identical codebases drift in three directions; the
whole point of the white-label platform is to amortise the chrome.

### Branding stored in a database table

Rejected for now. Domain branding doesn't change between deploys, so a
file in the repo is simpler, atomically versioned with code, and works
in CI. Revisit if domains grow per-tenant.

## Consequences

**Positive**:

- Shipping a new branded app is `cp config/domains/energy.yaml
  crypto.yaml`, edit, set `PULSE_DOMAIN=crypto`, build.
- API key never leaves the server — easier to audit, easier to rotate.
- Pages are server-rendered: no client-side loading spinner, fast first
  paint, works without JS for the table view.

**Negative / trade-offs**:

- Recharts is a sizable client-side dep just for one chart. Lazy-load
  later if bundle size matters; for now it's loaded eagerly on the
  home page.
- Two source-of-truth schemas (Python Pydantic + TS interface). When a
  new field lands, both files must change in the same PR. ADR-006
  already calls this out; no extra tooling for now.
- Manual `next-env.d.ts` will be generated by `next build` on first run
  — gitignored.

**Revisit when**:

- Mobile shell (task 3.2) lands and we discover useful component-level
  primitives that should live in a shared package.
- A domain needs a feature flag or A/B test — at that point a config
  table or remote-config service is justified.
- We exceed one or two pages of dynamic data and a real component
  library (or Radix + a generated design system) becomes worth the
  cost.

## References

- Task 3.5 in `docs/PLAN.md`.
- ADR-006: domain config YAML schema.
- ADR-007: API key auth — the shape this shell consumes.
- `web/` directory at repo root.
- `.github/workflows/web-ci.yml`.
