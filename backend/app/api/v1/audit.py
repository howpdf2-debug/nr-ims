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
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AUDIT_READ)) # <-- सिर्फ IRCA Admin
):
    query = select(RemoteAction, Device).join(Device, RemoteAction.device_id == Device.id).order_by(RemoteAction.created_at.desc())
    result = await db.execute(query)
    
    logs = []
    for action, device in result.all():
        logs.append({
            "id": str(action.id),
            "device_hostname": device.hostname,
            "device_ip": device.ip_address,
            "action_type": action.action_type,
            "status": action.status,
            "performed_by": action.performed_by,
            "created_at": action.created_at.isoformat(),
            "output_log": action.output_log
        })
    return logs