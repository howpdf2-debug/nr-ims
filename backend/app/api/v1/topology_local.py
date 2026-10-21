"""Station-local (device level) topology: devices as nodes, device_links as edges.

Shapes are what ``StationDetail.tsx`` (React Flow) consumes. Every read/write goes through the
same scope helpers as the rest of the API, so foreign stations/devices/links answer 404.
"""

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.device import Device
from app.models.device_link import DeviceLink
from app.models.user import User
from app.schemas.topology import DevicePosition, LocalLinkCreate
from app.security.rbac import Permission, require_permission
from app.security.scope import get_device_for_user, require_station
from app.services.audit import record_audit

router = APIRouter(prefix="/topology/local", tags=["topology-local"])


def _edge_label(media_type: str) -> str:
    return "OFC" if media_type == "ofc" else "Cu"


@router.get("/{station_code}")
async def get_local_topology(station_code: str, db: AsyncSession = Depends(get_db),
                             user: User = Depends(require_permission(Permission.DEVICE_READ))):
    await require_station(db, user, station_code)
    devices = (await db.execute(
        select(Device).where(Device.station_code == station_code).order_by(Device.hostname, Device.id))).scalars().all()
    by_id = {d.id: d for d in devices}
    links: Sequence[DeviceLink] = []
    if by_id:
        links = (await db.execute(select(DeviceLink).where(
            DeviceLink.source_device_id.in_(by_id), DeviceLink.destination_device_id.in_(by_id)))).scalars().all()
    nodes = [{
        "id": str(d.id), "type": "deviceNode",
        "data": {"label": d.hostname, "ip": d.ip_address, "category": d.category, "status": d.status,
                 "is_maintenance": d.is_maintenance,
                 "parent_device_id": str(d.parent_device_id) if d.parent_device_id else None},
        "position": {"x": d.position_x or 0, "y": d.position_y or 0},
    } for d in devices]
    edges = []
    for lk in links:
        src, dst = by_id[lk.source_device_id], by_id[lk.destination_device_id]
        edges.append({
            "id": str(lk.id), "source": str(src.id), "target": str(dst.id),
            "label": _edge_label(lk.media_type),
            "data": {"media_type": lk.media_type, "description": lk.description,
                     "source_host": src.hostname, "source_ip": src.ip_address,
                     "dest_host": dst.hostname, "dest_ip": dst.ip_address},
        })
    return {"nodes": nodes, "edges": edges}


@router.post("/links", status_code=201)
async def create_local_link(req: LocalLinkCreate, db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    if req.source_device_id == req.destination_device_id:
        raise HTTPException(422, "A device cannot be linked to itself")
    a = await get_device_for_user(db, user, req.source_device_id)
    b = await get_device_for_user(db, user, req.destination_device_id)
    if a.station_code != b.station_code:
        raise HTTPException(422, "Local links must connect devices of the same station")
    exists = await db.scalar(select(DeviceLink.id).where(or_(
        and_(DeviceLink.source_device_id == a.id, DeviceLink.destination_device_id == b.id),
        and_(DeviceLink.source_device_id == b.id, DeviceLink.destination_device_id == a.id))).limit(1))
    if exists:
        raise HTTPException(409, "These devices are already linked")
    link = DeviceLink(id=uuid.uuid4(), source_device_id=a.id, destination_device_id=b.id,
                      media_type=req.media_type, description=req.description)
    db.add(link)
    record_audit(db, user, "device_link.create", "device_link", link.id,
                 {"source": a.hostname, "destination": b.hostname, "media": req.media_type})
    await db.commit()
    return {"id": str(link.id), "message": "Link created"}


@router.delete("/links/{link_id}")
async def delete_local_link(link_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    link = await db.get(DeviceLink, link_id)
    if link is None:
        raise HTTPException(404, "Link not found")
    try:  # both ends must be in the caller's scope, otherwise the link does not exist for them
        await get_device_for_user(db, user, link.source_device_id)
        await get_device_for_user(db, user, link.destination_device_id)
    except HTTPException:
        raise HTTPException(404, "Link not found") from None
    await db.delete(link)
    record_audit(db, user, "device_link.delete", "device_link", link_id)
    await db.commit()
    return {"message": "Link deleted"}


@router.put("/device/{device_id}/position")
async def save_device_position(device_id: uuid.UUID, pos: DevicePosition, db: AsyncSession = Depends(get_db),
                               user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    device = await get_device_for_user(db, user, device_id)
    device.position_x, device.position_y = pos.x, pos.y
    await db.commit()
    return {"message": "Position saved"}
