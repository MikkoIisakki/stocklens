# Pulse web shell

White-label Next.js 15 app. One codebase, one branded deployment per domain.
Branding, region defaults, and the API contract come from
`config/domains/<name>.yaml`. See [ADR-008](../decisions/008-web-shell-nextjs.md).

## Quick start

```bash
cd web
cp .env.example .env.local      # set PULSE_DOMAIN, PULSE_API_BASE_URL, PULSE_API_KEY
npm install
npm run dev                     # http://localhost:3001
```

The backend API must be running and reachable at `PULSE_API_BASE_URL`. For
local dev with `docker compose up`:

- Backend: `http://localhost:8000`
- Master API key: set `MASTER_API_KEY=pulse_dev_local_only_change_me` in
  `.env` at the repo root, then use the same value as `PULSE_API_KEY`
  here.

## Pages

| Path | What it shows |
|---|---|
| `/` | Today's prices for the default region — line chart + raw interval table. |
| `/cheap-intervals` | Top-N cheapest slots ranked ascending by total c/kWh. |
| `/alerts` | Fired threshold alerts, newest first. |

All three accept `?region=...` and `?date=...` query params (date can be
`today`, `tomorrow`, or `YYYY-MM-DD`).

## Adding a new branded domain

1. Add `config/domains/<name>.yaml` (copy `energy.yaml`, edit fields).
2. Set `PULSE_DOMAIN=<name>` in the deployment env.
3. Same `next build`; nothing else changes.

## Commands

```bash
npm run dev        # development server
npm run build      # production build
npm run start      # serve production build
npm run lint       # eslint via next lint
npm run typecheck  # tsc --noEmit
```
