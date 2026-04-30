# ADR-010: EAS build pipeline driven by GitHub Actions

**Date**: 2026-04-30
**Status**: Accepted
**Deciders**: architect, devops, orchestrator

## Context

ADR-009 picked Expo + Expo Router as the mobile shell framework. Task
3.6 wires that shell into a build pipeline so a developer (or a tag
push) can produce signed iOS / Android binaries without owning a Mac
build server, manually rotating certificates, or running a long
`fastlane` checklist.

Constraints:

1. Different domains build to different Expo slugs (one App Store entry
   per branded app), driven by `PULSE_DOMAIN`.
2. iOS + Android signing credentials must live somewhere durable and
   shared across runs — not on a developer's laptop.
3. Builds need to be reproducible: same git commit + same env vars =
   same artefact.
4. The first electricity-app release (task 7.1) goes through this
   pipeline; later domains (crypto, stocks) reuse the same shape.

## Decision

### Build infrastructure

**EAS Build** (Expo Application Services) for both platforms. macOS
builds run on EAS's managed cloud; Linux builds are also EAS-hosted so
we don't pay for two flavours of CI runner. Bare React Native +
self-hosted Mac fastlane was rejected — the operational burden buys
nothing for a one-developer project on free-tier EAS.

### `mobile/eas.json` profiles

```
development      developmentClient on simulator/device
preview          internal distribution (TestFlight / signed APK)
production       base profile: channel "production", autoIncrement
energy-prod      extends production, env { PULSE_DOMAIN=energy }
crypto-prod      extends production, env { PULSE_DOMAIN=crypto }
stocks-prod      extends production, env { PULSE_DOMAIN=stocks }
```

`extends` keeps the profile pyramid honest: production-shape settings
(channel, autoIncrement) live in one place, branded variants only set
the `PULSE_DOMAIN` env override that `app.config.ts` reads. Adding a
new branded build is one block in `eas.json` plus a YAML file under
`config/domains/`.

### `.github/workflows/mobile-build.yml`

Two trigger surfaces:

1. **`workflow_dispatch`** with three inputs (`profile`, `platform`,
   defaults `preview` / `all`) — for ad-hoc preview builds.
2. **`push: tags: ['mobile-v*']`** — defaults to `energy-prod` / all
   platforms, so cutting `mobile-v1.0.0` ships a release.

Steps:

1. Checkout, set up Node 20 with npm cache (lockfile committed in 3.2).
2. `npm ci` for reproducibility.
3. `expo/expo-github-action@v8` configures the `EXPO_TOKEN` env so
   `eas-cli` doesn't prompt.
4. `eas build --non-interactive --no-wait` queues the job on EAS;
   results land in the dashboard. Adding `--wait` would block the
   runner for the duration of the build (15–25 min), wasting GitHub
   minutes.

### Required GitHub secrets

| Secret | Source | Used by |
|---|---|---|
| `EXPO_TOKEN` | `expo.dev` → Access Tokens | `eas` CLI auth |
| `EXPO_PUBLIC_API_BASE_URL` | Pulse deployment URL | Embedded in JS bundle |
| `EXPO_PUBLIC_API_KEY` | Output of `app.tools.create_api_key` | Bundled per ADR-009 |

`EXPO_TOKEN` is rotatable from the Expo dashboard without changing
your account password. Store one token per CI environment; revoke +
reissue if a runner is compromised.

### Bundle / package identifiers

`app.config.ts` derives `ios.bundleIdentifier` and `android.package` as
`${PULSE_BUNDLE_PREFIX}.${domain.name}` so each branded build has a
distinct App Store / Play Store identity. Default prefix is
`com.example.pulse` — operators must override it via
`PULSE_BUNDLE_PREFIX` to a prefix they own (e.g.
`fi.iisakki.pulse`) before submitting to a real store.

## Alternatives considered

### GitHub macOS runners running fastlane

Rejected. ~$0.08/min × ~20-min iOS builds = ~$1.60 per build before
queue overhead, and we'd still write fastlane configs ourselves. EAS
free tier covers our expected cadence (few builds per month per
domain) at zero marginal cost.

### Self-hosted Mac mini runner

Rejected for now. Realistic for a team that already maintains macOS
infra; not realistic for a one-person project. Revisit if EAS pricing
changes or we hit their job-time caps.

### One workflow per domain (mobile-build-energy.yml, ...)

Rejected. The dispatch-input + tag pattern handles all three branded
profiles from one file; copying the workflow per domain would just
mean three drift sources. The matrix-of-profiles approach is also on
the table once the cron-style cadence justifies parallelism.

### Unified backend + mobile workflow

Rejected. Backend CI runs on every push; mobile builds are on-demand
and cost EAS minutes. Splitting them keeps the cheap path cheap.

## Consequences

**Positive**:

- One file to ship a new branded mobile app: `eas.json` profile +
  `config/domains/*.yaml` + (optional) bundle prefix override.
- No Mac build server to maintain; no fastlane config to write.
- OTA updates available via the same `channel` field — unlocked when
  needed without infra work.

**Negative / trade-offs**:

- Builds can't run before EAS credentials and the EXPO_TOKEN secret
  are provisioned — so the workflow can fail loudly until step 5 of
  the prereqs is completed. Documented at the top of the workflow.
- EAS pricing model: free tier ~30 builds/month for individuals, then
  per-minute. Cheap today, watch the meter as cadence grows.
- The `EXPO_PUBLIC_*` env vars are bundled into the JS — see ADR-009
  for the API-key migration path.

**Revisit when**:

- We exceed the EAS free tier or hit job-time caps.
- A native module needs a custom dev client EAS doesn't cover.
- The team grows and a self-hosted Mac builder is cheaper than EAS
  minutes.

## References

- Task 3.6 in `docs/PLAN.md`.
- ADR-009: mobile shell — sibling decision.
- `mobile/eas.json`: build profiles.
- `.github/workflows/mobile-build.yml`: dispatch + tag triggers.
- https://docs.expo.dev/build/introduction/
