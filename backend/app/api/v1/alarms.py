from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime, timezone
from app.deps import get_db, get_current_user
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission, Role

router = APIRouter(prefix="/alarms", tags=["alarms"])

# Correlation Engine: सिर्फ सबसे खतरनाक अलार्म दिखाएगा
def correlate_alarms(alarms: List[Alarm]) -> List[Alarm]:
    severity_rank = {"critical": 4, "major": 3, "minor": 2, "warning": 1, "info": 0}
    correlated = {}
    for alarm in alarms:
        existing = correlated.get(alarm.device_id)
        if not existing or severity_rank.get(alarm.severity, 0) > severity_rank.get(existing.severity, 0):
            correlated[alarm.device_id] = alarm
    return list(correlated.values())

@router.get("/")
async def list_alarms(
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(require_permission(Permission.ALARM_READ))
):
    # Join Alarm, Device, and Station
    query = select(Alarm, Device, Station).join(Device, Alarm.device_id == Device.id).join(Station, Device.station_code == Station.code)
    
    # Data Scoping
    if current_user.role != Role.IRCA_ADMIN and "*" not in current_user.scopes:
        query = query.where(Station.division.in_(current_user.scopes))
        
    result = await db.execute(query.order_by(Alarm.first_seen.desc()))
    raw_data = result.all()
    
    # Extract just the alarms for correlation
    raw_alarms = [row[0] for row in raw_data]
    correlated = correlate_alarms(raw_alarms)
    
    # Enrich with device and station info
    enriched_alarms = []
    for alarm in correlated:
        # Find matching device and station from raw_data
        device = next((row[1] for row in raw_data if row[0].id == alarm.id), None)
        station = next((row[2] for row in raw_data if row[0].id == alarm.id), None)
        
        enriched_alarms.append({
            "id": str(alarm.id),
            "device_id": str(alarm.device_id),
            "device_name": device.hostname if device else "Unknown",
            "station_code": station.code if station else "Unknown",
            "station_name": station.name if station else "Unknown",
            "severity": alarm.severity,
            "message": alarm.message,
            "status": alarm.status,
            "first_seen": alarm.first_seen.isoformat(),
            "acked_by": alarm.acked_by
        })
        
    return enriched_alarms

@router.patch("/{alarm_id}/ack")
async def acknowledge_alarm(
    alarm_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.ALARM_ACK))
):
    res = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = res.scalar_one_or_none()
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")
        
    alarm.status = "acknowledged"
    alarm.acked_by = current_user.email
    alarm.acked_at = datetime.now(timezone.utc)
    await db.commit()
    
    return {"message": "Alarm acknowledged successfully"}