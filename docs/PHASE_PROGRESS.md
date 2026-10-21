# NR-IMS Phase Progress

## Current Phase
- Phase 1: API/UI contract repair — status: **done; Codespace verification in progress**. Confirmed in your Codespace: `make up` (network fix auto-applied), `make seed` (+98 devices/+98 links/+238 interfaces), `make frontend-ci` (typecheck + build OK, lint 4 baseline warnings). Still pending in Codespace: `make ci`, `make test-integration`, browser checklist.

## Completed Phases
| # | Name | Tag | Date | Files | Tests |
|---|------|-----|------|-------|-------|
| 1 | API/UI contract repair | `phase-1-contract` | 2026-10-21 | 22 changed/new (see Phase 1 list) | 83 collected = 70 unit + 13 integration, all pass on a pristine DB; Phase-1 integration tests re-runnable (0 leftover rows); ruff 0; mypy 0; no schema drift; FE typecheck/build OK, lint at baseline (4 warnings); 8 throwaway jsdom render tests against live payloads pass |
| 0 | Baseline freeze | `phase-0-baseline` | 2026-10-21 | 14 changed/new (see list below) | 51 collected = 45 unit + 6 integration, all pass (33 unit tests are new); ruff 0; mypy 0; migration gate green and proven to fail on injected drift; frontend typecheck/build OK |

### Phase 1 file list
Backend (new): `schemas/link.py`, `schemas/topology.py`, `api/v1/topology_local.py`, `seed_inventory.py`, `tests/test_schemas_phase1.py` (25), `tests/test_api_phase1.py` (7 integration, self-cleaning)
Backend (modified): `schemas/device.py`, `api/v1/devices.py`, `api/v1/links.py`, `api/v1/dashboard.py`, `main.py` (router + `expose_headers`), `Dockerfile` (copies `seed_inventory.py`)
Frontend (new): `components/ErrorBoundary.tsx`
Frontend (modified): `lib/api.ts` (`errorMessage`), `App.tsx`, `pages/Login.tsx`, `pages/DeviceDetail.tsx`, `pages/Dashboard.tsx`, `pages/StationDetail.tsx`
Other: `Makefile` (`make seed` runs `seed_inventory.py` between links and admin), `docs/PHASE_PROGRESS.md`

New / changed API surface (all additive except the links scope change):
| Method + path | Perm | Notes |
|---|---|---|
| `GET /devices/{id}/detail` | DEVICE_READ | `{device, interfaces, ospf_neighbors}`; `ospf_neighbors` is `[]` until Phase 3 |
| `POST /devices/` | DEVICE_WRITE | 201; 404 outside scope, 409 duplicate hostname/IP in station, 422 validation; status starts `unknown`; audited |
| `DELETE /devices/{id}` | DEVICE_WRITE | children re-parented; links cascade; returns `links_deleted`; audited |
| `GET /devices/` | DEVICE_READ | now sets `X-Total-Count` (exposed via CORS) |
| `GET /topology/local/{code}` | DEVICE_READ | React Flow `{nodes, edges}` |
| `POST /topology/local/links`, `DELETE /topology/local/links/{id}`, `PUT /topology/local/device/{id}/position` | DEVICE_WRITE | same-station only; 409 duplicate (either direction); foreign = 404 |
| `GET /dashboard/summary` | DEVICE_READ | scoped KPIs computed in SQL |
| `GET /links/`, `GET /links/{code}` | DEVICE_READ | **behaviour change:** only links with BOTH stations in scope (was: either); typed `LinkRead` |

### Phase 0 file list
- `backend/app/api/v1/discovery.py` — handle `enqueue_job() -> None` (arq returns None on duplicate job id): 409 instead of `AttributeError` 500
- `backend/app/workers/discovery.py` — mypy fix (`bool(s.error)`), no behaviour change
- `backend/app/services/snmp.py` — `zip(..., strict=True)`
- `backend/migrations/env.py` — removed duplicate `import app.models` (E402/F811)
- `backend/pyproject.toml` — narrow, commented ruff ignores (applied migrations stay immutable)
- `backend/tests/test_correlation.py`, `test_rbac_scope.py`, `test_tokens.py`, `test_discovery_helpers.py` — 33 new unit tests (RCA 7, RBAC/scope 12, JWT 7, discovery/CSV helpers 7)
- `scripts/check_migrations.sh` — upgrade-from-empty + `alembic check` (drift) gate
- `Makefile` — `migrations-check` target
- `.github/workflows/ci.yml` — guards, backend lint/type/test, migrations gate (Postgres service), frontend lint/typecheck/build
- `README.md` — real phase table, points to this file
- `docs/PHASE_PROGRESS.md` — this file

