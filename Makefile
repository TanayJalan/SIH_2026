SHELL := /bin/bash
COMPOSE := docker compose
PYTHON ?= python3

.PHONY: help dev seed seed-aph test coverage e2e openapi migrate logs shell down reset-demo prod prod-down

help:
	@echo "make dev      Build and start postgres, mailpit, backend and frontend"
	@echo "make seed     Apply migrations and seed the full demo dataset"
	@echo "make seed-aph Regenerate backend/seeds/aph/*.json from the APH reference PDF/spec"
	@echo "make test     Run backend tests (migrations applied first)"
	@echo "make coverage Run the core-module coverage gate (80% minimum)"
	@echo "make e2e      Run the Playwright smoke tests against the running stack"
	@echo "make openapi  Export the OpenAPI schema to docs/openapi.json"
	@echo "make migrate  Apply pending Alembic migrations to the running backend"
	@echo "make logs     Follow logs from all services"
	@echo "make shell    Open a shell in the backend container"
	@echo "make down     Stop and remove containers (keeps the database volume)"
	@echo "make reset-demo   Wipe seeded rows and rebuild the demo dataset"
	@echo "make prod     Start the production Compose profile"
	@echo "make prod-down Stop the production Compose profile"

dev:
	$(COMPOSE) up --build

seed:
	$(COMPOSE) run --rm backend python -m app.seed

seed-aph:
	$(PYTHON) scripts/seed_aph.py

test:
	$(COMPOSE) run --rm backend sh -c "alembic upgrade head && pytest -q"

coverage:
	$(COMPOSE) run --rm backend sh -c "alembic upgrade head && pytest -q \
		--cov=app.services.workflow \
		--cov=app.services.workflow_catalogue \
		--cov=app.services.compliance \
		--cov=app.services.compliance_calculators \
		--cov=app.services.alert_engine \
		--cov=app.services.alert_triggers \
		--cov=app.services.fee_calculator \
		--cov=app.api.routes.auth \
		--cov=app.services.auth \
		--cov-report=term-missing --cov-fail-under=80"

e2e:
	cd frontend && npm run test:e2e

openapi:
	$(COMPOSE) exec -T backend python -m scripts.export_openapi > docs/openapi.json

prod:
	$(COMPOSE) -f docker-compose.prod.yml up -d --build

prod-down:
	$(COMPOSE) -f docker-compose.prod.yml down

migrate:
	$(COMPOSE) exec backend alembic upgrade head

logs:
	$(COMPOSE) logs -f

shell:
	$(COMPOSE) exec backend bash

down:
	$(COMPOSE) down

# Rebuilds the exact state of `make seed`: drops and recreates the public
# schema (data and migration-owned rows), re-runs Alembic, then seeds again.
# The Demo time offset is process-local, so restart the backend to clear it.
reset-demo:
	$(COMPOSE) run --rm backend python -m app.reset_demo
