"""ICMP sweep with bounded concurrency using icmplib."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from icmplib import async_ping

log = logging.getLogger(__name__)


@dataclass
class PingResult:
    host: str
    alive: bool
    rtt_ms: float | None
    packet_loss: float
    error: str | None = None


async def ping_host(host: str, count: int = 2, timeout: float = 1.5,
                    interval: float = 0.2) -> PingResult:
    try:
        h = await async_ping(
            host, count=count, timeout=timeout, interval=interval, privileged=True
        )
        return PingResult(
            host=host,
            alive=h.is_alive,
            rtt_ms=round(h.avg_rtt, 2) if h.is_alive else None,
            packet_loss=h.packet_loss,
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("ping %s failed: %s", host, exc)
        return PingResult(host=host, alive=False, rtt_ms=None,
                          packet_loss=1.0, error=str(exc))


async def sweep(hosts: list[str], concurrency: int = 32, count: int = 2,
                timeout: float = 1.5) -> list[PingResult]:
    sem = asyncio.Semaphore(concurrency)

    async def _one(h: str) -> PingResult:
        async with sem:
            return await ping_host(h, count=count, timeout=timeout)

    return await asyncio.gather(*[_one(h) for h in hosts])
