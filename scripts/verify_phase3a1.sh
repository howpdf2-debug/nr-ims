#!/usr/bin/env bash
# Phase 3a-1 verification - ONE command, run from the repository root:
#
#     bash scripts/verify_phase3a1.sh
#
# Prerequisite: the stack is up (`make up`), so Postgres and Valkey answer on the ports in .env.
# What it does (about 2-3 minutes the first time, because it installs the SNMP simulator once):
#   1 register the new models   2 lint + types + forbidden-pattern guards   3 unit tests (no DB, no network)
#   4 migrate + drift check     5 start a REAL SNMPv3 simulator and run the integration tests
#   6 full regression: `make test-integration` (every earlier phase's tests + this phase's)
# On failure it prints the last lines and stops. Send me those lines, plus the file named at the end.
set -uo pipefail
cd "$(dirname "$0")/.."

LOG=/tmp/nrims-verify-phase3a1.log
SIM_VENV="${NRIMS_SIM_VENV:-$HOME/.cache/nrims-sim-venv}"
: > "$LOG"

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
bold()  { printf '\n\033[1m%s\033[0m\n' "$*"; }

fail() {
  red "✘ $1"
  echo "---- last 25 lines of $LOG ----"; tail -n 25 "$LOG"
  red "Not green. Reply:  fix: <paste the lines above>"
  exit 1
}

# run "label" command...   (output goes to the log; only the verdict is shown)
run() {
  local label="$1"; shift
  echo "### $label" >> "$LOG"
  if "$@" >> "$LOG" 2>&1; then green "✔ $label"; else fail "$label"; fi
}

bold "0/6 prerequisites"
[ -f .env ] || fail ".env not found. Run 'make up' once first (it creates .env)."
set -a; . ./.env; set +a
PGPORT="${POSTGRES_HOST_PORT:-5432}"; VKPORT="${VALKEY_HOST_PORT:-6379}"
for port in "$PGPORT" "$VKPORT"; do
  python3 - "$port" >/dev/null 2>&1 <<'PY' || fail "nothing listens on 127.0.0.1:$port. Start the stack with 'make up'."
import socket, sys
socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=3).close()
PY
done
run "install / refresh the backend virtualenv" make install
PY=.venv/bin/python

bold "1/6 register the Phase 3a-1 models"
run "models registered in app/models/__init__.py" "$PY" scripts/phase3a1_register_models.py

bold "2/6 static checks"
run "ruff (lint)" make lint
run "mypy (types)" make type
run "forbidden-pattern guards" make guards

bold "3/6 unit tests (no DB, no network)"
run "unit tests: Phase 3a-1" bash -c "cd backend && ../.venv/bin/pytest -q -o addopts='' tests/unit/test_phase3a1_unit.py"

bold "4/6 database migration"
export NRIMS_DATABASE_URL="postgresql+asyncpg://nrims:${POSTGRES_PASSWORD}@127.0.0.1:${PGPORT}/nrims"
export NRIMS_VALKEY_URL="redis://:${VALKEY_PASSWORD}@127.0.0.1:${VKPORT}/0"
run "alembic upgrade head" bash -c "cd backend && ../.venv/bin/alembic upgrade head"
run "alembic check (models and migrations agree)" bash -c "cd backend && ../.venv/bin/alembic check"

bold "5/6 real SNMPv3 simulator + integration tests"
if [ ! -x "$SIM_VENV/bin/snmpsim-command-responder" ]; then
  echo "installing the SNMP simulator once into $SIM_VENV (separate from the project venv on purpose)"
  run "create simulator virtualenv" python3 -m venv "$SIM_VENV"
  run "install snmpsim-lextudio" "$SIM_VENV/bin/pip" install -q snmpsim-lextudio
fi
export NRIMS_SNMPSIM_BIN="$SIM_VENV/bin/snmpsim-command-responder"
run "integration tests: Phase 3a-1 (SNMPv3, failure modes, DB constraints, migration roundtrip)" \
  bash -c "cd backend && NRIMS_INTEGRATION=1 ../.venv/bin/pytest -q -o addopts='' tests/integration/test_phase3a1_integration.py"

bold "6/6 full regression (all earlier phases + this one)"
run "make test-integration" make test-integration

bold "RESULT"
green "ALL GREEN. Phase 3a-1 verified in your environment."
echo "Reply:  next"
echo "(full log: $LOG)"
