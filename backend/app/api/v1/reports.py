import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission
from app.security.scope import scope_stations

router = APIRouter(prefix="/reports", tags=["reports"])
_EXPORT_LIMIT = 50_000


def _csv_safe(v: object) -> str:
    """Neutralise spreadsheet formula injection (=,+,-,@ at start of a cell)."""
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


@router.get("/summary")
async def get_report_summary(db: AsyncSession = Depends(get_db),
                             user: User = Depends(require_permission(Permission.ALARM_READ))):
    dev = scope_stations(select(func.count(Device.id)).join(Station, Device.station_code == Station.code), user)
    total = await db.scalar(dev) or 0
    down = await db.scalar(dev.where(Device.status == "down")) or 0

    def alarms():
        return scope_stations(select(func.count(Alarm.id)).join(Device, Alarm.device_id == Device.id)
                              .join(Station, Device.station_code == Station.code), user)

    total_alarms = await db.scalar(alarms()) or 0
    active = await db.scalar(alarms().where(Alarm.status == "active")) or 0

    sev_q = scope_stations(select(Alarm.severity, func.count(Alarm.id)).join(Device, Alarm.device_id == Device.id)
                           .join(Station, Device.station_code == Station.code), user).group_by(Alarm.severity)
    top_base = (select(Station.name, func.count(Alarm.id).label("c"))
                .join(Device, Device.station_code == Station.code)
                .join(Alarm, Alarm.device_id == Device.id))
    top_q = (scope_stations(top_base, user).group_by(Station.name).order_by(func.count(Alarm.id).desc()).limit(5))
    return {
        "kpi": {"total_devices": total, "down_devices": down,
                "uptime_pct": round((total - down) / total * 100, 2) if total else 100.0,
                "total_alarms": total_alarms, "active_alarms": active},
        "severity_distribution": [{"name": r[0].capitalize(), "value": r[1]} for r in (await db.execute(sev_q)).all()],
        "top_stations": [{"name": r[0], "count": r[1]} for r in (await db.execute(top_q)).all()],
    }


@router.get("/export/alarms")
async def export_alarms_csv(db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_permission(Permission.ALARM_READ))):
    q = (select(Alarm, Device, Station).join(Device, Alarm.device_id == Device.id)
         .join(Station, Device.station_code == Station.code))
    q = scope_stations(q, user).order_by(Alarm.first_seen.desc()).limit(_EXPORT_LIMIT)
    rows = (await db.execute(q)).all()

    def stream():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Alarm ID", "Severity", "Status", "Message", "Device", "Station", "First Seen"])
        for a, d, s in rows:
            w.writerow([a.id, a.severity, a.status, _csv_safe(a.message), _csv_safe(d.hostname),
                        _csv_safe(s.name), a.first_seen.strftime("%Y-%m-%d %H:%M:%S")])
            if buf.tell() > 64_000:
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate()
        yield buf.getvalue()

    name = f"nr_ims_alarms_{datetime.now(UTC):%Y%m%d}.csv"
    return StreamingResponse(stream(), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})
