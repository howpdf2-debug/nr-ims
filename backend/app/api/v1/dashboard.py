from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission
from app.security.scope import scope_stations

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_down = func.count(Device.id).filter(Device.status == "down")


@router.get("/divisions")
async def get_division_summary(db: AsyncSession = Depends(get_db),
                               user: User = Depends(require_permission(Permission.DEVICE_READ))):
    # One query (was 1 + N): stations and down-device counts per division, scoped.
    q = (select(Station.division, func.count(func.distinct(Station.code)).label("total"),
                _down.label("down"))
         .select_from(Station).outerjoin(Device, Device.station_code == Station.code)
         .group_by(Station.division).order_by(Station.division))
    rows = (await db.execute(scope_stations(q, user))).all()
    return [{"division": r.division, "total_stations": r.total, "down_devices": r.down,
             "status": "critical" if r.down else "healthy"} for r in rows]


@router.get("/divisions/{division_code}/stations")
async def get_division_stations(division_code: str, db: AsyncSession = Depends(get_db),
                                user: User = Depends(require_permission(Permission.DEVICE_READ))):
    q = (select(Station, _down.label("down")).outerjoin(Device, Device.station_code == Station.code)
         .where(Station.division == division_code).group_by(Station.code).order_by(Station.code))
    rows = (await db.execute(scope_stations(q, user))).all()
    return [{"code": s.code, "name": s.name, "tier": s.tier, "type": s.station_type,
             "down_devices": down, "status": "critical" if down else "healthy"} for s, down in rows]
