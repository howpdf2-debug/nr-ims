"""arq worker entrypoint. Run: arq arq_worker.WorkerSettings.

Jobs:
* ``discover``      on demand (API enqueues it by name): ICMP sweep + SNMP probe -> discovered_devices.
* ``poll_devices``  cron, every 60 s (Phase 3a-2): ICMP + SNMPv3 polling of every enabled device.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, TypedDict, cast

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import text

from app.config import ConfigError, get_settings
from app.db.session import async_session_maker
from app.monitoring.profiles import ProfileRegistry
from app.monitoring.security import build_fernet, get_monitoring_settings
from app.services.ping import ping_host
from app.services.poller import CONCURRENCY, poll_all_devices
from app.workers.discovery import discover

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

# The worker runs ONE job at a time (see max_jobs). A poll job that waited behind a long discovery scan is
# stale by the time it starts: running it would only repeat the next minute's work, so it is dropped.
MAX_POLL_QUEUE_AGE_S = 90
POLL_JOB_TIMEOUT_S = 58  # below the 60 s cadence: a stuck cycle can never overlap the next one
POLL_HARD_TIMEOUT_S = POLL_JOB_TIMEOUT_S - 3  # C3: our own clean timeout fires before arq's cancellation


class PollCtx(TypedDict, total=False):
    """D3: the keys arq 0.26 puts in the job context (worker.py builds job_ctx with these)."""

    redis: Any  # ArqRedis
    job_id: str
    job_try: int
    enqueue_time: datetime
    score: int | None


async def _self_check() -> None:
    """C4: one INFO per passing check; a failing check that would make polling useless raises, the rest warn."""
    async with async_session_maker() as session:
        await session.execute(text("SELECT 1"))
        log.info("self-check: database connectivity OK")
        table = await session.execute(text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = 'device_poll_state'"))
        if table.first() is None:
            raise RuntimeError("self-check FAILED: table device_poll_state is missing (run `alembic upgrade head`)")
        log.info("self-check: table device_poll_state present")

    # A typo in profiles.toml must stop the worker now, not in the middle of a poll.
    registry = ProfileRegistry.load(get_monitoring_settings().snmp_profiles_file)
    log.info("self-check: SNMP vendor profiles loaded: %s", ", ".join(registry.names))

    # C2: fail-fast. build_fernet() only raises when the key is invalid or (in production) missing.
    try:
        build_fernet()
    except ConfigError as exc:
        log.error("self-check FAILED: SNMP credential key: %s", exc)
        raise
    log.info("self-check: SNMP credential key OK")

    # C1: if ICMP cannot run (missing NET_RAW) every poll degrades to INCONCLUSIVE, so say it loudly. Warn only:
    # SNMP polling still works without ICMP.
    ping = await ping_host("127.0.0.1", count=1, timeout=1.0)
    if not ping.alive or ping.error:
        log.warning("ICMP self-check FAILED (missing NET_RAW?): all ICMP polls will be INCONCLUSIVE. error=%s",
                    ping.error)
    else:
        log.info("ICMP self-check OK")


async def on_startup(ctx: dict) -> None:
    settings = get_settings()
    log.info(
        "arq worker starting: env=%s data_provider=%s db=%s",
        settings.env.value,
        settings.data_provider.value,
        settings.database_host,
    )
    # Fail-fast on DB misconfig — worker shouldn't silently accept tasks
    # it can't persist results for.
    try:
        await _self_check()
    except Exception as exc:  # noqa: BLE001
        log.error("arq worker startup self-check FAILED: %s", exc)
        raise


async def on_shutdown(ctx: dict) -> None:
    log.info("arq worker stopping")


async def poll_devices(ctx: dict[str, Any]) -> dict[str, Any]:
    """Cron job: one polling cycle. Uses the module-level sessionmaker (same engine/pool as discovery)."""
    pc = cast(PollCtx, ctx)  # arq's cron() is typed for a plain dict named ctx; PollCtx makes key typos a mypy error
    enqueued = pc.get("enqueue_time")  # arq sets this (a datetime) for every job, cron included
    if isinstance(enqueued, datetime):
        age = (datetime.now(UTC) - enqueued.astimezone(UTC)).total_seconds()
        if age > MAX_POLL_QUEUE_AGE_S:
            log.warning("dropping stale poll job (queued %.0f s ago; the worker was busy)", age)
            return {"v": 1, "dropped_stale": True}
    redis = pc.get("redis")
    if redis is None:  # A11: arq always provides it; if it ever does not, say so instead of degrading silently
        log.warning("no Redis in arq ctx: falling back to the in-memory counter store; "
                    "interface rates will not survive worker restarts")
    try:  # C3
        stats = await asyncio.wait_for(
            poll_all_devices(async_session_maker, redis=redis, concurrency=CONCURRENCY),
            timeout=POLL_HARD_TIMEOUT_S)
    except TimeoutError:
        log.error("poll cycle hard-timed out at %ds", POLL_HARD_TIMEOUT_S)
        return {"v": 1, "timed_out": True}
    return {"v": 1, "stats": asdict(stats)}  # D2


class WorkerSettings:
    functions = [discover]
    cron_jobs = [
        # second=0 and every other field unset = every minute, on the minute. unique=True (default): with several
        # workers only one of them runs a given minute. run_at_startup: fresh data right after a (re)start.
        cron(poll_devices, second=0, run_at_startup=True, timeout=POLL_JOB_TIMEOUT_S, max_tries=1,
             keep_result=0),
    ]
    redis_settings = RedisSettings.from_dsn(
        get_settings().valkey_url.get_secret_value()
    )
    # Serialize discovery jobs — prevents concurrent DELETE+INSERT races. Side effect: a long discovery scan
    # pauses polling (stale poll jobs are dropped above). If that becomes a problem, run polling in its own
    # worker service instead of raising max_jobs (that would allow two scans at once).
    max_jobs = 1
    # 1024 hosts worst case × 2s SNMP / 16 concurrent ≈ 128s + ICMP padding
    job_timeout = 900
    # Discovery jobs are stateless; no retry (each retry wipes results)
    max_tries = 1
    # Results not polled — short TTL
    keep_result = 300
    # Reconnect on Redis blips
    health_check_interval = 60
    on_startup = on_startup
    on_shutdown = on_shutdown