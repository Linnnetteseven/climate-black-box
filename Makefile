# Climate Black Box -- developer entry points.
# Everything the plan's "fresh clone to running stack in two commands" promise
# depends on lives here.

SHELL := /bin/bash
PY    := .venv/bin/python
PIP   := .venv/bin/pip
PYTEST:= .venv/bin/pytest
-include .env
export

.PHONY: help setup up down db-wait db-reset db-migrate db-seed test test-unit api web ingest anchor verify fmt clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "};{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## create venv and install python deps
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@test -f .env || cp .env.example .env
	@echo "Now edit .env, then: make up && make db-reset"

up: ## start oracle (local dev database)
	docker compose up -d oracle
	@$(MAKE) db-wait

down: ## stop oracle
	docker compose down

db-wait: ## block until the database answers
	@echo -n "waiting for oracle"
	@for i in $$(seq 1 90); do \
	  if [ "$$(docker inspect --format='{{.State.Health.Status}}' cbb-oracle 2>/dev/null)" = "healthy" ]; then \
	    echo " ready"; exit 0; fi; \
	  echo -n "."; sleep 5; done; \
	echo " TIMED OUT"; docker logs --tail 40 cbb-oracle; exit 1

db-reset: db-migrate db-seed ## drop, migrate and seed from zero

db-migrate: ## apply migrations (drop first; errors on a clean db are expected)
	@$(PY) scripts/run_sql.py database/migrations/000_drop.sql --tolerant
	@$(PY) scripts/run_sql.py database/migrations/001_core.sql
	@$(PY) scripts/run_sql.py database/migrations/002_spatial.sql --tolerant
	@$(PY) scripts/run_sql.py database/views/010_views.sql

db-seed: ## load the demo projects and derive spatial geometry
	@$(PY) scripts/run_sql.py database/seed/010_project.sql
	@$(PY) scripts/run_sql.py database/seed/020_mau_project.sql
	@$(PY) scripts/run_sql.py database/seed/040_mikoko_project.sql
	@$(PY) scripts/run_sql.py database/seed/030_spatial_backfill.sql --tolerant

genai-check: ## report which OCI Generative AI models this tenancy can use
	$(PY) scripts/check_genai.py

test: ## run every test
	$(PYTEST)

test-unit: ## pure-function tests only; no database, no network
	$(PYTEST) services -q

api: ## run the API
	.venv/bin/uvicorn services.api.main:app --reload --host $${API_HOST:-0.0.0.0} --port $${API_PORT:-8000}

web: ## run the frontend
	cd apps/web && pnpm dev

ingest: ## re-run the Landsat + rainfall pipeline and diff against the fixture
	$(PY) -m services.analytics.ingest --check

ingest-write: ## re-run the pipeline and overwrite the fixture
	$(PY) -m services.analytics.ingest

load: ## load the observation fixture into Oracle (idempotent)
	$(PY) scripts/load_observations.py

anchor: ## anchor any unanchored evidence to CKB testnet
	$(PY) scripts/anchor_pending.py --project $${PROJECT:-mau-transmara-demo}

verify: ## verify every anchored evidence record against the chain
	$(PY) scripts/verify_chain.py --project $${PROJECT:-mau-transmara-demo}

tamper: ## demonstrate that verification fails on an altered manifest
	$(PY) scripts/verify_chain.py --project $${PROJECT:-mau-transmara-demo} --tamper observed_value

clean:
	rm -rf .venv apps/web/node_modules apps/web/.next .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

build-web: ## production build of the frontend, into .next-build so `make web` keeps serving
	cd apps/web && NEXT_DIST_DIR=.next-build pnpm build
