from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel

from app.deps import get_db
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.models.interface import Interface
from app.models.device_link import DeviceLink
from app.models.alarm import Alarm
from app.schemas.device import DeviceRead
from app.security.rbac import Permission, require_permission, Role

router = APIRouter(prefix="/devices", tags=["devices"])

class DeviceCreate(BaseModel):
    hostname: str
    ip_address: str
    category: str
    station_code: str
    parent_device_id: str | None = None

@router.get("/", response_model=List[DeviceRead])
async def list_devices(station_code: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_READ))):
    query = select(Device).join(Station)
    if current_user.role != Role.IRCA_ADMIN and "*" not in current_user.scopes:
        query = query.where(Station.division.in_(current_user.scopes))
    if station_code: query = query.where(Device.station_code == station_code)
    return (await db.execute(query.limit(500))).scalars().all()

@router.post("/")
async def create_device(req: DeviceCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    new_device = Device(id=uuid.uuid4(), external_id=str(uuid.uuid4())[:8], hostname=req.hostname, ip_address=req.ip_address, category=req.category, station_code=req.station_code, status="up", parent_device_id=uuid.UUID(req.parent_device_id) if req.parent_device_id else None, source_system="admin_ui", source_timestamp=datetime.now(timezone.utc))
    db.add(new_device); await db.commit()
    return {"message": "Device created", "id": str(new_device.id)}

@router.get("/{device_id}")
async def get_device_details(device_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_READ))):
    stmt = select(Device).where(Device.id == device_id)
    res = await db.execute(stmt)
    device = res.scalar_one_or_none()
    if not device: raise HTTPException(status_code=404, detail="Device not found")

    int_stmt = select(Interface).where(Interface.device_id == device.id)
    int_res = await db.execute(int_stmt)
    interfaces = int_res.scalars().all()

    # डमी OSPF डेटा
    ospf_neighbors = [
        {"neighbor_ip": "10.10.1.5", "state": "FULL", "interface": "Gi0/1", "uptime": "12d 4h"},
        {"neighbor_ip": "10.10.2.5", "state": "FULL", "interface": "Gi0/2", "uptime": "10d 2h"},
    ]

    return {
        "device": {
            "id": str(device.id), "hostname": device.hostname, "ip_address": device.ip_address,
            "status": device.status, "category": device.category, "is_maintenance": device.is_maintenance,
            "uptime": "45 days, 12 hours", "cpu_usage": 24, "memory_usage": 58
        },
        "interfaces": [
            {
                "id": str(i.id), "name": i.name, "ip_address": i.ip_address,
                "status": i.status, "description": i.description,
                "in_mbps": i.in_mbps, "out_mbps": i.out_mbps, "errors": i.errors
            } for i in interfaces
        ],
        "ospf_neighbors": ospf_neighbors
    }

@router.delete("/{device_id}")
async def delete_device(device_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one_or_none()
    if not device: raise HTTPException(404, "Device not found")
    all_ids = [device.id]
    children = (await db.execute(select(Device).where(Device.parent_device_id == device.id))).scalars().all()
    while children:
        next_c = []
        for c in children:
            all_ids.append(c.id)
            sub = (await db.execute(select(Device).where(Device.parent_device_id == c.id))).scalars().all()
            next_c.extend(sub)
        children = next_c
    await db.execute(delete(DeviceLink).where((DeviceLink.source_device_id.in_(all_ids)) | (DeviceLink.destination_device_id.in_(all_ids))))
    await db.execute(delete(Interface).where(Interface.device_id.in_(all_ids)))
    await db.execute(delete(Alarm).where(Alarm.device_id.in_(all_ids)))
    await db.execute(delete(Device).where(Device.id.in_(all_ids)))
    await db.commit()
    return {"message": "Device and all children deleted"}