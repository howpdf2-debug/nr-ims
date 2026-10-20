"""Idempotent dev seed for users. Never deletes existing users. Refuses to run in production.

Password: NRIMS_SEED_ADMIN_PASSWORD, else a random one is generated and printed ONCE.
"""
import asyncio
import secrets

from sqlalchemy import select

from app.config import Env, get_settings
from app.db.session import async_session_maker, engine
from app.models.user import User
from app.security.passwords import hash_password

USERS = [
    ("irca@nr-ims.local", "irca_admin", ["*"]),
    ("dual@nr-ims.local", "divisional_admin", ["LKO", "MB"]),
    ("dli@nr-ims.local", "divisional_admin", ["DLI"]),
    ("bsb@nr-ims.local", "tier1_incharge", ["BSB"]),
]


async def create_users() -> None:
    s = get_settings()
    if s.env is Env.PRODUCTION:
        raise SystemExit("seed_admin.py is disabled in production")
    configured = s.seed_admin_password.get_secret_value() if s.seed_admin_password else ""
    password = configured or secrets.token_urlsafe(14)
    created = 0
    async with async_session_maker() as db:
        for email, role, scopes in USERS:
            existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if existing:
                print(f"= exists: {email}")
                continue
            db.add(User(email=email, hashed_password=hash_password(password), role=role,
                        scopes=scopes, is_active=True))
            created += 1
        await db.commit()
    print(f"Created {created} user(s).")
    if created and not configured:
        print(f"Generated password (shown once): {password}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_users())
