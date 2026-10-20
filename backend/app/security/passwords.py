from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ph = PasswordHasher()
DUMMY_HASH = ph.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerificationError, InvalidHashError):
        return False
