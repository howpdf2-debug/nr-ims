"""Read-only SNMPv3 client and one-device poll (Phase 3a-1).

Security properties (each one is covered by a test):

* SEC-32  SNMPv3 only, with authentication AND encryption (authPriv; authNoPriv is accepted, v1/v2c is not
          even constructible here). Weak algorithms (MD5, DES) are not offered.
* SEC-34  READ-ONLY by construction: this module imports ``get_cmd`` and ``bulk_walk_cmd`` and nothing that
          can send a SET. ``ReadOnlySnmpClient`` has no write method, and a test fails if one is ever added.
* SEC-31  A hung or slow device can never stall the worker: every request has a timeout and the whole poll of
          one device runs under ``asyncio.timeout(poll_deadline_s)``.
* SEC-35  Only IP literals inside the allow-list are contacted (``check_snmp_target``).
* SEC-33  Credentials never appear in ``repr``/logs/error text; error messages contain only the error class.

``poll_device`` never raises for device problems: it returns a ``PollSample`` with ``ok=False`` and a
machine-readable ``error_kind`` (timeout / auth / unreachable / protocol / deadline / target_not_allowed), so the
caller (Phase 3a-2 worker) can count failures and drive the dead-man switch without parsing text.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pysnmp.hlapi.v3arch.asyncio import (
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    bulk_walk_cmd,
    get_cmd,
    usmAesCfb128Protocol,
    usmAesCfb192Protocol,
    usmAesCfb256Protocol,
    usmHMAC192SHA256AuthProtocol,
    usmHMAC256SHA384AuthProtocol,
    usmHMAC384SHA512AuthProtocol,
    usmHMACSHAAuthProtocol,
)

from app.monitoring.profiles import (
    ProfileRegistry,
    read_cpu,
    read_memory_pct,
    read_temperature,
)
from app.monitoring.security import MonitoringSettings, TargetNotAllowed, check_snmp_target, get_monitoring_settings

log = logging.getLogger(__name__)

OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
OID_SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"

AUTH_PROTOCOLS = {
    "SHA": usmHMACSHAAuthProtocol,
    "SHA256": usmHMAC192SHA256AuthProtocol,
    "SHA384": usmHMAC256SHA384AuthProtocol,
    "SHA512": usmHMAC384SHA512AuthProtocol,
}
PRIV_PROTOCOLS = {
    "AES128": usmAesCfb128Protocol,
    "AES192": usmAesCfb192Protocol,
    "AES256": usmAesCfb256Protocol,
}
MIN_PASSPHRASE = 8  # RFC 3414 minimum

_INT_TYPES = frozenset({"Integer", "Integer32", "Counter32", "Counter64", "Gauge32", "Unsigned32", "TimeTicks",
                        "Unsigned"})
_MISSING_TYPES = frozenset({"NoSuchObject", "NoSuchInstance", "EndOfMibView"})
_AUTH_ERRORS = frozenset({
    "UnknownUserName", "WrongDigest", "DecryptionError", "UnsupportedSecurityLevel", "UnsupportedAuthProtocol",
    "UnsupportedPrivProtocol", "AuthenticationError", "AuthenticationFailure", "NoAuthentication", "NoEncryption",
    "UnknownSecurityName",
})
_GET_CHUNK = 8  # varbinds per GET request (keeps responses well below any agent's size limit)


class SnmpErrorKind(StrEnum):
    TIMEOUT = "timeout"
    AUTH = "auth"
    UNREACHABLE = "unreachable"
    PROTOCOL = "protocol"
    DEADLINE = "deadline"
    NOT_ALLOWED = "target_not_allowed"


class SnmpError(Exception):
    def __init__(self, kind: SnmpErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass(frozen=True)
class SnmpV3Credentials:
    """Never printed: the passphrases are excluded from ``repr``."""

    username: str
    auth_protocol: str
    auth_key: str = field(repr=False)
    priv_protocol: str | None = None
    priv_key: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not 1 <= len(self.username) <= 64:
            raise ValueError("SNMPv3 username must be 1-64 characters")
        if self.auth_protocol not in AUTH_PROTOCOLS:
            raise ValueError(f"auth protocol must be one of {sorted(AUTH_PROTOCOLS)}")
        if len(self.auth_key) < MIN_PASSPHRASE:
            raise ValueError(f"auth passphrase must be at least {MIN_PASSPHRASE} characters")
        if (self.priv_protocol is None) != (self.priv_key is None):
            raise ValueError("priv protocol and priv passphrase must be given together")
        if self.priv_protocol is not None:
            if self.priv_protocol not in PRIV_PROTOCOLS:
                raise ValueError(f"priv protocol must be one of {sorted(PRIV_PROTOCOLS)}")
            if len(self.priv_key or "") < MIN_PASSPHRASE:
                raise ValueError(f"priv passphrase must be at least {MIN_PASSPHRASE} characters")

    @property
    def security_level(self) -> str:
        return "authPriv" if self.priv_protocol else "authNoPriv"

    def usm(self) -> UsmUserData:
        if self.priv_protocol and self.priv_key:
            return UsmUserData(self.username, self.auth_key, self.priv_key,
                               authProtocol=AUTH_PROTOCOLS[self.auth_protocol],
                               privProtocol=PRIV_PROTOCOLS[self.priv_protocol])
        return UsmUserData(self.username, self.auth_key, authProtocol=AUTH_PROTOCOLS[self.auth_protocol])


def classify_error(indication: Any) -> tuple[SnmpErrorKind, str]:
    """Map a pysnmp error indication to (kind, safe message). Only the class name is exposed."""
    name = type(indication).__name__
    if name == "RequestTimedOut":
        return SnmpErrorKind.TIMEOUT, "no SNMP response before timeout"
    if name in _AUTH_ERRORS:
        return SnmpErrorKind.AUTH, f"SNMPv3 authentication or encryption failed ({name})"
    return SnmpErrorKind.PROTOCOL, f"SNMP error ({name})"


def to_python(value: Any) -> Any:
    """pysnmp value -> int | str | None (None = the agent does not have this object)."""
    names = {c.__name__ for c in type(value).__mro__}
    if names & _MISSING_TYPES:
        return None
    if names & _INT_TYPES:
        return int(value)
    if "OctetString" in names:
        raw = bytes(value)
        if all(32 <= b < 127 for b in raw):
            return raw.decode("ascii")
        return ":".join(f"{b:02x}" for b in raw)
    if names & {"ObjectIdentifier", "ObjectIdentity", "ObjectName"}:
        # Always the NUMERIC form. prettyPrint() would give "SNMPv2-SMI::enterprises.9.1.1234" and break
        # sysObjectID prefix matching (found by the simulator test: on the wire this arrives as ObjectIdentity).
        as_tuple = getattr(value, "asTuple", None)
        return ".".join(str(x) for x in as_tuple()) if callable(as_tuple) else str(value)
    return str(value)


class ReadOnlySnmpClient:
    """GET and GETBULK only. There is deliberately NO method that writes to a device."""

    def __init__(self, host: str, creds: SnmpV3Credentials, *, port: int = 161, timeout_s: float = 2.0,
                 retries: int = 1, context_name: str = "", max_concurrency: int = 4) -> None:
        self._host, self._port = host, port
        self._timeout_s, self._retries = timeout_s, retries
        self._usm = creds.usm()
        self._ctx = ContextData(contextName=context_name)
        self._sem = asyncio.Semaphore(max_concurrency)
        self._engine: SnmpEngine | None = None
        self._target: UdpTransportTarget | None = None

    async def __aenter__(self) -> ReadOnlySnmpClient:
        self._engine = SnmpEngine()
        try:
            self._target = await UdpTransportTarget.create((self._host, self._port), timeout=self._timeout_s,
                                                           retries=self._retries)
        except Exception:
            self._engine.close_dispatcher()
            raise SnmpError(SnmpErrorKind.UNREACHABLE, f"cannot open an SNMP transport to {self._host}") from None
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._engine is not None:
            try:
                self._engine.close_dispatcher()
            except Exception:  # closing must never mask the real result
                log.debug("closing SNMP dispatcher failed", exc_info=True)

    def _ready(self) -> tuple[SnmpEngine, UdpTransportTarget]:
        if self._engine is None or self._target is None:
            raise RuntimeError("use ReadOnlySnmpClient as an async context manager")
        return self._engine, self._target

    async def _get(self, oids: list[str]) -> list[Any]:
        engine, target = self._ready()
        async with self._sem:
            try:
                ei, es, _idx, vbs = await get_cmd(engine, self._usm, target, self._ctx,
                                                  *[ObjectType(ObjectIdentity(o)) for o in oids])
            except OSError:
                raise SnmpError(SnmpErrorKind.UNREACHABLE, f"network error talking to {self._host}") from None
        if ei:
            kind, msg = classify_error(ei)
            raise SnmpError(kind, msg)
        if es:
            raise SnmpError(SnmpErrorKind.PROTOCOL, f"SNMP error status {es.prettyPrint()}")
        return [to_python(v) for _, v in vbs]

    async def get_optional(self, oid: str) -> Any:
        return (await self._get([oid]))[0]

    async def get_many(self, oids: list[str]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for i in range(0, len(oids), _GET_CHUNK):
            chunk = oids[i:i + _GET_CHUNK]
            out.update(zip(chunk, await self._get(chunk), strict=True))
        return out

    async def walk(self, oid: str, max_rows: int = 512) -> list[tuple[tuple[int, ...], Any]]:
        """Rows under ``oid`` as ``(index-suffix, value)``; stops after ``max_rows`` (bounded work per device)."""
        engine, target = self._ready()
        base_len = len(oid.split("."))
        rows: list[tuple[tuple[int, ...], Any]] = []
        async with self._sem:
            try:
                async for ei, es, _idx, vbs in bulk_walk_cmd(engine, self._usm, target, self._ctx, 0, 25,
                                                             ObjectType(ObjectIdentity(oid)),
                                                             lexicographicMode=False):
                    if ei:
                        kind, msg = classify_error(ei)
                        raise SnmpError(kind, msg)
                    if es:
                        raise SnmpError(SnmpErrorKind.PROTOCOL, f"SNMP error status {es.prettyPrint()}")
                    for name, val in vbs:
                        value = to_python(val)
                        if value is None:
                            continue
                        rows.append((tuple(int(p) for p in str(name).split("."))[base_len:], value))
                        if len(rows) >= max_rows:
                            return rows
            except OSError:
                raise SnmpError(SnmpErrorKind.UNREACHABLE, f"network error talking to {self._host}") from None
        return rows


# ── interfaces ──────────────────────────────────────────────────────────────────────────────────
_IF = "1.3.6.1.2.1.2.2.1"
_IFX = "1.3.6.1.2.1.31.1.1.1"
_IF_COLUMNS = {
    "name": f"{_IFX}.1", "descr": f"{_IF}.2", "admin": f"{_IF}.7", "oper": f"{_IF}.8", "speed": f"{_IF}.5",
    "high_speed": f"{_IFX}.15", "in_hc": f"{_IFX}.6", "out_hc": f"{_IFX}.10", "in_32": f"{_IF}.10",
    "out_32": f"{_IF}.16", "in_err": f"{_IF}.14", "out_err": f"{_IF}.20", "in_disc": f"{_IF}.13",
    "out_disc": f"{_IF}.19",
}


@dataclass
class InterfaceSample:
    if_index: int
    name: str
    admin_status: int | None  # IF-MIB: 1 up, 2 down, 3 testing
    oper_status: int | None  # IF-MIB: 1 up, 2 down, 3 testing, 5 dormant, 7 lowerLayerDown ...
    speed_mbps: int | None
    in_octets: int | None
    out_octets: int | None
    in_errors: int | None
    out_errors: int | None
    in_discards: int | None
    out_discards: int | None
    counter_bits: int | None  # 64 = ifHC*Octets, 32 = ifIn/OutOctets, None = no octet counters


async def collect_interfaces(client: ReadOnlySnmpClient, max_interfaces: int = 256) -> list[InterfaceSample]:
    keys = list(_IF_COLUMNS)
    results = await asyncio.gather(*[client.walk(_IF_COLUMNS[k], max_rows=max_interfaces) for k in keys],
                                   return_exceptions=True)
    failures = [r for r in results if isinstance(r, BaseException)]
    if len(failures) == len(results):
        first = failures[0]
        raise first if isinstance(first, SnmpError) else SnmpError(SnmpErrorKind.PROTOCOL, "interface walk failed")
    cols: dict[str, dict[int, Any]] = {}
    for key, res in zip(keys, results, strict=True):
        cols[key] = {} if isinstance(res, BaseException) else {s[0]: v for s, v in res if s}

    indexes = sorted(set(cols["oper"]) | set(cols["name"]) | set(cols["descr"]))[:max_interfaces]
    out: list[InterfaceSample] = []
    for idx in indexes:
        hs, sp = cols["high_speed"].get(idx), cols["speed"].get(idx)
        speed = int(hs) if isinstance(hs, int) and hs > 0 else (
            sp // 1_000_000 if isinstance(sp, int) and sp > 0 else None)
        has_hc = idx in cols["in_hc"] and idx in cols["out_hc"]
        has_32 = idx in cols["in_32"] and idx in cols["out_32"]
        bits = 64 if has_hc else 32 if has_32 else None
        in_key, out_key = ("in_hc", "out_hc") if has_hc else ("in_32", "out_32")
        out.append(InterfaceSample(
            if_index=idx, name=str(cols["name"].get(idx) or cols["descr"].get(idx) or f"if{idx}")[:50],
            admin_status=cols["admin"].get(idx), oper_status=cols["oper"].get(idx), speed_mbps=speed,
            in_octets=cols[in_key].get(idx) if bits else None, out_octets=cols[out_key].get(idx) if bits else None,
            in_errors=cols["in_err"].get(idx), out_errors=cols["out_err"].get(idx),
            in_discards=cols["in_disc"].get(idx), out_discards=cols["out_disc"].get(idx), counter_bits=bits))
    return out


# ── one device ──────────────────────────────────────────────────────────────────────────────────
@dataclass
class PollSample:
    ok: bool
    host: str
    polled_at: float  # epoch seconds
    error_kind: SnmpErrorKind | None = None
    error: str | None = None
    sys_descr: str | None = None
    sys_name: str | None = None
    sys_object_id: str | None = None
    uptime_s: float | None = None
    vendor_profile: str | None = None
    cpu_pct: float | None = None
    mem_pct: float | None = None
    temp_c: float | None = None
    interfaces: list[InterfaceSample] = field(default_factory=list)


async def _optional_metric(coro: Any) -> float | None:
    """A metric the device cannot answer must not fail the poll; "device gone" errors still propagate."""
    try:
        return await coro
    except SnmpError as exc:
        if exc.kind is not SnmpErrorKind.PROTOCOL:
            raise
        log.debug("optional metric unavailable: %s", exc.message)
        return None


async def _collect(client: ReadOnlySnmpClient, host: str, registry: ProfileRegistry, started: float) -> PollSample:
    system = await client.get_many([OID_SYS_DESCR, OID_SYS_OBJECT_ID, OID_SYS_UPTIME, OID_SYS_NAME])
    if all(v is None for v in system.values()):
        raise SnmpError(SnmpErrorKind.PROTOCOL, "device answered but exposes no system MIB values")
    sys_descr, sys_oid = system[OID_SYS_DESCR], system[OID_SYS_OBJECT_ID]
    ticks = system[OID_SYS_UPTIME]
    profile = registry.select(sys_oid, sys_descr)
    return PollSample(
        ok=True, host=host, polled_at=started, sys_descr=sys_descr, sys_name=system[OID_SYS_NAME],
        sys_object_id=sys_oid, uptime_s=ticks / 100 if isinstance(ticks, int) else None,
        vendor_profile=profile.name,
        cpu_pct=await _optional_metric(read_cpu(client, profile)),
        mem_pct=await _optional_metric(read_memory_pct(client, profile)),
        temp_c=await _optional_metric(read_temperature(client, profile)),
        interfaces=await collect_interfaces(client),
    )


async def poll_device(host: str, creds: SnmpV3Credentials, registry: ProfileRegistry, *,
                      mon: MonitoringSettings | None = None) -> PollSample:
    """Poll one device. Never raises for device/network problems; see the module docstring."""
    mon = mon or get_monitoring_settings()
    started = time.time()

    def failed(kind: SnmpErrorKind, message: str) -> PollSample:
        return PollSample(ok=False, host=host, polled_at=started, error_kind=kind, error=message)

    try:
        check_snmp_target(host, mon.snmp_allowed_cidrs)
    except TargetNotAllowed as exc:
        return failed(SnmpErrorKind.NOT_ALLOWED, str(exc))
    try:
        async with asyncio.timeout(mon.poll_deadline_s):
            async with ReadOnlySnmpClient(host, creds, port=mon.snmp_port, timeout_s=mon.snmp_timeout_s,
                                          retries=mon.snmp_retries, context_name=mon.snmp_context_name) as client:
                return await _collect(client, host, registry, started)
    except SnmpError as exc:
        return failed(exc.kind, exc.message)
    except TimeoutError:
        return failed(SnmpErrorKind.DEADLINE, f"poll exceeded the {mon.poll_deadline_s:g}s deadline")
    except Exception:
        log.exception("unexpected error while polling %s", host)
        return failed(SnmpErrorKind.PROTOCOL, "internal error while polling (details in the worker log)")
