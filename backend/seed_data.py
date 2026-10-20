import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete

from app.config import Env, get_settings
from app.db.session import async_session_maker

if get_settings().env is Env.PRODUCTION:
    raise SystemExit("seed_data.py is disabled in production")
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.station import Station


async def seed():
    async with async_session_maker() as db:
        # Safety guard (added post-audit): prevent accidental data loss.
        # This legacy script is NOT called by `make seed` but is manually runnable.
        # Only clear existing data if NRIMS_ALLOW_DESTRUCTIVE_SEED=true.
        import os
        from sqlalchemy import func, select

        existing_stations = await db.scalar(select(func.count()).select_from(Station))
        allow_destructive = os.getenv("NRIMS_ALLOW_DESTRUCTIVE_SEED", "false").lower() == "true"

        if existing_stations and existing_stations > 0 and not allow_destructive:
            print(f"Database already has {existing_stations} station(s) - skipping destructive seed.")
            print("To force re-seed (DATA LOSS): NRIMS_ALLOW_DESTRUCTIVE_SEED=true python seed_data.py")
            return

        if existing_stations and existing_stations > 0 and allow_destructive:
            print(f"NRIMS_ALLOW_DESTRUCTIVE_SEED=true -> clearing {existing_stations} station(s) and related data...")
        else:
            print("Empty database -> seeding fresh...")

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
                source_timestamp=datetime.now(UTC)
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
                    first_seen=datetime.now(UTC), 
                    last_seen=datetime.now(UTC)
                )
                db.add(a)
        
        await db.commit()
        print("✅ Northern Railway Base Data Seeded Successfully!")

if __name__ == "__main__":
    asyncio.run(seed())