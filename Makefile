SHELL := /bin/bash
BACKEND := backend
FRONTEND := frontend
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: migrate seed db-doctor help install lint type test guards ci audit sbom \
        up down logs ps clean \
        frontend-install frontend-ci frontend-dev dev-backend

help:
	@echo "Backend : install lint type test guards ci audit sbom dev-backend"
	@echo "Stack   : up down logs ps clean"
	@echo "Frontend: frontend-install frontend-ci frontend-dev"

# ---------- Backend ----------
$(VENV)/bin/activate: $(BACKEND)/pyproject.toml
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e "$(BACKEND)[dev]"
	@touch $(VENV)/bin/activate

install: $(VENV)/bin/activate

lint: install
	$(VENV)/bin/ruff check $(BACKEND)

type: install
	cd $(BACKEND) && ../$(VENV)/bin/mypy app

test: install
	cd $(BACKEND) && ../$(VENV)/bin/pytest -q

guards:
	python3 scripts/check_forbidden.py
	python3 scripts/check_secrets_placeholders.py

ci: guards lint type test

audit: install
	$(VENV)/bin/pip-audit --strict || true

sbom: install
	mkdir -p SBOM
	$(VENV)/bin/pip-audit --format=cyclonedx-json --output=SBOM/backend.cdx.json || true

dev-backend: install
	cd $(BACKEND) && ../$(VENV)/bin/uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000

# ---------- Stack ----------
up:
	cd deploy && docker compose up -d --build

down:
	cd deploy && docker compose down

logs:
	cd deploy && docker compose logs -f --tail=200

ps:
	cd deploy && docker compose ps

clean:
	rm -rf $(VENV) SBOM/*.json
	find $(BACKEND) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ---------- Frontend ----------
frontend-install:
	cd $(FRONTEND) && npm ci

frontend-dev:
	cd $(FRONTEND) && npm run dev

frontend-ci: frontend-install
	cd $(FRONTEND) && npm run lint
	cd $(FRONTEND) && npm run typecheck
	cd $(FRONTEND) && npm run build

# ---------- Ops ----------
migrate:
	cd deploy && docker compose run --rm migrate

seed:
	cd deploy && docker compose exec backend python seed_master.py && docker compose exec backend python seed_admin.py

db-doctor:
	cd deploy && docker compose run --rm --no-deps migrate python -m app.db.wait --diagnose
