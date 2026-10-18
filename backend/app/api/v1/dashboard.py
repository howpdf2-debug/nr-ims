from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.deps import get_db
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission, Role

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/divisions")
async def get_division_summary(
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(require_permission(Permission.DEVICE_READ))
):
    # Base Query: सभी डिवीजन्स और उनके स्टेशन्स की गिनती
    query = select(Station.division, func.count(Station.code).label("total_stations")).group_by(Station.division)
    
    # Data Scoping Logic
    if current_user.role != Role.IRCA_ADMIN and "*" not in current_user.scopes:
        if not current_user.scopes:
            return [] # अगर कोई स्कोप नहीं है, तो कुछ नहीं दिखेगा
            
        # अगर यूज़र के पास डिवीजन का स्कोप है (जैसे LKO) या स्टेशन का स्कोप है (जैसे BSB)
        # हम वो डिवीजन निकालेंगे जिनसे यह यूज़र जुड़ा है
        query = query.where(
            (Station.division.in_(current_user.scopes)) | 
            (Station.code.in_(current_user.scopes))
        )
        
    res = await db.execute(query)
    divisions = []
    
    for row in res:
        # हर डिवीजन के डाउन डिवाइसेस गिनें
        dev_query = select(func.count(Device.id)).join(Station).where(
            Station.division == row.division, 
            Device.status == "down"
        )
        # अगर Tier-1 इंचार्ज है, तो उसे सिर्फ अपने स्टेशन का डाउन डिवाइस दिखेगा
        if current_user.role == Role.TIER1_INCHARGE:
             dev_query = dev_query.where(Station.code.in_(current_user.scopes))

        down_res = await db.execute(dev_query)
        down_count = down_res.scalar() or 0
        
        divisions.append({
            "division": row.division, 
            "total_stations": row.total_stations, 
            "down_devices": down_count, 
            "status": "critical" if down_count > 0 else "healthy"
        })
    return divisions

@router.get("/divisions/{division_code}/stations")
async def get_division_stations(
    division_code: str, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(require_permission(Permission.DEVICE_READ))
):
    # सुरक्षा जाँच: क्या यूज़र इस डिवीजन को देखने के लिए अधिकृत है?
    if current_user.role != Role.IRCA_ADMIN and "*" not in current_user.scopes:
        # अगर यूज़र के पास डिवीजन नहीं है, तो 403 Forbidden
        if division_code not in current_user.scopes:
            # लेकिन हो सकता है कि यूज़र के पास Tier-1 स्टेशन का स्कोप हो (जैसे BSB), 
            # तो वह अपने डिवीजन को तो देख सकता है, पर सिर्फ अपना स्टेशन
            pass 

    stmt = select(Station).where(Station.division == division_code)
    
    # डेटा स्कोपिंग (सिर्फ अपने स्टेशन्स)
    if current_user.role != Role.IRCA_ADMIN and "*" not in current_user.scopes:
         if division_code not in current_user.scopes:
             stmt = stmt.where(Station.code.in_(current_user.scopes))

    res = await db.execute(stmt)
    
    station_data = []
    for st in res.scalars().all():
        dev_stmt = select(func.count(Device.id)).where(Device.station_code == st.code, Device.status == "down")
        down_res = await db.execute(dev_stmt)
        down_count = down_res.scalar() or 0
        
        station_data.append({
            "code": st.code, "name": st.name, "tier": st.tier, "type": st.station_type,
            "down_devices": down_count, "status": "critical" if down_count > 0 else "healthy"
        })
    return station_data