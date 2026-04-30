# Pulse

White-label screener platform. One codebase, multiple domain-focused apps — electricity spot prices, crypto, and stock screening. Each domain ships as a separately branded app built from shared infrastructure via configuration.

**Domains:**
- **Pulse Energy** — electricity spot price monitoring and cheap-interval alerts (ENTSO-E day-ahead, PT15M/PT60M)
- **Pulse Crypto** — crypto screening and price alerts (CoinGecko)
- **Pulse Stocks** — stock screening for US and Finnish markets (Phase 4+, app store gated)

## Getting started

```bash
# One-time: install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and set up
cp .env.example .env          # fill in DB password and API keys
uv sync --dev                 # create .venv and install all dependencies
uv run pre-commit install     # install git hooks (gitleaks + ruff + mypy on every commit)

# Start the system
make up                       # build and start all services
make migrate                  # apply DB migrations
make seed                     # load seed data
```

`GET http://localhost:8000/v1/health/ready` — confirm the system is running (no auth).

## API authentication

Domain endpoints (`/v1/energy/*`, `/v1/assets/*`) require an API key:

```bash
curl -H "Authorization: Bearer pulse_<your-key>" http://localhost:8000/v1/energy/prices?region=FI&date=today
```

For local dev, set `MASTER_API_KEY=pulse_dev` in `.env` and use that. For
production keys, issue them via:

```bash
docker compose exec api python -m app.tools.create_api_key --name pulse-mobile-prod
```

The raw key is printed once; only its SHA-256 hash is stored. To revoke,
set `revoked_at` on the row in `api_key`. See ADR-007.

## Development

```bash
make test       # run pytest with coverage
make lint       # ruff check
make typecheck  # mypy --strict
make fresh      # wipe everything and start clean
make shell-db   # open psql in the db container
```

## Web shell

`web/` is the Next.js 15 white-label app. Configure via `web/.env.local`
(see `web/README.md`); one build serves any domain by setting
`PULSE_DOMAIN`.

```bash
cd web
npm install
npm run dev    # http://localhost:3001
```

## Mobile shell

`mobile/` is the Expo (React Native) white-label app. Same domain-config
pattern as web; see `mobile/README.md` and ADR-009.

```bash
cd mobile
npm install
PULSE_DOMAIN=energy npx expo start
```

See [docs/PLAN.md](docs/PLAN.md) for the full project plan and task status.
