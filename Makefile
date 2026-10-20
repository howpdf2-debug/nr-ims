SHELL := /bin/bash
BACKEND := backend
FRONTEND := frontend
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip


.PHONY: diag init creds reset test-integration lock migrate seed db-doctor help install lint type test guards ci audit sbom \
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
up: .env
	@docker compose up -d --build || { echo; echo '=== START FAILED. migrate/db logs: ==='; docker compose ps -a; docker compose logs migrate db --tail=60; exit 1; }
	bash scripts/wait_ready.sh

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

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
	docker compose run --rm migrate

seed: .env
	docker compose exec backend python seed_master.py && docker compose exec backend python seed_links.py && docker compose exec backend python seed_admin.py

db-doctor:
	docker compose run --rm --no-deps migrate python -m app.db.wait --diagnose

.env:
	@$(MAKE) --no-print-directory init

init:  ## create .env with strong random secrets (never overwrites)
	@if [ -f .env ]; then echo ".env already exists - not touched"; else \
	  printf 'POSTGRES_PASSWORD=%s\nVALKEY_PASSWORD=%s\nNRIMS_SECRET_KEY=%s\nNRIMS_SEED_ADMIN_PASSWORD=%s\nNRIMS_ENV=development\nNRIMS_DATA_PROVIDER=simulator\nNRIMS_DOCS_ENABLED=true\nHTTP_PORT=80\nPOSTGRES_HOST_PORT=5432\nVALKEY_HOST_PORT=6379\n' \
	    "$$(openssl rand -hex 24)" "$$(openssl rand -hex 24)" "$$(openssl rand -hex 32)" "$$(openssl rand -base64 18 | tr -d '/+=')" > .env; \
	  echo ".env created"; fi

creds:  ## show dev login (all seed users share this password)
	@echo "email   : irca@nr-ims.local (admin), dual@, dli@, bsb@nr-ims.local"
	@echo "password: $$(grep ^NRIMS_SEED_ADMIN_PASSWORD .env | cut -d= -f2)"

reset:  ## DEV ONLY: wipe DB volume, rebuild, migrate, seed
	docker compose down -v
	$(MAKE) up
	$(MAKE) seed

test-integration: install  ## needs `make up && make seed` first
	@set -a; . ./.env; set +a; cd $(BACKEND) && \
	 NRIMS_INTEGRATION=1 \
	 NRIMS_DATABASE_URL="postgresql+asyncpg://nrims:$$POSTGRES_PASSWORD@127.0.0.1:$${POSTGRES_HOST_PORT:-5432}/nrims" \
	 NRIMS_VALKEY_URL="redis://:$$VALKEY_PASSWORD@127.0.0.1:$${VALKEY_HOST_PORT:-6379}/0" \
	 NRIMS_SEED_ADMIN_PASSWORD="$$NRIMS_SEED_ADMIN_PASSWORD" ../$(VENV)/bin/pytest -q

lock:  ## regenerate backend/constraints.txt (pinned, reproducible Docker builds)
	python3.12 -m venv /tmp/nrims-lock && /tmp/nrims-lock/bin/pip install -q --upgrade pip && \
	 /tmp/nrims-lock/bin/pip install -q $(BACKEND) && /tmp/nrims-lock/bin/pip freeze --exclude-editable | grep -vi '^nr-ims' > $(BACKEND)/constraints.txt

diag:  ## collect everything needed to debug a failed start into diag.txt
	@{ echo "## docker"; docker version --format '{{.Server.Version}}'; docker compose version; \
	   echo "## ps"; docker compose ps -a; \
	   echo "## env keys (values hidden)"; sed 's/=.*/=***/' .env; \
	   echo "## logs"; docker compose logs --tail=80 db cache migrate backend frontend 2>&1; \
	 } > diag.txt 2>&1; echo "wrote diag.txt ($$(wc -l < diag.txt) lines) - paste it"

fix-network:  ## DinD/Codespaces: ensure legacy iptables FORWARD policy is ACCEPT
	@bash scripts/fix_legacy_forward.sh
