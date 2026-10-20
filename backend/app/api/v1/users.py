import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.security.passwords import hash_password
from app.security.rbac import Permission, Role, require_permission
from app.services.audit import record_audit

router = APIRouter(prefix="/users", tags=["users"])
_manage = Depends(require_permission(Permission.USER_MANAGE))


async def _active_admins(db: AsyncSession) -> int:
    return await db.scalar(select(func.count(User.id)).where(
        User.role == Role.IRCA_ADMIN, User.is_active.is_(True))) or 0


@router.get("/", response_model=list[UserRead])
async def list_users(db: AsyncSession = Depends(get_db), _: User = _manage):
    return (await db.execute(select(User).order_by(User.email))).scalars().all()


@router.post("/", response_model=UserRead, status_code=201)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db), me: User = _manage):
    if (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none():
        raise HTTPException(400, "Email already exists")
    u = User(email=body.email, hashed_password=hash_password(body.password), role=body.role,
             scopes=body.scopes, is_active=True)
    db.add(u)
    await db.flush()
    record_audit(db, me, "user.create", "user", u.id, {"role": u.role, "scopes": u.scopes})
    await db.commit()
    await db.refresh(u)
    return u


@router.put("/{user_id}", response_model=UserRead)
async def update_user(user_id: uuid.UUID, body: UserUpdate, db: AsyncSession = Depends(get_db),
                      me: User = _manage):
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    demoting = u.role == Role.IRCA_ADMIN and (
        (body.role is not None and body.role != Role.IRCA_ADMIN) or body.is_active is False)
    if demoting and await _active_admins(db) <= 1:
        raise HTTPException(400, "Cannot remove the last active IRCA admin")
    if body.role is not None:
        u.role = body.role
    if body.scopes is not None:
        u.scopes = body.scopes
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.password:
        u.hashed_password = hash_password(body.password)
    record_audit(db, me, "user.update", "user", u.id,
                 {k: v for k, v in body.model_dump(exclude_none=True).items() if k != "password"})
    await db.commit()
    return u


@router.delete("/{user_id}")
async def delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), me: User = _manage):
    if me.id == user_id:
        raise HTTPException(400, "Cannot delete your own account")
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.role == Role.IRCA_ADMIN and u.is_active and await _active_admins(db) <= 1:
        raise HTTPException(400, "Cannot delete the last active IRCA admin")
    await db.delete(u)
    record_audit(db, me, "user.delete", "user", user_id, {"email": u.email})
    await db.commit()
    return {"message": "User deleted"}
