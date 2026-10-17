from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.deps import get_db
from app.models.alarm import Alarm
from app.models.device import Device
from app.schemas.alarm import AlarmRead
from app.security.rbac import Permission, require_permission

router = APIRouter(prefix="/alarms", tags=["alarms"])

# CRIS NMS स्टाइल का Event Correlation Engine
def correlate_alarms(alarms: List[Alarm]) -> List[Alarm]:
    severity_rank = {"critical": 4, "major": 3, "minor": 2, "warning": 1, "info": 0}
    correlated = {}
    
    for alarm in alarms:
        existing = correlated.get(alarm.device_id)
        # अगर उस डिवाइस के लिए पहले से कोई अलार्म है, तो सिर्फ ज्यादा सीरियस वाला रखें
        if not existing or severity_rank.get(alarm.severity, 0) > severity_rank.get(existing.severity, 0):
            correlated[alarm.device_id] = alarm
            
    return list(correlated.values())

@router.get("/", response_model=List[AlarmRead])
async def list_alarms(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission(Permission.ALARM_READ))
):
    """
    Fetch all active alarms (with Correlation applied).
    Returns only the most critical alarm per device.
    """
    # सिर्फ एक्टिव (Active) अलार्म्स फेच करें
    result = await db.execute(
        select(Alarm).where(Alarm.status == "active").order_by(Alarm.first_seen.desc())
    )
    raw_alarms = result.scalars().all()
    
    # कोरिलेशन लागू करें
    correlated_alarms = correlate_alarms(raw_alarms)
    return correlated_alarms

@router.get("/device/{device_id}", response_model=List[AlarmRead])
async def get_device_alarms(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission(Permission.ALARM_READ))
):
    """किसी विशेष डिवाइस के सभी अलार्म्स (कोई कोरिलेशन नहीं, ताकि इंजीनियर को पूरा इतिहास दिखे)"""
    result = await db.execute(
        select(Alarm).where(
            Alarm.device_id == device_id, 
            Alarm.status == "active"
        ).order_by(Alarm.first_seen.desc())
    )
    return result.scalars().all()