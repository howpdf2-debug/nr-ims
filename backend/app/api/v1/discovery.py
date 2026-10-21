"""Discovery API: scan/results/approve/reject.

Simulator mode (NRIMS_DATA_PROVIDER=simulator): mock devices, synchronous.
Live mode (NRIMS_DATA_PROVIDER=live): enqueues arq `discover` task;
client polls /results while worker populates discovered_devices.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from arq.connections import ArqRedis, RedisSettings, create_pool
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DataProvider, get_settings
from app.deps import get_db
from app.models.device import Device
from app.models.discovery import DiscoveredDevice
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission
from app.services.audit import record_audit

router = APIRouter(prefix="/discovery", tags=["discovery"])
_admin = Depends(require_permission(Permission.DISCOVERY_MANAGE))

_MOCK = [
    ("10.1.15.1", "00:1A:2B:3C:4D:5E", "lko-core-rtr", "router", False, "LKO Division"),
    ("10.2.20.5", "AA:BB:CC:DD:EE:FF", "unknown-pc", "PC", True, "MB Division"),
    ("10.6.10.9", "11:22:33:44:55:66", "hacker-laptop", "Unknown", True, "DLI Division"),
]

# Module-level arq pool singleton (lazy init)
_arq_pool: ArqRedis | None = None


async def _get_arq_pool() -> ArqRedis:
    global _arq_pool
    if _arq_pool is None:
        s = get_settings()
        _arq_pool = await create_pool(
            RedisSettings.from_dsn(s.valkey_url.get_secret_value())
        )
    return _arq_pool


class ScanRequest(BaseModel):
    targets: str = Field(
        ..., min_length=1,
        description="CIDR, IP, hostname; comma-separated",
    )
    community: str = Field(default="public", min_length=1)
    snmp_port: int = Field(default=161, ge=1, le=65535)
    station_code: str | None = Field(
        default=None,
        description="Station code used as location guess for approve flow",
    )


@router.post("/scan")
async def run_scan(
    payload: ScanRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = _admin,
):
    s = get_settings()

    if s.data_provider == DataProvider.SIMULATOR:
        await db.execute(delete(DiscoveredDevice))
        for ip, mac, host, typ, rogue, loc in _MOCK:
            db.add(DiscoveredDevice(
                id=uuid.uuid4(), ip_address=ip, mac_address=mac, hostname=host,
                detected_type=typ, is_rogue=rogue, location_guess=loc,
                status="rogue" if rogue else "pending",
            ))
        record_audit(db, user, "discovery.scan", "discovery", "all")
        await db.commit()
        return {"message": "Scan complete", "mode": "simulator"}

    # ---- live mode ----
    if payload is None or not payload.targets:
        raise HTTPException(422, "targets required in live mode")

    station_code = payload.station_code or getattr(user, "station_code", None)
    if station_code:
        station = await db.get(Station, station_code)
        if station is None:
            raise HTTPException(422, f"station '{station_code}' not found")

    try:
        pool = await _get_arq_pool()
        job = await pool.enqueue_job(
            "discover",
            payload.targets,
            payload.community,
            payload.snmp_port,
            station_code,
            _job_id=f"discovery:scan:{uuid.uuid4().hex[:8]}",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"failed to enqueue: {exc}") from exc

    if job is None:  # arq returns None when a job with the same id already exists
        raise HTTPException(409, "A scan with this job id is already queued")

    record_audit(db, user, "discovery.scan", "discovery", job.job_id)
    await db.commit()
    return {"message": "Scan queued", "mode": "live", "job_id": job.job_id}


@router.get("/results")
async def get_scan_results(db: AsyncSession = Depends(get_db), user: User = _admin):
    rows = (await db.execute(select(DiscoveredDevice))).scalars().all()
    return [
        {"id": str(d.id), "ip": d.ip_address, "mac": d.mac_address,
         "hostname": d.hostname, "type": d.detected_type, "status": d.status,
         "is_rogue": d.is_rogue, "location": d.location_guess}
        for d in rows
    ]


@router.post("/approve/{discovery_id}")
async def approve_device(
    discovery_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = _admin,
):
    d = await db.get(DiscoveredDevice, discovery_id)
    if not d:
        raise HTTPException(404, "Not found")
    if d.is_rogue:
        raise HTTPException(400, "Rogue devices cannot be approved")
    code = (d.location_guess or "").split(" ")[0]
    if not code or not await db.get(Station, code):
        raise HTTPException(
            422, f"Cannot map location '{d.location_guess}' to a station"
        )
    db.add(Device(
        id=uuid.uuid4(), external_id=uuid.uuid4().hex[:8],
        hostname=d.hostname or f"auto-{d.ip_address}",
        ip_address=d.ip_address, category=d.detected_type, station_code=code,
        status="up", source_system="discovery",
        source_timestamp=datetime.now(UTC),
    ))
    await db.delete(d)
    record_audit(db, user, "discovery.approve", "discovery", discovery_id,
                 {"ip": d.ip_address})
    await db.commit()
    return {"message": "Device approved"}


@router.delete("/{discovery_id}")
async def reject_device(
    discovery_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = _admin,
):
    await db.execute(
        delete(DiscoveredDevice).where(DiscoveredDevice.id == discovery_id)
    )
    record_audit(db, user, "discovery.reject", "discovery", discovery_id)
    await db.commit()
    return {"message": "Removed"}