from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from app.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserRead
from app.security.passwords import hash_password
from app.security.rbac import Permission, require_permission

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=List[UserRead])
async def list_users(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.USER_MANAGE))):
    res = await db.execute(select(User))
    return res.scalars().all()

@router.post("/", response_model=UserRead)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.USER_MANAGE))):
    existing = await db.execute(select(User).where(User.email == user.email))
    if existing.scalar_one_or_none(): raise HTTPException(400, "Email already exists")
    
    new_user = User(email=user.email, hashed_password=hash_password(user.password), role=user.role, scopes=user.scopes, is_active=True)
    db.add(new_user); await db.commit(); await db.refresh(new_user)
    return new_user

@router.put("/{user_id}", response_model=UserRead)
async def update_user(user_id: str, user: UserUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.USER_MANAGE))):
    db_user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not db_user: raise HTTPException(404, "User not found")
    
    if user.role is not None: db_user.role = user.role
    if user.scopes is not None: db_user.scopes = user.scopes
    if user.is_active is not None: db_user.is_active = user.is_active
    await db.commit(); return db_user

@router.delete("/{user_id}")
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_permission(Permission.USER_MANAGE))):
    if str(current_user.id) == user_id: raise HTTPException(400, "Cannot delete your own account")
    await db.execute(delete(User).where(User.id == user_id)); await db.commit()
    return {"message": "User deleted"}