## Open Gap Register
Severity: C = critical (feature broken / wrong data), H = high, M = medium, L = low.
Evidence: **V** = reproduced live on Postgres 16 + Valkey this session, **R** = read in code.

| ID | Gap | Sev | Ev | Planned | Status |
|----|-----|-----|----|---------|--------|
| G-01 | `GET /devices/{id}` returns flat `DeviceRead`; `DeviceDetail.tsx` destructures `{device, interfaces, ospf_neighbors}` -> TypeError, blank page (no error boundary) | C | V | P1 | **fixed** (detail endpoint + page + boundary) |
| G-02 | Frontend calls 6 non-existent endpoints: `POST /devices/`, `DELETE /devices/{id}`, `GET /topology/local/{code}`, `POST|DELETE /topology/local/links`, `PUT /topology/local/device/{id}/position` (405/404). `device_links` table has 0 rows and no API | C | V | P1 | **fixed** (server side + live-payload render test; edge drawing needs your browser check) |
| G-03 | `interfaces` table: 0 rows, no API, no seed, no poller. OSPF neighbours have no model at all | H | V | P1 (API+seed) / P3 (poll) | partial: API + seed done; live polling and OSPF model in P3 |
| G-04 | Alarm lifecycle: acked alarms vanish from every list; no resolve; no dedupe (`external_id` not unique); list shows only the first alarm per device; no alarm history | H | V | P2 | open |
| G-05 | No monitoring engine: device status/alarms only come from seeds / `simulate_fault.py` | C | R | P3 | open |
| G-06 | Remote actions are simulated; live mode returns 501; no executor, no command allow-list | H | R | P5 | open |
| G-07 | JWT in `localStorage`, 8 h lifetime, no refresh/logout/revocation; role read client-side from unsigned payload | H | R | P4 | open |
| G-08 | `Login.tsx` pre-fills `admin@nr-ims.local` / `Admin@123` (matches no seeded user; credential hint in shipped bundle) | M | R | P1 | **fixed** (also label/input association) |
| G-09 | Audit split (`remote_actions` vs `audit_events`); `/audit/events` is IRCA-only and unscoped; UI shows only remote actions; divisional admin cannot see in-scope auth/user/station audit | M | R | P4 | open |
| G-10 | `slowapi` and `pyotp` are dependencies but unused: only login is rate-limited; no MFA; no self-service password change | M | R | P4 | open |
| G-11 | Discovery: arbitrary targets (no allow-list), each scan wipes all results, `is_rogue` always False in live mode (no inventory comparison), approve parses `"LKO Division"` string, dead `getattr(user,"station_code")`, worker runs as root, `snmpsim:latest` unpinned | H | R | P5 | open |
| G-12 | SNMP v2c only (community string); no v3 | M | R | P5 | open |
| G-13 | Migrations are forward-only: `alembic downgrade base` fails at `961615880a29` (duplicate `interface_name`); `drop_constraint(None, ...)` in `1cf5697e6a41`, `9a606f7f60ea`; `961615880a29` upgrade drops a column. Cannot edit applied history | M | V | P0 policy + CI gate | **mitigated** |
| G-14 | No integrity constraints: no UNIQUE on device ip / (station, hostname) / alarm (device, external_id) / link pair; status columns are free text (no CHECK) | M | R | P2 | open |
| G-15 | No status history / time-series; SLA uptime uses current state only; no retention for alarms/audit | H | R | P3 | open |
| G-16 | Dashboard "Total devices" = `devices.length` of a list capped at 100 -> wrong KPI beyond 100 devices; lists are bare arrays with no totals | H | V | P1 | **fixed** (`/dashboard/summary`, `X-Total-Count`; seed now yields 112 devices so the cap is observable) |
| G-17 | `GET /links/` returns raw ORM rows and exposes the foreign endpoint code of boundary links | L | R | P1 | **fixed** (behaviour change, see API table) |
| G-18 | CI regression: 16 ruff + 3 mypy findings introduced after the last audit (Phase-1 arq/SNMP code) | H | V | P0 | **fixed** |
| G-19 | No CI pipeline in repo (`.github/` absent) | H | R | P0 | **fixed** |
| G-20 | Tests thin: `test_rca_suppression_and_ack` permanently acks one of the 2 seeded alarms per run, so the integration suite fails from the 3rd run on the same DB; no frontend/e2e tests | M | V | P0 (unit) / P6 | partial |
| G-21 | No metrics, tracing, request IDs, backup/restore drill, TLS | H | R | P8 | open |
| G-22 | Repo hygiene: 2 nested zips committed, `apply_v3_1.sh` patch script, stale README | L | V | P0 | partial (see Known Issues) |
| G-23 | Frontend: ~100 `any`, no toasts (alert() used), inline styles, polling instead of push, 1.1 MB charts chunk, 4 oxlint warnings; `StationDetail` keeps one module-level dagre graph that is never cleared (stale nodes from earlier stations skew layout); icon-only view-toggle buttons have no accessible name | M | R | P7 | open |
| G-24 | `worker` + `snmpsim` live only in `docker-compose.override.yml` (lost with `-f docker-compose.yml`); worker `user: 0:0` | M | R | P5/P8 | open |
| G-25 | `PUT /actions/{id}/maintenance` exit sets status `"down"` regardless of real state; no maintenance window/expiry; simulated REBOOT/RESTART force `"up"` | H | R | P2 | open |
| G-26 | Tier/station_type/severity are free text; no enums shared between backend and frontend (device `category` is now an enum on create only; discovery-approve and seeds still write free text) | L | R | P2 | open |
| G-27 | Dashboard showed invented KPIs ("Compliance 98.5%", "Traffic 45%") | H | R | P1 | **fixed** (real availability % and maintenance count) |
| G-28 | Failed mutations were silent; any render error blanked the app | M | R | P1 | partial: boundary + `errorMessage` applied to Login, DeviceDetail, StationDetail; Users/Stations/Discovery/Actions pages still silent (P7) |
| G-29 | `EmailStr` rejects `.local`: dev seed users (`@nr-ims.local`) cannot be created through the user API/UI | L | V | P4 | open |
| G-31 | `make install` used `.venv/bin/activate` as its "done" stamp, which `python3 -m venv` itself creates: with a hand-made venv `make install` did nothing, so `make lint/type/test/test-integration` failed (`.venv/bin/ruff` missing). My Phase 0/1 instructions told you to create the venv by hand | H | V | hotfix 1.1 | **fixed** (own stamp `.venv/.nrims-installed`, prefers python3.12, uses `constraints.txt`) |
| G-32 | Codespaces/Docker-in-Docker: container-to-container traffic dropped (`[db-wait] TCP TIMEOUT ... packets dropped`), so `migrate` fails and the stack never starts. The repo already had `make fix-network` but `make up` did not run it and it is lost on Codespace restart | H | R (symptom in your log; fix not runnable without Docker in my sandbox) | hotfix 1.1 | **fixed, confirmed in Codespace** (`-P FORWARD DROP` found, `make up` applied the fix and the stack became healthy) |
| G-33 | Setup instructions: placeholder path (`<apne-repo-ka-naam>`) pasted literally; WIP commit made on `main` before the branch switch; tags created although `make ci` had failed; `make ci` result never verified on your side | M | V | hotfix 1.1 | **fixed** (recovery steps given; README corrected) |
| G-34 | Codespace has `python3.12` without the `venv` module (`python3` is 3.14): `make install` failed, and the failed attempt left a half-made `.venv` (python symlink, no pip) that the fix1 Makefile accepted as valid (`.venv/bin/pip: No such file`) | M | V | hotfix 1.2 | **fixed** (pip-based validity check, self-heals partial venv, prints the apt hint; you still need `sudo apt-get install -y python3.12-venv` once) |
| G-30 | Device create is check-then-insert with no DB UNIQUE: two concurrent creates can both pass the duplicate check | M | R | P2 (with G-14) | open |

