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

    cp deploy/.env.example deploy/.env
    make up
    curl http://localhost:8000/readyz

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