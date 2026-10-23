# NR-IMS Phase Progress

## Current Phase
- Phase 2f (alarm UI, F-1..F-5 + F-6): status: **done in Claude's sandbox; Codespace + browser verification pending** (`make test-all`, then the browser checklist in the Phase 2f section).
- Phase 2 (backend) was re-verified independently from the delivered ZIP before 2f was built (131 tests x 3 consecutive runs green, 0 leftover rows, no migration drift).
- Phase 1 was verified in your Codespace earlier (see Completed Phases).

## Completed Phases
| # | Name | Tag | Date | Files | Tests |
|---|------|-----|------|-------|-------|
| 2f | Alarm UI (F-1..F-6) | _tag after Codespace `make test-all` + browser checklist are green_ | 2026-10-22 | 14 files: frontend 4 new + 6 modified, backend 2 modified, 1 new integration test file, this state file (see Phase 2f list) | 134 collected = 104 unit + 30 integration (+3); sandbox: all pass 3 consecutive runs, 0 leftover rows; ruff 0; mypy 0; no drift; FE typecheck/build OK, lint unchanged (4 warnings, none new); 29 throwaway jsdom tests (sound engine 15, Alarm Center/Dashboard/Reports 14) on payloads captured from the live backend, mutation-checked |
| 2 | Alarm lifecycle, integrity, maintenance (backend) | _tag after your Codespace `make test-all` is green_ | 2026-10-22 | 9 new + 11 modified (see Phase 2 file list) | 131 collected = 104 unit + 27 integration; sandbox: all 131 pass 3 consecutive runs on one DB (0 leftover rows); ruff 0; mypy 0; `alembic check` no drift from empty and from a seeded DB; migration round-trip (preflight refusal, upgrade+backfill, downgrade, upgrade-back) green |
| 1 | API/UI contract repair | `phase-1-contract` | 2026-10-21 | 22 changed/new (see Phase 1 list) | 83 collected = 70 unit + 13 integration, all pass on a pristine DB; Phase-1 integration tests re-runnable (0 leftover rows); ruff 0; mypy 0; no schema drift; FE typecheck/build OK, lint at baseline (4 warnings); 8 throwaway jsdom render tests against live payloads pass |
| 0 | Baseline freeze | `phase-0-baseline` | 2026-10-21 | 14 changed/new (see list below) | 51 collected = 45 unit + 6 integration, all pass (33 unit tests are new); ruff 0; mypy 0; migration gate green and proven to fail on injected drift; frontend typecheck/build OK |

### Phase 2f file list
Frontend (new): `lib/alarms.ts` (types, badge/severity helpers), `lib/alarmSound.ts` (sound engine), `lib/auth.ts` (`getRole`, UI gating only), `components/AlarmStatusBadge.tsx`
Frontend (modified): `hooks/useAlarmsQuery.ts` (F-1), `hooks/useAlarmSound.ts` (F-4), `pages/Alarms.tsx` (rewritten: F-2, F-3), `pages/Wallboard.tsx` (asks for `status=active`, typed), `pages/Dashboard.tsx` (F-6), `pages/Reports.tsx` (F-5)
Backend (modified): `api/v1/reports.py` (F-5), `api/v1/dashboard.py` (F-6)
Tests (new): `backend/tests/integration/test_alarm_kpis_phase2f.py` (3, mutation-checked)

