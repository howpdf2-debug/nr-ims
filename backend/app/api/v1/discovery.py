import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.device import Device
from app.models.discovery import DiscoveredDevice
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission
from app.services.audit import record_audit

router = APIRouter(prefix="/discovery", tags=["discovery"])
_admin = Depends(require_permission(Permission.DISCOVERY_MANAGE))  # IRCA only (via role matrix)

_MOCK = [  # TODO: replace with real scanner (nmap/SNMP) behind NRIMS_DATA_PROVIDER=live
    ("10.1.15.1", "00:1A:2B:3C:4D:5E", "lko-core-rtr", "router", False, "LKO Division"),
    ("10.2.20.5", "AA:BB:CC:DD:EE:FF", "unknown-pc", "PC", True, "MB Division"),
    ("10.6.10.9", "11:22:33:44:55:66", "hacker-laptop", "Unknown", True, "DLI Division"),
]


@router.post("/scan")
async def run_scan(db: AsyncSession = Depends(get_db), user: User = _admin):
    await db.execute(delete(DiscoveredDevice))
    for ip, mac, host, typ, rogue, loc in _MOCK:
        db.add(DiscoveredDevice(id=uuid.uuid4(), ip_address=ip, mac_address=mac, hostname=host,
                                detected_type=typ, is_rogue=rogue, location_guess=loc,
                                status="rogue" if rogue else "pending"))
    record_audit(db, user, "discovery.scan", "discovery", "all")
    await db.commit()
    return {"message": "Scan complete"}


@router.get("/results")
async def get_scan_results(db: AsyncSession = Depends(get_db), user: User = _admin):
    return [{"id": str(d.id), "ip": d.ip_address, "mac": d.mac_address, "hostname": d.hostname,
             "type": d.detected_type, "status": d.status, "is_rogue": d.is_rogue,
             "location": d.location_guess} for d in (await db.execute(select(DiscoveredDevice))).scalars()]


@router.post("/approve/{discovery_id}")
async def approve_device(discovery_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = _admin):
    d = await db.get(DiscoveredDevice, discovery_id)
    if not d:
        raise HTTPException(404, "Not found")
    if d.is_rogue:
        raise HTTPException(400, "Rogue devices cannot be approved")
    code = (d.location_guess or "").split(" ")[0]
    if not code or not await db.get(Station, code):
        raise HTTPException(422, f"Cannot map location '{d.location_guess}' to a station")
    db.add(Device(id=uuid.uuid4(), external_id=uuid.uuid4().hex[:8], hostname=d.hostname or f"auto-{d.ip_address}",
                  ip_address=d.ip_address, category=d.detected_type, station_code=code, status="up",
                  source_system="discovery", source_timestamp=datetime.now(UTC)))
    await db.delete(d)
    record_audit(db, user, "discovery.approve", "discovery", discovery_id, {"ip": d.ip_address})
    await db.commit()
    return {"message": "Device approved"}


@router.delete("/{discovery_id}")
async def reject_device(discovery_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = _admin):
    await db.execute(delete(DiscoveredDevice).where(DiscoveredDevice.id == discovery_id))
    record_audit(db, user, "discovery.reject", "discovery", discovery_id)
    await db.commit()
    return {"message": "Removed"}
