import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

ALGORITHM = "HS256"


def create_access_token(subject: str, role: str, scopes: list[str]) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(subject), "role": role, "scopes": scopes,
        "iat": now, "exp": now + timedelta(minutes=s.access_token_expire_minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, s.secret_key.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token, get_settings().secret_key.get_secret_value(), algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
