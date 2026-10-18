import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, update
from app.db.session import async_session_maker
from app.models.device import Device
from app.models.alarm import Alarm

async def simulate():
    async with async_session_maker() as db:
        # 1. 'bsb-rtr' और 'mb-rtr' को डाउन करें
        await db.execute(update(Device).where(Device.hostname == 'bsb-rtr').values(status='down'))
        await db.execute(update(Device).where(Device.hostname == 'mb-rtr').values(status='down'))
        await db.commit()

        # 2. जो भी डिवाइस डाउन है, उसके लिए अलार्म जनरेट करें
        res = await db.execute(select(Device).where(Device.status == 'down'))
        down_devices = res.scalars().all()
        
        for d in down_devices:
            # चेक करें कि कहीं पहले से अलार्म तो नहीं है
            a_res = await db.execute(select(Alarm).where(Alarm.device_id == d.id, Alarm.status == 'active'))
            if not a_res.scalar_one_or_none():
                a = Alarm(
                    id=uuid.uuid4(), 
                    external_id=f"alm-{d.hostname}", 
                    device_id=d.id, 
                    severity="critical", 
                    message=f"Router unreachable at {d.station_code}", 
                    status="active", 
                    first_seen=datetime.now(timezone.utc), 
                    last_seen=datetime.now(timezone.utc)
                )
                db.add(a)
        await db.commit()
        print(f"✅ Fault Simulation Successful: {len(down_devices)} devices are now DOWN.")

if __name__ == "__main__":
    asyncio.run(simulate())