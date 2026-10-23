"""Phase 3a-1 integration tests.

Two independent gates (each test skips cleanly when its prerequisite is missing):

* simulator tests  need ``NRIMS_SNMPSIM_BIN`` = path of ``snmpsim-command-responder`` (scripts/verify_phase3a1.sh
  installs it into its OWN venv: installing it into the project venv downgrades pysnmp).
* database tests   need ``NRIMS_INTEGRATION=1`` and a migrated DB (the same convention as the other tests).

The simulator speaks real SNMPv3 (SHA auth + AES128 privacy), so these tests exercise the actual wire protocol,
authentication failures and timeouts, not mocks. One simulator serves four fake devices, one per SNMP context.
"""

import asyncio
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.device import Device
from app.models.interface import Interface
from app.models.monitoring import DeviceMetric, DevicePollState, InterfaceMetric, SnmpCredentialProfile
from app.monitoring.profiles import ProfileRegistry
from app.monitoring.security import MonitoringSettings, decrypt_secret, encrypt_secret
from app.services.snmp_v3 import SnmpErrorKind, SnmpV3Credentials, poll_device

BACKEND = Path(__file__).resolve().parents[2]
SIM_BIN = os.getenv("NRIMS_SNMPSIM_BIN")
needs_sim = pytest.mark.skipif(not SIM_BIN, reason="set NRIMS_SNMPSIM_BIN to run simulator tests")
needs_db = pytest.mark.skipif(os.getenv("NRIMS_INTEGRATION") != "1", reason="integration")

USER, AUTH_KEY, PRIV_KEY = "nrimsv3", "authkey-12345", "privkey-12345"


# ── simulator ───────────────────────────────────────────────────────────────────────────────────
def _snmprec(records: dict[str, tuple[int, object]]) -> str:
    """snmpsim data file; OIDs MUST be sorted numerically. Types: 2 int, 4 str, 6 oid, 65 c32, 66 g32, 67 ticks, 70 c64."""
    rows = sorted(records.items(), key=lambda kv: tuple(int(p) for p in kv[0].split(".")))
    return "\n".join(f"{oid}|{typ}|{val}" for oid, (typ, val) in rows) + "\n"


def _system(descr: str, object_id: str, name: str, uptime_s: int = 86400) -> dict:
    return {"1.3.6.1.2.1.1.1.0": (4, descr), "1.3.6.1.2.1.1.2.0": (6, object_id),
            "1.3.6.1.2.1.1.3.0": (67, uptime_s * 100), "1.3.6.1.2.1.1.5.0": (4, name)}


def _hc_interfaces() -> dict:
    r: dict = {}
    for idx, (name, oper, hc_in, hc_out, err) in {1: ("Gi0/0/0", 1, 123456789012, 98765432100, 12),
                                                  2: ("Gi0/0/1", 2, 0, 0, 0)}.items():
        r |= {f"1.3.6.1.2.1.31.1.1.1.1.{idx}": (4, name), f"1.3.6.1.2.1.2.2.1.2.{idx}": (4, name),
              f"1.3.6.1.2.1.2.2.1.7.{idx}": (2, 1), f"1.3.6.1.2.1.2.2.1.8.{idx}": (2, oper),
              f"1.3.6.1.2.1.31.1.1.1.15.{idx}": (66, 1000), f"1.3.6.1.2.1.31.1.1.1.6.{idx}": (70, hc_in),
              f"1.3.6.1.2.1.31.1.1.1.10.{idx}": (70, hc_out), f"1.3.6.1.2.1.2.2.1.14.{idx}": (65, err),
              f"1.3.6.1.2.1.2.2.1.20.{idx}": (65, 0), f"1.3.6.1.2.1.2.2.1.13.{idx}": (65, 3),
              f"1.3.6.1.2.1.2.2.1.19.{idx}": (65, 0)}
    return r


def _generic_host_resources() -> dict:
    return {"1.3.6.1.2.1.25.3.3.1.2.196608": (2, 20), "1.3.6.1.2.1.25.3.3.1.2.196609": (2, 40),
            "1.3.6.1.4.1.2021.4.5.0": (2, 8_000_000), "1.3.6.1.4.1.2021.4.6.0": (2, 2_000_000)}


