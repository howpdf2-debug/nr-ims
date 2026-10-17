from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
import uuid
from app.deps import get_db, get_current_user
from app.models.user import User
from app.models.device import Device
from app.models.action import RemoteAction
from app.security.rbac import Permission, require_permission
from sqlalchemy import select

router = APIRouter(prefix="/actions", tags=["actions"])

class ActionRequest(BaseModel):
    device_id: uuid.UUID
    interface_name: Optional[str] = None
    action_type: str

@router.post("/execute")
async def execute_action(req: ActionRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    res = await db.execute(select(Device).where(Device.id == req.device_id))
    device = res.scalar_one_or_none()
    if not device: raise HTTPException(status_code=404, detail="Device not found")

    output_log = f"Simulated {req.action_type} on {req.interface_name or device.hostname}"
    action = RemoteAction(device_id=device.id, interface_name=req.interface_name, action_type=req.action_type, status="success", output_log=output_log, performed_by=current_user.email)
    db.add(action)
    await db.commit()
    return {"message": "Action executed successfully", "output": output_log}