## Assumption Log
| # | Assumption | Confirmed? |
|---|------------|-----------|
| A1 | Target runtime stays Docker Compose (Codespaces for dev); Python 3.12, Postgres 15, Valkey 7.2 kept | no |
| A2 | "Live" data = ICMP + SNMP polling by our own worker (no vendor EMS/API integration) | no |
| A3 | Production migrations are forward-only (expand/contract) + backup first; downgrade is not a supported path | no |
| A4 | Hindi code comments are acceptable and are kept as is | no |
| A5 | Single zone (Northern Railway); divisions/stations as seeded | no |
| A10 | Local venv uses Python 3.12 (the version `constraints.txt` is pinned and CI-tested on); other versions get an unpinned install with a warning | no |
| A6 | Existing dev DB volumes must keep working: no destructive migration, no edits to applied revisions (Phase 1 added NO migration) | no |
| A7 | Manually created devices start as `unknown` (we do not claim `up` without a poller) | no |
| A8 | Deleting a device re-parents its children to the deleted device's parent instead of blocking or cascading | no |
| A9 | Tightening `/links/` to both-endpoints-in-scope is acceptable (matches `/topology/`; no frontend consumer) | no |

## Known Issues / Deferred
- Git hygiene: local `main` was reset to `origin/main` (done, confirmed). The tags `phase-0-baseline` / `phase-1-contract` do not exist in your repo (nothing to delete): create `phase-1-contract` only after `make ci`, `make test-integration`, `make frontend-ci` and the browser checklist are all green.
- The `make fix-network` iptables setting does not survive a Codespace restart (now re-applied by `make up` when `$CODESPACES=true`).
- Two stray archives remain in the repo root: `nr-ims-fixed.zip`, `nr-ims-fixed latest claude.zip` (ignored by `.gitignore` but already tracked). Remove with: `git rm --cached "nr-ims-fixed.zip" "nr-ims-fixed latest claude.zip" && rm -f nr-ims-fixed*.zip "nr-ims-fixed latest claude.zip"`
- `apply_v3_1.sh` is a historical patch script; left in place, delete in Phase 8 once all environments are on v3.2+.
- Phase 1 UI render tests ran in a throwaway copy (vitest + jsdom + testing-library, NOT added to `package.json`); adopting a real frontend test setup is Phase 7. jsdom cannot draw React Flow edges, so edge rendering and drag-to-save-position are **not** machine-verified: check them in your browser.
- Docker Compose stack and GitHub Actions were not executed in my sandbox (native Postgres 16 + Redis used). Compose uses Postgres 15.
- `make seed` on an existing DB adds inventory (idempotent); `make reset` + `make seed` for a clean slate.
- Integration test `test_rca_suppression_and_ack` consumes one seeded alarm per run (2 seeded): the 3rd run on the same DB fails with `assert []`. Workaround: `UPDATE alarms SET status='active', acked_by=NULL, acked_at=NULL, ack_note=NULL;` or `make reset`. Fixed properly in Phase 6 (test isolation).
- `alembic downgrade` is unsupported (G-13).
- oxlint reports 4 warnings (unused catch bindings); deferred to Phase 7.

## Roadmap
| Phase | Name | Closes |
|-------|------|--------|
| 0 | Baseline freeze (**done**) | G-13 (mitigated), G-18, G-19, part of G-20, G-22 |
| 1 | API/UI contract repair (**done**) | G-01, G-02, G-03 (API+seed), G-08, G-16, G-17, G-27, G-28 (partial) |
| 2 | Alarm lifecycle, integrity, maintenance | G-04, G-14, G-25, G-26 |
| 3 | Monitoring engine + history | G-05, G-15, G-03 (live) |
| 4 | Auth and audit hardening | G-07, G-09, G-10 |
| 5 | Discovery and remote execution | G-06, G-11, G-12, G-24 |
| 6 | Seeds, test isolation, e2e | G-20 |
| 7 | Frontend quality and realtime | G-23 |
| 8 | Ops: observability, backup, TLS | G-21, G-24 |
| 9 | Release candidate | — |

## Next Phase
- Phase 2: Alarm lifecycle, integrity, maintenance (G-04, G-14, G-25, G-26, G-30) — starts when you reply `next`. Will add the first schema migration (expand-only: constraints, alarm history, status enums).
