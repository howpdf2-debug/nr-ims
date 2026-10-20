import uuid
from enum import StrEnum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DataProvider
from app.deps import get_db
from app.models.action import RemoteAction
from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission
from app.security.scope import get_device_for_user, scope_stations
from app.services.audit import record_audit
from fastapi import Request

router = APIRouter(prefix="/actions", tags=["actions"])


class ActionType(StrEnum):
    PING = "PING"
    RESTART_PORT = "RESTART_PORT"
    REBOOT = "REBOOT"


class ActionRequest(BaseModel):
    device_id: uuid.UUID
    action_type: ActionType


class MaintenanceUpdate(BaseModel):
    is_maintenance: bool


@router.get("/down-devices")
async def get_down_devices(db: AsyncSession = Depends(get_db),
                           user: User = Depends(require_permission(Permission.DEVICE_READ))):
    q = (select(Device, Station).join(Station, Device.station_code == Station.code)
         .where(Device.status.in_(["down", "maintenance"])))
    rows = (await db.execute(scope_stations(q, user))).all()
    return [{"device_id": str(d.id), "hostname": d.hostname, "category": d.category,
             "station_code": s.code, "station_name": s.name, "ip_address": d.ip_address,
             "is_maintenance": d.is_maintenance, "status": d.status} for d, s in rows]


@router.post("/execute")
async def execute_action(req: ActionRequest, request: Request, db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    device = await get_device_for_user(db, user, req.device_id)
    if request.app.state.settings.data_provider is not DataProvider.SIMULATOR:
        # No real executor is wired up yet; never pretend a live device was touched.
        raise HTTPException(501, "Remote execution backend not configured for live data")

    ip, host = device.ip_address, device.hostname
    if req.action_type is ActionType.PING:
        output = f"[SIMULATED] Reply from {ip}: bytes=32 time<1ms TTL=64\n4 sent, 4 received, 0% loss"
    elif req.action_type is ActionType.RESTART_PORT:
        output = f"[SIMULATED] {host}# interface Gi0/1\n shutdown\n no shutdown\n! Port reset successful."
        device.status = "up"
    else:
        output = f"[SIMULATED] {host}# reload\n*** System going down NOW ***"
        device.status = "up"

    db.add(RemoteAction(device_id=device.id, action_type=req.action_type.value, status="success",
                        output_log=output, performed_by=user.email))
    record_audit(db, user, "device.action", "device", device.id, {"action": req.action_type.value})
    await db.commit()
    return {"message": "Action executed", "output": output}


@router.put("/{device_id}/maintenance")
async def toggle_maintenance(device_id: uuid.UUID, req: MaintenanceUpdate,
                             db: AsyncSession = Depends(get_db),
                             user: User = Depends(require_permission(Permission.DEVICE_WRITE))):
    device = await get_device_for_user(db, user, device_id)
    device.is_maintenance = req.is_maintenance
    device.status = "maintenance" if req.is_maintenance else "down"
    record_audit(db, user, "device.maintenance", "device", device.id, {"enabled": req.is_maintenance})
    await db.commit()
    return {"message": f"Maintenance mode {'enabled' if req.is_maintenance else 'disabled'}"}
