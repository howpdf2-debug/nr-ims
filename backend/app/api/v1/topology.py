import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.link import Link
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission
from app.security.scope import require_station, scope_stations
from app.services.audit import record_audit

router = APIRouter(prefix="/topology", tags=["topology"])


class LinkStatusUpdate(BaseModel):
    status: str
    is_admin: bool = False


class PositionUpdate(BaseModel):
    x: float
    y: float


@router.get("/")
async def get_topology(db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_permission(Permission.DEVICE_READ))):
    stations = (await db.execute(scope_stations(select(Station), user))).scalars().all()
    visible = {s.code for s in stations}
    links = [lk for lk in (await db.execute(select(Link))).scalars().all()
             if lk.source_station in visible or lk.destination_station in visible]  # no leaking foreign nodes
    return {
        "nodes": [{"id": s.code, "type": "customNode",
                   "data": {"label": s.name, "code": s.code, "tier": s.tier, "division": s.division},
                   "position": {"x": s.position_x or 0, "y": s.position_y or 0}} for s in stations],
        "edges": [{"id": str(lk.id), "source": lk.source_station, "target": lk.destination_station,
                   "label": f"{lk.provider} ({lk.bandwidth_mbps}M)",
                   "data": {"provider": lk.provider, "status": lk.status, "bandwidth": lk.bandwidth_mbps,
                            "latency": lk.latency_ms, "packet_loss": lk.packet_loss_pct,
                            "crc": lk.crc_errors, "is_admin_shutdown": lk.is_admin_shutdown}}
                  for lk in links if lk.source_station in visible and lk.destination_station in visible],
    }


@router.put("/links/{link_id}/status")
async def toggle_link_status(link_id: uuid.UUID, req: LinkStatusUpdate, db: AsyncSession = Depends(get_db),
                             user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    if req.status not in {"up", "down", "degraded"}:
        raise HTTPException(422, "status must be up, down or degraded")
    link = await db.get(Link, link_id)
    if not link:
        raise HTTPException(404, "Link not found")
    await require_station(db, user, link.source_station)
    link.status = req.status
    link.is_admin_shutdown = req.is_admin and req.status == "down"
    link.packet_loss_pct = 100.0 if req.status == "down" else 0.0
    record_audit(db, user, "link.status", "link", link.id, {"status": req.status})
    await db.commit()
    return {"message": f"Link status changed to {req.status}"}


@router.put("/station/{station_code}/position")
async def save_station_position(station_code: str, pos: PositionUpdate, db: AsyncSession = Depends(get_db),
                                user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    await require_station(db, user, station_code)
    st = await db.get(Station, station_code)
    assert st is not None  # guaranteed by require_station
    st.position_x, st.position_y = pos.x, pos.y
    await db.commit()
    return {"message": "Position saved"}
