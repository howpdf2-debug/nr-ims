# NR-IMS — Northern Railway Integrated Network Management System

NOC application for monitoring approved railway network infrastructure.

**Status:** Phase 1 (API/UI contract repair) is complete; the project is being taken to a production-grade,
upgrade-safe release in numbered phases. Live progress, the open gap register and the roadmap are in
[`docs/PHASE_PROGRESS.md`](docs/PHASE_PROGRESS.md) (single source of truth). Not yet for operational use.

## Quick start

Stack (Docker):

    make init            # .env with random secrets (also auto-run by make up)
    make up              # build, migrate, start, wait until /readyz is 200
    make seed            # master data, links, users
    make creds           # dev login
    make test-integration

Backend only (`make install` creates `.venv` by itself; do not create it by hand):

    make install         # python3.12 venv + pinned dependencies (backend/constraints.txt)
                         # Debian/Ubuntu/Codespaces may first need: sudo apt-get install -y python3.12-venv
    make ci              # guards + ruff + mypy + unit tests

GitHub Codespaces: `make up` automatically applies the Docker-in-Docker network fix
(`make fix-network`). If a start still fails with `TCP TIMEOUT ... packets dropped`, run
`make fix-network && make down && make up`. The fix is not persistent across Codespace restarts.

Frontend: `make frontend-ci` (lint, typecheck, build).

## Quality gates (also run by `.github/workflows/ci.yml`)

| Gate | Command |
| :--- | :--- |
| Repo guards, ruff, mypy, unit tests | `make ci` |
| Migrations: upgrade from empty DB + model drift | `NRIMS_DATABASE_URL=<empty scratch db> make migrations-check` |
| Integration tests (needs `make up && make seed`) | `make test-integration` |
| Frontend | `make frontend-ci` |

## Migrations policy

Migrations are **forward-only** (expand/contract). Never edit an applied revision: add a new one.
`alembic downgrade` is not a supported path (see gap G-13). Take a backup before migrating production.

## Seed safety (v3.2+)

`make seed` is idempotent and **will not delete existing data**.
It loads divisions/stations/routers, inter-station links, a demo device inventory (switches, counters,
TS, BTS, modems + device links + interfaces) and the dev users.
To force a destructive re-seed (dev only, DATA LOSS):

    NRIMS_ALLOW_DESTRUCTIVE_SEED=true make seed

Never use in production.
