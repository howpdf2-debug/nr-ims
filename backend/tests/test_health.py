"""Tests for /healthz and /readyz endpoints using fake DB and cache."""

import httpx
import pytest

from app.config import Settings
from app.main import create_app


class FakeCache:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def ping(self) -> bool:
        if self.fail:
            raise ConnectionError("redis://user:secretpw@host down")
        return True

    async def aclose(self) -> None:
        return None


class FakeConn:
    def __init__(self, fail: bool) -> None:
        self.fail = fail

    async def __aenter__(self) -> "FakeConn":
        if self.fail:
            raise ConnectionError("postgresql://u:secretpw@db down")
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def execute(self, *_: object) -> None:
        return None


class FakeEngine:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def connect(self) -> FakeConn:
        return FakeConn(self.fail)

    async def dispose(self) -> None:
        return None


def client(
    settings: Settings, db_fail: bool = False, cache_fail: bool = False
) -> httpx.AsyncClient:
    app = create_app(settings)
    app.state.engine = FakeEngine(db_fail)
    app.state.cache = FakeCache(cache_fail)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_healthz_ok(test_settings: Settings) -> None:
    async with client(test_settings) as c:
        r = await c.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_security_headers_present(test_settings: Settings) -> None:
    async with client(test_settings) as c:
        r = await c.get("/healthz")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


async def test_readyz_ready(test_settings: Settings) -> None:
    async with client(test_settings) as c:
        r = await c.get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


@pytest.mark.parametrize(
    ("db_fail", "cache_fail", "failed"),
    [
        (True, False, "database"),
        (False, True, "cache"),
    ],
)
async def test_readyz_503_when_dependency_down(
    test_settings: Settings, db_fail: bool, cache_fail: bool, failed: str
) -> None:
    async with client(test_settings, db_fail, cache_fail) as c:
        r = await c.get("/readyz")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    bad = [x for x in body["checks"] if not x["ok"]]
    assert [x["name"] for x in bad] == [failed]
    assert "secretpw" not in r.text  # no credential leakage via error output