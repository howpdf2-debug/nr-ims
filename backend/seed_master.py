import asyncio
from sqlalchemy import select, delete
from datetime import datetime, timezone
import uuid
import random
from app.db.session import async_session_maker
from app.models.device import Device
from app.models.alarm import Alarm
from app.models.station import Station
from app.models.link import Link
from app.models.interface import Interface

RAW_DATA = [
    ("DLI", "NDLS", "PRS"), ("DLI", "GZB", "PRS"), ("DLI", "ANAND VIHAR", "PRS"), 
    ("LKO", "LKO", "PRS"), ("LKO", "BSB", "PRS"), ("LKO", "PRG", "PRS"), 
    ("LKO", "JNU", "PRS"), ("LKO", "SLN", "PRS"), ("LKO", "RBL", "PRS"),
    ("MB", "MB", "PRS"), ("MB", "BE", "PRS"), ("MB", "DDN", "PRS"),
    ("FZR", "ASR", "PRS"), ("FZR", "LDH", "PRS"), ("FZR", "FZR", "PRS"),
    ("UMB", "UMB", "PRS"), ("UMB", "CDG", "PRS"), ("UMB", "SML", "PRS")
]

async def seed():
    async with async_session_maker() as db:
        print("Clearing existing data...")
        await db.execute(delete(Alarm))
        await db.execute(delete(Interface))
        await db.execute(delete(Link))
        await db.execute(delete(Device))
        await db.execute(delete(Station))
        await db.commit()

        print(f"Seeding {len(RAW_DATA)} stations...")
        seen_codes = set()

        for div, loc, stype in RAW_DATA:
            code = loc.split(" (")[0].replace(" ", "").upper()[:4]
            counter = 1
            while code in seen_codes:
                code = f"{code[:3]}{counter}"
                counter += 1
            seen_codes.add(code)

            st = Station(code=code, name=loc, division=div, tier="Tier 1" if "PRS" in stype else "Tier 2", station_type=stype)
            db.add(st)
            
            r_status = "up" if random.random() > 0.15 else "down"
            router = Device(id=uuid.uuid4(), external_id=f"{code}-RTR", hostname=f"{code.lower()}-rtr", ip_address=f"10.10.{len(seen_codes)}.1", category="router", status=r_status, station_code=code, source_system="simulator", source_timestamp=datetime.now(timezone.utc))
            switch = Device(id=uuid.uuid4(), external_id=f"{code}-SW", hostname=f"{code.lower()}-sw", ip_address=f"10.10.{len(seen_codes)}.2", category="switch", status="up", station_code=code, source_system="simulator", source_timestamp=datetime.now(timezone.utc))
            db.add_all([router, switch])

            for i in range(1, 4):
                db.add(Interface(id=uuid.uuid4(), device_id=router.id, name=f"Gi0/{i}", ip_address=f"{router.ip_address.rsplit('.', 1)[0]}.{i}", status="up" if r_status == "up" else "down", description="Uplink", in_mbps=random.uniform(10, 900), out_mbps=random.uniform(10, 900), errors=0))

            if r_status == "down":
                db.add(Alarm(id=uuid.uuid4(), external_id=f"alm-{code}", device_id=router.id, severity="critical", message=f"Router unreachable at {loc}", status="active", first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc)))

        await db.commit()
        print(f"✅ Successfully seeded {len(seen_codes)} stations!")

if __name__ == "__main__":
    asyncio.run(seed())