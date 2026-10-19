from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.deps import get_db
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission, Role

router = APIRouter(prefix="/alarms", tags=["alarms"])


@router.get("/")
async def list_alarms(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ALARM_READ)),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(500, ge=1, le=2000, description="Page size"),
):
    query = (
        select(Alarm, Device, Station)
        .join(Device, Alarm.device_id == Device.id)
        .join(Station, Device.station_code == Station.code)
        .where(Alarm.status == "active")
    )
    if current_user.role != Role.IRCA_ADMIN and "*" not in current_user.scopes:
        query = query.where(Station.division.in_(current_user.scopes))

    query = query.order_by(Alarm.first_seen.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    raw_data = result.all()

    parent_down_map: dict[str, bool] = {}
    for _a, _d, s in raw_data:
        if s.tier == "Tier 0":
            parent_down_map["ALL"] = True
        if s.code in ["LKO", "MB", "NDLS", "UMB"]:
            parent_down_map[s.code] = True

    processed_alarms = []
    seen_devices: set = set()

    for a, d, s in raw_data:
        if d.id in seen_devices:
            continue
        seen_devices.add(d.id)

        is_suppressed = False
        root_cause = None

        if parent_down_map.get("ALL") and s.tier != "Tier 0":
            is_suppressed = True
            root_cause = "IRCA Core Down"
        elif s.parent_station_code and parent_down_map.get(s.parent_station_code):
            is_suppressed = True
            root_cause = f"Parent Station {s.parent_station_code} Down"

        processed_alarms.append(
            {
                "id": str(a.id),
                "device_id": str(d.id),
                "device_name": d.hostname,
                "station_code": s.code,
                "station_name": s.name,
                "severity": a.severity,
                "message": a.message,
                "status": a.status,
                "first_seen": a.first_seen.isoformat(),
                "is_suppressed": is_suppressed,
                "root_cause": root_cause,
            }
        )

    return processed_alarms


@router.patch("/{alarm_id}/ack")
async def acknowledge_alarm(
    alarm_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ALARM_ACK)),
):
    try:
        res = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    except Exception:
        raise HTTPException(400, "Invalid alarm ID format")

    alarm = res.scalar_one_or_none()
    if not alarm:
        raise HTTPException(404, "Alarm not found")

    if alarm.status == "acknowledged":
        return {"message": "Alarm already acknowledged", "already_done": True}

    alarm.status = "acknowledged"
    alarm.acked_by = current_user.email
    await db.commit()
    return {"message": "Alarm acknowledged", "already_done": False}