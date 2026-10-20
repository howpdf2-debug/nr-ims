from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.link import Link
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission
from app.security.scope import require_station, scope_stations
from app.services.audit import record_audit

router = APIRouter(prefix="/links", tags=["links"])


class LinkCreate(BaseModel):
    source_station: str
    destination_station: str
    provider: str = Field(min_length=1, max_length=50)
    status: str = Field(default="up", pattern="^(up|down|degraded)$")


async def _visible_codes(db: AsyncSession, user: User) -> set[str]:
    return set((await db.execute(scope_stations(select(Station.code), user))).scalars())


@router.get("/")
async def get_all_links(db: AsyncSession = Depends(get_db),
                        user: User = Depends(require_permission(Permission.DEVICE_READ))):
    vis = await _visible_codes(db, user)
    links = (await db.execute(select(Link))).scalars().all()
    return [lk for lk in links if lk.source_station in vis or lk.destination_station in vis]


@router.post("/", status_code=201)
async def create_link(req: LinkCreate, db: AsyncSession = Depends(get_db),
                      user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    if req.source_station == req.destination_station:
        raise HTTPException(422, "Source and destination must differ")
    await require_station(db, user, req.source_station)
    if not await db.get(Station, req.destination_station):
        raise HTTPException(404, "Destination station not found")
    link = Link(**req.model_dump())
    db.add(link)
    await db.flush()
    record_audit(db, user, "link.create", "link", link.id)
    await db.commit()
    return {"message": "Link created"}


@router.get("/{station_code}")
async def get_station_links(station_code: str, db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_permission(Permission.DEVICE_READ))):
    await require_station(db, user, station_code)
    q = select(Link).where(or_(Link.source_station == station_code, Link.destination_station == station_code))
    return (await db.execute(q)).scalars().all()
