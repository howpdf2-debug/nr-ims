#!/bin/sh
# Waits for Postgres (printing a precise diagnosis if it cannot connect), then
# optionally migrates, then execs the real command. Migrations normally run in the
# dedicated `migrate` compose service; set NRIMS_RUN_MIGRATIONS=true for single-container setups.
set -eu
python -m app.db.wait
if [ "${NRIMS_RUN_MIGRATIONS:-false}" = "true" ]; then
  alembic upgrade head
fi
exec "$@"
