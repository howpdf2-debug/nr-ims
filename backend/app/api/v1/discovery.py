from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import uuid
from datetime import datetime, timezone
from app.deps import get_db
from app.models.user import User
from app.models.device import Device
from app.models.discovery import DiscoveredDevice
from app.security.rbac import Permission, require_permission, Role

router = APIRouter(prefix="/discovery", tags=["discovery"])

@router.post("/scan")
async def run_scan(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    if current_user.role != Role.IRCA_ADMIN: raise HTTPException(403, "Only IRCA Admin")
    await db.execute(delete(DiscoveredDevice)); await db.commit()

    mock_results = [
        {"ip": "10.1.15.1", "mac": "00:1A:2B:3C:4D:5E", "host": "lko-core-rtr", "type": "router", "rogue": False, "loc": "LKO Division"},
        {"ip": "10.2.20.5", "mac": "AA:BB:CC:DD:EE:FF", "host": "unknown-pc", "type": "PC", "rogue": True, "loc": "MB Division"},
        {"ip": "10.6.10.9", "mac": "11:22:33:44:55:66", "host": "hacker-laptop", "type": "Unknown", "rogue": True, "loc": "DLI Division"},
    ]
    for res in mock_results:
        db.add(DiscoveredDevice(id=uuid.uuid4(), ip_address=res["ip"], mac_address=res["mac"], hostname=res["host"], detected_type=res["type"], is_rogue=res["rogue"], location_guess=res["loc"], status="rogue" if res["rogue"] else "pending"))
    await db.commit()
    return {"message": "Scan complete"}

@router.get("/results")
async def get_scan_results(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_READ))):
    res = await db.execute(select(DiscoveredDevice))
    return [{"id": str(d.id), "ip": d.ip_address, "mac": d.mac_address, "hostname": d.hostname, "type": d.detected_type, "status": d.status, "is_rogue": d.is_rogue, "location": d.location_guess} for d in res.scalars().all()]

@router.post("/approve/{discovery_id}")
async def approve_device(discovery_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    if current_user.role != Role.IRCA_ADMIN: raise HTTPException(403, "Only IRCA Admin")
    device = (await db.execute(select(DiscoveredDevice).where(DiscoveredDevice.id == discovery_id))).scalar_one_or_none()
    if not device: raise HTTPException(404, "Not found")
    if device.is_rogue: raise HTTPException(400, "Rogue devices cannot be approved")
    
    station_code = device.location_guess.split(" ")[0] if device.location_guess else "LKO"
    new_device = Device(id=uuid.uuid4(), external_id=str(uuid.uuid4())[:8], hostname=device.hostname or f"auto-{device.ip_address}", ip_address=device.ip_address, category=device.detected_type, station_code=station_code, status="up", source_system="discovery", source_timestamp=datetime.now(timezone.utc))
    db.add(new_device); await db.delete(device); await db.commit()
    return {"message": "Device approved"}

@router.delete("/{discovery_id}")
async def reject_device(discovery_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    await db.execute(delete(DiscoveredDevice).where(DiscoveredDevice.id == discovery_id)); await db.commit()
    return {"message": "Removed"}