CONTEXTS = {
    "cisco": {**_system("Cisco IOS Software, ISR4331 (simulated)", "1.3.6.1.4.1.9.1.1234", "cisco-sim"),
              "1.3.6.1.4.1.9.9.109.1.1.1.1.8.1": (66, 37), "1.3.6.1.4.1.9.9.109.1.1.1.1.8.2": (66, 52),
              "1.3.6.1.4.1.9.9.48.1.1.1.5.1": (66, 300_000_000), "1.3.6.1.4.1.9.9.48.1.1.1.6.1": (66, 100_000_000),
              "1.3.6.1.4.1.9.9.13.1.3.1.3.1": (66, 41), "1.3.6.1.4.1.9.9.13.1.3.1.3.2": (66, 47), **_hc_interfaces()},
    "huawei": {**_system("Huawei VRP (simulated)", "1.3.6.1.4.1.2011.2.100", "huawei-sim"),
               "1.3.6.1.4.1.2011.5.25.31.1.1.1.1.5.1": (66, 23), "1.3.6.1.4.1.2011.5.25.31.1.1.1.1.7.1": (66, 61),
               "1.3.6.1.4.1.2011.5.25.31.1.1.1.1.11.1": (66, 0), "1.3.6.1.4.1.2011.5.25.31.1.1.1.1.11.2": (66, 45),
               **_hc_interfaces()},
    "generic": {**_system("Linux generic-host 5.15", "1.3.6.1.4.1.8072.3.2.10", "generic-sim"),
                **_generic_host_resources(),
                # 32-bit counters only, speed only from ifSpeed (bps): the fallback paths
                "1.3.6.1.2.1.2.2.1.2.1": (4, "eth0"), "1.3.6.1.2.1.2.2.1.7.1": (2, 1), "1.3.6.1.2.1.2.2.1.8.1": (2, 1),
                "1.3.6.1.2.1.2.2.1.5.1": (66, 100_000_000), "1.3.6.1.2.1.2.2.1.10.1": (65, 4_000_000_000),
                "1.3.6.1.2.1.2.2.1.16.1": (65, 1_500_000_000)},
    # Nivetti placeholder: unknown enterprise number, recognised only by sysDescr, generic metrics
    "nivetti": {**_system("Nivetti NiOS 3.2 Router (simulated)", "1.3.6.1.4.1.99999.1.1", "nivetti-sim"),
                **_generic_host_resources(), **_hc_interfaces()},
    "empty": {"1.3.6.1.2.1.99.9.9.0": (4, "unrelated")},
}


