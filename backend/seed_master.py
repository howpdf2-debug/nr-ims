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

# आपके डिवीजन्स का डेटा (LKO, DLI, MB आदि)
RAW_DATA = [
    ("LKO", "LKO", "Tier 1", "PRS", None),
    ("LKO", "BSB", "Tier 1", "PRS", None),
    ("LKO", "PRG", "Tier 1", "PRS", None),
    ("LKO", "KEH", "Tier 2", "UTS", "BSB"),
    ("LKO", "MOF", "Tier 2", "UTS", "BSB"),
    ("DLI", "NDLS", "Tier 1", "PRS", None),
    ("DLI", "GZB", "Tier 1", "PRS", None),
    ("DLI", "ANAND VIHAR", "Tier 1", "PRS", None),
    ("MB", "MB", "Tier 1", "PRS", None),
    ("MB", "BE", "Tier 1", "PRS", None),
    ("FZR", "ASR", "Tier 1", "PRS", None),
    ("UMB", "UMB", "Tier 1", "PRS", None),
    ("JAT", "JAT", "Tier 1", "PRS", None),
    ("IRCA", "Baroda House", "Tier 0", "PRS", None),
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

        for div, loc, tier, stype, parent in RAW_DATA:
            # स्टेशन कोड बनाएँ (जैसे NDLS)
            code = loc.split(" (")[0].replace(" ", "").upper()[:4]
            counter = 1
            while code in seen_codes:
                code = f"{code[:3]}{counter}"
                counter += 1
            seen_codes.add(code)

            st = Station(
                code=code, name=loc, division=div, tier=tier, 
                station_type=stype, parent_station_code=parent
            )
            db.add(st)
            
            # राउटर और स्विच बनाएँ
            r_status = "up" if random.random() > 0.15 else "down"
            router = Device(
                id=uuid.uuid4(), external_id=f"{code}-RTR", hostname=f"{code.lower()}-rtr", 
                ip_address=f"10.10.{len(seen_codes)}.1", category="router", status=r_status, 
                station_code=code, source_system="simulator", source_timestamp=datetime.now(timezone.utc)
            )
            switch = Device(
                id=uuid.uuid4(), external_id=f"{code}-SW", hostname=f"{code.lower()}-sw", 
                ip_address=f"10.10.{len(seen_codes)}.2", category="switch", status="up", 
                station_code=code, source_system="simulator", source_timestamp=datetime.now(timezone.utc)
            )
            db.add_all([router, switch])

            # इंटरफेस बनाएँ
            for i in range(1, 4):
                db.add(Interface(
                    id=uuid.uuid4(), device_id=router.id, name=f"Gi0/{i}", 
                    ip_address=f"{router.ip_address.rsplit('.', 1)[0]}.{i}", 
                    status="up" if r_status == "up" else "down", description="Uplink", 
                    in_mbps=random.uniform(10, 900), out_mbps=random.uniform(10, 900), errors=0
                ))

            # अलार्म बनाएँ (अगर राउटर डाउन है)
            if r_status == "down":
                db.add(Alarm(
                    id=uuid.uuid4(), external_id=f"alm-{code}", device_id=router.id, 
                    severity="critical", message=f"Router unreachable at {loc}", status="active", 
                    first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc)
                ))

        await db.commit()
        print(f"✅ Successfully seeded {len(seen_codes)} stations with devices!")

if __name__ == "__main__":
    asyncio.run(seed())