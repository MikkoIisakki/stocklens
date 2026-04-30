# Pulse mobile shell

White-label Expo / React Native app. One codebase, multiple branded App
Store / Play Store listings. Branding, region defaults, and the API
contract come from `config/domains/<name>.yaml` at build time. See
[ADR-009](../decisions/009-mobile-shell-expo.md).

## Quick start

```bash
cd mobile
cp .env.example .env
npm install

# Set the build-time domain (and read the rest from .env)
export $(grep -v '^#' .env | xargs)
PULSE_DOMAIN=energy npx expo start
```

Press `i` (iOS sim), `a` (Android emulator), or `w` (web preview).

The backend API must be reachable at `EXPO_PUBLIC_API_BASE_URL`. For
local dev with `docker compose up` and a phone on the same Wi-Fi, set
`EXPO_PUBLIC_API_BASE_URL=http://<your-laptop-LAN-ip>:8000` —
`localhost` won't resolve from the device.

## Screens

| Path | What it shows |
|---|---|
| `/` (`app/index.tsx`) | Today's interval prices for the default region — table view. |
| `/cheap-intervals` | Top 10 cheapest slots ranked ascending by total c/kWh. |
| `/alerts` | Fired threshold alerts, newest first. |

## Adding a new branded domain

1. Add `config/domains/<name>.yaml` (copy `energy.yaml`, edit fields).
2. Set `PULSE_DOMAIN=<name>` in the EAS build profile (or local env).
3. Same `expo build` / `eas build` — no code changes.

## Commands

```bash
npm run typecheck   # tsc --noEmit
npm run start       # expo start
npm run ios         # expo start --ios
npm run android     # expo start --android
npm run web         # expo start --web
```

## Production builds (EAS)

EAS-driven builds for the App Store / Play Store. See ADR-010.

```bash
# One-time setup per branded slug:
npx eas login
PULSE_DOMAIN=energy npx eas init               # registers pulse-energy
PULSE_DOMAIN=energy npx eas credentials        # provisions iOS certs / Android keystore

# Manual local build:
PULSE_DOMAIN=energy EXPO_PUBLIC_API_BASE_URL=https://... \
EXPO_PUBLIC_API_KEY=pulse_... \
npx eas build --profile energy-prod --platform all
```

CI also runs the same flow:

- `.github/workflows/mobile-build.yml` — manually dispatch a build with a
  profile of your choice, or push a `mobile-v*` tag for the production
  release path. Requires `EXPO_TOKEN`, `EXPO_PUBLIC_API_BASE_URL`, and
  `EXPO_PUBLIC_API_KEY` repository secrets.

Adding a new branded build = `eas.json` profile entry + a YAML in
`config/domains/`. Override the bundle ID prefix via
`PULSE_BUNDLE_PREFIX` to a domain you own.

## Why is the API key in the bundle?

Honest v1 trade-off documented in ADR-009: the key is a build-time
bootstrap secret with read-only scope, NOT a per-user identity. Per-
install device registration lands when a feature needs personal user
state.