def _free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def sim_port():
    if not SIM_BIN:
        pytest.skip("NRIMS_SNMPSIM_BIN not set")
    data = Path(tempfile.mkdtemp(prefix="nrims-snmpsim-"))
    data.chmod(0o755)
    for ctx, records in CONTEXTS.items():
        f = data / f"{ctx}.snmprec"
        f.write_text(_snmprec(records), encoding="utf-8")
        f.chmod(0o644)
    port = _free_udp_port()
    cmd = [SIM_BIN, f"--data-dir={data}", f"--agent-udpv4-endpoint=127.0.0.1:{port}", f"--v3-user={USER}",
           f"--v3-auth-key={AUTH_KEY}", "--v3-auth-proto=SHA", f"--v3-priv-key={PRIV_KEY}", "--v3-priv-proto=AES"]
    if os.geteuid() == 0:  # snmpsim refuses to run as root without dropping privileges
        cmd += ["--process-user=nobody", "--process-group=nogroup"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.fail("snmpsim exited during start-up; run it by hand to see why")
            if asyncio.run(_ready(port)):
                break
            time.sleep(0.5)
        else:
            pytest.fail("snmpsim did not answer within 20 s")
        yield port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


async def _ready(port: int) -> bool:
    return (await poll_device("127.0.0.1", _creds(), REGISTRY, mon=_mon(port, "cisco", timeout=1, deadline=3))).ok


REGISTRY = ProfileRegistry.load()


def _creds(**kw) -> SnmpV3Credentials:
    base = dict(username=USER, auth_protocol="SHA", auth_key=AUTH_KEY, priv_protocol="AES128", priv_key=PRIV_KEY)
    return SnmpV3Credentials(**{**base, **kw})


def _mon(port: int, ctx: str = "", *, timeout: float = 2, retries: int = 0, deadline: float = 15) -> MonitoringSettings:
    return MonitoringSettings(snmp_port=port, snmp_context_name=ctx, snmp_timeout_s=timeout, snmp_retries=retries,
                              poll_deadline_s=deadline)


# ═══ real SNMPv3 polls ══════════════════════════════════════════════════════════════════════════
@needs_sim
async def test_cisco_style_device_full_poll(sim_port):
    s = await poll_device("127.0.0.1", _creds(), REGISTRY, mon=_mon(sim_port, "cisco"))
    assert s.ok, (s.error_kind, s.error)
    assert (s.vendor_profile, s.sys_name, s.uptime_s) == ("cisco", "cisco-sim", 86400.0)
    assert (s.cpu_pct, s.mem_pct, s.temp_c) == (52.0, 75.0, 47.0)      # max of cores / used÷(used+free) / hottest
    assert [(i.if_index, i.name, i.oper_status, i.speed_mbps, i.counter_bits) for i in s.interfaces] == [
        (1, "Gi0/0/0", 1, 1000, 64), (2, "Gi0/0/1", 2, 1000, 64)]
    first = s.interfaces[0]
    assert (first.in_octets, first.out_octets, first.in_errors, first.in_discards) == (
        123456789012, 98765432100, 12, 3)


@needs_sim
async def test_huawei_profile_and_zero_temperature_is_ignored(sim_port):
    s = await poll_device("127.0.0.1", _creds(), REGISTRY, mon=_mon(sim_port, "huawei"))
    assert s.ok and s.vendor_profile == "huawei"
    assert (s.cpu_pct, s.mem_pct, s.temp_c) == (23.0, 61.0, 45.0)      # the 0 °C sensor-less entity is dropped


@needs_sim
async def test_generic_agent_uses_host_resources_and_32bit_fallback(sim_port):
    s = await poll_device("127.0.0.1", _creds(), REGISTRY, mon=_mon(sim_port, "generic"))
    assert s.ok and s.vendor_profile == "generic"
    assert (s.cpu_pct, s.mem_pct, s.temp_c) == (30.0, 75.0, None)      # no temperature on this agent: None, not 0
    [eth] = s.interfaces
    assert (eth.name, eth.speed_mbps, eth.counter_bits, eth.in_octets) == ("eth0", 100, 32, 4_000_000_000)


@needs_sim
async def test_nivetti_placeholder_is_monitored_with_generic_metrics(sim_port):
    s = await poll_device("127.0.0.1", _creds(), REGISTRY, mon=_mon(sim_port, "nivetti"))
    assert s.ok and s.vendor_profile == "nivetti"
    assert (s.cpu_pct, s.mem_pct) == (30.0, 75.0) and len(s.interfaces) == 2


@needs_sim
async def test_device_without_system_mib_is_a_protocol_failure(sim_port):
    s = await poll_device("127.0.0.1", _creds(), REGISTRY, mon=_mon(sim_port, "empty"))
    assert not s.ok and s.error_kind is SnmpErrorKind.PROTOCOL and "system MIB" in s.error


@needs_sim
@pytest.mark.parametrize("override", [{"auth_key": "wrong-auth-key"}, {"priv_key": "wrong-priv-key"},
                                      {"username": "nobody-here"}])
async def test_wrong_credentials_are_reported_as_auth_failures_without_leaking(sim_port, override):
    s = await poll_device("127.0.0.1", _creds(**override), REGISTRY, mon=_mon(sim_port, "cisco"))
    assert not s.ok and s.error_kind is SnmpErrorKind.AUTH
    leaked = [v for v in (AUTH_KEY, PRIV_KEY, *override.values()) if v in (s.error or "")]
    assert not leaked, leaked


@needs_sim
async def test_unanswered_port_times_out_promptly(sim_port):
    t0 = time.time()
    s = await poll_device("127.0.0.1", _creds(), REGISTRY, mon=_mon(_free_udp_port(), timeout=1, deadline=8))
    assert not s.ok and s.error_kind in {SnmpErrorKind.TIMEOUT, SnmpErrorKind.UNREACHABLE}
    assert time.time() - t0 < 8


@needs_sim
async def test_hung_device_can_never_exceed_the_poll_deadline_sec31(sim_port):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as mute:   # accepts packets, never answers
        mute.bind(("127.0.0.1", 0))
        port = mute.getsockname()[1]
        t0 = time.time()
        s = await poll_device("127.0.0.1", _creds(), REGISTRY, mon=_mon(port, timeout=2, retries=3, deadline=3))
    assert not s.ok and s.error_kind in {SnmpErrorKind.DEADLINE, SnmpErrorKind.TIMEOUT}
    assert time.time() - t0 < 6, "retries x timeout would take 8 s: the deadline must cut it short"


@needs_sim
async def test_many_polls_in_parallel_do_not_interfere(sim_port):
    ctxs = ["cisco", "huawei", "generic", "nivetti"] * 4
    samples = await asyncio.gather(*[poll_device("127.0.0.1", _creds(), REGISTRY, mon=_mon(sim_port, c)) for c in ctxs])
    assert all(s.ok for s in samples)
    assert [s.vendor_profile for s in samples] == ctxs


# ═══ database ═══════════════════════════════════════════════════════════════════════════════════
@pytest.fixture
async def sm():
    engine = create_async_engine(get_settings().database_url.get_secret_value())
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _attempt(sm, *rows) -> bool:
    async with sm() as s:
        s.add_all(rows)
        try:
            await s.commit()
        except IntegrityError:
            await s.rollback()
            return False
        return True


def _profile(name: str, **over) -> SnmpCredentialProfile:
    base = dict(id=uuid.uuid4(), name=name, security_level="authPriv", username="u", auth_protocol="SHA",
                auth_key_enc=encrypt_secret(AUTH_KEY), priv_protocol="AES128", priv_key_enc=encrypt_secret(PRIV_KEY),
                is_default=False)
    return SnmpCredentialProfile(**{**base, **over})


@needs_db
async def test_credentials_are_stored_encrypted_and_constraints_hold(sm):
    tag = f"p3a1-{uuid.uuid4().hex[:8]}"
    try:
        assert await _attempt(sm, _profile(tag)) is True
        async with sm() as s:
            raw = (await s.execute(text("SELECT auth_key_enc, priv_key_enc FROM snmp_credential_profiles "
                                        "WHERE name = :n"), {"n": tag})).one()
        assert AUTH_KEY not in raw.auth_key_enc and PRIV_KEY not in raw.priv_key_enc          # SEC-33
        assert decrypt_secret(raw.auth_key_enc) == AUTH_KEY and decrypt_secret(raw.priv_key_enc) == PRIV_KEY

        assert await _attempt(sm, _profile(tag)) is False                                      # unique name
        assert await _attempt(sm, _profile(f"{tag}-a", auth_protocol="MD5")) is False          # weak algorithm
        assert await _attempt(sm, _profile(f"{tag}-b", priv_protocol="DES")) is False
        assert await _attempt(sm, _profile(f"{tag}-c", security_level="noAuthNoPriv")) is False
        assert await _attempt(sm, _profile(f"{tag}-d", priv_protocol=None, priv_key_enc=None)) is False   # authPriv w/o priv
        assert await _attempt(sm, _profile(f"{tag}-e", security_level="authNoPriv")) is False             # authNoPriv with priv
        assert await _attempt(sm, _profile(f"{tag}-f", security_level="authNoPriv", priv_protocol=None,
                                           priv_key_enc=None)) is True
        # only one default profile may exist
        async with sm() as s:
            existing_default = await s.scalar(text("SELECT count(*) FROM snmp_credential_profiles WHERE is_default"))
        if existing_default == 0:
            assert await _attempt(sm, _profile(f"{tag}-g", is_default=True)) is True
            assert await _attempt(sm, _profile(f"{tag}-h", is_default=True)) is False
    finally:
        async with sm() as s:
            await s.execute(delete(SnmpCredentialProfile).where(SnmpCredentialProfile.name.like(f"{tag}%")))
            await s.commit()


@needs_db
async def test_poll_state_and_metrics_tables_enforce_their_rules(sm):
    async with sm() as s:
        device_id = await s.scalar(select(Device.id).limit(1))
        interface_id = await s.scalar(select(Interface.id).limit(1))
    if device_id is None or interface_id is None:
        pytest.skip("seed data (make seed) required: need one device and one interface")
    tag, now = f"p3a1-{uuid.uuid4().hex[:8]}", datetime.now(UTC)
    prof = _profile(tag)
    try:
        assert await _attempt(sm, prof) is True
        assert await _attempt(sm, DevicePollState(device_id=device_id, credential_profile_id=prof.id)) is True
        assert await _attempt(sm, DevicePollState(device_id=device_id)) is False                   # one state per device
        # deleting a profile keeps the device's poll state and falls back to the default (SET NULL)
        async with sm() as s:
            await s.execute(delete(SnmpCredentialProfile).where(SnmpCredentialProfile.id == prof.id))
            await s.commit()
            kept = (await s.execute(select(DevicePollState).where(DevicePollState.device_id == device_id))).scalar_one()
        assert kept.credential_profile_id is None
        async with sm() as s:
            await s.execute(text("UPDATE device_poll_state SET consecutive_failures = 3 WHERE device_id = :d"),
                            {"d": device_id})
            await s.commit()
        assert await _attempt(sm, DeviceMetric(device_id=device_id, ts=now, cpu_pct=150)) is False
        assert await _attempt(sm, DeviceMetric(device_id=device_id, ts=now, mem_pct=-1)) is False
        assert await _attempt(sm, DeviceMetric(device_id=device_id, ts=now, cpu_pct=12.5, mem_pct=40, temp_c=44,
                                               uptime_s=100)) is True
        assert await _attempt(sm, DeviceMetric(device_id=device_id, ts=now)) is False               # duplicate (device, ts)
        assert await _attempt(sm, InterfaceMetric(interface_id=interface_id, ts=now, in_util_pct=101)) is False
        assert await _attempt(sm, InterfaceMetric(interface_id=interface_id, ts=now, in_bps=10**10, in_util_pct=99.5,
                                                  in_errors=2, oper_status=1)) is True
        async with sm() as s:   # failure counter may not go negative
            with pytest.raises(IntegrityError):
                await s.execute(text("UPDATE device_poll_state SET consecutive_failures = -1 WHERE device_id = :d"),
                                {"d": device_id})
    finally:
        async with sm() as s:
            await s.execute(delete(DeviceMetric).where(DeviceMetric.device_id == device_id, DeviceMetric.ts == now))
            await s.execute(delete(InterfaceMetric).where(InterfaceMetric.interface_id == interface_id,
                                                          InterfaceMetric.ts == now))
            await s.execute(delete(DevicePollState).where(DevicePollState.device_id == device_id))
            await s.execute(delete(SnmpCredentialProfile).where(SnmpCredentialProfile.name == tag))
            await s.commit()


# ═══ migration on a scratch database ════════════════════════════════════════════════════════════
async def _alembic(db_url: str, *args: str) -> tuple[int, str]:
    env = {**os.environ, "NRIMS_DATABASE_URL": db_url}
    proc = await asyncio.create_subprocess_exec(  # noqa: S603
        sys.executable, "-m", "alembic", *args, cwd=BACKEND, env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await proc.communicate()
    return proc.returncode or 0, out.decode(errors="replace")


@needs_db
async def test_migration_creates_only_new_tables_and_roundtrips():
    base = make_url(get_settings().database_url.get_secret_value())
    name = f"nrims_p3a1_{uuid.uuid4().hex[:8]}"
    admin = create_async_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as c:
            await c.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as exc:  # no CREATEDB privilege
        await admin.dispose()
        pytest.skip(f"cannot create a scratch database: {type(exc).__name__}")
    url = base.set(database=name).render_as_string(hide_password=False)
    eng = create_async_engine(url)
    new = {"snmp_credential_profiles", "device_poll_state", "device_metrics", "interface_metrics"}

    async def tables() -> set[str]:
        async with eng.connect() as c:
            return set((await c.execute(text("SELECT table_name FROM information_schema.tables "
                                             "WHERE table_schema = 'public'"))).scalars())
    try:
        code, out = await _alembic(url, "upgrade", "b7e19c3a5d20")
        assert code == 0, out
        full = await tables()
        assert new <= full
        code, out = await _alembic(url, "check")
        assert code == 0, f"model/migration drift:\n{out}"

        code, out = await _alembic(url, "downgrade", "-1")                  # drops exactly the four new tables
        assert code == 0, out
        assert await tables() == full - new
        code, out = await _alembic(url, "upgrade", "b7e19c3a5d20")
        assert code == 0 and await tables() == full
    finally:
        await eng.dispose()
        async with admin.connect() as c:
            await c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await admin.dispose()
