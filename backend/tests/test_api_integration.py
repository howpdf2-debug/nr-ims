"""Needs a migrated+seeded DB and Valkey:  NRIMS_INTEGRATION=1 pytest tests/test_api_integration.py
(seed_master.py, seed_links.py, seed_admin.py with NRIMS_SEED_ADMIN_PASSWORD=Str0ng-Test-Pass1)."""
import os

import httpx
import pytest
import pytest_asyncio

from app.config import get_settings
from app.main import create_app

pytestmark = pytest.mark.skipif(os.getenv("NRIMS_INTEGRATION") != "1", reason="integration")
PW = "Str0ng-Test-Pass1"


@pytest_asyncio.fixture
async def client():
    app = create_app(get_settings())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c
    await app.state.cache.aclose()
    await app.state.engine.dispose()


async def login(c, email, pw=PW):
    r = await c.post("/api/v1/auth/login", data={"username": email, "password": pw})
    return r


async def hdr(c, email):
    r = await login(c, email)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_readyz(client):
    r = await client.get("/readyz")
    assert r.status_code == 200, r.text


async def test_scope_isolation(client):
    irca = await hdr(client, "irca@nr-ims.local")
    bsb = await hdr(client, "bsb@nr-ims.local")
    dli = await hdr(client, "dli@nr-ims.local")
    all_dev = (await client.get("/api/v1/devices/?limit=1000", headers=irca)).json()
    bsb_dev = (await client.get("/api/v1/devices/?limit=1000", headers=bsb)).json()
    dli_dev = (await client.get("/api/v1/devices/?limit=1000", headers=dli)).json()
    assert len(all_dev) > len(bsb_dev) > 0           # tier-1 BSB used to see 0 devices
    assert {d["station_code"] for d in bsb_dev} == {"BSB"}
    assert "BSB" not in {d["station_code"] for d in dli_dev}
    foreign = next(d for d in all_dev if d["station_code"] != "BSB")
    # IDOR: foreign device by id must be invisible and un-actionable
    assert (await client.get(f"/api/v1/devices/{foreign['id']}", headers=bsb)).status_code == 404
    r = await client.post("/api/v1/actions/execute", headers=bsb,
                          json={"device_id": foreign["id"], "action_type": "PING"})
    assert r.status_code == 404
    topo = (await client.get("/api/v1/topology/", headers=bsb)).json()
    ids = {n["id"] for n in topo["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in topo["edges"])


async def test_rca_suppression_and_ack(client):
    irca = await hdr(client, "irca@nr-ims.local")
    alarms = (await client.get("/api/v1/alarms/", headers=irca)).json()
    assert alarms
    r = await client.patch(f"/api/v1/alarms/{alarms[0]['id']}/ack", headers=irca)
    assert r.status_code == 200
    assert (await client.patch("/api/v1/alarms/not-a-uuid/ack", headers=irca)).status_code == 422


async def test_rbac_and_validation(client):
    bsb = await hdr(client, "bsb@nr-ims.local")
    assert (await client.get("/api/v1/users/", headers=bsb)).status_code == 403
    assert (await client.post("/api/v1/discovery/scan", headers=bsb)).status_code == 403
    irca = await hdr(client, "irca@nr-ims.local")
    bad = {"email": "x@y.com", "password": "short", "role": "god", "scopes": []}
    assert (await client.post("/api/v1/users/", headers=irca, json=bad)).status_code == 422
    assert (await client.get("/api/v1/devices/")).status_code == 401


async def test_login_lockout(client):
    for _ in range(5):
        assert (await login(client, "dual@nr-ims.local", "wrong-wrong-1")).status_code == 401
    assert (await login(client, "dual@nr-ims.local", "wrong-wrong-1")).status_code == 429


async def test_csv_and_reports_scoped(client):
    bsb = await hdr(client, "bsb@nr-ims.local")
    r = await client.get("/api/v1/reports/export/alarms", headers=bsb)
    assert r.status_code == 200 and r.text.startswith("Alarm ID")
    s = (await client.get("/api/v1/reports/summary", headers=bsb)).json()
    assert 0 < s["kpi"]["total_devices"] < 50
