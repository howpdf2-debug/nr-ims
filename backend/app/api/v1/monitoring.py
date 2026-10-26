"""Monitoring API (Phase 3a-2): time-series for graphs and the aggregated network-health view.

* ``GET /devices/{device_id}/metrics``   device + per-interface time series, bucketed for charting.
* ``GET /dashboard/network-health``      scoped fleet status, polling health and the busiest devices.

Both need ``DEVICE_READ`` and are scoped exactly like the rest of the API (``scope_stations``): a device or
station outside the caller's scope is a 404 / simply not counted.

Register in ``app/main.py``: add ``monitoring`` to the ``from app.api.v1 import (...)`` list and to ``_V1``.
This module has no prefix; its paths are written out in full so it can share ``/devices`` and ``/dashboard``
with the existing routers without touching them.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Float, and_, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.device import Device
from app.models.interface import Interface
from app.models.monitoring import DeviceMetric, DevicePollState, InterfaceMetric
from app.models.station import Station
from app.models.user import User
from app.security.rbac import Permission, require_permission
from app.security.scope import get_device_for_user, scope_stations

router = APIRouter(tags=["monitoring"])

MAX_HOURS = 168  # raw retention is 7 days (ARC-09): asking for more would only return less
BUCKET_STEP_S = 60  # the poll cadence: a smaller bucket would just repeat raw samples
MAX_INTERFACES = 48  # one chart request never returns an unbounded number of series
STALE_AFTER_S = 300  # same 5 minutes as the poller's dead-man switch (kept local: the API does not import the worker)
RECENT_METRIC_S = 900  # "latest" CPU readings older than this are not shown as current
_ORIGIN = datetime(2000, 1, 3, tzinfo=UTC)  # any fixed Monday; date_bin aligns buckets to it


def _bucket_seconds(span_s: float, max_points: int) -> int:
    """Smallest multiple of 60 s that keeps a series at or below ``max_points`` points."""
    return max(BUCKET_STEP_S, math.ceil(span_s / max_points / BUCKET_STEP_S) * BUCKET_STEP_S)


def _bucket_expr(column: Any, bucket_s: int) -> Any:
    return func.date_bin(func.make_interval(0, 0, 0, 0, 0, 0, literal(float(bucket_s), Float)), column,
                         literal(_ORIGIN))


def _r(value: Any, digits: int = 1) -> float | None:
    return None if value is None else round(float(value), digits)


def _i(value: Any) -> int | None:
    return None if value is None else int(value)


@router.get("/devices/{device_id}/metrics")
async def get_device_metrics(
    device_id: uuid.UUID,
    hours: int = Query(24, ge=1, le=MAX_HOURS, description="window length, ending now"),
    max_points: int = Query(300, ge=30, le=1000, description="upper bound of points per series"),
    include_interfaces: bool = True,
    interface_id: uuid.UUID | None = Query(None, description="only this interface (must belong to the device)"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission(Permission.DEVICE_READ)),
) -> dict[str, Any]:
    """Time series for one device, aggregated into equal buckets (oldest first).

    Device points: mean CPU / memory / temperature and the highest uptime in the bucket.
    Interface points: mean bps, PEAK utilisation, error/discard SUMS (the stored values are per-poll deltas)
    and the highest ``oper_status`` (1 = up; any larger value means the interface was not up at some point).
    A bucket with no samples is simply absent: the chart should draw a gap, not a zero.
    """
    device = await get_device_for_user(db, user, device_id)  # 404 outside scope
    end = datetime.now(UTC)
    start = end - timedelta(hours=hours)
    bucket_s = _bucket_seconds(hours * 3600, max_points)

    b = _bucket_expr(DeviceMetric.ts, bucket_s).label("bucket")
    dq = (select(b, func.avg(DeviceMetric.cpu_pct).label("cpu"), func.avg(DeviceMetric.mem_pct).label("mem"),
                 func.avg(DeviceMetric.temp_c).label("temp"), func.max(DeviceMetric.uptime_s).label("uptime"))
          .where(DeviceMetric.device_id == device.id, DeviceMetric.ts >= start, DeviceMetric.ts <= end)
          .group_by(b).order_by(b))
    device_points = [{"ts": r.bucket, "cpu_pct": _r(r.cpu), "mem_pct": _r(r.mem), "temp_c": _r(r.temp),
                      "uptime_s": _i(r.uptime)} for r in (await db.execute(dq)).all()]

    # A12: validate the filter whether or not interfaces are returned; a bogus id must never be a silent no-op
    if interface_id is not None:
        found = await db.scalar(select(Interface.id).where(Interface.id == interface_id,
                                                           Interface.device_id == device.id))
        if found is None:
            raise HTTPException(404, "Interface not found")

    interfaces: list[dict[str, Any]] = []
    if include_interfaces:
        iq = select(Interface.id, Interface.name).where(Interface.device_id == device.id)
        if interface_id is not None:
            iq = iq.where(Interface.id == interface_id)
        itfs = (await db.execute(iq.order_by(Interface.name, Interface.id).limit(MAX_INTERFACES))).all()
        series: dict[uuid.UUID, list[dict[str, Any]]] = {i.id: [] for i in itfs}
        if itfs:
            ib = _bucket_expr(InterfaceMetric.ts, bucket_s).label("bucket")
            mq = (select(InterfaceMetric.interface_id, ib,
                         func.avg(InterfaceMetric.in_bps).label("in_bps"),
                         func.avg(InterfaceMetric.out_bps).label("out_bps"),
                         func.max(InterfaceMetric.in_util_pct).label("in_util"),
                         func.max(InterfaceMetric.out_util_pct).label("out_util"),
                         func.sum(InterfaceMetric.in_errors).label("in_err"),
                         func.sum(InterfaceMetric.out_errors).label("out_err"),
                         func.sum(InterfaceMetric.in_discards).label("in_disc"),
                         func.sum(InterfaceMetric.out_discards).label("out_disc"),
                         func.max(InterfaceMetric.oper_status).label("oper"))
                  .where(InterfaceMetric.interface_id.in_(list(series)), InterfaceMetric.ts >= start,
                         InterfaceMetric.ts <= end)
                  .group_by(InterfaceMetric.interface_id, ib).order_by(InterfaceMetric.interface_id, ib))
            for r in (await db.execute(mq)).all():
                series[r.interface_id].append({
                    "ts": r.bucket, "in_bps": _i(r.in_bps), "out_bps": _i(r.out_bps),
                    "in_util_pct": _r(r.in_util, 2), "out_util_pct": _r(r.out_util, 2),
                    "in_errors": _i(r.in_err), "out_errors": _i(r.out_err),
                    "in_discards": _i(r.in_disc), "out_discards": _i(r.out_disc), "oper_status": _i(r.oper)})
        interfaces = [{"interface_id": i.id, "name": i.name, "points": series[i.id]} for i in itfs]

    return {"device_id": device.id, "start": start, "end": end, "bucket_seconds": bucket_s,
            "device": device_points, "interfaces": interfaces}


@router.get("/dashboard/network-health")
async def get_network_health(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission(Permission.DEVICE_READ)),
) -> dict[str, Any]:
    """Scoped, aggregated network status. Every number is computed in SQL over the caller's scope.

    ``overall`` follows the same rule as ``/dashboard/divisions``: "critical" when anything is down, else "healthy".
    ``polling.stale`` counts enabled devices with no successful poll in the last 5 minutes (or ever), which is
    exactly the condition behind the poller's dead-man alarm.
    """
    now = datetime.now(UTC)
    stale_before = now - timedelta(seconds=STALE_AFTER_S)
    is_down = Device.status == "down"

    def scoped(q: Any) -> Any:
        return scope_stations(q, user)

    totals = (await db.execute(scoped(
        select(func.count(Device.id).label("total"),
               func.count(Device.id).filter(is_down).label("down"),
               func.count(Device.id).filter(Device.is_maintenance.is_(True)).label("maintenance"))
        .select_from(Device).join(Station, Device.station_code == Station.code)))).one()
    by_status = dict((await db.execute(scoped(
        select(Device.status, func.count(Device.id)).select_from(Device)
        .join(Station, Device.station_code == Station.code).group_by(Device.status)))).all())

    by_category = [{"category": r.category, "total": r.total, "down": r.down} for r in (await db.execute(scoped(
        select(Device.category, func.count(Device.id).label("total"),
               func.count(Device.id).filter(is_down).label("down"))
        .select_from(Device).join(Station, Device.station_code == Station.code)
        .group_by(Device.category).order_by(Device.category)))).all()]

    by_division = [{"division": r.division, "total": r.total, "down": r.down,
                    "status": "critical" if r.down else "healthy"} for r in (await db.execute(scoped(
        select(Station.division, func.count(Device.id).label("total"),
               func.count(Device.id).filter(is_down).label("down"))
        .select_from(Device).join(Station, Device.station_code == Station.code)
        .group_by(Station.division).order_by(Station.division)))).all()]

    enabled = DevicePollState.poll_enabled.is_not(False)  # no state row yet counts as enabled
    p = (await db.execute(scoped(
        select(func.count(Device.id).filter(enabled).label("enabled"),
               func.count(Device.id).filter(and_(enabled, DevicePollState.last_poll_at.is_(None))).label("never"),
               func.count(Device.id).filter(and_(enabled, DevicePollState.consecutive_failures > 0)).label("failing"),
               func.count(Device.id).filter(and_(enabled, func.coalesce(
                   DevicePollState.last_success_at < stale_before, True))).label("stale"),
               func.max(DevicePollState.last_poll_at).label("last_poll"))
        .select_from(Device).join(Station, Device.station_code == Station.code)
        .outerjoin(DevicePollState, DevicePollState.device_id == Device.id)))).one()

    # newest reading per device (DISTINCT ON), recent only, busiest five
    latest = (select(DeviceMetric.device_id, DeviceMetric.ts, DeviceMetric.cpu_pct, DeviceMetric.mem_pct,
                     DeviceMetric.temp_c)
              .where(DeviceMetric.ts >= now - timedelta(seconds=RECENT_METRIC_S))
              .distinct(DeviceMetric.device_id).order_by(DeviceMetric.device_id, DeviceMetric.ts.desc())
              .subquery("latest"))
    top = (await db.execute(scoped(
        select(Device.id, Device.hostname, Device.station_code, latest.c.cpu_pct, latest.c.mem_pct, latest.c.temp_c,
               latest.c.ts)
        .select_from(Device).join(Station, Device.station_code == Station.code)
        .join(latest, latest.c.device_id == Device.id).where(latest.c.cpu_pct.is_not(None))
        .order_by(latest.c.cpu_pct.desc(), Device.hostname).limit(5)))).all()

    return {
        "generated_at": now,
        "overall": "critical" if totals.down else "healthy",
        "devices": {"total": totals.total, "down": totals.down, "up": by_status.get("up", 0),
                    "unknown": by_status.get("unknown", 0), "maintenance": totals.maintenance,
                    "by_status": by_status},
        "availability_pct": round((totals.total - totals.down) / totals.total * 100, 2) if totals.total else None,
        "polling": {"enabled": p.enabled, "never_polled": p.never, "failing": p.failing, "stale": p.stale,
                    "stale_after_seconds": STALE_AFTER_S, "last_poll_at": p.last_poll},
        "by_category": by_category,
        "by_division": by_division,
        "top_cpu": [{"device_id": r.id, "hostname": r.hostname, "station_code": r.station_code,
                     "cpu_pct": _r(r.cpu_pct), "mem_pct": _r(r.mem_pct), "temp_c": _r(r.temp_c), "ts": r.ts}
                    for r in top],
    }