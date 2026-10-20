import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.schemas.device import DeviceRead
from app.security.rbac import Permission, require_permission
from app.security.scope import get_device_for_user, scope_stations

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/", response_model=list[DeviceRead])
async def list_devices(
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
    station_code: str | None = None, category: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission(Permission.DEVICE_READ)),
):
    q = select(Device).join(Station, Device.station_code == Station.code)
    if station_code:
        q = q.where(Device.station_code == station_code)
    if category:
        q = q.where(Device.category == category)
    q = scope_stations(q, user).order_by(Device.hostname, Device.id).offset(skip).limit(limit)
    return (await db.execute(q)).scalars().all()


@router.get("/{device_id}", response_model=DeviceRead)
async def get_device(device_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                     user: User = Depends(require_permission(Permission.DEVICE_READ))):
    return await get_device_for_user(db, user, device_id)
