"""Polling engine (Phase 3a-2): ICMP + SNMPv3 -> metrics tables, device status, dead-man alarm.

One cycle (``poll_all_devices``, run every 60 s by the arq cron in ``arq_worker.py``):

1. READ   one short session loads the devices to poll, their poll state and the SNMP credential profiles.
2. PROBE  per device, with NO database connection held: ICMP ping and (when a credential applies) an SNMPv3
          poll run concurrently. At most ``concurrency`` (50) devices are probed at once.
3. WRITE  per device, one short transaction: ``device_poll_state``, ``device_metrics``, ``interface_metrics``,
          the observed device status and the dead-man alarm. A failure in one device never touches another.

Decisions worth knowing (each is a named constant or a small pure function, so it is easy to change):

* A device is REACHABLE when ICMP answers OR SNMP answers (an SNMP *auth* error also proves the agent replied).
  Reachable -> status ``up``. Unreachable for ``DOWN_AFTER_FAILURES`` consecutive cycles -> ``down``
  (one lost cycle never flips a status).
* If ICMP itself cannot run (e.g. the worker has no NET_RAW), that is *our* problem, not the device's: the cycle
  is INCONCLUSIVE for that device, nothing is counted against it and its status is left alone.
* SNMP failing while ICMP answers is NOT an outage. It is recorded in ``device_poll_state.last_error*`` only
  (no alarm), so devices that simply do not speak SNMP do not flood the alarm list.
* Dead-man switch (ARC-04): no sign of life for ``DEADMAN_AFTER_S`` (5 min) -> ONE critical alarm per outage
  (``raise_alarm``); it is resolved automatically when the device answers again. Devices in maintenance never
  raise it. The check runs right after each device's own probe, so a worker restart cannot create false alarms.
* Interface counters need the previous sample to become rates (``app.monitoring.rates``). Snapshots live in
  Valkey (``RedisCounterStore``) so they survive worker restarts; without Valkey the first cycle after a
  restart simply has no rates (never a wrong rate).
* Interfaces are matched to the ``interfaces`` inventory by NAME. Interfaces the device reports but the
  inventory does not know are skipped (the poller never creates inventory rows).

PHASE-2 ADAPTER: the three calls into Account 1's Phase-2 services are isolated in ``_apply_status``,
``_raise_deadman`` and ``_resolve_deadman``. If a signature differs from the assumption written there, change
only those three functions. A failure in an adapter is logged and rolled back to a SAVEPOINT; it never stops
metric collection.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import ConfigError
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.interface import Interface
from app.models.monitoring import DeviceMetric, DevicePollState, InterfaceMetric, SnmpCredentialProfile
from app.monitoring.profiles import ProfileRegistry
from app.monitoring.rates import CounterSnapshot, compute_interface_rates
from app.monitoring.security import (
    CredentialError,
    MonitoringSettings,
    TargetNotAllowed,
    build_fernet,
    check_snmp_target,
    decrypt_secret,
    get_monitoring_settings,
)
from app.services import alarms as alarm_service  # Phase 2 (Account 1)
from app.services.maintenance import set_observed_status  # Phase 2 (Account 1)
from app.services.ping import PingResult, ping_host
from app.services.snmp_v3 import (
    InterfaceSample,
    PollSample,
    SnmpErrorKind,
    SnmpV3Credentials,
    poll_device,
)

log = logging.getLogger(__name__)

# ── tunables ────────────────────────────────────────────────────────────────────────────────────
POLL_INTERVAL_S = 60  # cadence of the cron job; also converts "5 minutes" into a cycle count
CONCURRENCY = 50  # devices probed at the same time
DB_CONCURRENCY = 8  # simultaneous write transactions (the pool is small; the API needs connections too)
CYCLE_BUDGET_S = 35.0  # no NEW device is started after this; running ones finish (<= poll_deadline_s)
DOWN_AFTER_FAILURES = 2  # consecutive unreachable cycles before status -> down
DEADMAN_AFTER_S = 300  # 5 minutes without any sign of life -> alarm (ARC-04)
DEADMAN_ALARM_ID = "poller-deadman"  # alarms.external_id (one open alarm per device)
DEADMAN_SEVERITY = "critical"
COUNTER_TTL_S = 1200  # previous counters older than this are useless anyway (rates.MAX_GAP_S = 900)
_INT32_MAX = 2_147_483_647  # error/discard columns are 32-bit; a 32-bit counter delta can exceed that
_ERR_MAX = 200  # device_poll_state.last_error is VARCHAR(200)
_GONE_KINDS = frozenset({SnmpErrorKind.TIMEOUT, SnmpErrorKind.UNREACHABLE, SnmpErrorKind.DEADLINE})


# ── ICMP and SNMP probes ────────────────────────────────────────────────────────────────────────
async def icmp_ping(host: str, *, count: int = 2, timeout: float = 1.5) -> PingResult:  # noqa: ASYNC109
    """ICMP echo via icmplib (``app.services.ping`` wraps ``icmplib.async_ping``). Never raises.

    ``PingResult.error`` is set only when the probe itself failed (no raw-socket permission, ...), which is
    different from "no reply" (``alive=False``, ``error=None``).
    """
    return await ping_host(host, count=count, timeout=timeout)


async def snmp_poll(host: str, creds: SnmpV3Credentials, registry: ProfileRegistry,
                    mon: MonitoringSettings) -> PollSample:
    """One SNMPv3 poll (system MIB, vendor CPU/memory/temperature, IF-MIB). Never raises for device problems."""
    return await poll_device(host, creds, registry, mon=mon)


class Outcome(StrEnum):
    UP = "up"
    DOWN = "down"
    INCONCLUSIVE = "inconclusive"


def classify_probe(ping: PingResult | None, sample: PollSample | None) -> Outcome:
    """Pure: what did this cycle prove about the device?"""
    snmp_ok = sample is not None and sample.ok
    snmp_replied = snmp_ok or (sample is not None and sample.error_kind is SnmpErrorKind.AUTH)
    if snmp_replied or (ping is not None and ping.alive):
        return Outcome.UP
    if ping is not None and ping.error is None:
        return Outcome.DOWN  # ICMP ran cleanly and nobody answered, and SNMP did not reply either
    # ICMP could not run. Only an SNMP "device is gone" failure is still evidence of an outage.
    if sample is not None and not sample.ok and sample.error_kind in _GONE_KINDS:
        return Outcome.DOWN
    return Outcome.INCONCLUSIVE


def deadman_due(last_success_at: datetime | None, failures: int, now: datetime) -> bool:
    """Pure: has the device been silent for ``DEADMAN_AFTER_S``?

    ``failures`` is the consecutive-failure count INCLUDING this cycle. A device that never answered has no
    ``last_success_at``, so the cycle count stands in for time.
    """
    if last_success_at is not None:
        return (now - last_success_at).total_seconds() >= DEADMAN_AFTER_S
    return failures >= DEADMAN_AFTER_S // POLL_INTERVAL_S


def desired_status(outcome: Outcome, failures: int) -> str | None:
    """Pure: the status to observe, or None to leave the current one alone."""
    if outcome is Outcome.UP:
        return "up"
    if outcome is Outcome.DOWN and failures >= DOWN_AFTER_FAILURES:
        return "down"
    return None


# ── interface counters between cycles ───────────────────────────────────────────────────────────
class CounterStore(Protocol):
    async def load(self, device_id: uuid.UUID) -> dict[str, CounterSnapshot]: ...

    async def save(self, device_id: uuid.UUID, snaps: dict[str, CounterSnapshot]) -> None: ...


class MemoryCounterStore:
    """Process-local. Used by tests and when Valkey is not reachable."""

    def __init__(self) -> None:
        self._data: dict[uuid.UUID, dict[str, CounterSnapshot]] = {}

    async def load(self, device_id: uuid.UUID) -> dict[str, CounterSnapshot]:
        return dict(self._data.get(device_id, {}))

    async def save(self, device_id: uuid.UUID, snaps: dict[str, CounterSnapshot]) -> None:
        self._data[device_id] = dict(snaps)


class RedisCounterStore:
    """Valkey/Redis-backed: survives worker restarts and works with several workers. Errors are never fatal."""

    FAIL_WARN_AFTER = 5

    def __init__(self, redis: Any, ttl_s: int = COUNTER_TTL_S) -> None:
        self._redis, self._ttl = redis, ttl_s
        self._fails = 0  # D1: consecutive Valkey failures (load or save)

    def _failed(self) -> None:
        self._fails += 1
        if self._fails == self.FAIL_WARN_AFTER:  # warn once per streak, not once per device
            log.warning("Valkey counter store has failed %d times in a row; interface rates will be missing",
                        self._fails)

    def _ok(self) -> None:
        self._fails = 0

    @staticmethod
    def _key(device_id: uuid.UUID) -> str:
        return f"nrims:poll:counters:{device_id}"

    async def load(self, device_id: uuid.UUID) -> dict[str, CounterSnapshot]:
        try:
            raw = await self._redis.get(self._key(device_id))
            self._ok()
            if not raw:
                return {}
            return {name: CounterSnapshot(**fields) for name, fields in json.loads(raw).items()}
        except Exception:  # noqa: BLE001  (a bad/missing cache entry only costs one cycle of rates)
            log.debug("counter load failed for %s", device_id, exc_info=True)
            self._failed()
            return {}

    async def save(self, device_id: uuid.UUID, snaps: dict[str, CounterSnapshot]) -> None:
        try:
            await self._redis.set(self._key(device_id), json.dumps({n: asdict(s) for n, s in snaps.items()}),
                                  ex=self._ttl)
            self._ok()
        except Exception:  # noqa: BLE001
            log.debug("counter save failed for %s", device_id, exc_info=True)
            self._failed()


_PROCESS_COUNTERS = MemoryCounterStore()  # shared across cycles when no Valkey connection is given


def build_snapshot(sample: PollSample, itf: InterfaceSample) -> CounterSnapshot | None:
    if itf.counter_bits is None or itf.in_octets is None or itf.out_octets is None:
        return None
    return CounterSnapshot(
        ts=sample.polled_at, uptime_s=sample.uptime_s, in_octets=itf.in_octets, out_octets=itf.out_octets,
        in_errors=itf.in_errors or 0, out_errors=itf.out_errors or 0,
        in_discards=itf.in_discards or 0, out_discards=itf.out_discards or 0, bits=itf.counter_bits)


def _i32(value: int | None) -> int | None:
    return None if value is None else max(0, min(int(value), _INT32_MAX))


# ── credentials ─────────────────────────────────────────────────────────────────────────────────
class CredentialUnavailable(Exception):  # noqa: N818
    """A credential profile exists but cannot be used (undecryptable or invalid). No secret in the message."""


@dataclass(frozen=True)
class _ProfileRow:
    id: uuid.UUID
    username: str
    auth_protocol: str
    auth_key_enc: str
    priv_protocol: str | None
    priv_key_enc: str | None
    is_default: bool


class CredentialBook:
    """Credential profiles loaded once per cycle; passphrases are decrypted lazily and kept only for the cycle."""

    def __init__(self, rows: list[_ProfileRow], fernet: Any | None, fernet_error: str | None = None) -> None:
        self._rows = {r.id: r for r in rows}
        self._default = next((r.id for r in rows if r.is_default), None)
        self._fernet, self._fernet_error = fernet, fernet_error
        self._cache: dict[uuid.UUID, SnmpV3Credentials | CredentialUnavailable] = {}

    def for_profile(self, profile_id: uuid.UUID | None) -> SnmpV3Credentials | None:
        """The credentials for a device (its own profile, else the default). None = no SNMP configured."""
        pid = profile_id if profile_id in self._rows else self._default
        if pid is None:
            return None
        cached = self._cache.get(pid)
        if cached is None:
            cached = self._build(self._rows[pid])
            self._cache[pid] = cached
        if isinstance(cached, CredentialUnavailable):
            raise cached
        return cached

    def _build(self, row: _ProfileRow) -> SnmpV3Credentials | CredentialUnavailable:
        if self._fernet is None:
            return CredentialUnavailable(self._fernet_error or "credential encryption key unavailable")
        try:
            return SnmpV3Credentials(
                username=row.username, auth_protocol=row.auth_protocol,
                auth_key=decrypt_secret(row.auth_key_enc, self._fernet),
                priv_protocol=row.priv_protocol,
                priv_key=decrypt_secret(row.priv_key_enc, self._fernet) if row.priv_key_enc else None)
        except CredentialError:
            return CredentialUnavailable("SNMP credential profile cannot be decrypted (key changed or data altered)")
        except ValueError:
            return CredentialUnavailable("SNMP credential profile is invalid")


@lru_cache(maxsize=4)
def _load_registry(path: Path | None) -> ProfileRegistry:
    return ProfileRegistry.load(path)


# ── data carried through one cycle ──────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class DeviceTarget:
    id: uuid.UUID
    hostname: str
    ip: str
    status: str
    is_maintenance: bool
    credential_profile_id: uuid.UUID | None
    consecutive_failures: int
    last_success_at: datetime | None


@dataclass
class ProbeResult:
    outcome: Outcome
    ping: PingResult | None = None
    sample: PollSample | None = None
    error_kind: str | None = None
    error: str | None = None
    skipped: bool = False  # never probed (target outside the allow-list): leaves state completely alone


@dataclass
class CycleStats:
    total: int = 0
    up: int = 0
    down: int = 0
    inconclusive: int = 0
    skipped_budget: int = 0
    errors: int = 0
    metrics_rows: int = 0
    interface_rows: int = 0
    duration_s: float = 0.0

    def line(self) -> str:
        return (f"poll cycle: devices={self.total} up={self.up} down={self.down} inconclusive={self.inconclusive} "
                f"skipped_budget={self.skipped_budget} errors={self.errors} device_metrics={self.metrics_rows} "
                f"interface_metrics={self.interface_rows} took={self.duration_s:.1f}s")


@dataclass
class _Cycle:
    sessionmaker: async_sessionmaker[AsyncSession]
    mon: MonitoringSettings
    registry: ProfileRegistry
    creds: CredentialBook
    counters: CounterStore
    probe_sem: asyncio.Semaphore
    db_sem: asyncio.Semaphore
    deadline: float  # loop.time() after which no new device is started
    now: datetime
    stats: CycleStats = field(default_factory=CycleStats)


def _short(text: str | None) -> str | None:
    return None if text is None else text[:_ERR_MAX]


# ── step 1: read ────────────────────────────────────────────────────────────────────────────────
_dup_itf_logged: set[uuid.UUID] = set()  # A10: one warning per device per process
_empty_ip_logged: set[uuid.UUID] = set()  # A8: log each device once per process, not once per minute


async def _load_targets(db: AsyncSession) -> list[DeviceTarget]:
    q = (select(Device.id, Device.hostname, Device.ip_address, Device.status, Device.is_maintenance,
                DevicePollState.credential_profile_id, DevicePollState.consecutive_failures,
                DevicePollState.last_success_at)
         .outerjoin(DevicePollState, DevicePollState.device_id == Device.id)
         .where(DevicePollState.poll_enabled.is_not(False))  # no state row yet (NULL) = enabled
         # never-polled first, then least recently polled: nobody starves when the budget runs out
         .order_by(DevicePollState.last_poll_at.asc().nullsfirst(), Device.id))
    targets: list[DeviceTarget] = []
    for r in (await db.execute(q)).all():
        ip = (r.ip_address or "").strip()
        if not ip:  # A8: nothing to probe; counting it as "down" would be a false outage
            if r.id not in _empty_ip_logged:
                _empty_ip_logged.add(r.id)
                log.info("device %s (%s) has no IP address: not polled", r.hostname, r.id)
            continue
        targets.append(DeviceTarget(id=r.id, hostname=r.hostname, ip=ip, status=r.status,
                                    is_maintenance=bool(r.is_maintenance),
                                    credential_profile_id=r.credential_profile_id,
                                    consecutive_failures=r.consecutive_failures or 0,
                                    last_success_at=r.last_success_at))
    return targets


async def _load_credentials(db: AsyncSession) -> CredentialBook:
    rows = [_ProfileRow(id=r.id, username=r.username, auth_protocol=r.auth_protocol, auth_key_enc=r.auth_key_enc,
                        priv_protocol=r.priv_protocol, priv_key_enc=r.priv_key_enc, is_default=bool(r.is_default))
            for r in (await db.execute(
                select(SnmpCredentialProfile.id, SnmpCredentialProfile.username,
                       SnmpCredentialProfile.auth_protocol, SnmpCredentialProfile.auth_key_enc,
                       SnmpCredentialProfile.priv_protocol, SnmpCredentialProfile.priv_key_enc,
                       SnmpCredentialProfile.is_default))).all()]
    if not rows:
        log.info("no SNMP credential profiles configured: running ICMP-only")  # A14
        return CredentialBook([], None)
    try:
        return CredentialBook(rows, build_fernet())
    except ConfigError as exc:
        log.error("SNMP polling disabled for this cycle (ICMP only): %s", exc)
        return CredentialBook(rows, None, "credential encryption key is not configured")


# ── step 2: probe ───────────────────────────────────────────────────────────────────────────────
async def probe_device(target: DeviceTarget, cycle: _Cycle) -> ProbeResult:
    """ICMP + SNMP for one device. No database access. Never raises for device problems."""
    try:
        check_snmp_target(target.ip, cycle.mon.snmp_allowed_cidrs)  # SEC-35 applies to ICMP too
    except TargetNotAllowed as exc:
        return ProbeResult(Outcome.INCONCLUSIVE, error_kind=SnmpErrorKind.NOT_ALLOWED.value,
                           error=_short(str(exc)), skipped=True)

    creds: SnmpV3Credentials | None = None
    cred_error: str | None = None
    try:
        creds = cycle.creds.for_profile(target.credential_profile_id)
    except CredentialUnavailable as exc:
        cred_error = str(exc)

    if creds is not None:
        ping, sample = await asyncio.gather(icmp_ping(target.ip), snmp_poll(target.ip, creds, cycle.registry,
                                                                           cycle.mon))
    else:
        ping, sample = await icmp_ping(target.ip), None

    outcome = classify_probe(ping, sample)
    kind: str | None = None
    error: str | None = None
    if sample is not None and not sample.ok:  # also when ICMP answered: SNMP blindness must stay visible
        kind, error = (sample.error_kind.value if sample.error_kind else "snmp"), sample.error
    elif cred_error is not None:
        kind, error = "credential", cred_error
    elif outcome is Outcome.DOWN:
        kind, error = "icmp", "no ICMP reply"
    elif outcome is Outcome.INCONCLUSIVE:
        kind, error = "icmp_error", "ICMP probe could not run (check NET_RAW / raw-socket permission)"
    return ProbeResult(outcome, ping=ping, sample=sample, error_kind=kind, error=_short(error))


# ── step 3: write ───────────────────────────────────────────────────────────────────────────────
_adapter_warned: set[str] = set()


def _adapter_failed(name: str, device_id: uuid.UUID) -> None:
    """Full traceback once per adapter, one line afterwards (a wrong signature would otherwise flood the log)."""
    if name not in _adapter_warned:
        _adapter_warned.add(name)
        log.exception("Phase-2 adapter %s failed (device %s). Check the assumed signature in poller.py.", name,
                      device_id)
    else:
        log.error("Phase-2 adapter %s failed again (device %s)", name, device_id)


# ---- PHASE-2 ADAPTER: the ONLY place that knows Account 1's function signatures -----------------
# TODO(phase-2-reconcile): B2 UNVERIFIED. All three signatures below are assumptions; also confirm that
# raise_alarm de-duplicates per (device_id, external_id) for open alarms.
async def _apply_status(db: AsyncSession, device: Device, status: str) -> None:
    # ASSUMED: set_observed_status(db, device, status) -> Any
    await set_observed_status(db, device, status)


async def _raise_deadman(db: AsyncSession, device: Device, message: str) -> None:
    # ASSUMED: raise_alarm(db, *, device, external_id, severity, message) -> Any  (de-duplicates per device+external_id)
    await alarm_service.raise_alarm(db, device=device, external_id=DEADMAN_ALARM_ID, severity=DEADMAN_SEVERITY,
                                    message=message)


async def _resolve_deadman(db: AsyncSession, alarm: Alarm) -> None:
    # ASSUMED: resolve_alarm(db, alarm, *, resolved_by, note) -> Any. Optional: skipped if the function is absent.
    resolve = getattr(alarm_service, "resolve_alarm", None)
    if resolve is None:
        if "resolve_alarm_missing" not in _adapter_warned:
            _adapter_warned.add("resolve_alarm_missing")
            log.warning("app.services.alarms has no resolve_alarm: dead-man alarms will not auto-resolve")
        return
    await resolve(db, alarm, resolved_by="nr-ims-poller", note="Auto-resolved: device is responding again")
# ---- end of PHASE-2 ADAPTER ---------------------------------------------------------------------


async def _guarded(db: AsyncSession, name: str, device_id: uuid.UUID, coro: Any) -> bool:
    """Run an adapter call inside a SAVEPOINT so a failure cannot poison the transaction holding the metrics."""
    try:
        async with db.begin_nested():
            await coro
        return True
    except Exception:  # noqa: BLE001
        _adapter_failed(name, device_id)
        return False


async def _upsert_poll_state(db: AsyncSession, target: DeviceTarget, probe: ProbeResult, failures: int,
                             now: datetime) -> None:
    values: dict[str, Any] = {"device_id": target.id, "last_poll_at": now, "updated_at": now,
                              "last_error_kind": probe.error_kind, "last_error": probe.error}
    if probe.outcome is Outcome.UP:
        values.update(last_success_at=now, consecutive_failures=0)
        if probe.sample is not None and probe.sample.ok and probe.sample.vendor_profile:
            values["vendor_profile"] = probe.sample.vendor_profile
    elif probe.outcome is Outcome.DOWN:
        values["consecutive_failures"] = failures
    else:  # inconclusive: do not count it for or against the device
        values["consecutive_failures"] = target.consecutive_failures
    # A3: explicit poll_enabled on first INSERT (independent of the column default). It is deliberately NOT part of
    # the ON CONFLICT update below, so an operator's poll_enabled=false is never overwritten.
    stmt = pg_insert(DevicePollState).values(**values, poll_enabled=True)
    stmt = stmt.on_conflict_do_update(index_elements=[DevicePollState.device_id],
                                      set_={k: stmt.excluded[k] for k in values if k != "device_id"})
    await db.execute(stmt)


async def _write_metrics(db: AsyncSession, target: DeviceTarget, sample: PollSample,
                         cycle: _Cycle) -> tuple[int, int, dict[str, CounterSnapshot]]:
    """Insert device + interface rows. Returns (device rows, interface rows, snapshots to remember).

    A7: runs inside its own SAVEPOINT (see _record). Nothing here touches shared state, so a rollback leaves
    the stats and the counter store exactly as they were.
    """
    ts = datetime.fromtimestamp(sample.polled_at, UTC)
    n_dev = 0
    if any(v is not None for v in (sample.cpu_pct, sample.mem_pct, sample.temp_c, sample.uptime_s)):
        await db.execute(pg_insert(DeviceMetric).values(
            device_id=target.id, ts=ts, cpu_pct=sample.cpu_pct, mem_pct=sample.mem_pct, temp_c=sample.temp_c,
            uptime_s=int(sample.uptime_s) if sample.uptime_s is not None else None).on_conflict_do_nothing())
        n_dev = 1

    previous = await cycle.counters.load(target.id)
    current: dict[str, CounterSnapshot] = {}
    by_name: dict[str, uuid.UUID] = {}
    # A10: ORDER BY makes "first one wins" the same interface every cycle (charts must not swing between twins)
    for iid, name in (await db.execute(
            select(Interface.id, Interface.name).where(Interface.device_id == target.id).order_by(Interface.id))):
        if name in by_name:
            if target.id not in _dup_itf_logged:
                _dup_itf_logged.add(target.id)
                log.warning("duplicate interface name %r on device %s: only the first one receives metrics",
                            name, target.id)
            continue
        by_name[name] = iid

    rows: list[dict[str, Any]] = []
    for itf in sample.interfaces:
        snap = build_snapshot(sample, itf)
        if snap is not None:
            current[itf.name] = snap
        interface_id = by_name.get(itf.name)
        if interface_id is None:
            continue
        rates = compute_interface_rates(previous.get(itf.name), snap, itf.speed_mbps) if snap is not None else None
        rows.append({
            "interface_id": interface_id, "ts": ts, "oper_status": itf.oper_status,
            "in_bps": rates.in_bps if rates else None, "out_bps": rates.out_bps if rates else None,
            "in_util_pct": rates.in_util_pct if rates else None,
            "out_util_pct": rates.out_util_pct if rates else None,
            "in_errors": _i32(rates.in_errors) if rates else None,
            "out_errors": _i32(rates.out_errors) if rates else None,
            "in_discards": _i32(rates.in_discards) if rates else None,
            "out_discards": _i32(rates.out_discards) if rates else None})
    if rows:
        await db.execute(pg_insert(InterfaceMetric).values(rows).on_conflict_do_nothing())
    return n_dev, len(rows), current


async def _open_deadman_alarm(db: AsyncSession, device_id: uuid.UUID) -> Alarm | None:
    # TODO(phase-2-reconcile): A4 UNVERIFIED. "resolved" is the string convention of the Phase-1 Alarm model
    # (status is String(20)). If Phase 2 introduces an enum / different value, or exposes an is-open helper in
    # app.services.alarms, switch to that here. A wrong value would cause duplicate alarms or a missed re-raise.
    q = (select(Alarm).where(Alarm.device_id == device_id, Alarm.external_id == DEADMAN_ALARM_ID,
                             Alarm.status != "resolved").limit(1))
    return (await db.execute(q)).scalars().first()


async def _record(db: AsyncSession, target: DeviceTarget, probe: ProbeResult, cycle: _Cycle) -> None:
    now = cycle.now
    if probe.skipped:  # outside the allow-list: only remember why
        await _upsert_poll_state(db, target, probe, target.consecutive_failures, now)
        return

    failures = target.consecutive_failures + 1 if probe.outcome is Outcome.DOWN else (
        0 if probe.outcome is Outcome.UP else target.consecutive_failures)
    await _upsert_poll_state(db, target, probe, failures, now)  # critical: drives down-detection and dead-man
    if probe.sample is not None and probe.sample.ok:
        try:  # A7: a metrics failure must not roll back the poll state written above
            async with db.begin_nested():
                n_dev, n_itf, snaps = await _write_metrics(db, target, probe.sample, cycle)
            cycle.stats.metrics_rows += n_dev
            cycle.stats.interface_rows += n_itf
            if snaps:  # only after the rows are safely in: a failed write keeps the older snapshot
                await cycle.counters.save(target.id, snaps)
        except Exception:  # noqa: BLE001
            log.exception("metrics write failed for %s; poll state preserved", target.id)

    status = desired_status(probe.outcome, failures)
    needs_status = status is not None and (target.is_maintenance or target.status != status)
    needs_deadman = probe.outcome is Outcome.DOWN and not target.is_maintenance and deadman_due(
        target.last_success_at, failures, now)
    # a dead-man alarm can only exist after >= 1 failed cycle, so healthy devices skip this query entirely
    recovering = probe.outcome is Outcome.UP and target.consecutive_failures > 0
    alarm = await _open_deadman_alarm(db, target.id) if (needs_deadman or recovering) else None
    needs_raise = needs_deadman and alarm is None
    needs_resolve = recovering and alarm is not None
    if not (needs_status or needs_raise or needs_resolve):
        return

    device = await db.get(Device, target.id)
    if device is None:  # deleted while we were polling
        return
    if needs_status and status is not None:
        await _guarded(db, "set_observed_status", target.id, _apply_status(db, device, status))
    if needs_raise:
        silent = (f"{int((now - target.last_success_at).total_seconds() // 60)} min"
                  if target.last_success_at else f"{failures} polls")
        await _guarded(db, "raise_alarm", target.id, _raise_deadman(
            db, device, f"No response from {target.hostname} ({target.ip}) for {silent}: monitoring lost contact"))
    if needs_resolve and alarm is not None:
        await _guarded(db, "resolve_alarm", target.id, _resolve_deadman(db, alarm))


async def _poll_one(target: DeviceTarget, cycle: _Cycle) -> None:
    stats = cycle.stats
    # Only mutated without an `await` between read and write, so no lock is needed in a single event loop.
    async with cycle.probe_sem:
        if asyncio.get_running_loop().time() > cycle.deadline:
            stats.skipped_budget += 1
            return
        try:
            probe = await probe_device(target, cycle)
        except Exception:  # noqa: BLE001  (a bug in one probe must not stop the other 999 devices)
            log.exception("probe crashed for %s (%s)", target.hostname, target.ip)
            probe = ProbeResult(Outcome.INCONCLUSIVE, error_kind="internal", error="internal poller error")
    # A6: probe_sem is released here. A slow commit or a queue for a DB slot no longer holds a probe slot.
    try:
        async with cycle.db_sem, cycle.sessionmaker() as db:
            await _record(db, target, probe, cycle)
            await db.commit()
    except Exception:  # noqa: BLE001
        log.exception("could not record poll result for %s (%s)", target.hostname, target.ip)
        stats.errors += 1
        return
    if probe.outcome is Outcome.UP:
        stats.up += 1
    elif probe.outcome is Outcome.DOWN:
        stats.down += 1
    else:
        stats.inconclusive += 1


async def poll_all_devices(sessionmaker: async_sessionmaker[AsyncSession], *, redis: Any | None = None,
                           concurrency: int = CONCURRENCY, budget_s: float = CYCLE_BUDGET_S,
                           mon: MonitoringSettings | None = None, counters: CounterStore | None = None,
                           now: datetime | None = None) -> CycleStats:
    """Run one polling cycle for every enabled device. Safe to call from tests with a throwaway sessionmaker."""
    started = time.monotonic()
    mon = mon or get_monitoring_settings()
    registry = _load_registry(mon.snmp_profiles_file)
    async with sessionmaker() as db:  # short read-only session; closed before any network I/O
        targets = await _load_targets(db)
        creds = await _load_credentials(db)
    if counters is None:
        counters = RedisCounterStore(redis) if redis is not None else _PROCESS_COUNTERS

    loop = asyncio.get_running_loop()
    cycle = _Cycle(sessionmaker=sessionmaker, mon=mon, registry=registry, creds=creds, counters=counters,
                   probe_sem=asyncio.Semaphore(concurrency), db_sem=asyncio.Semaphore(DB_CONCURRENCY),
                   deadline=loop.time() + budget_s, now=now or datetime.now(UTC))
    cycle.stats.total = len(targets)
    results = await asyncio.gather(*[_poll_one(t, cycle) for t in targets], return_exceptions=True)
    for res in results:
        if isinstance(res, BaseException):  # _poll_one handles its own errors; this is the last safety net
            log.error("unexpected poll task failure: %r", res)
            cycle.stats.errors += 1
    cycle.stats.duration_s = time.monotonic() - started
    log.info(cycle.stats.line())
    return cycle.stats