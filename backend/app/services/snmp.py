"""Async SNMP walker on pysnmp v7 asyncio HL API.

Uses numeric OIDs — pysnmp 7.x bundles only SNMPv2-MIB family. IF-MIB
requires pysmi compilation which is not shipped; numeric OIDs bypass
that dependency entirely and work on any SNMP agent (v1/v2c/v3).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    bulk_walk_cmd,
    get_cmd,
)

log = logging.getLogger(__name__)

# sysDescr etc — SNMPv2-MIB numeric equivalents
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"
OID_SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
OID_SYS_LOCATION = "1.3.6.1.2.1.1.6.0"
OID_SYS_UPTIME = "1.3.6.1.2.1.1.3.0"

# ifTable column numeric OIDs (IF-MIB bypassed — not bundled in pysnmp 7.x)
IF_COLUMNS: dict[str, str] = {
    "ifDescr":       "1.3.6.1.2.1.2.2.1.2",
    "ifType":        "1.3.6.1.2.1.2.2.1.3",
    "ifSpeed":       "1.3.6.1.2.1.2.2.1.5",
    "ifPhysAddress": "1.3.6.1.2.1.2.2.1.6",
    "ifOperStatus":  "1.3.6.1.2.1.2.2.1.8",
    "ifInOctets":    "1.3.6.1.2.1.2.2.1.10",
    "ifOutOctets":   "1.3.6.1.2.1.2.2.1.16",
}

# MIB integer-like classes — coerced to Python int for downstream use
_INT_CLASSES = (
    "Integer", "Integer32", "Counter32", "Counter64", "Gauge32",
    "Unsigned32", "TimeTicks",
)


@dataclass
class SnmpResult:
    reachable: bool
    sys_descr: str | None = None
    sys_name: str | None = None
    sys_object_id: str | None = None
    sys_location: str | None = None
    sys_uptime_ticks: int | None = None
    interfaces: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def _coerce(value: Any) -> Any:
    cls = value.__class__.__name__
    if cls in _INT_CLASSES:
        try:
            return int(value)
        except (TypeError, ValueError):
            return str(value)
    if cls == "OctetString":
        try:
            raw = bytes(value)
        except Exception:  # noqa: BLE001
            return str(value)
        if not raw:
            return ""
        # Printable ASCII → text (sysDescr, ifDescr, sysName, ...)
        if all(32 <= b < 127 for b in raw):
            return raw.decode("ascii", errors="replace")
        # Binary → MAC when 6 bytes, else colon-hex
        return ":".join(f"{b:02x}" for b in raw)
    if hasattr(value, "prettyPrint"):
        return value.prettyPrint()
    return value


async def _get_one(engine, auth, transport, ctx, oid: str) -> Any:
    ei, es, eidx, vbs = await get_cmd(
        engine, auth, transport, ctx, ObjectType(ObjectIdentity(oid))
    )
    if ei:
        raise RuntimeError(f"{oid}: {ei}")
    if es:
        raise RuntimeError(f"{oid}: {es.prettyPrint()} at {eidx}")
    return vbs[0][1]


async def _walk_column(engine, auth, transport, ctx, oid: str):
    """Walk one ifTable column. Returns [(ifIndex, value)]."""
    rows: list[tuple[int, Any]] = []
    try:
        async for ei, es, eidx, vbs in bulk_walk_cmd(
            engine, auth, transport, ctx, 0, 25,
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,
        ):
            if ei:
                log.warning("walk %s ei=%s", oid, ei)
                break
            if es:
                log.warning("walk %s es=%s at %s", oid, es, eidx)
                break
            for name, val in vbs:
                try:
                    idx = int(name.getOid()[-1])
                except (ValueError, IndexError):
                    continue
                rows.append((idx, val))
    except Exception as exc:  # noqa: BLE001
        log.warning("walk %s exception: %s", oid, exc)
    return rows


async def snmp_probe(
    host: str,
    community: str = "public",
    port: int = 161,
    timeout: float = 2.0,
    retries: int = 1,
) -> SnmpResult:
    engine = SnmpEngine()
    auth = CommunityData(community, mpModel=1)  # v2c
    ctx = ContextData()

    try:
        transport = await UdpTransportTarget.create(
            (host, port), timeout=timeout, retries=retries
        )
    except Exception as exc:  # noqa: BLE001
        return SnmpResult(reachable=False, error=f"transport: {exc}")

    try:
        sys_descr = _coerce(await _get_one(engine, auth, transport, ctx, OID_SYS_DESCR))
    except Exception as exc:  # noqa: BLE001
        return SnmpResult(reachable=False, error=str(exc))

    result = SnmpResult(reachable=True, sys_descr=sys_descr)

    async def _safe(oid: str, attr: str) -> None:
        try:
            setattr(result, attr, _coerce(await _get_one(engine, auth, transport, ctx, oid)))
        except Exception as exc:  # noqa: BLE001
            log.warning("get %s -> %s failed on %s: %s", oid, attr, host, exc)

    await asyncio.gather(
        _safe(OID_SYS_NAME, "sys_name"),
        _safe(OID_SYS_OBJECT_ID, "sys_object_id"),
        _safe(OID_SYS_LOCATION, "sys_location"),
        _safe(OID_SYS_UPTIME, "sys_uptime_ticks"),
    )
    # Defensive: if _coerce returns str somehow, still normalize to int
    if isinstance(result.sys_uptime_ticks, str):
        try:
            result.sys_uptime_ticks = int(float(result.sys_uptime_ticks))
        except ValueError:
            result.sys_uptime_ticks = None

    columns = list(IF_COLUMNS.keys())
    oid_strs = list(IF_COLUMNS.values())
    walks = await asyncio.gather(*[
        _walk_column(engine, auth, transport, ctx, oid) for oid in oid_strs
    ])
    merged: dict[int, dict[str, Any]] = {}
    for col, rows in zip(columns, walks):
        for idx, val in rows:
            merged.setdefault(idx, {"if_index": idx})[col] = _coerce(val)
    result.interfaces = [merged[k] for k in sorted(merged)]
    return result