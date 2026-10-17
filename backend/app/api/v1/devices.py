from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.deps import get_db
from app.models.device import Device
from app.models.interface import Interface
from app.schemas.device import DeviceRead
from app.security.rbac import Permission, require_permission

router = APIRouter(prefix="/devices", tags=["devices"])

@router.get("/", response_model=List[DeviceRead])
async def list_devices(
    station_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission(Permission.DEVICE_READ))
):
    """Fetch devices, optionally filtered by station."""
    query = select(Device)
    if station_code:
        query = query.where(Device.station_code == station_code)
    
    result = await db.execute(query.limit(100))
    return result.scalars().all()

@router.get("/{device_id}")
async def get_device_details(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission(Permission.DEVICE_READ))
):
    """Fetch a single device and its interfaces."""
    stmt = select(Device).where(Device.id == device_id)
    res = await db.execute(stmt)
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    int_stmt = select(Interface).where(Interface.device_id == device.id)
    int_res = await db.execute(int_stmt)
    interfaces = int_res.scalars().all()

    return {
        "device": {
            "id": str(device.id),
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "status": device.status,
            "category": device.category
        },
        "interfaces": [
            {
                "id": str(i.id),
                "name": i.name,
                "ip_address": i.ip_address,
                "status": i.status,
                "description": i.description,
                "in_mbps": i.in_mbps,
                "out_mbps": i.out_mbps,
                "errors": i.errors
            } for i in interfaces
        ]
    }