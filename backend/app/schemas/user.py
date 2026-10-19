from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import List

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str
    scopes: List[str]

class UserUpdate(BaseModel):
    role: str | None = None
    scopes: List[str] | None = None
    is_active: bool | None = None

class UserRead(BaseModel):
    id: UUID
    email: str
    role: str
    scopes: List[str]
    is_active: bool
    class Config:
        from_attributes = True