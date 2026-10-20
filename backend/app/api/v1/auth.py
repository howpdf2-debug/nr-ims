import contextlib

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.user import User
from app.schemas.auth import Token
from app.security.passwords import DUMMY_HASH, verify_password
from app.security.tokens import create_access_token
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])


async def _attempts(request: Request, key: str) -> int:
    try:
        return int(await request.app.state.cache.get(key) or 0)
    except Exception:  # noqa: BLE001  cache down -> fail open, never lock operators out
        return 0


@router.post("/login", response_model=Token)
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends(),
                db: AsyncSession = Depends(get_db)):
    s = request.app.state.settings
    ip = request.client.host if request.client else "?"
    key = f"login_fail:{form.username.lower()}:{ip}"
    if await _attempts(request, key) >= s.login_max_attempts:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try later.")

    user = (await db.execute(select(User).where(User.email == form.username))).scalar_one_or_none()
    # Always run one hash verification so timing does not reveal valid emails.
    ok = verify_password(form.password, user.hashed_password if user else DUMMY_HASH)
    if not user or not ok or not user.is_active:
        with contextlib.suppress(Exception):  # cache down must never block the 401 path
            await request.app.state.cache.incr(key)
            await request.app.state.cache.expire(key, s.login_lockout_seconds)
        record_audit(db, user, "auth.login_failed", "user", form.username[:100], {"ip": ip})
        await db.commit()
        raise HTTPException(401, "Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})

    with contextlib.suppress(Exception):
        await request.app.state.cache.delete(key)
    record_audit(db, user, "auth.login", "user", str(user.id), {"ip": ip})
    await db.commit()
    return {"access_token": create_access_token(str(user.id), user.role, user.scopes or []),
            "token_type": "bearer"}
