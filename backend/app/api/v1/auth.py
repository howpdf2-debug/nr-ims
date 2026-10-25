import contextlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, Token
from app.security.passwords import DUMMY_HASH, verify_password
from app.security.tokens import create_access_token
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_LOGIN_BODY_BYTES = 16 * 1024  # a login body is ~100 bytes; refuse anything else before parsing it
_MAX_IDENTIFIER, _MAX_PASSWORD = 255, 256  # same limits as LoginRequest, so JSON and form behave alike
_FORM_TYPES = frozenset({"application/x-www-form-urlencoded", "multipart/form-data"})

# POST /auth/login takes JSON or an OAuth2 form, so the OpenAPI document has to describe both bodies by hand.
_LOGIN_BODIES = {"requestBody": {"required": True, "content": {
    "application/json": {"schema": {
        "type": "object", "required": ["email", "password"], "additionalProperties": False,
        "properties": {"email": {"type": "string", "maxLength": _MAX_IDENTIFIER},
                       "password": {"type": "string", "format": "password", "maxLength": _MAX_PASSWORD}}}},
    "application/x-www-form-urlencoded": {"schema": {
        "type": "object", "required": ["username", "password"],
        "properties": {"username": {"type": "string", "maxLength": _MAX_IDENTIFIER},
                       "password": {"type": "string", "format": "password", "maxLength": _MAX_PASSWORD}}}}}}}


async def _attempts(request: Request, key: str) -> int:
    try:
        return int(await request.app.state.cache.get(key) or 0)
    except Exception:  # noqa: BLE001  cache down -> fail open, never lock operators out
        return 0


def _invalid(*loc: str, msg: str, kind: str) -> HTTPException:
    """422 in FastAPI's own shape. Never carries the submitted value: it would echo the password back."""
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                         detail=[{"loc": ["body", *loc], "msg": msg, "type": kind}])


def _check_lengths(identifier: str, password: str) -> None:
    if len(identifier) > _MAX_IDENTIFIER:
        raise _invalid("username", msg=f"String should have at most {_MAX_IDENTIFIER} characters",
                       kind="string_too_long")
    if len(password) > _MAX_PASSWORD:
        raise _invalid("password", msg=f"String should have at most {_MAX_PASSWORD} characters",
                       kind="string_too_long")


async def _json_credentials(request: Request) -> tuple[str, str]:
    body = bytearray()
    async for chunk in request.stream():  # bounded read: no unbounded body is ever buffered
        body += chunk
        if len(body) > MAX_LOGIN_BODY_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Login request is too large")
    try:
        raw = json.loads(bytes(body) or b"null")
    except ValueError:  # includes UnicodeDecodeError
        raise _invalid(msg="Request body is not valid JSON", kind="json_invalid") from None
    try:
        creds = LoginRequest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=[
            {"loc": ["body", *map(str, e["loc"])], "msg": e["msg"], "type": e["type"]} for e in exc.errors()
        ]) from None  # e["input"] (the password) is intentionally dropped
    return creds.email, creds.password


async def _form_credentials(request: Request) -> tuple[str, str]:
    if int(request.headers.get("content-length") or 0) > MAX_LOGIN_BODY_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Login request is too large")
    form = await request.form()
    username, password = form.get("username"), form.get("password")
    for name, value in (("username", username), ("password", password)):
        if not isinstance(value, str):
            raise _invalid(name, msg="Field required", kind="missing")
    assert isinstance(username, str) and isinstance(password, str)
    _check_lengths(username, password)
    return username, password


async def _authenticate(request: Request, db: AsyncSession, identifier: str, password: str) -> dict[str, str]:
    """The one login routine behind every login endpoint: rate limit, constant-time check, audit, token."""
    s = request.app.state.settings
    ip = request.client.host if request.client else "?"
    key = f"login_fail:{identifier.lower()}:{ip}"
    if await _attempts(request, key) >= s.login_max_attempts:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try later.")

    user = (await db.execute(select(User).where(User.email == identifier))).scalar_one_or_none()
    # Always run one hash verification so timing does not reveal valid emails.
    ok = verify_password(password, user.hashed_password if user else DUMMY_HASH)
    if not user or not ok or not user.is_active:
        with contextlib.suppress(Exception):  # cache down must never block the 401 path
            await request.app.state.cache.incr(key)
            await request.app.state.cache.expire(key, s.login_lockout_seconds)
        record_audit(db, user, "auth.login_failed", "user", identifier[:100], {"ip": ip})
        await db.commit()
        raise HTTPException(401, "Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})

    with contextlib.suppress(Exception):
        await request.app.state.cache.delete(key)
    record_audit(db, user, "auth.login", "user", str(user.id), {"ip": ip})
    await db.commit()
    return {"access_token": create_access_token(str(user.id), user.role, user.scopes or []),
            "token_type": "bearer"}


@router.post("/login", response_model=Token, openapi_extra=_LOGIN_BODIES)
async def login(request: Request, db: AsyncSession = Depends(get_db)):
    """Log in with JSON ``{"email", "password"}``.

    An OAuth2 form (``username`` + ``password``) is still accepted here: the web UI, Swagger's "Authorize"
    button and older scripts post it. ``/auth/login-form`` is the explicit, form-only alias of the same thing.
    """
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type == "application/json":
        identifier, password = await _json_credentials(request)
    elif content_type in _FORM_TYPES:
        identifier, password = await _form_credentials(request)
    else:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            "Send JSON {\"email\", \"password\"} or an OAuth2 form {username, password}")
    return await _authenticate(request, db, identifier, password)


@router.post("/login-form", response_model=Token)
async def login_form(request: Request, form: OAuth2PasswordRequestForm = Depends(),
                     db: AsyncSession = Depends(get_db)):
    """Form-data login only (legacy shape: ``username`` + ``password``)."""
    _check_lengths(form.username, form.password)
    return await _authenticate(request, db, form.username, form.password)