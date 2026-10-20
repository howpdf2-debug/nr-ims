import asyncio
import uuid

from sqlalchemy import delete

from app.config import Env, get_settings
from app.db.session import async_session_maker

if get_settings().env is Env.PRODUCTION:
    raise SystemExit("seed_links.py is disabled in production")
from app.models.link import Link


async def seed_links():
    async with async_session_maker() as db:
        # Safety guard (added post-audit): prevent accidental link data loss.
        # Only clear existing links if NRIMS_ALLOW_DESTRUCTIVE_SEED=true.
        import os
        from sqlalchemy import func, select

        existing_links = await db.scalar(select(func.count()).select_from(Link))
        allow_destructive = os.getenv("NRIMS_ALLOW_DESTRUCTIVE_SEED", "false").lower() == "true"

        if existing_links and existing_links > 0 and not allow_destructive:
            print(f"Database already has {existing_links} link(s) - skipping destructive seed.")
            print("To force re-seed (DATA LOSS): NRIMS_ALLOW_DESTRUCTIVE_SEED=true make seed")
            return

        if existing_links and existing_links > 0 and allow_destructive:
            print(f"NRIMS_ALLOW_DESTRUCTIVE_SEED=true -> clearing {existing_links} link(s)...")
        else:
            print("Empty links table -> seeding fresh...")

        # पुराने लिंक्स साफ करें
        # requires seed_master.py first (stations must exist)
        await db.execute(delete(Link))
        await db.commit()

        # नए लिंक्स का डेटा (Source, Destination, Provider, Bandwidth, Status)
        links = [
            ("LKO", "BSB", "OFC", 1000, "up"),
            ("LKO", "BSB", "BSNL", 10, "down"),  # BSNL डाउन है
            ("LKO", "MB", "RAILTEL", 100, "up"),
            ("LKO", "PRG", "OFC", 1000, "up"),
        ]

        for src, dst, provider, bw, status in links:
            db.add(Link(
                id=uuid.uuid4(), source_station=src, destination_station=dst,
                provider=provider, bandwidth_mbps=bw, status=status,
                latency_ms=12.0
            ))
        
        await db.commit()
        print("✅ Topology links seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_links())