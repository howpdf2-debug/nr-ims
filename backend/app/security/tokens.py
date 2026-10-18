from datetime import datetime, timedelta, timezone
import jwt
from app.config import get_settings

settings = get_settings()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours shift for NOC operators

def create_access_token(subject: str, role: str, scopes: list[str]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "exp": expire, 
        "sub": str(subject),
        "role": role,
        "scopes": scopes
    }
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key.get_secret_value(), algorithm=ALGORITHM
    )
    return encoded_jwt

def decode_access_token(token: str) -> dict | None:
    try:
        decoded = jwt.decode(
            token, settings.secret_key.get_secret_value(), algorithms=[ALGORITHM]
        )
        return decoded
    except jwt.PyJWTError:
        return None