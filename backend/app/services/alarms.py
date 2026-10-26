"""Alarm lifecycle service (Phase 2): raise (with de-duplication) and resolve.

These two functions are called by the poller (Phase 3a-2) and their signatures are a contract:

    raise_alarm(db, *, device, external_id, severity, message) -> Alarm
    resolve_alarm(db, alarm, *, resolved_by, note) -> None

An alarm is "open" while ``status != "resolved"``. The same fault re-reported while open only counts up
``occurrence_count``; once resolved, a recurrence creates a NEW alarm row. The caller owns the transaction (commit).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alarm import Alarm
from app.models.device import Device

RESOLVED = "resolved"


async def raise_alarm(db: AsyncSession, *, device: Device, external_id: str, severity: str, message: str) -> Alarm:
    """Return the open alarm for ``(device, external_id)`` (counting this report) or create a new active one."""
    now = datetime.now(UTC)
    query = (select(Alarm)
             .where(Alarm.device_id == device.id, Alarm.external_id == external_id, Alarm.status != RESOLVED)
             .limit(1))
    alarm = (await db.execute(query)).scalars().first()
    if alarm is not None:
        alarm.occurrence_count = (alarm.occurrence_count or 1) + 1
        alarm.last_seen = now
        alarm.message = message[:500]
        return alarm

    alarm = Alarm(id=uuid.uuid4(), external_id=external_id, device_id=device.id, severity=severity,
                  message=message[:500], status="active", first_seen=now, last_seen=now, occurrence_count=1)
    db.add(alarm)
    await db.flush()
    return alarm


async def resolve_alarm(db: AsyncSession, alarm: Alarm, *, resolved_by: str, note: str | None) -> None:
    """Close an alarm. Already-resolved alarms are left untouched (the first resolution is kept)."""
    if alarm.status == RESOLVED:
        return
    alarm.status = RESOLVED
    alarm.resolved_at = datetime.now(UTC)
    alarm.resolved_by = resolved_by[:100]
    alarm.resolve_note = note
    db.add(alarm)