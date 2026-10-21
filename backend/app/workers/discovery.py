"""arq task: ICMP sweep, SNMP probe, persist to discovered_devices."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import uuid
from typing import Any

from sqlalchemy import delete

from app.db.session import async_session_maker
from app.models.discovery import DiscoveredDevice
from app.services.ping import sweep
from app.services.snmp import SnmpResult, snmp_probe

log = logging.getLogger(__name__)

_HOSTNAME_MAX = 255
_LOCATION_MAX = 100


def _expand_targets(targets: str, limit: int = 1024) -> list[str]:
    """Expand comma-separated CIDR/IP/hostname. Dedupes, validates, capped."""
    out: list[str] = []
    seen: set[str] = set()
    for tok in targets.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            if "/" in tok:
                net = ipaddress.ip_network(tok, strict=False)
                for ip in net.hosts():
                    s = str(ip)
                    if s in seen:
                        continue
                    seen.add(s)
                    out.append(s)
                    if len(out) >= limit:
                        return out
            else:
                try:
                    ipaddress.ip_address(tok)
                    if tok not in seen:
                        seen.add(tok)
                        out.append(tok)
                except ValueError:
                    try:
                        resolved = socket.gethostbyname(tok)
                    except (socket.gaierror, OSError) as exc:
                        log.warning("cannot resolve %r: %s, skipping", tok, exc)
                        continue
                    if resolved not in seen:
                        seen.add(resolved)
                        out.append(resolved)
                        log.info("resolved %r -> %s", tok, resolved)
                if len(out) >= limit:
                    return out
        except ValueError:
            log.warning("invalid target %r, skipping", tok)
    return out


def _classify(sys_descr: str | None, interfaces: list[dict[str, Any]]) -> str:
    """Best-effort device type. Interface count wins for L2 gear detection."""
    d = (sys_descr or "").lower()
    n = len(interfaces)
    if n >= 8:
        return "switch"
    if any(k in d for k in ("linux", "windows", "unix", "freebsd")):
        return "server"
    if any(k in d for k in ("fortinet", "fortigate", "palo alto", "firewall")):
        return "firewall"
    if any(k in d for k in ("cisco", "juniper", "arista", "huawei", "nokia")):
        return "router"
    return "unknown"


def _pick_mac(interfaces: list[dict[str, Any]]) -> str | None:
    """First non-loopback 6-byte MAC (xx:xx:xx:xx:xx:xx)."""
    for iface in interfaces:
        descr = (iface.get("ifDescr") or "").lower()
        if descr == "lo":
            continue
        mac = iface.get("ifPhysAddress")
        if isinstance(mac, str) and len(mac) == 17:
            return mac
    return None


async def _probe_snmp(
    hosts: list[str], community: str, snmp_port: int, concurrency: int = 16
) -> list[tuple[str, SnmpResult | None]]:
    sem = asyncio.Semaphore(concurrency)

    async def _one(h: str) -> tuple[str, SnmpResult | None]:
        async with sem:
            try:
                r = await snmp_probe(h, community=community, port=snmp_port, timeout=2.0)
                return h, r
            except Exception as exc:  # noqa: BLE001
                log.warning("snmp probe %s failed: %s", h, exc)
                return h, None

    return await asyncio.gather(*[_one(h) for h in hosts])


async def discover(
    ctx: dict,
    targets: str,
    community: str = "public",
    snmp_port: int = 161,
    default_station_code: str | None = None,
) -> dict[str, Any]:
    """arq task: ICMP+SNMP sweep → persist discovered_devices."""
    ips = _expand_targets(targets)
    log.info("discover start: %d target(s) from %r", len(ips), targets)
    if not ips:
        return {"scanned": 0, "alive": 0, "snmp_responded": 0,
                "inserted": 0, "failed": 0, "error": "no targets"}

    try:
        pings = await sweep(ips, concurrency=32, count=2, timeout=1.5)
    except Exception as exc:  # noqa: BLE001
        log.exception("ICMP sweep crashed: %s", exc)
        pings = []

    alive = [p.host for p in pings if p.alive]
    log.info("discover: %d/%d ICMP-alive", len(alive), len(ips))

    icmp_blocked = bool(ips) and not alive
    probe_targets = ips if icmp_blocked else alive
    if icmp_blocked:
        log.warning("ICMP returned 0 alive for %d target(s) — SNMP fallback",
                    len(ips))

    probes = await _probe_snmp(probe_targets, community, snmp_port)
    snmp_hits = sum(1 for _, s in probes if s and s.reachable)
    snmp_errors = sum(1 for _, s in probes if s is None or bool(s.error))
    log.info("discover: %d/%d SNMP responded (%d errors)",
             snmp_hits, len(probe_targets), snmp_errors)

    loc = (
        f"{default_station_code} Division"[:_LOCATION_MAX]
        if default_station_code else None
    )
    inserted = 0
    failed = 0
    async with async_session_maker() as session:
        await session.execute(delete(DiscoveredDevice))
        for host, snmp in probes:
            try:
                hostname = None
                mac = None
                detected_type = "unknown"
                if snmp and snmp.reachable:
                    hostname = (snmp.sys_name or None)
                    if hostname:
                        hostname = hostname[:_HOSTNAME_MAX]
                    detected_type = _classify(snmp.sys_descr, snmp.interfaces)
                    mac = _pick_mac(snmp.interfaces)
                session.add(DiscoveredDevice(
                    id=uuid.uuid4(),
                    ip_address=host,
                    mac_address=mac,
                    hostname=hostname,
                    detected_type=detected_type,
                    status="pending",
                    is_rogue=False,
                    location_guess=loc,
                ))
                inserted += 1
            except Exception as exc:  # noqa: BLE001
                log.warning("insert %s failed: %s", host, exc)
                failed += 1
        try:
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            log.exception("commit failed: %s", exc)
            await session.rollback()
            return {"scanned": len(ips), "alive": len(alive),
                    "snmp_responded": snmp_hits, "inserted": 0,
                    "failed": len(probes), "error": f"commit: {exc}"}

    return {
        "scanned": len(ips),
        "alive": len(alive),
        "snmp_responded": snmp_hits,
        "snmp_errors": snmp_errors,
        "inserted": inserted,
        "failed": failed,
        "icmp_blocked_fallback": icmp_blocked,
    }