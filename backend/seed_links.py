import asyncio
import uuid
from sqlalchemy import delete
from app.db.session import async_session_maker
from app.models.link import Link

async def seed_links():
    async with async_session_maker() as db:
        # पुराने लिंक्स साफ करें
        await db.execute(delete(Link))
        await db.commit()

        # नए लिंक्स का डेटा (Source, Destination, Provider, Bandwidth, Status)
        links = [
            ("LKO", "BSB", "OFC", 1000, "up"),
            ("LKO", "BSB", "BSNL", 10, "down"),  # BSNL डाउन है
            ("LKO", "MB", "RAILTEL", 100, "up"),
            ("BSB", "KEH", "OFC", 1000, "up"),
            ("BSB", "MOF", "OFC", 1000, "up"),
            ("MB", "BE", "OFC", 1000, "up"),
            ("LKO", "PRG", "OFC", 1000, "up"),
        ]

        for src, dst, provider, bw, status in links:
            db.add(Link(
                id=uuid.uuid4(), source_station=src, destination_station=dst,
                provider=provider, bandwidth_mbps=bw, status=status,
                utilization_pct=45.0, latency_ms=12.0
            ))
        
        await db.commit()
        print("✅ Topology links seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_links())