.PHONY: up down logs migrate seed test lint typecheck fresh shell-db docs docs-serve

## Build and start all services
up:
	docker compose up --build -d

## Stop and remove containers
down:
	docker compose down

## Follow all service logs
logs:
	docker compose logs -f

## Apply all migrations in order
migrate:
	@for f in db/migrations/*.sql; do \
		echo "Applying $$f"; \
		docker compose exec -T db psql -U $${DB_USER:-stocks} -d $${DB_NAME:-stocks} -f "/dev/stdin" < "$$f"; \
	done

## Apply all seed files in order
seed:
	@for f in db/seeds/*.sql; do \
		echo "Seeding $$f"; \
		docker compose exec -T db psql -U $${DB_USER:-stocks} -d $${DB_NAME:-stocks} -f "/dev/stdin" < "$$f"; \
	done

## Run tests with coverage (requires: make up && make migrate && make seed)
test:
	DATABASE_URL=postgresql://$${DB_USER:-stocks}:$${DB_PASSWORD:-changeme}@localhost:5433/$${DB_NAME:-stocks} \
		uv run python -m pytest tests/ -q

## Run linter
lint:
	docker compose run --rm api ruff check backend/app/

## Run type checker
typecheck:
	docker compose run --rm api mypy backend/app/

## Open a psql shell in the db container
shell-db:
	docker compose exec db psql -U $${DB_USER:-stocks} -d $${DB_NAME:-stocks}

## Build documentation site to site/
docs:
	uv run mkdocs build --strict

## Serve documentation locally with live reload (http://localhost:8001)
docs-serve:
	uv run mkdocs serve --dev-addr 0.0.0.0:8001

## Nuclear reset: wipe everything and start fresh
fresh: down
	docker compose down -v
	$(MAKE) up
	@echo "Waiting for db to be healthy..."
	@sleep 5
	$(MAKE) migrate
	$(MAKE) seed
