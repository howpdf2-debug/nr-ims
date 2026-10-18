from enum import StrEnum
from fastapi import Depends, HTTPException, status
from app.deps import get_current_user
from app.models.user import User

class Permission(StrEnum):
    DEVICE_READ = "device:read"
    DEVICE_WRITE = "device:write" 
    ALARM_READ = "alarm:read"
    ALARM_ACK = "alarm:ack"
    AUDIT_READ = "audit:read" # <-- नई परमिशन

class Role(StrEnum):
    IRCA_ADMIN = "irca_admin"
    DIVISIONAL_ADMIN = "divisional_admin"
    TIER1_INCHARGE = "tier1_incharge"
    OPERATOR = "operator"

ROLE_PERMISSIONS = {
    Role.IRCA_ADMIN: set(Permission), # IRCA Admin के पास सब कुछ
    Role.DIVISIONAL_ADMIN: {
        Permission.DEVICE_READ, Permission.DEVICE_WRITE, 
        Permission.ALARM_READ, Permission.ALARM_ACK
        # नोट: इनके पास AUDIT_READ नहीं है
    },
    Role.TIER1_INCHARGE: {
        Permission.DEVICE_READ, Permission.DEVICE_WRITE, 
        Permission.ALARM_READ, Permission.ALARM_ACK
    },
    Role.OPERATOR: { Permission.DEVICE_READ, Permission.ALARM_READ }
}

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