| ID | Gap | Fix | Status |
|----|-----|-----|--------|
| F-1 | `useAlarmsQuery` hard-coded `/alarms/` | `useAlarmsQuery(status = "open", {enabled, limit})`; status is part of the query key (invalidate `["alarms"]` refreshes all); sound hook and Wallboard ask `status=active` (smaller payload, same meaning as their client-side filter) | fixed (sandbox) |
| F-2 | No Resolve button, no history | Details drawer: Acknowledge / Resolve with optional note (max 500), full history timeline (`event_type`, `from -> to`, actor, note), ack/resolve metadata; resolved alarms are read-only; read-only roles see an explanation instead of buttons; errors show the server message | fixed (sandbox) |
| F-3 | Two-state badge (`active ? red : green`) | `AlarmStatusBadge`: active red / acknowledged amber / resolved green, plus `xN` when an alarm was re-reported (de-duplicated recurrences). Tabs: Open / Unacknowledged / Acknowledged / Resolved (resolved is fetched only while its tab is open) | fixed (sandbox) |
| F-4 | `useAlarmSound` fragile. Found while reading the code: it is mounted by AppShell **and** the Alarms page **and** the Wallboard, each with its own counter, so one new alarm beeped once per mounted instance (double beep); beeps were triggered by a COUNT increase, so "one acknowledged + one new" (3 -> 3) was silent; 2 s `setInterval` polling of the AudioContext; `any` casts | One module-level engine (`lib/alarmSound.ts`) remembers announced alarm ids: each alarm sounds once however many components observe it; beeps on a NEW id entering {active, critical, unsuppressed} (new alarm, recurrence, escalation to critical, end of suppression); AudioContext tracked via `onstatechange` (no timer); mute synced across tabs via the `storage` event; unmuting reminds once instead of replaying a backlog; 2 s throttle kept; no `any` | fixed (sandbox) |
| F-5 | Reports counted only `active` | `/reports/summary` kpi adds `acknowledged_alarms`, `open_alarms`, `resolved_alarms` (`active_alarms` unchanged); Reports page card is "Open Alarms" with the breakdown; CSV export keeps its first 7 columns and APPENDS Last Seen, Occurrences, Acknowledged By/At/Note, Resolved By/At/Note (free-text notes are formula-injection safe) | fixed (sandbox) |
| F-6 | **New, found during analysis.** Dashboard "Active Incidents" counted only `active`, so an alarm vanished from the KPI the moment it was acknowledged while the Alarm Center (default `open`) still listed it | `/dashboard/summary` adds `open_alarms` and `acknowledged_alarms` (`active_alarms` unchanged); the card is now "Open Incidents" with "N unacknowledged" underneath and links to the Alarm Center (it used to open the Action Center) | fixed (sandbox) |

Behaviour changes to be aware of: (1) the Dashboard number is now OPEN alarms, so it will usually be higher than before; (2) the Wallboard and the alarm sound deliberately keep showing only UNACKNOWLEDGED alarms; (3) the Dashboard KPI card now opens `/alarms`.

Browser checklist (jsdom cannot cover real audio or real layout):
1. `make up && make seed`, log in, open **Alarm Center**: tabs show Open / Unacknowledged / Acknowledged / Resolved with counts.
2. Click an alarm: drawer opens with history. Type a note, **Acknowledge**: badge turns amber, card stays under Open, the Dashboard "Open Incidents" number does NOT drop, "unacknowledged" does.
3. **Resolve** an alarm: drawer closes, a green notice appears, it is under the Resolved tab with a green badge; Dashboard Open Incidents drops by one.
4. `docker compose exec backend python simulate_fault.py` twice: the second run raises 0 new alarms.
5. Sound: with the Alarm Center open (AppShell + page both mounted) a new critical alarm must beep ONCE. Mute in one browser tab, the other tab follows. If the browser blocks audio, click the blue banner once.
6. Log in as an operator: the drawer shows "read-only", no buttons.
7. Reports: "Open Alarms" card with the breakdown; the CSV opens with the extra columns on the right.

### Phase 2 file list
Backend (new): `models/enums.py`, `models/alarm_event.py`, `services/alarms.py`, `services/maintenance.py`, `migrations/versions/c4d2a8f61b30_phase2_alarm_lifecycle_integrity.py`, `tests/unit/test_phase2_unit.py` (34), `tests/integration/conftest.py`, `tests/integration/test_api_phase2.py` (13), `tests/integration/test_migration_phase2.py` (1)
Backend (modified): `models/alarm.py`, `models/device.py`, `models/device_link.py`, `models/link.py`, `models/__init__.py`, `schemas/alarm.py`, `api/v1/alarms.py` (rewritten), `api/v1/actions.py`, `api/v1/devices.py`, `api/v1/topology_local.py`, `api/v1/discovery.py`, `simulate_fault.py`
Other: `scripts/smoke_phase2.sh` (live API smoke test, 41 checks on a simulator stack / 39 + 1 SKIP on a live stack; `make smoke-phase2`), `scripts/phase2_apply_and_verify.sh`, `scripts/phase2_fix2.sh` (Codespaces apply/fix helpers), `backend/seed_master.py` (seeded alarms now get their 'raised' history event), `Makefile` (`make test-all`, `make smoke-phase2`), `.github/workflows/ci.yml` (migration round-trip step), `docs/PHASE_PROGRESS.md`

