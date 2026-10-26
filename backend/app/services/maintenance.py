"""Observed device status, as reported by the poller (Phase 3a-2).

    set_observed_status(db, device, status) -> None

The status column follows what monitoring saw. A device that an operator put into maintenance keeps its
``maintenance`` status: the poller still calls this for such devices every cycle, and the observation must not
silently end the maintenance. The caller owns the transaction (commit).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device


async def set_observed_status(db: AsyncSession, device: Device, status: str) -> None:
    """Set ``device.status`` to the observed ``status`` unless it is unchanged or the device is in maintenance."""
    if device.is_maintenance or device.status == status:
        return
    device.status = status
    db.add(device)