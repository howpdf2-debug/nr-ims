from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.deps import get_db
from app.models.station import Station
from app.security.rbac import Permission, require_permission

router = APIRouter(prefix="/stations", tags=["stations"])

class StationCreate(BaseModel):
    code: str
    name: str
    division: str
    tier: str
    station_type: str

@router.get("/")
async def list_stations(db: AsyncSession = Depends(get_db), _=Depends(require_permission(Permission.DEVICE_READ))):
    res = await db.execute(select(Station))
    return res.scalars().all()

@router.post("/")
async def create_station(
    req: StationCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission(Permission.DEVICE_WRITE))
):
    existing = await db.execute(select(Station).where(Station.code == req.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Station code already exists")

    st = Station(
        code=req.code, name=req.name, division=req.division, 
        tier=req.tier, station_type=req.station_type
    )
    db.add(st)
    await db.commit()
    return {"message": "Station created successfully"}