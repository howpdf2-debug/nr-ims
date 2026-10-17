"""Liveness and readiness endpoints (unauthenticated, no sensitive data)."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app import __version__
from app.cache import ping_cache
from app.db.session import ping_database

router = APIRouter(tags=["health"])


class Liveness(BaseModel):
    status: Literal["ok"]
    version: str


class DependencyCheck(BaseModel):
    name: str
    ok: bool
    error: str | None = None


class Readiness(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: list[DependencyCheck]


async def _run(
    name: str, probe: Callable[[], Awaitable[None]], limit: float
) -> DependencyCheck:
    try:
        async with asyncio.timeout(limit):
            await probe()
    except TimeoutError:
        return DependencyCheck(name=name, ok=False, error="timeout")
    except Exception as exc:  # noqa: BLE001
        # Never leak details (may hold DSNs) to clients; only class name
        return DependencyCheck(name=name, ok=False, error=type(exc).__name__)
    return DependencyCheck(name=name, ok=True)


@router.get("/healthz", response_model=Liveness)
async def healthz() -> Liveness:
    return Liveness(status="ok", version=__version__)


@router.get("/readyz", response_model=Readiness)
async def readyz(request: Request, response: Response) -> Readiness:
    state = request.app.state
    timeout: float = state.settings.readiness_timeout_seconds
    checks = await asyncio.gather(
        _run("database", lambda: ping_database(state.engine), timeout),
        _run("cache", lambda: ping_cache(state.cache), timeout),
    )
    ready = all(c.ok for c in checks)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Readiness(status="ready" if ready else "not_ready", checks=list(checks))