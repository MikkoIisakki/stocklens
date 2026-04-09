---
name: docker-compose-patterns
description: Docker Compose conventions, healthcheck patterns, network setup, and single-image multi-role backend pattern for the pulse project.
---

# Docker Compose Patterns

## Core Pattern: One Image, Multiple Roles

The backend is built once and run with different `command:` overrides:

```yaml
services:
  api:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"

  worker:
    build: ./backend
    command: python -m app.jobs.worker

  scheduler:
    build: ./backend
    command: python -m app.jobs.scheduler
```

All three share the same image — build once, tag once, promote once.

## Full Compose Structure

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: stocks
      POSTGRES_USER: stocks
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U stocks -d stocks"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - back-tier

  api:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    networks:
      - front-tier
      - back-tier

  worker:
    build: ./backend
    command: python -m app.jobs.worker
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    networks:
      - back-tier

  scheduler:
    build: ./backend
    command: python -m app.jobs.scheduler
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    networks:
      - back-tier

  grafana:
    image: grafana/grafana-oss:10.4.0
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
      GF_AUTH_ANONYMOUS_ENABLED: "false"
    volumes:
      - ./services/grafana/provisioning:/etc/grafana/provisioning:ro
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    depends_on:
      - db
    networks:
      - front-tier
      - back-tier

  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - api
      - grafana
    networks:
      - front-tier

volumes:
  postgres_data:
  grafana_data:
  caddy_data:
  caddy_config:

networks:
  front-tier:
  back-tier:
```

## Caddyfile (local dev)

```caddyfile
# Local dev — no TLS
:80 {
    handle /api/* {
        reverse_proxy api:8000
    }
    handle /grafana/* {
        reverse_proxy grafana:3000
    }
}
```

## Backend Dockerfile

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS dev
# Dev: source mounted as volume, hot-reload enabled
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS prod
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

## Rules

- **Never** use anonymous volumes for persistent data
- All services that depend on the DB must use `condition: service_healthy`
- Secrets only via `.env` — never in `docker-compose.yml` directly
- Use `back-tier` for all service-to-service communication; `front-tier` only for Caddy-facing services
- Grafana provisioning directory mounted as `:ro` (read-only)
