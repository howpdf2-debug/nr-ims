#!/usr/bin/env bash
# NR-IMS v3.1 patch: run from repo root. Idempotent. Does NOT touch Dockerfile (keeps the 9-minute pip layers cached).
set -euo pipefail
test -f docker-compose.yml && test -f FIX_VERSION || { echo "run from repo root (v3 applied)"; exit 1; }

python3 - <<'EOF'
import re
p="docker-compose.yml"; s=open(p).read()
# 1) healthcheck over TCP: the postgres image runs a temporary socket-only server during first init;
#    a socket pg_isready reports "healthy" too early and `migrate` then fails to connect.
s=s.replace('test: ["CMD-SHELL", "pg_isready -U nrims -d nrims"]','test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -U nrims -d nrims"]')
# 2) backend shares the image built by `migrate`; never try to pull it from Docker Hub
if "pull_policy: never" not in s:
    s=s.replace("  backend:\n    image: nr-ims-backend:local\n","  backend:\n    image: nr-ims-backend:local\n    pull_policy: never\n")
open(p,"w").write(s)

p="backend/entrypoint.sh"
open(p,"w",newline="\n").write('''#!/bin/sh
# Waits for Postgres (printing a precise diagnosis if it cannot connect), then runs the command.
# Migrations normally run in the dedicated `migrate` compose service.
set -eu
echo "[entrypoint] command: $*"
python -m app.db.wait
if [ "${NRIMS_RUN_MIGRATIONS:-false}" = "true" ]; then
  alembic upgrade head
fi
if [ "${1:-}" = "alembic" ]; then
  # no exec: lets us print a clear marker when a migration fails
  if "$@"; then echo "[entrypoint] alembic OK"; exit 0; fi
  echo "[entrypoint] ALEMBIC FAILED - read the traceback above this line"; exit 1
fi
exec "$@"
''')

p="Makefile"; s=open(p).read()
s=s.replace("up: .env\n\tdocker compose up -d --build\n\tbash scripts/wait_ready.sh",
"up: .env\n\t@docker compose up -d --build || { echo; echo '=== START FAILED. migrate/db logs: ==='; docker compose ps -a; docker compose logs migrate db --tail=60; exit 1; }\n\tbash scripts/wait_ready.sh")
if "\ndiag:" not in s:
    s+="""
diag:  ## collect everything needed to debug a failed start into diag.txt
\t@{ echo "## docker"; docker version --format '{{.Server.Version}}'; docker compose version; \\
\t   echo "## ps"; docker compose ps -a; \\
\t   echo "## env keys (values hidden)"; sed 's/=.*/=***/' .env; \\
\t   echo "## logs"; docker compose logs --tail=80 db cache migrate backend frontend 2>&1; \\
\t } > diag.txt 2>&1; echo "wrote diag.txt ($$(wc -l < diag.txt) lines) - paste it"
"""
    s=s.replace(".PHONY: init","\n.PHONY: diag init",1) if ".PHONY: diag" not in s else s
open(p,"w").write(s)
print("patched: docker-compose.yml backend/entrypoint.sh Makefile")
EOF
chmod +x backend/entrypoint.sh
echo "v3.1" > FIX_VERSION
grep -q '^diag.txt' .gitignore || echo "diag.txt" >> .gitignore
