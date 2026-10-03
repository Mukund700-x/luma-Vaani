# ─────────────────────────────────────────────────────────────────────────────
#  Luma Vaani — Developer Makefile
#  Usage: make <target>
# ─────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help
.PHONY: help up down build dev logs shell migrate rollback seed \
        test lint format typecheck check clean prod

# ── Config ────────────────────────────────────────────────────────────────────
API_SERVICE  = api
DC           = docker compose
DC_PROD      = docker compose -f docker-compose.yml -f docker-compose.prod.yml

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  💙 Luma Vaani — Available commands:"
	@echo ""
	@echo "  Development:"
	@echo "    make up         Start the full dev stack (hot-reload)"
	@echo "    make down       Stop all containers"
	@echo "    make build      Rebuild the API image"
	@echo "    make logs       Tail API logs"
	@echo "    make shell      Open a shell in the API container"
	@echo ""
	@echo "  Database:"
	@echo "    make migrate    Apply all Alembic migrations (head)"
	@echo "    make rollback   Rollback one migration"
	@echo "    make seed       Seed development data"
	@echo ""
	@echo "  Quality:"
	@echo "    make test       Run the full test suite"
	@echo "    make lint       Ruff lint check"
	@echo "    make format     Ruff auto-format"
	@echo "    make typecheck  Mypy strict type check"
	@echo "    make check      lint + typecheck + test"
	@echo ""
	@echo "  Production:"
	@echo "    make prod       Start production stack"
	@echo "    make clean      Remove containers, volumes, and build cache"
	@echo ""

# ── Development ───────────────────────────────────────────────────────────────
up:
	$(DC) up --build --remove-orphans

down:
	$(DC) down

build:
	$(DC) build $(API_SERVICE)

dev:
	$(DC) up $(API_SERVICE) --build

logs:
	$(DC) logs -f $(API_SERVICE)

shell:
	$(DC) exec $(API_SERVICE) /bin/bash

# ── Database ──────────────────────────────────────────────────────────────────
migrate:
	$(DC) run --rm migrate alembic upgrade head

rollback:
	$(DC) run --rm migrate alembic downgrade -1

revision:
	@read -p "Migration message: " msg; \
	$(DC) run --rm migrate alembic revision --autogenerate -m "$$msg"

seed:
	$(DC) run --rm $(API_SERVICE) python database/seed/seed_dev.py

# ── Quality ───────────────────────────────────────────────────────────────────
test:
	$(DC) run --rm $(API_SERVICE) \
		pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=70

lint:
	$(DC) run --rm $(API_SERVICE) ruff check app/

format:
	$(DC) run --rm $(API_SERVICE) ruff format app/

typecheck:
	$(DC) run --rm $(API_SERVICE) mypy app/ --ignore-missing-imports

check: lint typecheck test

# ── Production ────────────────────────────────────────────────────────────────
prod:
	$(DC_PROD) up -d --build

prod-down:
	$(DC_PROD) down

prod-logs:
	$(DC_PROD) logs -f $(API_SERVICE)

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	$(DC) down -v --rmi local --remove-orphans
	@echo "Cleaned up containers, volumes, and images."
