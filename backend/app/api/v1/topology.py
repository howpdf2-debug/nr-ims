from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
from app.deps import get_db
from app.models.station import Station
from app.models.link import Link
from app.models.device import Device
from app.models.device_link import DeviceLink
from app.models.user import User
from app.security.rbac import Permission, require_permission, Role

router = APIRouter(prefix="/topology", tags=["topology"])

class LinkStatusUpdate(BaseModel):
    status: str
    is_admin: bool = False

class PositionUpdate(BaseModel):
    x: float
    y: float

@router.get("/")
async def get_topology(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_READ))):
    st_query = select(Station)
    if current_user.role != Role.IRCA_ADMIN and "*" not in current_user.scopes:
        st_query = st_query.where(Station.division.in_(current_user.scopes))
    stations = (await db.execute(st_query)).scalars().all()
    links = (await db.execute(select(Link))).scalars().all()
    
    return {
        "nodes": [{"id": st.code, "type": "customNode", "data": {"label": st.name, "code": st.code, "tier": st.tier, "division": st.division}, "position": {"x": st.position_x or 0, "y": st.position_y or 0}} for st in stations],
        "edges": [{
            "id": str(l.id), "source": l.source_station, "target": l.destination_station, 
            "label": f"{l.provider} ({l.bandwidth_mbps}M)", 
            "data": {"provider": l.provider, "status": l.status, "bandwidth": l.bandwidth_mbps, "latency": l.latency_ms, "packet_loss": l.packet_loss_pct, "crc": l.crc_errors, "is_admin_shutdown": l.is_admin_shutdown} 
        } for l in links]
    }

@router.put("/links/{link_id}/status")
async def toggle_link_status(link_id: str, req: LinkStatusUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    link = (await db.execute(select(Link).where(Link.id == link_id))).scalar_one_or_none()
    if not link: raise HTTPException(404, "Link not found")
    link.status = req.status
    link.is_admin_shutdown = req.is_admin
    link.packet_loss_pct = 100.0 if req.status == "down" else 0.0
    await db.commit()
    return {"message": f"Link status changed to {req.status}"}

@router.put("/station/{station_code}/position")
async def save_station_position(station_code: str, pos: PositionUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    st = (await db.execute(select(Station).where(Station.code == station_code))).scalar_one_or_none()
    if not st: raise HTTPException(status_code=404, detail="Station not found")
    st.position_x = pos.x; st.position_y = pos.y
    await db.commit()
    return {"message": "Position saved"}