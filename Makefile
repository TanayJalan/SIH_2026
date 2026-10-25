SHELL := /bin/bash
COMPOSE := docker compose
PYTHON ?= python3

.PHONY: help dev seed seed-aph test migrate logs shell down

help:
	@echo "make dev      Build and start postgres, mailpit, backend and frontend"
	@echo "make seed     Generate APH JSON, apply migrations and seed demo data"
	@echo "make seed-aph Regenerate backend/seeds/aph/*.json from docs/reference/APH_SPEC.md"
	@echo "make test     Run backend tests (migrations applied first)"
	@echo "make migrate  Apply pending Alembic migrations to the running backend"
	@echo "make logs     Follow logs from all services"
	@echo "make shell    Open a shell in the backend container"
	@echo "make down     Stop and remove containers (keeps the database volume)"

dev:
	$(COMPOSE) up --build

seed: seed-aph
	$(COMPOSE) run --rm backend sh -c "alembic upgrade head && python -m app.seed"

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
