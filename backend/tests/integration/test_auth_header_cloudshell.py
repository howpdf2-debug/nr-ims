import os
import pytest
pytestmark = pytest.mark.skipif(not os.getenv("NRIMS_INTEGRATION"), reason="Needs NRIMS_INTEGRATION=1")
"""X-NRIMS-Auth end to end (the header the UI sends so proxies do not mistake it for their own Authorization).

Needs NRIMS_INTEGRATION=1 and a migrated + seeded DB. Read-only: creates nothing.
"""
import os

V1 = "/api/v1"

PW = os.getenv("NRIMS_SEED_ADMIN_PASSWORD", "Str0ng-Test-Pass1")


async def _token(client, email="irca@nr-ims.local") -> str:
    r = await client.post(f"{V1}/auth/login", data={"username": email, "password": PW})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_custom_header_authenticates_with_raw_token_and_with_bearer_prefix(client):
    t = await _token(client)
    for value in (t, f"Bearer {t}"):
        r = await client.get(f"{V1}/dashboard/summary", headers={"X-NRIMS-Auth": value})
        assert r.status_code == 200 and "total_devices" in r.json(), value[:12]


async def test_authorization_bearer_still_works_for_curl_scripts_and_swagger(client):
    t = await _token(client)
    r = await client.get(f"{V1}/dashboard/summary", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200


async def test_both_headers_the_custom_one_wins_without_fall_through(client):
    """Identity probe: the device list is scoped, so its total reveals WHICH user was authenticated."""
    irca, bsb = await _token(client), await _token(client, "bsb@nr-ims.local")

    async def total(headers: dict[str, str]) -> int:
        r = await client.get(f"{V1}/devices/?limit=1", headers=headers)
        assert r.status_code == 200, headers
        return int(r.headers["X-Total-Count"])

    irca_total = await total({"X-NRIMS-Auth": irca})
    bsb_total = await total({"Authorization": f"Bearer {bsb}"})
    assert irca_total > bsb_total, "seed: IRCA admin sees every station, BSB only its own"
    # custom header = IRCA, Authorization = BSB: the custom one decides
    assert await total({"X-NRIMS-Auth": irca, "Authorization": f"Bearer {bsb}"}) == irca_total
    assert await total({"X-NRIMS-Auth": bsb, "Authorization": f"Bearer {irca}"}) == bsb_total
    # an invalid custom header is a 401 even when Authorization is valid (no silent fall-through)
    bad = await client.get(f"{V1}/dashboard/summary", headers={"X-NRIMS-Auth": "garbage", "Authorization": f"Bearer {irca}"})
    assert bad.status_code == 401


async def test_missing_blank_or_forged_tokens_are_401_with_www_authenticate(client):
    t = await _token(client)
    cases = [{}, {"X-NRIMS-Auth": ""}, {"X-NRIMS-Auth": "Bearer "}, {"X-NRIMS-Auth": "not.a.jwt"},
             {"X-NRIMS-Auth": t[:-3] + "AAA"}, {"X-NRIMS-Auth": "", "Authorization": f"Bearer {t}"}]
    for headers in cases:
        r = await client.get(f"{V1}/dashboard/summary", headers=headers)
        assert r.status_code == 401, headers
        assert r.headers.get("www-authenticate") == "Bearer"


async def test_cors_preflight_allows_the_custom_header(client):
    r = await client.options(f"{V1}/dashboard/summary", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "x-nrims-auth"})
    if r.status_code == 200:  # only when the test environment configures that origin
        assert "x-nrims-auth" in r.headers["access-control-allow-headers"].lower()
