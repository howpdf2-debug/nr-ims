import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.action import RemoteAction
from app.models.audit import AuditEvent
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission
from app.security.scope import get_device_for_user, scope_stations

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
async def get_audit_logs(skip: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000),
                         db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_permission(Permission.AUDIT_READ))):
    q = (select(RemoteAction, Device).join(Device, RemoteAction.device_id == Device.id)
         .join(Station, Device.station_code == Station.code))
    q = scope_stations(q, user).order_by(RemoteAction.created_at.desc()).offset(skip).limit(limit)
    return [{"id": str(a.id), "device_hostname": d.hostname, "device_ip": d.ip_address,
             "action_type": a.action_type, "status": a.status, "performed_by": a.performed_by,
             "created_at": a.created_at.isoformat()} for a, d in (await db.execute(q)).all()]


@router.get("/events")
async def get_audit_events(skip: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000),
                           db: AsyncSession = Depends(get_db),
                           user: User = Depends(require_permission(Permission.USER_MANAGE))):
    q = select(AuditEvent).order_by(AuditEvent.created_at.desc()).offset(skip).limit(limit)
    return [{"id": str(e.id), "actor_id": str(e.actor_id) if e.actor_id else None, "action": e.action,
             "target_type": e.target_type, "target_id": e.target_id, "payload": e.payload,
             "created_at": e.created_at.isoformat()} for e in (await db.execute(q)).scalars()]


@router.get("/device/{device_id}")
async def get_device_audit(device_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                           user: User = Depends(require_permission(Permission.DEVICE_READ))):
    await get_device_for_user(db, user, device_id)
    q = select(RemoteAction).where(RemoteAction.device_id == device_id).order_by(RemoteAction.created_at.desc())
    return [{"id": str(a.id), "action_type": a.action_type, "status": a.status,
             "performed_by": a.performed_by, "created_at": a.created_at.isoformat()}
            for a in (await db.execute(q)).scalars()]
