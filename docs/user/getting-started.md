# Getting Started

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — runs the database and application containers
- [uv](https://docs.astral.sh/uv/) — Python package manager (for local development only)

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## First run

```bash
# 1. Clone the repository
git clone https://github.com/your-org/recommendator.git
cd recommendator

# 2. Create your environment file
cp .env.example .env
# Edit .env — set DB_PASSWORD and update DATABASE_URL to match

# 3. Install dependencies (creates .venv/)
uv sync --dev

# 4. Install git hooks (secret scanning + linting on every commit)
uv run pre-commit install

# 5. Start all services
make up

# 6. Apply the database schema
make migrate

# 7. Load the initial asset universe (50 US + 20 Finnish tickers)
make seed
```

## Verify it's running

```bash
curl http://localhost:8000/v1/health/ready
# → {"status": "ok"}   (after first ingest)
# → {"status": "degraded", "reason": "ingest stale or never run"}  (before ingest)
```

## Run the first ingest manually

The scheduler fires automatically at 17:00 UTC (Finnish) and 21:30 UTC (US).
To trigger an ingest immediately from the API container:

```bash
docker compose exec api python -c "
import asyncio, asyncpg
from app.ingestion.us_ingest import run_us_ingest
from app.common.config import settings

async def main():
    pool = await asyncpg.create_pool(settings.database_url)
    await run_us_ingest(pool)
    await pool.close()

asyncio.run(main())
"
```

## Query the API

```bash
# List all active assets
curl http://localhost:8000/v1/assets

# Filter by market
curl "http://localhost:8000/v1/assets?market=FI"

# Price history for Apple (last 90 trading days by default)
curl http://localhost:8000/v1/assets/AAPL/prices

# With date bounds
curl "http://localhost:8000/v1/assets/AAPL/prices?from=2024-01-01&to=2024-03-31"

# Finnish ticker
curl http://localhost:8000/v1/assets/NOKIA.HE/prices
```

## Local development

```bash
uv run pytest tests/unit/         # unit tests (no DB needed)
uv run pytest tests/              # all tests (requires DATABASE_URL pointing to a live DB)
uv run ruff check backend/        # linter
uv run mypy backend/app           # type checker
```

See [Operations](operations.md) for all available `make` targets.
