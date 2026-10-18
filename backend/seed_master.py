import asyncio
from sqlalchemy import select, delete
from datetime import datetime, timezone
import uuid
from app.db.session import async_session_maker
from app.models.device import Device
from app.models.alarm import Alarm
from app.models.station import Station
from app.models.link import Link
from app.models.interface import Interface
from app.models.device_link import DeviceLink

# IRCA को यहाँ से हटा दिया गया है
DIVISIONS = {
    "LKO": ["LKO", "BSB", "PRG", "RBL", "SLN"],
    "MB": ["MB", "HW"],
    "UMB": ["UMB", "DDN"],
    "FZR": ["LDH", "JUC", "FZR"],
    "JAT": ["JAT"],
    "DLI": ["NDLS", "GZB"]
}
DIV_IP_MAP = {"LKO": 1, "MB": 2, "UMB": 3, "FZR": 4, "JAT": 5, "DLI": 6}

async def seed():
    async with async_session_maker() as db:
        print("Clearing old data...")
        await db.execute(delete(Alarm)); await db.execute(delete(DeviceLink))
        await db.execute(delete(Interface)); await db.execute(delete(Link))
        await db.execute(delete(Device)); await db.execute(delete(Station))
        await db.commit()

        links_to_add = []
        
        # --- 1. CREATE IRCA CORE NETWORK ---
        print("Seeding IRCA Core Network...")
        irca_st = Station(code="IRCA", name="IRCA Core", division="IRCA", tier="Tier 0", station_type="Core")
        db.add(irca_st)
        
        irca_router = Device(id=uuid.uuid4(), external_id="IRCA-RTR", hostname="irca-core-rtr", ip_address="10.0.0.1", category="router", status="up", station_code="IRCA", source_system="simulator", source_timestamp=datetime.now(timezone.utc))
        db.add(irca_router)
        
        for i in range(1, 4):
            srv = Device(id=uuid.uuid4(), external_id=f"IRCA-SRV{i}", hostname=f"irca-server-{i}", ip_address=f"10.0.1.{i}", category="server", status="up", station_code="IRCA", parent_device_id=irca_router.id, source_system="simulator", source_timestamp=datetime.now(timezone.utc))
            db.add(srv)
            links_to_add.append(DeviceLink(id=uuid.uuid4(), source_device_id=irca_router.id, destination_device_id=srv.id, media_type="ofc", description=f"10G Uplink to Server {i}"))
        
        await db.commit()

        # --- 2. CREATE DIVISIONS & TIER-1 STATIONS ---
        st_idx = 10
        for div, stations in DIVISIONS.items():
            d_ip = DIV_IP_MAP[div]
            for code in stations:
                st_idx += 1
                st = Station(code=code, name=f"{code} Station", division=div, tier="Tier 1", station_type="PRS")
                db.add(st)

                r_status = "down" if code in ["BSB", "MB", "NDLS"] else "up"
                router = Device(id=uuid.uuid4(), external_id=f"{code}-RTR", hostname=f"{code.lower()}-rtr", ip_address=f"10.{d_ip}.{st_idx}.1", category="router", status=r_status, station_code=code, source_system="simulator", source_timestamp=datetime.now(timezone.utc))
                db.add(router)
                
                if r_status == "down":
                    db.add(Alarm(id=uuid.uuid4(), external_id=f"alm-{code}", device_id=router.id, severity="critical", message=f"Router unreachable at {code}", status="active", first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc)))

                switches = []
                num_switches = 5 if code == "BSB" else 2
                for sw_idx in range(1, num_switches + 1):
                    sw = Device(id=uuid.uuid4(), external_id=f"{code}-SW{sw_idx}", hostname=f"{code.lower()}-sw-{sw_idx}", ip_address=f"10.{d_ip}.{st_idx}.1{sw_idx}", category="switch", status="up", station_code=code, parent_device_id=router.id, source_system="simulator", source_timestamp=datetime.now(timezone.utc))
                    db.add(sw); switches.append(sw)
                    links_to_add.append(DeviceLink(id=uuid.uuid4(), source_device_id=router.id, destination_device_id=sw.id, media_type="ofc", description=f"OFC to SW{sw_idx}"))

                for i in range(1, 6):
                    sw = switches[i % num_switches]
                    cnt = Device(id=uuid.uuid4(), external_id=f"{code}-PRS{i}", hostname=f"{code.lower()}-prs-{i}", ip_address=f"10.{d_ip}.{st_idx}.2{i}", category="counter", status="up", station_code=code, parent_device_id=sw.id, source_system="simulator", source_timestamp=datetime.now(timezone.utc))
                    db.add(cnt)
                    links_to_add.append(DeviceLink(id=uuid.uuid4(), source_device_id=sw.id, destination_device_id=cnt.id, media_type="copper", description=f"Cu to PRS-{i}"))

                for i in range(1, 6):
                    sw = switches[i % num_switches]
                    cnt = Device(id=uuid.uuid4(), external_id=f"{code}-UTS{i}", hostname=f"{code.lower()}-uts-{i}", ip_address=f"10.{d_ip}.{st_idx}.3{i}", category="counter", status="up", station_code=code, parent_device_id=sw.id, source_system="simulator", source_timestamp=datetime.now(timezone.utc))
                    db.add(cnt)
                    links_to_add.append(DeviceLink(id=uuid.uuid4(), source_device_id=sw.id, destination_device_id=cnt.id, media_type="copper", description=f"Cu to UTS-{i}"))

                if code == "BSB":
                    for i in range(1, 26):
                        sw = switches[i % 5]
                        cnt = Device(id=uuid.uuid4(), external_id=f"BSB-ATVM{i}", hostname=f"bsb-atvm-{i}", ip_address=f"10.{d_ip}.{st_idx}.4{i}", category="counter", status="up", station_code="BSB", parent_device_id=sw.id, source_system="simulator", source_timestamp=datetime.now(timezone.utc))
                        db.add(cnt)
                        links_to_add.append(DeviceLink(id=uuid.uuid4(), source_device_id=sw.id, destination_device_id=cnt.id, media_type="copper", description=f"Cu to ATVM-{i}"))

        await db.commit()
        for link in links_to_add: db.add(link)
        
        # Inter-Station Links
        db.add(Link(id=uuid.uuid4(), source_station="LKO", destination_station="BSB", provider="Railway", bandwidth_mbps=1000, status="up"))
        db.add(Link(id=uuid.uuid4(), source_station="LKO", destination_station="BSB", provider="BSNL", bandwidth_mbps=10, status="down"))
        db.add(Link(id=uuid.uuid4(), source_station="MB", destination_station="HW", provider="Railway", bandwidth_mbps=1000, status="up"))
        db.add(Link(id=uuid.uuid4(), source_station="UMB", destination_station="DDN", provider="Railway", bandwidth_mbps=1000, status="up"))
        
        await db.commit()
        print("✅ Seed Complete: IRCA is now a Core Network!")

if __name__ == "__main__":
    asyncio.run(seed())