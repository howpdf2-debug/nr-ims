#!/usr/bin/env bash
# Migration gate: (1) upgrade an EMPTY database to head, (2) fail if models drifted from migrations.
# Usage: NRIMS_DATABASE_URL=postgresql+asyncpg://... bash scripts/check_migrations.sh
# Policy: migrations are forward-only (see docs/PHASE_PROGRESS.md G-13); downgrade is not tested.
set -euo pipefail
: "${NRIMS_DATABASE_URL:?set NRIMS_DATABASE_URL to an EMPTY throwaway database}"
cd "$(dirname "$0")/../backend"
ALEMBIC="${ALEMBIC:-alembic}"

heads="$($ALEMBIC heads 2>/dev/null | grep -c '(head)' || true)"
if [ "$heads" != "1" ]; then
  echo "FAIL: expected exactly 1 alembic head, found $heads (merge branches)"; exit 1
fi
echo "== upgrade head"
$ALEMBIC upgrade head
echo "== drift check (models vs migrations)"
if ! $ALEMBIC check; then
  echo "FAIL: models differ from migrations. Generate a NEW revision; never edit an applied one."; exit 1
fi
echo "OK: single head, upgrade clean, no drift"
