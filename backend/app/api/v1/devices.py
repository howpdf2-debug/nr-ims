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

@router.delete("/{device_id}")
async def delete_device(device_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    device = (await db.execute(select(Device).where(Device.id == device_id))).scalar_one_or_none()
    if not device: raise HTTPException(404, "Device not found")
    
    # Find all children recursively
    all_ids_to_delete = [device.id]
    children = (await db.execute(select(Device).where(Device.parent_device_id == device.id))).scalars().all()
    while children:
        next_children = []
        for child in children:
            all_ids_to_delete.append(child.id)
            sub_children = (await db.execute(select(Device).where(Device.parent_device_id == child.id))).scalars().all()
            next_children.extend(sub_children)
        children = next_children

    # Delete links, interfaces, alarms, and devices
    await db.execute(delete(DeviceLink).where((DeviceLink.source_device_id.in_(all_ids_to_delete)) | (DeviceLink.destination_device_id.in_(all_ids_to_delete))))
    await db.execute(delete(Interface).where(Interface.device_id.in_(all_ids_to_delete)))
    await db.execute(delete(Alarm).where(Alarm.device_id.in_(all_ids_to_delete)))
    await db.execute(delete(Device).where(Device.id.in_(all_ids_to_delete)))
    await db.commit()
    return {"message": "Device and all its children deleted successfully"}