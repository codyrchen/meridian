SHELL := /bin/bash
UV ?= uv
COMPOSE ?= docker compose

.PHONY: bootstrap db-up db-down migrate seed-event ingest report report-fixture \
        test test-integration lint format-check typecheck gate

bootstrap:            ## Install the workspace and dev tools
	$(UV) sync

db-up:                ## Start PostgreSQL 16 and wait until healthy
	$(COMPOSE) up -d --wait postgres

db-down:              ## Stop PostgreSQL (data volume is preserved)
	$(COMPOSE) down

migrate:              ## Apply Alembic migrations to head
	$(UV) run alembic upgrade head

seed-event:           ## Load the curated ARB unlock event and its source artifact
	$(UV) run python -m meridian_pipelines.cli seed-event --config config/slice.yaml

ingest:               ## Ingest daily ARB and BTC bars from CoinGecko (idempotent)
	$(UV) run python -m meridian_pipelines.cli ingest --config config/slice.yaml

report:               ## Run the [-30,+30] event study and write CSV/chart/manifest
	$(UV) run python -m meridian_pipelines.cli report --config config/slice.yaml

report-fixture:       ## Deterministic offline report from committed synthetic fixtures
	$(UV) run python -m meridian_pipelines.cli report-fixture

test:                 ## Unit tests only (no network, no database)
	$(UV) run pytest -q -m "not integration"

test-integration:     ## Integration tests (requires make db-up)
	$(UV) run pytest -q -m integration

lint:
	$(UV) run ruff check .

format-check:
	$(UV) run ruff format --check .

typecheck:
	$(UV) run mypy packages

gate: lint format-check typecheck  ## Full quality gate
	$(UV) run pytest -q
	@if [ -d apps/web ]; then \
		npm --prefix apps/web run lint && \
		npm --prefix apps/web run typecheck && \
		npm --prefix apps/web run test; \
	else \
		echo "apps/web not present; frontend gates skipped (per decision log)"; \
	fi
