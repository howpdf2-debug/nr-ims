from enum import StrEnum
from fastapi import Depends, HTTPException, status
from app.deps import get_current_user
from app.models.user import User

class Permission(StrEnum):
    DEVICE_READ = "device:read"
    DEVICE_WRITE = "device:write"  # <-- यह नई परमिशन जोड़ी गई है
    ALARM_READ = "alarm:read"
    ALARM_ACK = "alarm:ack"

class Role(StrEnum):
    ZONAL_ADMIN = "zonal_admin"

# Zonal Admin को सारी परमिशन मिलेंगी
ROLE_PERMISSIONS = {Role.ZONAL_ADMIN: set(Permission)}

def require_permission(permission: Permission):
    async def _guard(user: User = Depends(get_current_user)) -> User:
        try:
            role = Role(user.role)
            if permission not in ROLE_PERMISSIONS.get(role, set()):
                raise HTTPException(status_code=403, detail="Not enough permissions")
        except ValueError:
            raise HTTPException(status_code=403, detail="Invalid role")
        return user
    return _guard
    