Migration `c4d2a8f61b30` (down `e85b9a356da8`): PREFLIGHT aborts with a per-problem fix hint before any DDL if existing data would violate a new rule (bad statuses, duplicate hostname/IP per station, several open alarms per (device, external_id), duplicate/self-loop device_links). Adds `alarms.resolved_by/resolved_at/resolve_note/occurrence_count`, `devices.status_before_maintenance`, table `alarm_events` (existing alarms backfilled), CHECK constraints (alarm status/severity, device status, link status, no self-loop), UNIQUE (station, lower(hostname)), (station, ip), device_links pair, and a partial unique index for open alarms. **Reversible** (`alembic downgrade -1`; alarm history rows are lost on downgrade). The older "forward-only" policy (G-13) still applies to the pre-Phase-2 history; this revision is the first one proven reversible.

API changes (R13 - behaviour changes called out):
| Method + path | Perm | Notes |
|---|---|---|
| `GET /alarms/` | ALARM_READ | **behaviour change:** default `status=open` (active + acknowledged; was active only); returns EVERY alarm (was: first per device); filters `status` (`open/active/acknowledged/resolved/all`), `severity`, `device_id`, `station_code`; `X-Total-Count`; response is a superset of the old payload (no field removed) |
| `PATCH /alarms/{id}/ack` | ALARM_ACK | same shape; 409 on a resolved alarm (was: silently re-acked); body now rejects unknown fields |
| `POST /alarms/{id}/resolve` | ALARM_ACK | new; from active or acknowledged; idempotent (`already_done`) |
| `GET /alarms/{id}/history` | ALARM_READ | new; raised / escalated / acknowledged / resolved, oldest first; foreign alarm = 404 |
| `PUT /actions/{id}/maintenance` | DEVICE_WRITE | exit restores the remembered status (was: always `down`); legacy device with no memory -> `unknown` |
| `POST /actions/execute` | DEVICE_WRITE | simulated RESTART_PORT / REBOOT no longer force status `up` |
| `POST /devices/`, `POST /topology/local/links`, `POST /discovery/approve/{id}` | unchanged | a race past the pre-check now returns 409 from the DB unique index instead of 500 |

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
| G-04 | Alarm lifecycle: acked alarms vanish from every list; no resolve; no dedupe (`external_id` not unique); list shows only the first alarm per device; no alarm history | H | V | P2 | **fixed** (Phase 2: `test_full_lifecycle_history_and_recurrence`, `test_dedupe_and_escalation`, `test_list_defaults_to_open_shows_every_alarm_and_filters`) |
| G-05 | No monitoring engine: device status/alarms only come from seeds / `simulate_fault.py` | C | R | P3 | open |
| G-06 | Remote actions are simulated; live mode returns 501; no executor, no command allow-list | H | R | P5 | open |
| G-07 | JWT in `localStorage`, 8 h lifetime, no refresh/logout/revocation; role read client-side from unsigned payload | H | R | P4 | open |
| G-08 | `Login.tsx` pre-fills `admin@nr-ims.local` / `Admin@123` (matches no seeded user; credential hint in shipped bundle) | M | R | P1 | **fixed** (also label/input association) |
| G-09 | Audit split (`remote_actions` vs `audit_events`); `/audit/events` is IRCA-only and unscoped; UI shows only remote actions; divisional admin cannot see in-scope auth/user/station audit | M | R | P4 | open |
| G-10 | `slowapi` and `pyotp` are dependencies but unused: only login is rate-limited; no MFA; no self-service password change | M | R | P4 | open |
| G-11 | Discovery: arbitrary targets (no allow-list), each scan wipes all results, `is_rogue` always False in live mode (no inventory comparison), approve parses `"LKO Division"` string, dead `getattr(user,"station_code")`, worker runs as root, `snmpsim:latest` unpinned | H | R | P5 | open |
| G-12 | SNMP v2c only (community string); no v3 | M | R | P5 | open |
| G-13 | Migrations are forward-only: `alembic downgrade base` fails at `961615880a29` (duplicate `interface_name`); `drop_constraint(None, ...)` in `1cf5697e6a41`, `9a606f7f60ea`; `961615880a29` upgrade drops a column. Cannot edit applied history | M | V | P0 policy + CI gate | **mitigated** |
| G-14 | No integrity constraints: no UNIQUE on device ip / (station, hostname) / alarm (device, external_id) / link pair; status columns are free text (no CHECK) | M | R | P2 | **fixed** (`test_database_rejects_invalid_and_duplicate_rows`, `test_duplicate_device_links_rejected_at_db_and_api`; station-link pair uniqueness deliberately NOT added: parallel providers between two stations are legitimate) |
| G-15 | No status history / time-series; SLA uptime uses current state only; no retention for alarms/audit | H | R | P3 | open |
| G-16 | Dashboard "Total devices" = `devices.length` of a list capped at 100 -> wrong KPI beyond 100 devices; lists are bare arrays with no totals | H | V | P1 | **fixed** (`/dashboard/summary`, `X-Total-Count`; seed now yields 112 devices so the cap is observable) |
| G-17 | `GET /links/` returns raw ORM rows and exposes the foreign endpoint code of boundary links | L | R | P1 | **fixed** (behaviour change, see API table) |
| G-18 | CI regression: 16 ruff + 3 mypy findings introduced after the last audit (Phase-1 arq/SNMP code) | H | V | P0 | **fixed** |
| G-19 | No CI pipeline in repo (`.github/` absent) | H | R | P0 | **fixed** |
| G-20 | Tests thin: `test_rca_suppression_and_ack` permanently acks one of the 2 seeded alarms per run, so the integration suite fails from the 3rd run on the same DB; no frontend/e2e tests | M | V | P0 (unit) / P6 | partial: integration suite re-runnable (3 consecutive runs green on one DB; ack is idempotent and acked alarms stay listed); no frontend/e2e tests yet |
| G-21 | No metrics, tracing, request IDs, backup/restore drill, TLS | H | R | P8 | open |
| G-22 | Repo hygiene: 2 nested zips committed, `apply_v3_1.sh` patch script, stale README | L | V | P0 | partial (see Known Issues) |
| G-23 | Frontend: ~100 `any`, no toasts (alert() used), inline styles, polling instead of push, 1.1 MB charts chunk, 4 oxlint warnings; `StationDetail` keeps one module-level dagre graph that is never cleared (stale nodes from earlier stations skew layout); icon-only view-toggle buttons have no accessible name | M | R | P7 | open |
| G-24 | `worker` + `snmpsim` live only in `docker-compose.override.yml` (lost with `-f docker-compose.yml`); worker `user: 0:0` | M | R | P5/P8 | open |
| G-25 | `PUT /actions/{id}/maintenance` exit sets status `"down"` regardless of real state; no maintenance window/expiry; simulated REBOOT/RESTART force `"up"` | H | R | P2 | **fixed** (`test_maintenance_exit_restores_real_status`, `test_simulated_actions_no_longer_invent_status`; maintenance windows/expiry stay with Phase 7a) |
| G-26 | Tier/station_type/severity are free text; no enums shared between backend and frontend (device `category` is now an enum on create only; discovery-approve and seeds still write free text) | L | R | P2 | partial: alarm/device/link status + severity enums and CHECKs done; station tier/type and discovery-approve category remain free text |
| G-27 | Dashboard showed invented KPIs ("Compliance 98.5%", "Traffic 45%") | H | R | P1 | **fixed** (real availability % and maintenance count) |
| G-28 | Failed mutations were silent; any render error blanked the app | M | R | P1 | partial: boundary + `errorMessage` applied to Login, DeviceDetail, StationDetail; Users/Stations/Discovery/Actions pages still silent (P7) |
| G-29 | `EmailStr` rejects `.local`: dev seed users (`@nr-ims.local`) cannot be created through the user API/UI | L | V | P4 | open |
| G-31 | `make install` used `.venv/bin/activate` as its "done" stamp, which `python3 -m venv` itself creates: with a hand-made venv `make install` did nothing, so `make lint/type/test/test-integration` failed (`.venv/bin/ruff` missing). My Phase 0/1 instructions told you to create the venv by hand | H | V | hotfix 1.1 | **fixed** (own stamp `.venv/.nrims-installed`, prefers python3.12, uses `constraints.txt`) |
| G-32 | Codespaces/Docker-in-Docker: container-to-container traffic dropped (`[db-wait] TCP TIMEOUT ... packets dropped`), so `migrate` fails and the stack never starts. The repo already had `make fix-network` but `make up` did not run it and it is lost on Codespace restart | H | R (symptom in your log; fix not runnable without Docker in my sandbox) | hotfix 1.1 | **fixed, confirmed in Codespace** (`-P FORWARD DROP` found, `make up` applied the fix and the stack became healthy) |
| G-33 | Setup instructions: placeholder path (`<apne-repo-ka-naam>`) pasted literally; WIP commit made on `main` before the branch switch; tags created although `make ci` had failed; `make ci` result never verified on your side | M | V | hotfix 1.1 | **fixed** (recovery steps given; README corrected) |
| G-34 | Codespace has `python3.12` without the `venv` module (`python3` is 3.14): `make install` failed, and the failed attempt left a half-made `.venv` (python symlink, no pip) that the fix1 Makefile accepted as valid (`.venv/bin/pip: No such file`) | M | V | hotfix 1.2 | **fixed** (pip-based validity check, self-heals partial venv, prints the apt hint; you still need `sudo apt-get install -y python3.12-venv` once) |
| F-1..F-6 | Alarm UI gaps (details in the Phase 2f section) | M-H | V/R | 2f | **fixed** (sandbox; browser check pending) |
| G-30 | Device create is check-then-insert with no DB UNIQUE: two concurrent creates can both pass the duplicate check | M | R | P2 (with G-14) | **fixed** (`test_concurrent_device_create_exactly_one_wins_never_500`) |

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
- (resolved by Phase 2) `test_rca_suppression_and_ack` used to fail from the 3rd run: acknowledged alarms now stay in the default list and ack is idempotent.
- `alembic downgrade` is unsupported (G-13).
- oxlint reports 4 warnings (unused catch bindings); deferred to Phase 7.

