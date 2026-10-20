#!/usr/bin/env bash
# Polls the API until /readyz is 200 (db + cache ok) or prints diagnostics and fails.
set -u
URL="${1:-http://127.0.0.1:8000/readyz}"; TIMEOUT="${2:-180}"
echo "Waiting for $URL (max ${TIMEOUT}s)..."
for ((i=0; i<TIMEOUT; i+=3)); do
  if curl -fsS "$URL" >/dev/null 2>&1; then echo "READY after ~${i}s"; exit 0; fi
  sleep 3
done
echo "NOT READY after ${TIMEOUT}s. Diagnostics:"
docker compose ps
docker compose logs --tail=40 migrate backend
exit 1
