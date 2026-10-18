import asyncio
from sqlalchemy import select, delete
from app.db.session import async_session_maker
from app.models.user import User
from app.security.passwords import hash_password

async def create_users():
    async with async_session_maker() as db:
        print("Clearing old users...")
        await db.execute(delete(User))
        await db.commit()

        # 1. IRCA Global Admin (देख सकता है सब कुछ)
        irca = User(
            email="irca@nr-ims.local", hashed_password=hash_password("Admin@123"),
            role="irca_admin", scopes=["*"], is_active=True
        )
        
        # 2. Dual Charge Admin (LKO + MB दोनों का एक्सेस)
        dual_admin = User(
            email="dual@nr-ims.local", hashed_password=hash_password("Admin@123"),
            role="divisional_admin", scopes=["LKO", "MB"], is_active=True
        )

        # 3. Single Divisional Admin (सिर्फ DLI का एक्सेस)
        dli_admin = User(
            email="dli@nr-ims.local", hashed_password=hash_password("Admin@123"),
            role="divisional_admin", scopes=["DLI"], is_active=True
        )

        # 4. Tier-1 Incharge (सिर्फ BSB और उसके चाइल्ड स्टेशन्स)
        bsb_incharge = User(
            email="bsb@nr-ims.local", hashed_password=hash_password("Admin@123"),
            role="tier1_incharge", scopes=["BSB"], is_active=True
        )

        db.add_all([irca, dual_admin, dli_admin, bsb_incharge])
        await db.commit()
        print("✅ Admin users created: irca, dual (LKO+MB), dli, bsb")

if __name__ == "__main__":
    asyncio.run(create_users())