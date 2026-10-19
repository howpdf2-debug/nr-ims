from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.deps import get_db
from app.models.action import RemoteAction
from app.models.device import Device
from app.models.user import User
from app.security.rbac import Permission, require_permission

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/logs")
async def get_audit_logs(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.AUDIT_READ))):
    query = select(RemoteAction, Device).join(Device, RemoteAction.device_id == Device.id).order_by(RemoteAction.created_at.desc())
    result = await db.execute(query)
    return [{"id": str(a.id), "device_hostname": d.hostname, "device_ip": d.ip_address, "action_type": a.action_type, "status": a.status, "performed_by": a.performed_by, "created_at": a.created_at.isoformat()} for a, d in result.all()]

@router.get("/device/{device_id}")
async def get_device_audit(device_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_READ))):
    query = select(RemoteAction).where(RemoteAction.device_id == device_id).order_by(RemoteAction.created_at.desc())
    result = await db.execute(query)
    return [{"id": str(a.id), "action_type": a.action_type, "status": a.status, "performed_by": a.performed_by, "created_at": a.created_at.isoformat()} for a in result.scalars().all()]