from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel
from app.deps import get_db
from app.models.link import Link
from app.security.rbac import Permission, require_permission

router = APIRouter(prefix="/links", tags=["links"])

class LinkCreate(BaseModel):
    source_station: str
    destination_station: str
    provider: str
    status: str = "up"

@router.get("/")
async def get_all_links(db: AsyncSession = Depends(get_db), _=Depends(require_permission(Permission.DEVICE_READ))):
    res = await db.execute(select(Link))
    return res.scalars().all()

@router.post("/")
async def create_link(req: LinkCreate, db: AsyncSession = Depends(get_db), _=Depends(require_permission(Permission.DEVICE_WRITE))):
    link = Link(source_station=req.source_station, destination_station=req.destination_station, provider=req.provider, status=req.status)
    db.add(link)
    await db.commit()
    return {"message": "Link created"}

@router.get("/{station_code}")
async def get_station_links(station_code: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission(Permission.DEVICE_READ))):
    stmt = select(Link).where(or_(Link.source_station == station_code, Link.destination_station == station_code))
    res = await db.execute(stmt)
    return res.scalars().all()