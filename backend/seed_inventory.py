"""Idempotent dev seed: per-station switches/counters/TS/BTS/modem, device links and interfaces.

Run AFTER seed_master.py (needs the `<CODE>-RTR` routers). Safe to re-run: every device is keyed by
external_id, every link by (source, destination), interfaces are only created for devices that have none.
Never deletes anything. Refuses to run in production.
"""
import asyncio
import random
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import Env, get_settings
from app.db.session import async_session_maker, engine

if get_settings().env is Env.PRODUCTION:
    raise SystemExit("seed_inventory.py is disabled in production")
from app.models.device import Device
from app.models.device_link import DeviceLink
from app.models.interface import Interface
from app.models.station import Station

# (suffix, category, parent suffix, last IP octet)
PLAN = [
    ("SW1", "switch", "RTR", 11), ("SW2", "switch", "RTR", 12),
    ("CTR1", "counter", "SW1", 21), ("CTR2", "counter", "SW1", 22),
    ("TS1", "ts", "SW2", 31), ("BTS1", "bts", "SW2", 41), ("MODEM1", "modem", "SW2", 51),
]
# (from suffix, to suffix, media)
LINKS = [
    ("RTR", "SW1", "ofc"), ("RTR", "SW2", "ofc"), ("SW1", "CTR1", "copper"), ("SW1", "CTR2", "copper"),
    ("SW2", "TS1", "copper"), ("SW2", "BTS1", "ofc"), ("SW2", "MODEM1", "copper"),
]


def _iface_specs(device: Device) -> list[tuple[str, str | None]]:
    base = device.ip_address.rsplit(".", 1)[0]
    if device.category == "router":
        return [(f"Gi0/{n}", f"{base}.{100 + n}") for n in range(4)]
    if device.category == "switch":
        return [(f"Fa0/{n}", None) for n in range(1, 5)]
    return [("eth0", None)]


async def seed() -> None:
    created_dev = created_links = created_ifaces = 0
    async with async_session_maker() as db:
        stations = (await db.execute(select(Station.code).order_by(Station.code))).scalars().all()
        existing_links = {(s, d) for s, d in (await db.execute(
            select(DeviceLink.source_device_id, DeviceLink.destination_device_id))).all()}
        for code in stations:
            devs = {d.external_id: d for d in (await db.execute(
                select(Device).where(Device.station_code == code))).scalars()}
            router = devs.get(f"{code}-RTR")
            if router is None:
                print(f"! {code}: no {code}-RTR router, skipped (run seed_master.py first)")
                continue
            base = router.ip_address.rsplit(".", 1)[0]
            by_suffix: dict[str, Device] = {"RTR": router}
            for suffix, category, parent, octet in PLAN:
                ext = f"{code}-{suffix}"
                dev = devs.get(ext)
                if dev is None:
                    dev = Device(
                        id=uuid.uuid4(), external_id=ext, hostname=f"{code.lower()}-{suffix.lower()}",
                        ip_address=f"{base}.{octet}", category=category, status="up", station_code=code,
                        parent_device_id=by_suffix[parent].id, source_system="simulator",
                        source_timestamp=datetime.now(UTC))
                    db.add(dev)
                    created_dev += 1
                by_suffix[suffix] = dev
            await db.flush()
            for a, b, media in LINKS:
                key = (by_suffix[a].id, by_suffix[b].id)
                if key in existing_links or key[::-1] in existing_links:
                    continue
                db.add(DeviceLink(id=uuid.uuid4(), source_device_id=key[0], destination_device_id=key[1],
                                  media_type=media, description=f"{a} to {b}"))
                existing_links.add(key)
                created_links += 1
            for dev in by_suffix.values():
                has = await db.scalar(select(Interface.id).where(Interface.device_id == dev.id).limit(1))
                if has:
                    continue
                rnd = random.Random(f"{code}-{dev.external_id}")  # deterministic per device
                down = dev.status == "down"
                for n, (name, ip) in enumerate(_iface_specs(dev)):
                    db.add(Interface(
                        id=uuid.uuid4(), device_id=dev.id, name=name, ip_address=ip,
                        status="down" if down else "up", description="Uplink" if n == 0 else f"Port {n}",
                        in_mbps=0.0 if down else round(rnd.uniform(1, 900), 1),
                        out_mbps=0.0 if down else round(rnd.uniform(1, 900), 1),
                        errors=0 if down else rnd.choice([0, 0, 0, 3])))
                    created_ifaces += 1
        await db.commit()
    print(f"Inventory seed: +{created_dev} devices, +{created_links} links, +{created_ifaces} interfaces "
          f"({len(stations)} stations).")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
