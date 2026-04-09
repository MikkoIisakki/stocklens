# Operations

## Make targets

| Target | Command | Description |
|---|---|---|
| `up` | `make up` | Build images and start all services in the background |
| `down` | `make down` | Stop and remove containers (data volume preserved) |
| `logs` | `make logs` | Follow logs from all containers |
| `migrate` | `make migrate` | Apply all SQL migrations in `db/migrations/` in order |
| `seed` | `make seed` | Load initial asset universe from `db/seeds/` |
| `test` | `make test` | Run pytest with coverage inside the api container |
| `lint` | `make lint` | Run ruff linter inside the api container |
| `typecheck` | `make typecheck` | Run mypy inside the api container |
| `shell-db` | `make shell-db` | Open a psql shell in the db container |
| `fresh` | `make fresh` | Nuclear reset — wipe volumes, restart, migrate, seed |

## Health check

```bash
curl http://localhost:8000/v1/health/ready
```

| Response | Meaning | Action |
|---|---|---|
| `{"status": "ok"}` | All good | — |
| `{"status": "degraded"}` | Ingest hasn't run in >25h | Check scheduler logs |
| HTTP 503 | Database unreachable | Check db container: `make logs` |

## Scheduler

The scheduler container runs APScheduler with two cron jobs:

| Market | Time | Local time |
|---|---|---|
| Finnish (FI) | 17:00 UTC | 19:00 EET / 20:00 EEST |
| US | 21:30 UTC | 23:30 EET / 00:30 EEST |

`misfire_grace_time = 3600` — if the container was down when the job was due,
it will fire up to 1 hour late rather than being skipped.

Check scheduler logs:

```bash
docker compose logs scheduler -f
```

## Database migrations

Migrations are plain SQL files in `db/migrations/`, applied in lexical order.

```bash
make migrate     # apply all pending migrations
make shell-db    # open psql to inspect schema manually
```

### Current schema

| Table | Purpose |
|---|---|
| `asset` | Securities master — one row per ticker |
| `ingest_run` | Audit log for each ingest job execution |
| `daily_price` | EOD OHLCV per asset per trading day |
| `raw_source_snapshot` | Immutable raw API responses (JSONB) |

## Logs

```bash
make logs                              # all containers
docker compose logs api -f             # API only
docker compose logs scheduler -f       # scheduler only
docker compose logs db -f              # postgres only
```

Log level is controlled by `LOG_LEVEL` in `.env` (default: `INFO`).

## Resetting everything

```bash
make fresh    # stops, wipes data volume, restarts, migrates, seeds
```

!!! danger
    `make fresh` **deletes all price data**. Only use it on a local dev
    environment, never in production.