## Roadmap
| Phase | Name | Closes |
|-------|------|--------|
| 0 | Baseline freeze (**done**) | G-13 (mitigated), G-18, G-19, part of G-20, G-22 |
| 1 | API/UI contract repair (**done**) | G-01, G-02, G-03 (API+seed), G-08, G-16, G-17, G-27, G-28 (partial) |
| 2 | Alarm lifecycle, integrity, maintenance (**done**: backend + UI Phase 2f, Codespace/browser verification pending) | G-04, G-14, G-25, G-30, G-26 (partial) |
| 3 | Monitoring engine + history | G-05, G-15, G-03 (live) |
| 4 | Auth and audit hardening | G-07, G-09, G-10 |
| 5 | Discovery and remote execution | G-06, G-11, G-12, G-24 |
| 6 | Seeds, test isolation, e2e | G-20 |
| 7 | Frontend quality and realtime | G-23 |
| 8 | Ops: observability, backup, TLS | G-21, G-24 |
| 9 | Release candidate | — |

## Known Issues added by the 2f review
- `docs/AUDIT_REPORT_v1.md` and this file were produced by **two separate Claude sessions** (one worked from a "master prompt" with its own 16-phase roadmap: 2f, 3a..8c and T/SEC/ARC/UX ids; the other from this file's 10-phase roadmap). This file's roadmap above is the one that was actually delivered; if you keep using the other prompt, reconcile the two before Phase 3 so ids do not collide.
- `scripts/phase2_apply_and_verify.sh` and `scripts/phase2_fix2.sh` are one-off Codespaces repair helpers (the second one rewrites `tests/integration/conftest.py`, which is already fixed in the tree). Delete both once `make test-all` is green in your Codespace; they are not part of the product.
- Frontend tests are still throwaway (vitest + jsdom were NOT added to `package.json`). Phase 7 should adopt `src/lib/alarmSound.ts` and the 29 tests as the first real frontend suite.
- `alembic.ini` lacks `path_separator = os` (Alembic prints a DeprecationWarning on every test run; harmless today, becomes an error in Alembic 2.x). One-line fix, deferred.
- Test layout is mixed: `tests/unit/` and `tests/integration/` exist next to older top-level `test_*.py` files; move them in Phase 6.
- Verified by reading only, not run anywhere: real browser audio, real layout of the drawer at small widths, GitHub Actions.

## Next Phase
- Phase 3: Monitoring engine + history (G-05, G-15, G-03 live polling): arq cron poller (ICMP + SNMP) feeding `raise_alarm` / `set_observed_status`, status history table. Starts when you reply `next`, after your Codespace `make test-all` and the Phase 2f browser checklist are green.
