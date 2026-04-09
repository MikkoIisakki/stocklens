# Pulse

White-label screener platform. One codebase, multiple domain-focused apps — electricity spot prices, crypto, and stock screening. Each domain ships as a separately branded app built from shared infrastructure via configuration.

**Domains:**
- **Pulse Energy** — electricity spot price monitoring and cheap-hour alerts (Nordpool/ENTSO-E)
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

`GET http://localhost:8000/v1/health/ready` — confirm the system is running.

## Development

```bash
make test       # run pytest with coverage
make lint       # ruff check
make typecheck  # mypy --strict
make fresh      # wipe everything and start clean
make shell-db   # open psql in the db container
```

See [docs/PLAN.md](docs/PLAN.md) for the full project plan and task status.
