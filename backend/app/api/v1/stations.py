from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.deps import get_db
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission, Role

router = APIRouter(prefix="/stations", tags=["stations"])

class StationCreate(BaseModel):
    code: str
    name: str
    division: str
    tier: str
    station_type: str
    parent_station_code: str | None = None

class StationUpdate(BaseModel):
    name: str
    tier: str
    station_type: str

@router.get("/")
async def list_stations(
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(require_permission(Permission.DEVICE_READ))
):
    query = select(Station)
    # Data Scoping
    if current_user.role != Role.IRCA_ADMIN and "*" not in current_user.scopes:
        query = query.where(Station.division.in_(current_user.scopes))
    
    res = await db.execute(query)
    return res.scalars().all()

@router.post("/")
async def create_station(
    req: StationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))
):
    # Check if user has permission to create station in this division
    if current_user.role != Role.IRCA_ADMIN and req.division not in current_user.scopes:
        raise HTTPException(status_code=403, detail="You do not have access to this division")

    existing = await db.execute(select(Station).where(Station.code == req.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Station code already exists")

    st = Station(**req.dict())
    db.add(st)
    await db.commit()
    return {"message": "Station created successfully"}

@router.put("/{code}")
async def update_station(
    code: str,
    req: StationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))
):
    res = await db.execute(select(Station).where(Station.code == code))
    st = res.scalar_one_or_none()
    if not st:
        raise HTTPException(status_code=404, detail="Station not found")

    if current_user.role != Role.IRCA_ADMIN and st.division not in current_user.scopes:
        raise HTTPException(status_code=403, detail="Unauthorized")

    st.name = req.name
    st.tier = req.tier
    st.station_type = req.station_type
    await db.commit()
    return {"message": "Station updated"}

@router.delete("/{code}")
async def delete_station(
    code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))
):
    res = await db.execute(select(Station).where(Station.code == code))
    st = res.scalar_one_or_none()
    if not st:
        raise HTTPException(status_code=404, detail="Station not found")

    if current_user.role != Role.IRCA_ADMIN and st.division not in current_user.scopes:
        raise HTTPException(status_code=403, detail="Unauthorized")

    await db.delete(st)
    await db.commit()
    return {"message": "Station deleted"}