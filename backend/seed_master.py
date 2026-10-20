import asyncio
from sqlalchemy import delete
from datetime import datetime, timezone
import uuid
from app.db.session import async_session_maker
from app.config import Env, get_settings

if get_settings().env is Env.PRODUCTION:
    raise SystemExit("seed_master.py is disabled in production")
from app.models.device import Device
from app.models.alarm import Alarm
from app.models.station import Station
from app.models.link import Link
from app.models.device_link import DeviceLink

PARENT = {  # child -> parent. Drives root-cause correlation.
    "LKO": "IRCA", "MB": "IRCA", "UMB": "IRCA", "NDLS": "IRCA", "FZR": "IRCA", "JAT": "IRCA",
    "BSB": "LKO", "PRG": "LKO", "HW": "MB", "DDN": "UMB", "GZB": "NDLS", "LDH": "FZR", "JUC": "FZR",
}

STATIONS = [
    # Core Network
    ("IRCA", "IRCA Core", "IRCA", "Tier 0"),
    
    # LKO Division
    ("LKO", "LKO Station", "LKO", "Tier 1"), ("BSB", "BSB Station", "LKO", "Tier 1"), ("PRG", "PRG Station", "LKO", "Tier 1"),
    
    # MB Division
    ("MB", "MB Station", "MB", "Tier 1"), ("HW", "HW Station", "MB", "Tier 1"),
    
    # UMB Division
    ("UMB", "UMB Station", "UMB", "Tier 1"), ("DDN", "DDN Station", "UMB", "Tier 1"),
    
    # DLI Division
    ("NDLS", "NDLS Station", "DLI", "Tier 1"), ("GZB", "GZB Station", "DLI", "Tier 1"),
    
    # FZR Division (नया जोड़ा गया)
    ("FZR", "FZR Station", "FZR", "Tier 1"), ("LDH", "LDH Station", "FZR", "Tier 1"), ("JUC", "JUC Station", "FZR", "Tier 1"),
    
    # JAT Division (नया जोड़ा गया)
    ("JAT", "JAT Station", "JAT", "Tier 1")
]

async def seed():
    async with async_session_maker() as db:
        print("Clearing old data...")
        await db.execute(delete(Alarm))
        await db.execute(delete(DeviceLink))
        await db.execute(delete(Link))
        await db.execute(delete(Device))
        await db.execute(delete(Station))
        await db.commit()

        print("Seeding Stations and Devices with Alarms...")
        for code, name, div, tier in STATIONS:  # parents first (FK), then children
            db.add(Station(code=code, name=name, division=div, tier=tier, station_type="PRS"))
        await db.flush()
        for code, parent in PARENT.items():
            (await db.get(Station, code)).parent_station_code = parent
        await db.flush()
        for i, (code, name, div, tier) in enumerate(STATIONS):
            
            # BSB और MB को जानबूझकर डाउन किया गया है
            r_status = "down" if code in ["BSB", "MB"] else "up"
            router = Device(
                id=uuid.uuid4(), external_id=f"{code}-RTR", hostname=f"{code.lower()}-rtr", 
                ip_address=f"10.10.{i}.1", category="router", status=r_status, 
                station_code=code, source_system="simulator", source_timestamp=datetime.now(timezone.utc)
            )
            db.add(router)
            
            # अगर डाउन है, तो अलार्म जनरेट करें
            if r_status == "down":
                db.add(Alarm(
                    id=uuid.uuid4(), external_id=f"alm-{code}", device_id=router.id, 
                    severity="critical", message=f"Router unreachable at {code}", 
                    status="active", first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc)
                ))
        await db.commit()

        print("Seeding IRCA to Divisional Links...")
        # IRCA से सभी डिवीजन्स के मुख्य स्टेशन तक लिंक्स
        db.add(Link(id=uuid.uuid4(), source_station="IRCA", destination_station="LKO", provider="Railway", bandwidth_mbps=10000, status="up", latency_ms=2.0))
        db.add(Link(id=uuid.uuid4(), source_station="IRCA", destination_station="MB", provider="Railway", bandwidth_mbps=10000, status="up", latency_ms=2.0))
        db.add(Link(id=uuid.uuid4(), source_station="IRCA", destination_station="UMB", provider="Railway", bandwidth_mbps=10000, status="up", latency_ms=2.0))
        db.add(Link(id=uuid.uuid4(), source_station="IRCA", destination_station="NDLS", provider="Railway", bandwidth_mbps=10000, status="up", latency_ms=2.0))
        db.add(Link(id=uuid.uuid4(), source_station="IRCA", destination_station="FZR", provider="Railway", bandwidth_mbps=10000, status="up", latency_ms=2.0)) # नया
        db.add(Link(id=uuid.uuid4(), source_station="IRCA", destination_station="JAT", provider="Railway", bandwidth_mbps=10000, status="up", latency_ms=2.0)) # नया
        
        # डिवीजन्स के अंदरूनी लिंक्स (LKO - BSB)
        db.add(Link(id=uuid.uuid4(), source_station="LKO", destination_station="BSB", provider="Railway", bandwidth_mbps=1000, status="up", latency_ms=5.0))
        db.add(Link(id=uuid.uuid4(), source_station="LKO", destination_station="BSB", provider="BSNL", bandwidth_mbps=10, status="degraded", latency_ms=120.0, packet_loss_pct=15.0, crc_errors=450))

        await db.commit()
        print("✅ Seed Complete: All 7 Divisions, Data and Alarms created!")

if __name__ == "__main__":
    asyncio.run(seed())