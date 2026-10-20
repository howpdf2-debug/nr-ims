from enum import StrEnum

from fastapi import Depends, HTTPException

from app.deps import get_current_user
from app.models.user import User


class Permission(StrEnum):
    DEVICE_READ = "device:read"
    DEVICE_WRITE = "device:write"
    ALARM_READ = "alarm:read"
    ALARM_ACK = "alarm:ack"
    AUDIT_READ = "audit:read"
    USER_MANAGE = "user:manage"
    STATION_MANAGE = "station:manage"
    DISCOVERY_MANAGE = "discovery:manage"


class Role(StrEnum):
    IRCA_ADMIN = "irca_admin"
    DIVISIONAL_ADMIN = "divisional_admin"
    TIER1_INCHARGE = "tier1_incharge"
    OPERATOR = "operator"


_RW = {Permission.DEVICE_READ, Permission.DEVICE_WRITE, Permission.ALARM_READ, Permission.ALARM_ACK}
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.IRCA_ADMIN: set(Permission),
    Role.DIVISIONAL_ADMIN: _RW | {Permission.STATION_MANAGE, Permission.AUDIT_READ},
    Role.TIER1_INCHARGE: set(_RW),
    Role.OPERATOR: {Permission.DEVICE_READ, Permission.ALARM_READ},
}


def require_permission(permission: Permission):
    async def _guard(user: User = Depends(get_current_user)) -> User:
        try:
            role = Role(user.role)
        except ValueError:
            raise HTTPException(403, "Invalid role") from None
        if permission not in ROLE_PERMISSIONS.get(role, set()):
            raise HTTPException(403, "Not enough permissions")
        return user

    return _guard
