import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.security.rbac import Role

Scopes = Annotated[list[Annotated[str, Field(min_length=1, max_length=50)]], Field(max_length=100)]


def _check_role(v: str | None) -> str | None:
    if v is not None and v not in {r.value for r in Role}:
        raise ValueError(f"role must be one of {[r.value for r in Role]}")
    return v


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: str
    scopes: Scopes
    _r = field_validator("role")(_check_role)


class UserUpdate(BaseModel):
    role: str | None = None
    scopes: Scopes | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=10, max_length=128)
    _r = field_validator("role")(_check_role)


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    scopes: list[str]
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
