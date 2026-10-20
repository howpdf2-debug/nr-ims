# NR-IMS — Northern Railway Integrated Network Management System

NOC application for monitoring approved railway network infrastructure.
Status: **Phase P0 (Foundation) — early development, not for operational use.**

## Quick start (local)

Backend:

    python3 -m venv .venv
    source .venv/bin/activate
    make install
    make ci

Stack (Docker):

    make init            # .env with random secrets (also auto-run by make up)
    make up              # build, migrate, start, wait until /readyz is 200
    make seed            # master data, links, users
    make creds           # dev login
    make test-integration

## Phases

| Day | Phase | Status |
| :--- | :--- | :--- |
| 1 | P0 Foundation | in progress |
| 2 | P1 Data + Audit | pending |
| 3 | P2 Auth + RBAC | pending |
| 4 | P3 Core APIs | pending |
| 5 | P4 Integrations | pending |
| 6 | P5 Frontend shell | pending |
| 7 | P6 Main screens | pending |
| 8 | P7 Incidents, Topology, Live | pending |
| 9 | P8 Hardening | pending |
| 10 | P9 Release | pending |

See `docs/` for architecture and ADRs.
## Seed Safety (v3.2+)

`make seed` is now idempotent and **will not delete existing data**.
To force a destructive re-seed (dev only, DATA LOSS):

    NRIMS_ALLOW_DESTRUCTIVE_SEED=true make seed

This is a safety guard against accidental data loss. Never use in production.
