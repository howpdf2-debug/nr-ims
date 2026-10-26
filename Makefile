SHELL := /bin/bash
BACKEND := backend
FRONTEND := frontend
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
# The project is pinned/tested on Python 3.12 (backend/constraints.txt). Prefer it when present.
PYTHON ?= $(shell command -v python3.12 2>/dev/null || command -v python3)
# "Installed" is tracked by OUR OWN stamp. (It used to be .venv/bin/activate, which `python3 -m venv`
# itself creates - so a hand-made venv made `make install` silently do nothing and ruff/pytest were missing.)
STAMP := $(VENV)/.nrims-installed


.PHONY: diag init creds reset test-integration test-all smoke-phase2 check-edge unlock-login lock migrate migrations-check seed db-doctor help install lint type test guards ci audit sbom \
        up down logs ps clean \
        frontend-install frontend-ci frontend-dev dev-backend

help:
	@echo "Backend : install lint type test guards ci audit sbom dev-backend"
	@echo "Stack   : up down logs ps clean"
	@echo "Frontend: frontend-install frontend-ci frontend-dev"

# ---------- Backend ----------
$(STAMP): $(BACKEND)/pyproject.toml $(BACKEND)/constraints.txt
	@# A venv is usable only if pip exists. A failed `python -m venv` (missing python3.X-venv package) leaves a
	@# half-made .venv (python symlink, no pip): discard it and recreate, with a clear hint if that fails again.
	@if [ ! -x $(PIP) ]; then \
	  rm -rf $(VENV); \
	  $(PYTHON) -m venv $(VENV) || { rm -rf $(VENV); \
	    echo; echo "ERROR: could not create a virtualenv with '$(PYTHON)'."; \
	    echo "  Debian/Ubuntu/Codespaces:  sudo apt-get install -y python3.12-venv   (then run make again)"; \
	    echo "  Or use another interpreter: make install PYTHON=python3"; exit 1; }; \
	fi
	$(PIP) install --upgrade pip
	@if $(PY) -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'; then \
	  $(PIP) install -c $(BACKEND)/constraints.txt -e "$(BACKEND)[dev]"; \
	else \
	  echo "WARNING: $$($(PY) -V) is not Python 3.12 (pinned/tested version): installing UNPINNED dependencies"; \
	  $(PIP) install -e "$(BACKEND)[dev]"; \
	fi
	@touch $(STAMP)

install: $(STAMP)

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
	@# Codespaces/Docker-in-Docker: stale iptables-legacy FORWARD DROP silently drops container-to-container
	@# traffic ("[db-wait] TCP TIMEOUT ... packets dropped"). The script is idempotent and a no-op elsewhere.
	@if [ "$$CODESPACES" = "true" ]; then bash scripts/fix_legacy_forward.sh || true; fi
	@docker compose up -d --build || { echo; echo '=== START FAILED. migrate/db logs: ==='; docker compose ps -a; docker compose logs migrate db --tail=60; \
	  echo; echo "HINT: on 'TCP TIMEOUT ... packets dropped' (Codespaces): make fix-network && make down && make up"; exit 1; }
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

# Needs an EMPTY throwaway DB: NRIMS_DATABASE_URL=postgresql+asyncpg://u:p@127.0.0.1:5432/scratch make migrations-check
migrations-check: install
	ALEMBIC=$(CURDIR)/$(VENV)/bin/alembic bash scripts/check_migrations.sh

seed: .env
	docker compose exec backend python seed_master.py && docker compose exec backend python seed_links.py && docker compose exec backend python seed_inventory.py && docker compose exec backend python seed_admin.py

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

test-all: ci test-integration frontend-ci  ## everything: guards+ruff+mypy+unit, integration (+migration round-trip), frontend

smoke-phase2:  ## live API smoke test of Phase 2 against the running stack (needs make up && make seed)
	bash scripts/smoke_phase2.sh

check-edge:  ## what the BROWSER sees through nginx: cache headers, CSP, /nrims-api path, X-NRIMS-Auth (needs make up && make seed)
	bash scripts/check_edge.sh

unlock-login:  ## dev only: clear login lockouts (5 wrong passwords lock a user for 15 min, even for the right password)
	@set -a; . ./.env; set +a; \
	[ "$$NRIMS_ENV" != production ] || { echo "refusing: NRIMS_ENV=production"; exit 1; }; \
	docker compose exec -T cache valkey-cli -a "$$VALKEY_PASSWORD" --no-auth-warning \
	  EVAL "for _,k in ipairs(redis.call('keys','login_fail:*')) do redis.call('del',k) end return 1" 0 >/dev/null \
	&& echo "login lockouts cleared"

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
