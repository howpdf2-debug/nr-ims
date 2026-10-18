from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
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

class PositionUpdate(BaseModel):
    x: float
    y: float

class LocalLinkCreate(BaseModel):
    source_device_id: str
    destination_device_id: str
    media_type: str
    description: str | None = None

@router.get("/")
async def get_topology(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_READ))):
    st_query = select(Station)
    if current_user.role != Role.IRCA_ADMIN and "*" not in current_user.scopes:
        st_query = st_query.where(Station.division.in_(current_user.scopes))
    stations = (await db.execute(st_query)).scalars().all()
    links = (await db.execute(select(Link))).scalars().all()
    return {
        "nodes": [{"id": st.code, "type": "customNode", "data": {"label": st.name, "code": st.code, "tier": st.tier, "division": st.division}, "position": {"x": st.position_x or 0, "y": st.position_y or 0}} for st in stations],
        "edges": [{"id": str(l.id), "source": l.source_station, "target": l.destination_station, "label": f"{l.provider} ({l.bandwidth_mbps}M)", "data": {"provider": l.provider, "status": l.status, "bandwidth": l.bandwidth_mbps}} for l in links]
    }

@router.get("/local/{station_code}")
async def get_local_topology(station_code: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_READ))):
    station = (await db.execute(select(Station).where(Station.code == station_code))).scalar_one_or_none()
    if not station: raise HTTPException(404, "Station not found")
    
    # Data Scoping
    if current_user.role != Role.IRCA_ADMIN and "*" not in current_user.scopes:
        if station.division not in current_user.scopes:
            raise HTTPException(403, "Unauthorized to view this station")

    devices = (await db.execute(select(Device).where(Device.station_code == station_code))).scalars().all()
    if not devices: return {"nodes": [], "edges": []}

    device_ids = [d.id for d in devices]
    device_map = {str(d.id): d for d in devices}
    
    device_links = (await db.execute(select(DeviceLink).where((DeviceLink.source_device_id.in_(device_ids)) | (DeviceLink.destination_device_id.in_(device_ids))))).scalars().all()

    nodes = [{"id": str(d.id), "type": "deviceNode", "data": {"label": d.hostname, "category": d.category, "status": d.status, "ip": d.ip_address}, "position": {"x": d.position_x or 0, "y": d.position_y or 0}} for d in devices]
    edges = []
    for l in device_links:
        is_ofc = l.media_type.lower() == 'ofc'
        src, dst = device_map.get(str(l.source_device_id)), device_map.get(str(l.destination_device_id))
        edges.append({
            "id": str(l.id), "source": str(l.source_device_id), "target": str(l.destination_device_id),
            "label": "OFC" if is_ofc else "Cu",
            "data": {"description": l.description, "media_type": l.media_type, "source_ip": src.ip_address if src else "N/A", "dest_ip": dst.ip_address if dst else "N/A", "source_host": src.hostname if src else "Unknown", "dest_host": dst.hostname if dst else "Unknown"},
            "animated": is_ofc, "style": {"stroke": "#10b981" if is_ofc else "#f59e0b", "strokeWidth": 3 if is_ofc else 2}
        })
    return {"nodes": nodes, "edges": edges}

@router.post("/local/links")
async def create_local_link(req: LocalLinkCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    new_link = DeviceLink(id=uuid.uuid4(), source_device_id=uuid.UUID(req.source_device_id), destination_device_id=uuid.UUID(req.destination_device_id), media_type=req.media_type, description=req.description)
    db.add(new_link); await db.commit()
    return {"message": "Local link created"}

@router.delete("/local/links/{link_id}")
async def delete_local_link(link_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    link = (await db.execute(select(DeviceLink).where(DeviceLink.id == link_id))).scalar_one_or_none()
    if not link: raise HTTPException(404, "Link not found")
    await db.delete(link); await db.commit()
    return {"message": "Local link deleted"}