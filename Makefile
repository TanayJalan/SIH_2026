SHELL := /bin/bash
COMPOSE := docker compose
PYTHON ?= python3

.PHONY: help dev seed seed-aph test migrate logs shell down reset-demo

help:
	@echo "make dev      Build and start postgres, mailpit, backend and frontend"
	@echo "make seed     Apply migrations and seed the full demo dataset"
	@echo "make seed-aph Regenerate backend/seeds/aph/*.json from the APH reference PDF/spec"
	@echo "make test     Run backend tests (migrations applied first)"
	@echo "make migrate  Apply pending Alembic migrations to the running backend"
	@echo "make logs     Follow logs from all services"
	@echo "make shell    Open a shell in the backend container"
	@echo "make down     Stop and remove containers (keeps the database volume)"
	@echo "make reset-demo   Wipe seeded rows and rebuild the demo dataset"

dev:
	$(COMPOSE) up --build

seed:
	$(COMPOSE) run --rm backend python -m app.seed

seed-aph:
	$(PYTHON) scripts/seed_aph.py

test:
	$(COMPOSE) run --rm backend sh -c "alembic upgrade head && pytest -q"

migrate:
	$(COMPOSE) exec backend alembic upgrade head

logs:
	$(COMPOSE) logs -f

shell:
	$(COMPOSE) exec backend bash

down:
	$(COMPOSE) down

# Rebuilds the exact state of `make seed`: truncates every seeded table (the
# Alembic version table is kept) and runs the seeder again. Simulated time is
# process-local, so restart the backend container to clear it.
reset-demo:
	$(COMPOSE) run --rm backend python -m app.reset_demo
