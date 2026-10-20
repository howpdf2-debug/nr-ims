import asyncio
from sqlalchemy import select, delete
from datetime import datetime, timezone
import uuid
from app.db.session import async_session_maker
from app.config import Env, get_settings

if get_settings().env is Env.PRODUCTION:
    raise SystemExit("seed_data.py is disabled in production")
from app.models.device import Device
from app.models.alarm import Alarm
from app.models.station import Station

async def seed():
    async with async_session_maker() as db:
        print("Clearing old data...")
        await db.execute(delete(Alarm))
        await db.execute(delete(Device))
        await db.execute(delete(Station))
        await db.commit()

        print("Creating Northern Railway Divisions and Stations...")
        # 1. Stations create karein (Divisions ke hisaab se)
        stations = [
            Station(code="NDLS", name="New Delhi", division="DLI"),
            Station(code="GZB", name="Ghaziabad", division="DLI"),
            Station(code="MB", name="Moradabad", division="MB"),
            Station(code="LKO", name="Lucknow", division="LKO"),
            Station(code="UMB", name="Ambala Cantt", division="UMB"),
            Station(code="JAT", name="Jammu Tawi", division="JAT"),
            Station(code="FZR", name="Firozpur Cantt", division="FZR"),
        ]
        db.add_all(stations)
        await db.commit()

        print("Creating NDLS Server and Network Devices...")
        # 2. Devices create karein (NDLS me Server aur baaki stations par Router)
        devices_data = [
            # NDLS (New Delhi) - Server & Core Network
            {"st": "NDLS", "cat": "server", "name": "ndls-core-server-01", "status": "up"},
            {"st": "NDLS", "cat": "router", "name": "ndls-gateway-router-01", "status": "up"},
            {"st": "NDLS", "cat": "switch", "name": "ndls-core-switch-01", "status": "up"},
            
            # GZB (Ghaziabad) - Down Router
            {"st": "GZB", "cat": "router", "name": "gzb-router-01", "status": "down"},
            
            # MB (Moradabad) - Up
            {"st": "MB", "cat": "router", "name": "mb-router-01", "status": "up"},
            
            # LKO (Lucknow) - Telecom Device Down
            {"st": "LKO", "cat": "telecom", "name": "lko-telecom-01", "status": "down"},
            
            # UMB (Ambala) - Up
            {"st": "UMB", "cat": "switch", "name": "umb-switch-01", "status": "up"},
            
            # JAT (Jammu) - Up
            {"st": "JAT", "cat": "router", "name": "jat-router-01", "status": "up"},
            
            # FZR (Firozpur) - OFC Link Down
            {"st": "FZR", "cat": "ofc", "name": "fzr-ofc-link", "status": "down"},
        ]

        dev_objs = []
        for i, d in enumerate(devices_data):
            dev = Device(
                id=uuid.uuid4(), 
                external_id=f"ext-{i}", 
                hostname=d["name"],
                ip_address=f"10.10.{i}.1", 
                category=d["cat"], 
                status=d["status"], 
                station_code=d["st"],
                source_system="simulator", 
                source_timestamp=datetime.now(timezone.utc)
            )
            db.add(dev)
            dev_objs.append(dev)
        
        await db.commit()

        print("Generating Alarms for DOWN devices...")
        # 3. Alarms create karein (Sirf DOWN devices ke liye)
        for d in dev_objs:
            if d.status == "down":
                a = Alarm(
                    id=uuid.uuid4(), 
                    external_id=str(uuid.uuid4())[:8], 
                    device_id=d.id,
                    severity="critical" if d.category in ["server", "router"] else "major", 
                    message=f"{d.category.upper()} connectivity lost at {d.station_code}", 
                    status="active",
                    first_seen=datetime.now(timezone.utc), 
                    last_seen=datetime.now(timezone.utc)
                )
                db.add(a)
        
        await db.commit()
        print("✅ Northern Railway Base Data Seeded Successfully!")

if __name__ == "__main__":
    asyncio.run(seed())