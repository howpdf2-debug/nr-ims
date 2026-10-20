# NR-IMS Audit & Fix Report

## 1. Root cause of the asyncpg `TimeoutError`
Verified on a real Postgres 16 with the original code: with a correct URL, `alembic upgrade head` and all seeds run fine, so the code was never the problem; the URL was resolving to the wrong place.

| Symptom | Meaning |
|---|---|
| `gaierror` | hostname wrong (e.g. `@db` while the service is called `postgres`) |
| `ConnectionRefusedError` | right host, nothing listening |
| **`TimeoutError`** | **packets silently dropped: wrong network / IP / firewall** |
| auth error | volume initialised with a different password |

Findings:
1. `config.py` uses `env_prefix="NRIMS_"`. `DATABASE_URL` (no prefix) in compose is **ignored**; Settings falls back to the default `localhost:5432` (proved by test). Pydantic's `.env` does NOT override real env vars; the real bug is the missing prefix.
2. The `docker-compose.yml` in the zip has no `backend`/`frontend` service, and the DB service is `postgres`, not `db`. The Dockerfile copied only `app/`, so `alembic.ini`, `migrations/` and `seed_*.py` were not in the image.
3. `ssl=False` was a red herring: SSL negotiation against a plain Postgres answers instantly.
4. Passwords containing `@ : / # %` break the URL, and `%` also crashed alembic's configparser.

Fix: single prefixed variable, fail-fast validation (`NRIMS_IN_CONTAINER` rejects localhost), `python -m app.db.wait --diagnose` prints which of the four failures it is, 10s connect timeout.

## 2. Fixed (all verified: 18 tests, real Postgres + Redis, alembic check = no drift, frontend build OK)
**Infra**: full compose (db, valkey+auth, one-shot `migrate`, backend, nginx frontend), healthchecks, no DB port exposed beyond 127.0.0.1, non-root image with tini, complete Dockerfiles, nginx with CSP/headers, `.env.example`s, Makefile targets.
**Security**: scoping was broken and leaky. Tier-1 `BSB` matched `Station.division` so saw nothing; device detail, actions, maintenance, discovery, links, topology edges, reports, CSV and audit had no scope check (IDOR). Now one `security/scope.py` is used everywhere (404 for foreign objects). Added login lockout (Valkey), timing-safe login, JWT `iat/jti/required exp`, role/scope/password validation, last-admin protection, CSV formula-injection guard, audit trail actually written (`AuditEvent` was never used), discovery limited to IRCA, station delete requires `?force=true`, station management permission, docs disabled in production.
**Correctness**: `/readyz` crashed (`app.state.settings` never set); two engines per process; tests could not run (`create_app(settings)`); RCA never fired because seeds had no `parent_station_code` and parents were hardcoded; alarm ack never set `acked_at`; dashboard N+1 queries; `seed_admin` deleted every user on each run and used hard-coded passwords; `seed_links` crashed (removed column, missing stations); `seed_master` failed (`is_maintenance` NOT NULL without default).
**DB**: migration `e5a1c0de0011` adds missing server defaults and hot-path indexes; advisory lock makes concurrent migrations safe; stale `requirements.txt` (python-jose/passlib vs pyjwt/argon2) removed.
**Frontend**: `npm run build` was failing (13 unused-symbol TS errors + Vite 8 `manualChunks` object form), so the Docker image could not build. Fixed; added `typecheck` script.

## 3. Remaining gaps (not changed, need your decision)
- JWT is in `localStorage` (XSS-exposed). Move to httpOnly cookie + CSRF, or at least short-lived token + refresh/revocation.
- Discovery scan and remote actions are **simulated**; live mode now returns 501 instead of pretending. A real executor (SNMP/SSH/nmap worker, ideally via a queue such as arq/Celery) is the largest missing feature.
- No real monitoring poller / event ingestion; alarms come from seeds. NOC wallboard polls; consider SSE/WebSocket.
- No metrics (Prometheus), tracing, or backup/restore plan for Postgres; add `pg_dump` cron and a restore drill.
- No TLS termination in the stack; put a reverse proxy (Caddy/Traefik) with HTTPS in front for production.
- Historical SLA data: reports use current state only; add a time-series/status-history table for true uptime %.
- Existing legacy lint debt (~270 ruff style findings, mostly line length in seeds).
- Pin image digests and add `pip-audit`/`npm audit` plus Dependabot in CI.

## 4. Migrations in production
Run migrations as a separate one-shot job (`migrate` service / CI deploy step), never inside every app replica. Backend starts only after `service_completed_successfully`. Keep migrations additive (expand/contract), and take a backup first.

## 5. Commands
```
cd deploy && cp .env.example .env     # fill with: openssl rand -hex 24
docker compose up -d --build           # db -> migrate -> backend -> frontend
docker compose exec backend python seed_master.py
docker compose exec backend python seed_links.py
docker compose exec backend python seed_admin.py   # prints generated password once
make db-doctor                          # explains connectivity failures
```
If your Postgres volume was created with a different password: `docker compose down -v` (dev only).
