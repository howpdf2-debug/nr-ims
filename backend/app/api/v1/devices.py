"""Devices API: scoped list (with total count), detail composite, create, delete.

Contract notes
- ``GET /devices/{id}`` stays the flat resource (unchanged, backward compatible).
- ``GET /devices/{id}/detail`` is the composite the device page needs (device + interfaces + OSPF).
- ``GET /devices/`` sets ``X-Total-Count`` so callers never infer totals from a capped page.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.device import Device
from app.models.device_link import DeviceLink
from app.models.interface import Interface
from app.models.station import Station
from app.models.user import User
from app.schemas.device import DeviceCreate, DeviceDetail, DeviceRead, InterfaceRead
from app.security.rbac import Permission, require_permission
from app.security.scope import get_device_for_user, require_station, scope_stations
from app.services.audit import record_audit

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/", response_model=list[DeviceRead])
async def list_devices(
    response: Response,
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
    station_code: str | None = None, category: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission(Permission.DEVICE_READ)),
):
    base = select(Device).join(Station, Device.station_code == Station.code)
    if station_code:
        base = base.where(Device.station_code == station_code)
    if category:
        base = base.where(Device.category == category)
    base = scope_stations(base, user)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    response.headers["X-Total-Count"] = str(total)
    q = base.order_by(Device.hostname, Device.id).offset(skip).limit(limit)
    return (await db.execute(q)).scalars().all()


@router.post("/", response_model=DeviceRead, status_code=201)
async def create_device(body: DeviceCreate, db: AsyncSession = Depends(get_db),
                        user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    await require_station(db, user, body.station_code)  # 404 for stations outside the caller's scope
    if body.parent_device_id is not None:
        parent = await get_device_for_user(db, user, body.parent_device_id)
        if parent.station_code != body.station_code:
            raise HTTPException(422, "Parent device must belong to the same station")
    clash = await db.scalar(
        select(func.count(Device.id)).where(
            Device.station_code == body.station_code,
            or_(func.lower(Device.hostname) == body.hostname.lower(), Device.ip_address == body.ip_address),
        )
    ) or 0
    if clash:
        raise HTTPException(409, "A device with this hostname or IP already exists in this station")

    device = Device(
        id=uuid.uuid4(), external_id=f"MAN-{uuid.uuid4().hex[:8]}", hostname=body.hostname,
        ip_address=body.ip_address, category=body.category.value, status="unknown",  # no poller yet: do not claim "up"
        station_code=body.station_code, parent_device_id=body.parent_device_id,
        source_system="manual", source_timestamp=datetime.now(UTC),
    )
    db.add(device)
    record_audit(db, user, "device.create", "device", device.id,
                 {"hostname": device.hostname, "ip": device.ip_address, "station": device.station_code,
                  "category": device.category})
    await db.commit()
    await db.refresh(device)
    return device


@router.get("/{device_id}", response_model=DeviceRead)
async def get_device(device_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                     user: User = Depends(require_permission(Permission.DEVICE_READ))):
    return await get_device_for_user(db, user, device_id)


@router.get("/{device_id}/detail", response_model=DeviceDetail)
async def get_device_detail(device_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_permission(Permission.DEVICE_READ))):
    device = await get_device_for_user(db, user, device_id)
    ifaces = (await db.execute(
        select(Interface).where(Interface.device_id == device.id).order_by(Interface.name))).scalars().all()
    return DeviceDetail(
        device=DeviceRead.model_validate(device),
        interfaces=[InterfaceRead.model_validate(i) for i in ifaces],
        ospf_neighbors=[],  # collected by the monitoring engine (Phase 3); empty list is the honest answer today
    )


@router.delete("/{device_id}")
async def delete_device(device_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                        user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    device = await get_device_for_user(db, user, device_id)
    links = await db.scalar(select(func.count(DeviceLink.id)).where(
        or_(DeviceLink.source_device_id == device.id, DeviceLink.destination_device_id == device.id))) or 0
    # Children keep their place in the hierarchy: move them up to the deleted device's parent.
    await db.execute(update(Device).where(Device.parent_device_id == device.id)
                     .values(parent_device_id=device.parent_device_id))
    snapshot = {"hostname": device.hostname, "ip": device.ip_address, "station": device.station_code,
                "links_deleted": links}
    await db.delete(device)  # alarms/interfaces: ORM cascade; links/actions: FK ON DELETE CASCADE
    record_audit(db, user, "device.delete", "device", device_id, snapshot)
    await db.commit()
    return {"message": "Device deleted", "links_deleted": links}
