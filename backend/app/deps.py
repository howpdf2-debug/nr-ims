"""FastAPI dependencies: DB session and the authenticated user.

Where the access token is read from
-----------------------------------
1. ``X-NRIMS-Auth`` (what the web UI sends): the raw JWT, or ``Bearer <jwt>``.
2. ``Authorization: Bearer <jwt>`` (curl, scripts, tests, the Swagger "Authorize" button): unchanged.

Why a second header exists: some hosting proxies treat a browser request that carries an ``Authorization`` header as
THEIR OWN credentials and answer 302 to a Google sign-in page (seen behind Google Cloud Shell Web Preview), so the UI
never gets its data. A neutral custom header avoids that. It carries exactly the same JWT, is validated by exactly the
same code, and grants nothing the Authorization header does not.

If both headers are present the custom one wins and there is NO fall-through: an invalid ``X-NRIMS-Auth`` is a 401
even if ``Authorization`` is valid, so a request can never be authenticated by something other than what it sent first.
"""

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.security.tokens import decode_access_token

AUTH_HEADER = "X-NRIMS-Auth"

# auto_error=False: a missing Authorization header must not be an error by itself, because the token may be in
# X-NRIMS-Auth. The scheme stays declared so OpenAPI/Swagger still offers "Authorize".
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def extract_token(custom_header: str | None, bearer_token: str | None) -> str | None:
    """Pick the access token: the X-NRIMS-Auth value (optionally prefixed with "Bearer ") wins; else the bearer.

    Returns None when no usable token was supplied. Pure function (unit-tested without a server).
    """
    if custom_header is not None:
        head, _, rest = custom_header.strip().partition(" ")  # a JWT never contains a space
        value = rest.strip() if head.lower() == "bearer" else custom_header.strip()
        return value or None  # present-but-empty/blank means "no token", never a fall-through to Authorization
    return bearer_token or None


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with request.app.state.sessionmaker() as session:
        yield session


async def get_current_user(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = extract_token(request.headers.get(AUTH_HEADER), bearer_token)
    if not token:
        raise credentials_exception

    # decode_access_token returns the claims dict, or None when the token is invalid/expired/forged
    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError:
        raise credentials_exception from None

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    return user
