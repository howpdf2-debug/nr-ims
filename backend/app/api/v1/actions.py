from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
import asyncio
from datetime import datetime, timezone

from app.deps import get_db, get_current_user
from app.models.user import User
from app.models.device import Device
from app.models.station import Station
from app.models.action import RemoteAction
from app.security.rbac import Permission, require_permission, Role

router = APIRouter(prefix="/actions", tags=["actions"])

class ActionRequest(BaseModel):
    device_id: uuid.UUID
    action_type: str # "PING", "RESTART_PORT", "REBOOT"

@router.get("/down-devices")
async def get_down_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.DEVICE_READ))
):
    query = select(Device, Station).join(Station).where(Device.status == "down")
    
    if current_user.role != Role.IRCA_ADMIN and "*" not in current_user.scopes:
        query = query.where(Station.division.in_(current_user.scopes))

    res = await db.execute(query)
    return [
        {
            "device_id": str(d.id), "hostname": d.hostname, "category": d.category,
            "station_code": s.code, "station_name": s.name, "ip_address": d.ip_address
        } for d, s in res.all()
    ]

@router.post("/execute")
async def execute_action(
    req: ActionRequest, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(require_permission(Permission.DEVICE_WRITE))
):
    res = await db.execute(select(Device).where(Device.id == req.device_id))
    device = res.scalar_one_or_none()
    if not device: raise HTTPException(status_code=404, detail="Device not found")

    # Command Simulation
    await asyncio.sleep(1.5) # Simulate network delay
    output = ""
    
    if req.action_type == "PING":
        output = f"Pinging {device.ip_address} with 32 bytes of data:\nReply from {device.ip_address}: bytes=32 time<1ms TTL=64\nReply from {device.ip_address}: bytes=32 time<1ms TTL=64\n\nPing statistics for {device.ip_address}:\n    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss)"
    elif req.action_type == "RESTART_PORT":
        output = f"Connecting to {device.ip_address}...\nUsername: admin\nPassword: ********\n\n{device.hostname}# configure terminal\n{device.hostname}(config)# interface GigabitEthernet0/1\n{device.hostname}(config-if)# shutdown\n{device.hostname}(config-if)# no shutdown\n\n! Port Gi0/1 has been reset successfully."
        device.status = "up" # Auto-fix for simulation
    elif req.action_type == "REBOOT":
        output = f"Connecting to {device.ip_address}...\n{device.hostname}# reload\nSystem configuration has been modified. Save? [yes/no]: no\nProceed with reload? [confirm]\n\n*** System going down NOW ***"
        device.status = "up" # Auto-fix for simulation

    action = RemoteAction(
        device_id=device.id, action_type=req.action_type, status="success", 
        output_log=output, performed_by=current_user.email
    )
    db.add(action)
    await db.commit()
    
    return {"message": "Action executed", "output": output}