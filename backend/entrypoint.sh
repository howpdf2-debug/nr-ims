#!/bin/sh
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
