"""Inter-station links. A link is visible only when BOTH of its stations are in the caller's scope
(same rule as /topology/), so a boundary link never reveals a foreign station code."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.link import Link
from app.models.station import Station
from app.models.user import User
from app.schemas.link import LinkRead
from app.security.rbac import Permission, require_permission
from app.security.scope import is_unrestricted, require_station, scope_stations
from app.services.audit import record_audit

router = APIRouter(prefix="/links", tags=["links"])


class LinkCreate(BaseModel):
    source_station: str
    destination_station: str
    provider: str = Field(min_length=1, max_length=50)
    status: str = Field(default="up", pattern="^(up|down|degraded)$")


async def _visible_codes(db: AsyncSession, user: User) -> set[str]:
    return set((await db.execute(scope_stations(select(Station.code), user))).scalars())


@router.get("/", response_model=list[LinkRead])
async def get_all_links(db: AsyncSession = Depends(get_db),
                        user: User = Depends(require_permission(Permission.DEVICE_READ))):
    q = select(Link).order_by(Link.source_station, Link.destination_station, Link.provider, Link.id)
    if not is_unrestricted(user):
        vis = await _visible_codes(db, user)
        q = q.where(Link.source_station.in_(vis), Link.destination_station.in_(vis))
    return (await db.execute(q)).scalars().all()


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


@router.get("/{station_code}", response_model=list[LinkRead])
async def get_station_links(station_code: str, db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_permission(Permission.DEVICE_READ))):
    await require_station(db, user, station_code)
    q = select(Link).where(or_(Link.source_station == station_code, Link.destination_station == station_code))
    if not is_unrestricted(user):
        vis = await _visible_codes(db, user)
        q = q.where(Link.source_station.in_(vis), Link.destination_station.in_(vis))
    return (await db.execute(q.order_by(Link.provider, Link.id))).scalars().all()
