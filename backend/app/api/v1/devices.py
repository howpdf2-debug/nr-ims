from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.deps import get_db
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission, Role

# ── यह लाइन मिसिंग थी, अब इसे जोड़ दिया गया है ──
router = APIRouter(prefix="/devices", tags=["devices"])

@router.get("/")
async def list_devices(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=1000, description="Page size"),
    station_code: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DEVICE_READ))
):
    query = select(Device)
    
    # Filters based on query params
    if station_code:
        query = query.where(Device.station_code == station_code)
    if category:
        query = query.where(Device.category == category)

    # RBAC Scope filter (if user is not IRCA admin)
    if current_user.role != Role.IRCA_ADMIN and "*" not in current_user.scopes:
        query = query.join(Station, Device.station_code == Station.code).where(
            Station.division.in_(current_user.scopes)
        )

    # Pagination
    query = query.order_by(Device.hostname).offset(skip).limit(limit)
    
    result = await db.execute(query)
    devices = result.scalars().all()
    
    return devices

@router.get("/{device_id}")
async def get_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DEVICE_READ))
):
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(404, "Device not found")
        
    return device