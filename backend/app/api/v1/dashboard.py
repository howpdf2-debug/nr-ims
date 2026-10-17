from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from app.deps import get_db
from app.models.device import Device
from app.models.station import Station
from app.security.rbac import Permission, require_permission

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/divisions")
async def get_division_summary(db: AsyncSession = Depends(get_db), _=Depends(require_permission(Permission.DEVICE_READ))):
    # सभी डिवीजन्स को ग्रुप करें
    stmt = select(Station.division, func.count(Station.code).label("total_stations")).group_by(Station.division)
    res = await db.execute(stmt)
    
    divisions = []
    for row in res:
        # हर डिवीजन के डाउन डिवाइसेस गिनें
        dev_stmt = select(func.count(Device.id)).join(Station).where(Station.division == row.division, Device.status == "down")
        down_res = await db.execute(dev_stmt)
        down_count = down_res.scalar() or 0
        
        divisions.append({
            "division": row.division,
            "total_stations": row.total_stations,
            "down_devices": down_count,
            "status": "critical" if down_count > 0 else "healthy"
        })
    return divisions

@router.get("/divisions/{division_code}/stations")
async def get_division_stations(division_code: str, db: AsyncSession = Depends(get_db), _=Depends(require_permission(Permission.DEVICE_READ))):
    stmt = select(Station).where(Station.division == division_code)
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