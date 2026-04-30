# ADR-009: White-label mobile shell — Expo SDK 52 + Expo Router

**Date**: 2026-04-30
**Status**: Accepted
**Deciders**: architect, frontend, orchestrator

## Context

Phase 3 calls for a white-label mobile shell (task 3.2). Goals mirror
the web shell (ADR-008): one codebase, multiple branded App Store
listings, branding driven by `config/domains/<name>.yaml`. The mobile
shell is a prerequisite for the EAS build pipeline (3.6) and the push
notifications layer (3.4).

Decisions clustered around three questions:

1. **Framework**: bare React Native vs Expo, classic vs Expo Router.
2. **Domain config**: how to feed the YAML into a JS bundle that runs
   on a phone with no filesystem access to the repo.
3. **API auth**: how to ship a Bearer token without compromising the
   key model from ADR-007.

## Decision

### Framework

**Expo SDK 52** with **Expo Router** v4. Reasons:

- Same file-system routing model as the web shell's Next.js App Router
  — a developer who can navigate one can navigate the other.
- EAS build/submit pipeline (task 3.6) is the most mature path to App
  Store distribution; Expo is the tightest fit.
- Native modules we need (push, secure storage, file system) are first
  party in Expo and don't require a custom dev client for v1.
- React Native 0.76 + new architecture enabled by default — better
  performance baseline.

Bare React Native was rejected: the "eject when needed" insurance
costs more than it saves at this scope, and Expo's prebuild flow makes
ejection painless if it ever becomes necessary.

### Domain config

`mobile/app.config.ts` runs at **build time** under Node, reads
`config/domains/<name>.yaml` from the repo root via `fs` + `js-yaml`,
and injects the parsed object into Expo's `extra` field. At runtime,
`src/lib/domain.ts` reads the value back via
`Constants.expoConfig?.extra.domain`.

Selecting a domain at build time:

```bash
PULSE_DOMAIN=energy   npx expo start
PULSE_DOMAIN=crypto   eas build --profile crypto-prod    # future
```

This mirrors the Python `app.common.domain` (ADR-006) and the web
`web/src/lib/domain.ts` (ADR-008). Three sources of truth for the same
schema; a fitness function in CI verifies they agree (existing
`test_domain_config.py` covers Python; web/mobile typecheck guards the
TS shape).

### API authentication — v1 compromise

The mobile shell sends `Authorization: Bearer <key>` per ADR-007. The
key is read from `EXPO_PUBLIC_API_KEY` at build time, exposed to JS
via `Constants.expoConfig.extra.apiKey`.

**This is a known v1 limitation**: anything in the JS bundle can be
extracted from a shipped APK/IPA. The token *is* a build-time secret,
not a per-user identity. Acceptable for the first electricity-app
release because:

- The key only authorises **read** access to public-ish regional data.
  Worst-case extraction = unauthenticated access to ENTSO-E day-ahead
  prices that are also free at source.
- One key per build profile means revoke-and-rebuild is a real
  remediation (rotate on the api_key table, ship a new app version).

**Migration path** (future task, not in this ADR):

1. Add `/v1/auth/register-device` returning a per-install token
   (limited scope, time-bounded).
2. Mobile app calls it on first launch with the build-time bootstrap
   key.
3. Per-install token stored in `expo-secure-store`, used for all
   subsequent calls.
4. Bootstrap key gets read-only / register-only scope; the per-install
   key gets full read scope.

That work is gated on the first feature requiring per-user state
(saved alerts, watchlists, notification preferences) — pure YAGNI
until then.

### Styling

Inline `StyleSheet` for v1; Tailwind/NativeWind deferred. Reasons:

- The mobile shell has three thin screens; a styling system is more
  ceremony than benefit at this scope.
- NativeWind v4 has its own babel plugin and metro config quirks;
  punt the integration cost until a real design system lands.
- Visual parity with the web shell is not a v1 goal — a designer would
  redo both anyway when branding gets polished.

### CI

`.github/workflows/mobile-ci.yml` runs `npm ci` + `npm run typecheck`
on changes under `mobile/` or `config/domains/`. Build/EAS work lands
in task 3.6. Lint via `expo lint` is added as a follow-up once the
project is stable enough for the eslint config to be tuned.

## Alternatives considered

### NativeWind v4 + Tailwind from day one

Rejected for v1. Useful when there's a design system to share with the
web shell. The integration cost (babel plugin, metro config, type
generation) is not free, and the styles would still need refactoring
when the actual design lands.

### Bare React Native + react-navigation

Rejected. Lose Expo Router's file-system parity with Next.js, lose
EAS-managed code-signing, lose Expo's first-party push module. The
trade-off only pays off if we hit an Expo limitation, which we
haven't.

### Per-install JWT now

Rejected. Requires a backend register-device endpoint that doesn't
exist yet; gating Phase 3 mobile shell on that work would push 3.2
into Phase 7 territory. Build-time bootstrap key + clear migration
path is honest about the scope.

### Reading the YAML at runtime via `expo-asset` or a fetched file

Rejected. The YAML is intrinsic to the build identity — different
bundles for different domains. Bundling it as an asset would let a
`crypto` build accidentally load `energy.yaml` if the env wasn't set
right. Build-time injection is single-source-of-truth.

## Consequences

**Positive**:

- Same `cp config/domains/energy.yaml crypto.yaml` workflow as the web
  shell adds a new branded mobile app.
- Three screens validate the API contract end-to-end on a physical
  device.
- EAS pipeline (3.6) plugs in without architectural changes.

**Negative / trade-offs**:

- API key is in the JS bundle — see the migration-path section above.
- Three TS interface mirrors of the same YAML schema (Python, web,
  mobile). When a field lands, three files change in the same PR. If
  the count grows past three or the schema gets richer, generate the
  TS types from the Pydantic model instead.
- Inline styles will need a redesign pass before the App Store
  release.

**Revisit when**:

- A feature needs per-user server state — ship the device-registration
  flow.
- A second domain (crypto) ships and styling drift becomes obvious —
  pull a shared component lib out of `web/` and `mobile/`.
- The new architecture (bridgeless) breaks a third-party module we
  depend on — turn it off in `app.json`.

## References

- Task 3.2 in `docs/PLAN.md`.
- ADR-006: domain config YAML schema.
- ADR-007: API key auth.
- ADR-008: web shell — sibling decision.
- `mobile/` directory at repo root.
- `.github/workflows/mobile-ci.yml`.
