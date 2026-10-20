"""arq worker entrypoint. Run: arq arq_worker.WorkerSettings."""
from __future__ import annotations

import logging

from arq.connections import RedisSettings
from sqlalchemy import text

from app.config import get_settings
from app.db.session import async_session_maker
from app.workers.discovery import discover

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


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
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        log.info("arq worker DB connectivity OK")
    except Exception as exc:  # noqa: BLE001
        log.error("arq worker DB connectivity FAILED: %s", exc)
        raise


async def on_shutdown(ctx: dict) -> None:
    log.info("arq worker stopping")


class WorkerSettings:
    functions = [discover]
    redis_settings = RedisSettings.from_dsn(
        get_settings().valkey_url.get_secret_value()
    )
    # Serialize discovery jobs — prevents concurrent DELETE+INSERT races
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