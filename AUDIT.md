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

## 4b. Aapke `docker-compose.yml` (root) ka analysis
| # | Problem in your compose | Effect | Fix |
|---|---|---|---|
| 1 | No migration step | DB empty -> every API call 500, login fails | `migrate` one-shot service; backend waits for it |
| 2 | Frontend `80:80`, but nginx must proxy `/api/` (frontend uses relative `/api/v1`) | Login/API return 404 from static nginx | `frontend/deploy/nginx.conf` proxies `/api/` to `backend:8000`; container listens on 8080 (`${HTTP_PORT:-80}:8080`) |
| 3 | `5432` and `6379` published on 0.0.0.0, Valkey without password | Anyone on the LAN can read/write DB and cache | DB bound to 127.0.0.1, Valkey internal-only + `requirepass` |
| 4 | Hard-coded `nrims_secure_password`; no `NRIMS_SECRET_KEY` | JWTs signed with the public default key (anyone can forge admin tokens) | `.env` via `make init`; compose refuses to start if unset |
| 5 | `NRIMS_CORS_ORIGINS=["*"]` with credentials | Unsafe, and rejected in production | Same-origin through nginx -> `[]` |
| 6 | Valkey `service_started`, no backend healthcheck, frontend waits only for "started" | Race at boot, nginx can crash on unresolved `backend` | healthchecks + `condition: service_healthy` |
| 7 | `container_name` everywhere | Blocks scaling/parallel stacks | removed |
| 8 | Old volume + new password | `password authentication failed` | `make reset` (dev) or keep old password in `.env` |
| 9 | Windows CRLF in `entrypoint.sh` | `exec ... no such file` | Dockerfile strips CR, `.gitattributes` forces LF |
| 10 | Google Fonts `@import` | Blocked by CSP and fails on air-gapped railway networks | removed, system font stack |
| 11 | nginx `add_header` in a `location` silently drops security headers | CSP/X-Frame missing | shared include in every location |
Postgres 15 and Valkey 7.2 are kept so your existing volume stays readable.

## 5. Commands
```
make init                              # creates .env with random secrets
make up                                # db -> migrate -> backend -> frontend
make seed                              # master data, links, users (prints password once)
make db-doctor                          # explains connectivity failures
```
If your Postgres volume was created with a different password: `docker compose down -v` (dev only).


## 6. v3 additions (found while testing in GitHub Codespaces)
| Finding | Fix |
|---|---|
| Codespace had the **old v1 zip** (deploy/ layout, no `make init`) | `FIX_VERSION` marker + verify step in the apply commands |
| `make up` failed with 11 "variable is missing" errors when `.env` did not exist | `make up`/`make seed` now auto-create `.env` |
| `up --wait` with a one-shot `migrate` container is Compose-version dependent | replaced by `scripts/wait_ready.sh` (polls `/readyz`, prints logs on failure) |
| Seed password was random and easy to miss | `make init` stores one in `.env`; `make creds` prints it |
| Integration tests could not reach Valkey; lockout test locked a real user for 15 min | Valkey on 127.0.0.1 only; `make test-integration`; lockout test uses a probe account and cleans up |
| Unpinned deps (`>=`) -> builds differ between Codespace (py3.14) and Docker (py3.12) | `backend/constraints.txt` (pinned, tested on py3.12); `make lock` refreshes it |
| `make ci` failed: 273 ruff + 76 mypy findings | ruff 0 findings, mypy 0 errors (lint also caught a regression I had introduced in links/topology) |
| `nr-ims-fixed.zip` was committed to git | `*.zip` in `.gitignore` |
