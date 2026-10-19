from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import io
import csv
from datetime import datetime

from app.deps import get_db
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/summary")
async def get_report_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ALARM_READ))
):
    # 1. Real Device Counts for Network Health
    total_devices = await db.scalar(select(func.count(Device.id))) or 0
    down_devices = await db.scalar(select(func.count(Device.id)).where(Device.status == "down")) or 0
    
    # Calculate actual Uptime %
    uptime_pct = 100.0
    if total_devices > 0:
        uptime_pct = round(((total_devices - down_devices) / total_devices) * 100, 2)

    # 2. Total & Active Alarms
    total_alarms = await db.scalar(select(func.count(Alarm.id))) or 0
    active_alarms = await db.scalar(select(func.count(Alarm.id)).where(Alarm.status == "active")) or 0
    
    # 3. Alarms by Severity (Real Data)
    severity_query = select(Alarm.severity, func.count(Alarm.id)).group_by(Alarm.severity)
    severity_result = await db.execute(severity_query)
    severity_data = [{"name": row[0].capitalize(), "value": row[1]} for row in severity_result.all()]

    # 4. Top 5 Problem Stations
    station_query = (
        select(Station.name, func.count(Alarm.id).label("alarm_count"))
        .join(Device, Device.station_code == Station.code)
        .join(Alarm, Alarm.device_id == Device.id)
        .group_by(Station.name)
        .order_by(func.count(Alarm.id).desc())
        .limit(5)
    )
    station_result = await db.execute(station_query)
    top_stations = [{"name": row[0], "count": row[1]} for row in station_result.all()]

    return {
        "kpi": {
            "total_devices": total_devices,
            "down_devices": down_devices,
            "uptime_pct": uptime_pct,
            "total_alarms": total_alarms,
            "active_alarms": active_alarms
        },
        "severity_distribution": severity_data,
        "top_stations": top_stations
    }

@router.get("/export/alarms")
async def export_alarms_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ALARM_READ))
):
    # Fetch all alarms for export
    query = select(Alarm, Device, Station).join(Device, Alarm.device_id == Device.id).join(Station, Device.station_code == Station.code)
    result = await db.execute(query)
    rows = result.all()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write Header
    writer.writerow(["Alarm ID", "Severity", "Status", "Message", "Device", "Station", "First Seen"])

    # Write Data
    for alarm, device, station in rows:
        writer.writerow([
            str(alarm.id),
            alarm.severity,
            alarm.status,
            alarm.message,
            device.hostname,
            station.name,
            alarm.first_seen.strftime("%Y-%m-%d %H:%M:%S")
        ])

    output.seek(0)
    
    # Return as downloadable file
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=nr_ims_alarms_{datetime.now().strftime('%Y%m%d')}.csv"}
    )