import asyncio
from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.user import User
from app.security.passwords import hash_password

async def create_admin():
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.email == "admin@nr-ims.local"))
        if result.scalar_one_or_none():
            print("Admin already exists!")
            return
        admin = User(
            email="admin@nr-ims.local",
            hashed_password=hash_password("Admin@123"),
            role="zonal_admin",
            is_active=True
        )
        db.add(admin)
        await db.commit()
        print("Admin user created successfully!")

if __name__ == "__main__":
    asyncio.run(create_admin())
