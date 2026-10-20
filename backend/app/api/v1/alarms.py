import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission
from app.security.scope import scope_stations
from app.services.audit import record_audit
from app.services.correlation import build_parent_map, find_root_cause

router = APIRouter(prefix="/alarms", tags=["alarms"])


class AckBody(BaseModel):
    note: str | None = Field(default=None, max_length=500)


@router.get("/")
async def list_alarms(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission(Permission.ALARM_READ)),
    skip: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=2000),
):
    q = (select(Alarm, Device, Station)
         .join(Device, Alarm.device_id == Device.id)
         .join(Station, Device.station_code == Station.code)
         .where(Alarm.status == "active"))
    q = scope_stations(q, user).order_by(Alarm.first_seen.desc(), Alarm.id).offset(skip).limit(limit)
    rows = (await db.execute(q)).all()

    # RCA must see the WHOLE hierarchy, not only what this user may view.
    parent_of = build_parent_map((await db.execute(select(Station.code, Station.parent_station_code))).all())
    alarming = set((await db.execute(
        select(Station.code).join(Device, Device.station_code == Station.code)
        .join(Alarm, Alarm.device_id == Device.id).where(Alarm.status == "active").distinct())).scalars())

    out, seen = [], set()
    for a, d, s in rows:
        if d.id in seen:
            continue
        seen.add(d.id)
        root = find_root_cause(s.code, parent_of, alarming)
        out.append({
            "id": str(a.id), "device_id": str(d.id), "device_name": d.hostname,
            "station_code": s.code, "station_name": s.name, "severity": a.severity,
            "message": a.message, "status": a.status, "first_seen": a.first_seen.isoformat(),
            "is_suppressed": root is not None,
            "root_cause": f"Upstream station {root} is down" if root else None,
        })
    return out


@router.patch("/{alarm_id}/ack")
async def acknowledge_alarm(alarm_id: uuid.UUID, body: AckBody | None = None,
                            db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_permission(Permission.ALARM_ACK))):
    q = scope_stations(
        select(Alarm).join(Device, Alarm.device_id == Device.id)
        .join(Station, Device.station_code == Station.code).where(Alarm.id == alarm_id), user)
    alarm = (await db.execute(q)).scalar_one_or_none()
    if not alarm:
        raise HTTPException(404, "Alarm not found")
    if alarm.status == "acknowledged":
        return {"message": "Alarm already acknowledged", "already_done": True}
    alarm.status = "acknowledged"
    alarm.acked_by = user.email
    alarm.acked_at = datetime.now(UTC)
    alarm.ack_note = body.note if body else None
    record_audit(db, user, "alarm.ack", "alarm", alarm.id)
    await db.commit()
    return {"message": "Alarm acknowledged", "already_done": False}
