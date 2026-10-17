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

# आपके द्वारा दी गई लिस्ट का एक बड़ा हिस्सा
RAW_DATA = [
    # DLI Division
    ("DLI", "NDLS", "PRS"), ("DLI", "DELHI CANTT.", "PRS"), ("DLI", "GURGAON", "PRS"), 
    ("DLI", "PANIPAT", "PRS"), ("DLI", "ROHTAK", "PRS"), ("DLI", "SONIPAT", "PRS"), 
    ("DLI", "MEERUT CITY", "PRS"), ("DLI", "SHAMLI", "PRS"),
    # FZR Division
    ("FZR", "ASR", "PRS+UCP"), ("FZR", "BEAS", "PRS"), ("FZR", "FZR", "PRS"), 
    ("FZR", "JUC", "PRS"), ("FZR", "LDH", "PRS"), ("FZR", "MOGA", "PRS"),
    # IRCA Division (New)
    ("IRCA", "Baroda House", "PRS"), ("IRCA", "PRS Delhi", "PRS"), ("IRCA", "PRS Nizamuddin", "PRS"), 
    ("IRCA", "PRS Railway Board", "PRS"),
    # JAT Division
    ("JAT", "CAMB", "PRS"), ("JAT", "JAT", "PRS"), ("JAT", "KTHU", "PRS+UCP"), 
    ("JAT", "SVDK", "PRS"),
    # LKO Division
    ("LKO", "VARANASI", "PRS"), ("LKO", "LUCKNOW", "PRS"), ("LKO", "SULTANPUR", "PRS"), 
    ("LKO", "RAIBERALLI", "PRS"), ("LKO", "PRAYAG", "PRS"), ("LKO", "JAUNPUR JN", "PRS"),
    # MB Division
    ("MB", "Amroha", "PRS"), ("MB", "Bareilly", "PRS"), ("MB", "Dehradun", "PRS"), 
    ("MB", "Haridwar", "PRS"), ("MB", "Moradabad", "PRS"), ("MB", "Roorkee", "PRS"),
    # UMB Division
    ("UMB", "Ambala Cant", "PRS"), ("UMB", "Chandigarh", "PRS"), ("UMB", "Kalka", "PRS"), 
    ("UMB", "Patiala", "PRS"), ("UMB", "Shimla", "PRS+UCP")
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
        all_devices = []

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
            router = Device(id=uuid.uuid4(), external_id=f"{code}-RTR", hostname=f"{code.lower()}-rtr", ip_address=f"10.{div[0].encode().hex()[:2]}.{len(seen_codes)}.1", category="router", status=r_status, station_code=code, source_system="simulator", source_timestamp=datetime.now(timezone.utc))
            switch = Device(id=uuid.uuid4(), external_id=f"{code}-SW", hostname=f"{code.lower()}-sw", ip_address=f"10.{div[0].encode().hex()[:2]}.{len(seen_codes)}.2", category="switch", status="up", station_code=code, source_system="simulator", source_timestamp=datetime.now(timezone.utc))
            db.add_all([router, switch])
            all_devices.extend([router, switch])

            # Interfaces generate करें
            for i in range(1, 4):
                db.add(Interface(id=uuid.uuid4(), device_id=router.id, name=f"Gi0/{i}", ip_address=f"{router.ip_address.rsplit('.', 1)[0]}.{i}", status="up" if r_status == "up" else "down", description="Uplink", in_mbps=random.uniform(10, 900), out_mbps=random.uniform(10, 900), errors=0))

            if r_status == "down":
                db.add(Alarm(id=uuid.uuid4(), external_id=f"alm-{code}", device_id=router.id, severity="critical", message=f"Router unreachable at {loc}", status="active", first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc)))

        print("Generating link topology...")
        stations = list(seen_codes)
        for _ in range(20):
            src, dst = random.sample(stations, 2)
            provider = random.choice(["BSNL", "OFC"])
            bw = random.choice([10, 100, 1000])
            db.add(Link(id=uuid.uuid4(), source_station=src, destination_station=dst, provider=provider, bandwidth_mbps=bw, status="up", utilization_pct=random.uniform(10, 95), latency_ms=random.uniform(5, 50)))

        await db.commit()
        print(f"✅ Successfully seeded {len(seen_codes)} stations with devices and links!")

if __name__ == "__main__":
    asyncio.run(seed())