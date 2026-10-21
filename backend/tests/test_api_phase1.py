"""Phase 1 contract tests. Need a migrated + seeded DB (make up && make seed) and Valkey:
    NRIMS_INTEGRATION=1 pytest tests/test_api_phase1.py
Every test creates its own uniquely-named data and removes it in `finally` (no seed data is mutated).
"""
import os
import uuid

import httpx
import pytest
import pytest_asyncio

from app.config import get_settings
from app.main import create_app

pytestmark = pytest.mark.skipif(os.getenv("NRIMS_INTEGRATION") != "1", reason="integration")
PW = os.getenv("NRIMS_SEED_ADMIN_PASSWORD", "Str0ng-Test-Pass1")
V1 = "/api/v1"


@pytest_asyncio.fixture
async def client():
    app = create_app(get_settings())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c
    await app.state.cache.aclose()
    await app.state.engine.dispose()


async def hdr(c, email):
    r = await c.post(f"{V1}/auth/login", data={"username": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _payload(station="BSB", **over):
    n = uuid.uuid4().hex[:8]
    base = {"hostname": f"p1-{n}", "ip_address": f"172.31.{int(n[:2], 16)}.{int(n[2:4], 16) % 250 + 1}",
            "category": "switch", "station_code": station, "parent_device_id": None}
    return {**base, **over}


async def _mk(c, h, **over):
    r = await c.post(f"{V1}/devices/", headers=h, json=_payload(**over))
    assert r.status_code == 201, r.text
    return r.json()


async def _rm(c, h, *devices):
    for d in devices:
        await c.delete(f"{V1}/devices/{d['id']}", headers=h)


async def test_device_detail_contract_and_scope(client):
    irca, bsb = await hdr(client, "irca@nr-ims.local"), await hdr(client, "bsb@nr-ims.local")
    mine = (await client.get(f"{V1}/devices/?station_code=BSB", headers=bsb)).json()
    router = next(d for d in mine if d["category"] == "router")
    r = await client.get(f"{V1}/devices/{router['id']}/detail", headers=bsb)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"device", "interfaces", "ospf_neighbors"}
    assert body["device"]["id"] == router["id"] and body["interfaces"], "seed_inventory.py must have run"
    assert {"name", "status", "in_mbps", "out_mbps", "errors"} <= set(body["interfaces"][0])
    # flat resource is unchanged (backward compatible)
    assert "hostname" in (await client.get(f"{V1}/devices/{router['id']}", headers=bsb)).json()
    foreign = next(d for d in (await client.get(f"{V1}/devices/?limit=1000", headers=irca)).json()
                   if d["station_code"] != "BSB")
    assert (await client.get(f"{V1}/devices/{foreign['id']}/detail", headers=bsb)).status_code == 404


async def test_device_create_validation_scope_and_duplicates(client):
    irca, bsb = await hdr(client, "irca@nr-ims.local"), await hdr(client, "bsb@nr-ims.local")
    d = await _mk(client, bsb)
    try:
        assert d["status"] == "unknown" and d["source_system"] == "manual" and d["station_code"] == "BSB"
        dup_host = await client.post(f"{V1}/devices/", headers=bsb, json=_payload(hostname=d["hostname"].upper()))
        dup_ip = await client.post(f"{V1}/devices/", headers=bsb, json=_payload(ip_address=d["ip_address"]))
        assert dup_host.status_code == 409 and dup_ip.status_code == 409
        assert (await client.post(f"{V1}/devices/", headers=bsb, json=_payload(ip_address="nope"))).status_code == 422
        assert (await client.post(f"{V1}/devices/", headers=bsb, json=_payload(category="toaster"))).status_code == 422
        # a tier-1 user cannot create inside a station outside their scope (and gets 404, not 403)
        assert (await client.post(f"{V1}/devices/", headers=bsb, json=_payload(station="NDLS"))).status_code == 404
        other = await _mk(client, irca, station="NDLS")
        try:  # parent must be in the same station
            r = await client.post(f"{V1}/devices/", headers=irca,
                                  json=_payload(parent_device_id=other["id"]))
            assert r.status_code == 422
        finally:
            await _rm(client, irca, other)
        # audit trail written
        ev = (await client.get(f"{V1}/audit/events?limit=50", headers=irca)).json()
        assert any(e["action"] == "device.create" and e["target_id"] == d["id"] for e in ev)
    finally:
        await _rm(client, irca, d)


async def test_operator_cannot_write(client):
    irca = await hdr(client, "irca@nr-ims.local")
    email = f"p1-op-{uuid.uuid4().hex[:8]}@example.com"
    mk = await client.post(f"{V1}/users/", headers=irca,
                           json={"email": email, "password": PW, "role": "operator", "scopes": ["BSB"]})
    assert mk.status_code == 201, mk.text
    try:
        op = await hdr(client, email)
        assert (await client.post(f"{V1}/devices/", headers=op, json=_payload())).status_code == 403
        assert (await client.post(f"{V1}/topology/local/links", headers=op, json={})).status_code == 403
        assert (await client.get(f"{V1}/topology/local/BSB", headers=op)).status_code == 200  # read is allowed
    finally:
        await client.delete(f"{V1}/users/{mk.json()['id']}", headers=irca)


async def test_delete_reparents_children_and_removes_links(client):
    h = await hdr(client, "bsb@nr-ims.local")
    parent = await _mk(client, h)
    child = await _mk(client, h, parent_device_id=parent["id"])
    other = await _mk(client, h)
    try:
        lk = await client.post(f"{V1}/topology/local/links", headers=h, json={
            "source_device_id": parent["id"], "destination_device_id": other["id"], "media_type": "ofc"})
        assert lk.status_code == 201, lk.text
        r = await client.delete(f"{V1}/devices/{parent['id']}", headers=h)
        assert r.status_code == 200 and r.json()["links_deleted"] == 1
        assert (await client.get(f"{V1}/devices/{parent['id']}", headers=h)).status_code == 404
        again = (await client.get(f"{V1}/devices/{child['id']}", headers=h)).json()
        assert again["parent_device_id"] is None  # re-parented to the deleted device's parent (none)
        topo = (await client.get(f"{V1}/topology/local/BSB", headers=h)).json()
        assert lk.json()["id"] not in {e["id"] for e in topo["edges"]}
    finally:
        await _rm(client, h, child, other, parent)


async def test_local_topology_shape_links_and_position(client):
    irca, bsb = await hdr(client, "irca@nr-ims.local"), await hdr(client, "bsb@nr-ims.local")
    topo = (await client.get(f"{V1}/topology/local/BSB", headers=bsb)).json()
    assert len(topo["nodes"]) >= 8 and topo["edges"], "seed_inventory.py must have run"
    n = topo["nodes"][0]
    assert n["type"] == "deviceNode" and {"label", "ip", "category", "status", "is_maintenance"} <= set(n["data"])
    assert {"x", "y"} == set(n["position"])
    e = topo["edges"][0]
    assert {"media_type", "description", "source_host", "source_ip", "dest_host", "dest_ip"} <= set(e["data"])
    ids = {x["id"] for x in topo["nodes"]}
    assert all(x["source"] in ids and x["target"] in ids for x in topo["edges"])
    assert (await client.get(f"{V1}/topology/local/NDLS", headers=bsb)).status_code == 404

    a, b = await _mk(client, bsb), await _mk(client, bsb)
    foreign = await _mk(client, irca, station="NDLS")
    try:
        body = {"source_device_id": a["id"], "destination_device_id": b["id"], "media_type": "copper", "description": ""}
        lk = await client.post(f"{V1}/topology/local/links", headers=bsb, json=body)
        assert lk.status_code == 201, lk.text
        rev = {**body, "source_device_id": b["id"], "destination_device_id": a["id"]}
        assert (await client.post(f"{V1}/topology/local/links", headers=bsb, json=rev)).status_code == 409
        self_link = {**body, "destination_device_id": a["id"]}
        assert (await client.post(f"{V1}/topology/local/links", headers=bsb, json=self_link)).status_code == 422
        cross = {**body, "destination_device_id": foreign["id"]}
        assert (await client.post(f"{V1}/topology/local/links", headers=bsb, json=cross)).status_code == 404
        cross_admin = await client.post(f"{V1}/topology/local/links", headers=irca, json=cross)
        assert cross_admin.status_code == 422  # visible to admin but not the same station
        assert (await client.delete(f"{V1}/topology/local/links/{lk.json()['id']}", headers=irca)).status_code == 200
        lk2 = await client.post(f"{V1}/topology/local/links", headers=bsb, json=body)
        assert (await client.delete(f"{V1}/topology/local/links/{lk2.json()['id']}", headers=bsb)).status_code == 200
        # a link the caller cannot see answers 404, not 403/200
        ndls = [d for d in (await client.get(f"{V1}/devices/?station_code=NDLS", headers=irca)).json()][:2]
        foreign_lk = (await client.get(f"{V1}/topology/local/NDLS", headers=irca)).json()["edges"][0]
        assert (await client.delete(f"{V1}/topology/local/links/{foreign_lk['id']}", headers=bsb)).status_code == 404
        assert len(ndls) == 2
        pos = await client.put(f"{V1}/topology/local/device/{a['id']}/position", headers=bsb, json={"x": 12.5, "y": 40})
        assert pos.status_code == 200
        topo2 = (await client.get(f"{V1}/topology/local/BSB", headers=bsb)).json()
        moved = next(x for x in topo2["nodes"] if x["id"] == a["id"])
        assert moved["position"] == {"x": 12.5, "y": 40}
        bad = await client.put(f"{V1}/topology/local/device/{a['id']}/position", headers=bsb, json={"x": 9e9, "y": 0})
        assert bad.status_code == 422
        assert (await client.put(f"{V1}/topology/local/device/{foreign['id']}/position", headers=bsb,
                                 json={"x": 1, "y": 1})).status_code == 404
    finally:
        await _rm(client, irca, a, b, foreign)


async def test_summary_and_total_count_are_not_capped_and_scoped(client):
    for email in ("irca@nr-ims.local", "bsb@nr-ims.local", "dual@nr-ims.local"):
        h = await hdr(client, email)
        page = await client.get(f"{V1}/devices/?limit=1", headers=h)
        total = int(page.headers["X-Total-Count"])
        s = (await client.get(f"{V1}/dashboard/summary", headers=h)).json()
        assert s["total_devices"] == total, email
        assert 0 <= s["down_devices"] <= total and s["total_stations"] >= 1
        assert s["availability_pct"] is None or 0 <= s["availability_pct"] <= 100
    irca = await hdr(client, "irca@nr-ims.local")
    assert int((await client.get(f"{V1}/devices/?limit=1", headers=irca)).headers["X-Total-Count"]) > 100


async def test_links_hide_foreign_endpoints(client):
    irca, bsb = await hdr(client, "irca@nr-ims.local"), await hdr(client, "bsb@nr-ims.local")
    visible = {s["code"] for s in (await client.get(f"{V1}/stations/", headers=bsb)).json()}
    mine = (await client.get(f"{V1}/links/", headers=bsb)).json()
    assert all(lk["source_station"] in visible and lk["destination_station"] in visible for lk in mine)
    assert len((await client.get(f"{V1}/links/", headers=irca)).json()) >= len(mine)
    per_station = (await client.get(f"{V1}/links/BSB", headers=bsb)).json()
    assert all(lk["source_station"] in visible and lk["destination_station"] in visible for lk in per_station)
    assert {"id", "provider", "status", "bandwidth_mbps"} <= set(mine[0]) if mine else True
