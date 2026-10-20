"""Single source of truth for data scoping (RBAC scopes -> SQL filters).

A scope entry matches a station when it equals the station's division, its code,
or its parent's code (so Tier-1 'BSB' sees BSB and its child stations).
IRCA admins and '*' scopes are unrestricted. Empty scopes see nothing.
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Role


def is_unrestricted(user: User) -> bool:
    return user.role == Role.IRCA_ADMIN or "*" in (user.scopes or [])


def station_clause(user: User):
    """SQL clause over `Station`, or None when the user is unrestricted."""
    if is_unrestricted(user):
        return None
    scopes = list(user.scopes or [])
    if not scopes:
        return false()
    return or_(
        Station.division.in_(scopes),
        Station.code.in_(scopes),
        Station.parent_station_code.in_(scopes),
    )


def scope_stations(query, user: User):
    """Apply scope to any query that already selects/joins `Station`."""
    clause = station_clause(user)
    return query if clause is None else query.where(clause)


async def can_see_station(db: AsyncSession, user: User, code: str) -> bool:
    q = scope_stations(select(Station.code).where(Station.code == code), user)
    return (await db.execute(q)).first() is not None


async def require_station(db: AsyncSession, user: User, code: str) -> None:
    if not await can_see_station(db, user, code):
        raise HTTPException(404, "Station not found")  # 404, not 403: don't leak existence


async def get_device_for_user(db: AsyncSession, user: User, device_id: uuid.UUID) -> Device:
    q = scope_stations(
        select(Device).join(Station, Device.station_code == Station.code).where(Device.id == device_id),
        user,
    )
    device = (await db.execute(q)).scalar_one_or_none()
    if device is None:
        raise HTTPException(404, "Device not found")
    return device
