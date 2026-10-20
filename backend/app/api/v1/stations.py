from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission
from app.security.scope import is_unrestricted, require_station, scope_stations
from app.services.audit import record_audit

router = APIRouter(prefix="/stations", tags=["stations"])


class StationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z0-9]+$")
    name: str = Field(min_length=1, max_length=100)
    division: str = Field(min_length=1, max_length=50)
    tier: str = Field(max_length=20)
    station_type: str = Field(max_length=20)
    parent_station_code: str | None = None


class StationUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    tier: str = Field(max_length=20)
    station_type: str = Field(max_length=20)


@router.get("/")
async def list_stations(db: AsyncSession = Depends(get_db),
                        user: User = Depends(require_permission(Permission.DEVICE_READ))):
    return (await db.execute(scope_stations(select(Station), user).order_by(Station.code))).scalars().all()


@router.post("/", status_code=201)
async def create_station(req: StationCreate, db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_permission(Permission.STATION_MANAGE))):
    if not is_unrestricted(user) and req.division not in (user.scopes or []):
        raise HTTPException(403, "You do not have access to this division")
    if await db.get(Station, req.code):
        raise HTTPException(400, "Station code already exists")
    if req.parent_station_code and not await db.get(Station, req.parent_station_code):
        raise HTTPException(400, "Parent station does not exist")
    db.add(Station(**req.model_dump()))
    record_audit(db, user, "station.create", "station", req.code)
    await db.commit()
    return {"message": "Station created successfully"}


@router.put("/{code}")
async def update_station(code: str, req: StationUpdate, db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_permission(Permission.STATION_MANAGE))):
    await require_station(db, user, code)
    st = await db.get(Station, code)
    assert st is not None  # guaranteed by require_station
    st.name, st.tier, st.station_type = req.name, req.tier, req.station_type
    record_audit(db, user, "station.update", "station", code)
    await db.commit()
    return {"message": "Station updated"}


@router.delete("/{code}")
async def delete_station(code: str, force: bool = False, db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_permission(Permission.STATION_MANAGE))):
    await require_station(db, user, code)
    n = await db.scalar(select(func.count(Device.id)).where(Device.station_code == code)) or 0
    if n and not force:  # cascade-deleting devices+alarms must be explicit
        raise HTTPException(409, f"Station has {n} device(s); retry with ?force=true to delete them too")
    st = await db.get(Station, code)
    await db.delete(st)
    record_audit(db, user, "station.delete", "station", code, {"devices_deleted": n})
    await db.commit()
    return {"message": "Station deleted"}
