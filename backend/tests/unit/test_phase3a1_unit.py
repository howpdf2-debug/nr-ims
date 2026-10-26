"""Phase 3a-1 unit tests. No database, no network, no simulator: they run in `make test` and in CI.

Sections: credential crypto & allow-list (SEC-33/35) | rate maths | vendor profiles | SNMPv3 client guards
(SEC-31/32/34) | model + migration metadata.
"""

import ast
import inspect
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError
from pysnmp.proto import errind
from pysnmp.proto.rfc1902 import Counter64, Gauge32, Integer32, ObjectIdentifier, OctetString, TimeTicks
from pysnmp.proto.rfc1905 import NoSuchInstance

from app.config import ConfigError, Env
from app.db.base import Base
from app.models.monitoring import DeviceMetric, DevicePollState, InterfaceMetric, SnmpCredentialProfile
from app.monitoring import profiles as prof
from app.monitoring.profiles import MetricSource, ProfileError, ProfileRegistry
from app.monitoring.rates import CounterSnapshot, compute_interface_rates, counter_delta
from app.monitoring.security import (
    CredentialError,
    MonitoringSettings,
    TargetNotAllowed,
    build_fernet,
    check_snmp_target,
    decrypt_secret,
    encrypt_secret,
)
from app.services import snmp_v3
from app.services.snmp_v3 import (
    ReadOnlySnmpClient,
    SnmpErrorKind,
    SnmpV3Credentials,
    classify_error,
    poll_device,
    to_python,
)

BACKEND = Path(__file__).resolve().parents[2]


def _app(env=Env.DEVELOPMENT, secret="s" * 40):
    return SimpleNamespace(env=env, secret_key=SecretStr(secret))


# ═══ credential crypto & allow-list ═════════════════════════════════════════════════════════════
def test_encrypt_roundtrip_and_token_is_not_plaintext():
    f = build_fernet(_app(), MonitoringSettings())
    token = encrypt_secret("s3cret-passphrase", f)
    assert "s3cret" not in token and decrypt_secret(token, f) == "s3cret-passphrase"


def test_dev_key_is_stable_per_secret_and_differs_between_secrets():
    a1, a2 = build_fernet(_app(secret="a" * 40), MonitoringSettings()), build_fernet(_app(secret="a" * 40), MonitoringSettings())
    b = build_fernet(_app(secret="b" * 40), MonitoringSettings())
    token = encrypt_secret("x" * 10, a1)
    assert decrypt_secret(token, a2) == "x" * 10
    with pytest.raises(CredentialError):
        decrypt_secret(token, b)


def test_production_refuses_to_run_without_an_explicit_key():
    with pytest.raises(ConfigError, match="NRIMS_CREDENTIAL_KEY"):
        build_fernet(_app(env=Env.PRODUCTION), MonitoringSettings())


def test_invalid_key_is_rejected_with_instructions():
    with pytest.raises(ConfigError, match="Fernet"):
        build_fernet(_app(), MonitoringSettings(credential_key=SecretStr("not-a-key")))


def test_key_rotation_new_key_encrypts_old_token_still_decrypts():
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    f_old = build_fernet(_app(), MonitoringSettings(credential_key=SecretStr(old)))
    token = encrypt_secret("rotate-me-123", f_old)
    f_rot = build_fernet(_app(), MonitoringSettings(credential_key=SecretStr(f"{new},{old}")))
    assert decrypt_secret(token, f_rot) == "rotate-me-123"
    fresh = encrypt_secret("again-12345", f_rot)
    only_new = build_fernet(_app(), MonitoringSettings(credential_key=SecretStr(new)))
    assert decrypt_secret(fresh, only_new) == "again-12345"  # new tokens use the FIRST key


def test_tampered_or_garbage_token_raises_without_leaking():
    f = build_fernet(_app(), MonitoringSettings())
    token = encrypt_secret("topsecret-1", f)
    for bad in (token[:-4] + "AAAA", "garbage", ""):
        with pytest.raises(CredentialError) as exc:
            decrypt_secret(bad, f)
        assert "topsecret" not in str(exc.value)


@pytest.mark.parametrize(("host", "ok"), [
    ("10.1.2.3", True), ("172.16.5.5", True), ("192.168.0.9", True), ("127.0.0.1", True),
    ("8.8.8.8", False), ("172.32.0.1", False), ("203.0.113.9", False),
    ("router.local", False), ("10.1.2.3/24", False), ("", False), ("10.1.2", False), ("::1", False),
])
def test_default_allowlist(host, ok):
    cidrs = MonitoringSettings().snmp_allowed_cidrs
    if ok:
        assert str(check_snmp_target(host, cidrs)) == host
    else:
        with pytest.raises(TargetNotAllowed):
            check_snmp_target(host, cidrs)


def test_allowlist_can_be_narrowed_and_bad_cidr_is_rejected():
    assert check_snmp_target("10.9.9.9", ["10.9.0.0/16"])
    with pytest.raises(TargetNotAllowed):
        check_snmp_target("10.8.9.9", ["10.9.0.0/16"])
    with pytest.raises(ValidationError):
        MonitoringSettings(snmp_allowed_cidrs=["not-a-cidr"])


def test_settings_bounds():
    for bad in ({"snmp_timeout_s": 0}, {"snmp_retries": 99}, {"poll_deadline_s": 0}, {"snmp_port": 70000}):
        with pytest.raises(ValidationError):
            MonitoringSettings(**bad)


# ═══ rate maths ═════════════════════════════════════════════════════════════════════════════════
def snap(ts, up=1000.0, i=0, o=0, ie=0, oe=0, idc=0, odc=0, bits=64):
    return CounterSnapshot(ts=ts, uptime_s=up, in_octets=i, out_octets=o, in_errors=ie, out_errors=oe,
                           in_discards=idc, out_discards=odc, bits=bits)


def test_counter_delta_basic_wrap_and_reset_rules():
    assert counter_delta(100, 250, 64) == 150
    assert counter_delta(2**32 - 10, 5, 32) == 15            # 32-bit wrap
    assert counter_delta(500, 100, 64) is None                # 64-bit never wraps: reset
    assert counter_delta(-1, 5, 32) is None and counter_delta(5, -1, 32) is None
    assert counter_delta(2**32 - 10, 5, 32, max_plausible=10) is None   # wrap implies impossible rate -> reset
    assert counter_delta(0, 10**9, 64, max_plausible=1000) is None      # jump larger than the line can carry


def test_rates_normal_case_and_utilisation():
    prev = snap(0, i=0, o=0)
    curr = snap(60, i=750_000_000, o=75_000_000)  # 100 Mbit/s in, 10 Mbit/s out over 60 s
    r = compute_interface_rates(prev, curr, 1000)
    assert (r.in_bps, r.out_bps) == (100_000_000, 10_000_000)
    assert (r.in_util_pct, r.out_util_pct) == (10.0, 1.0)


def test_rates_none_when_no_reliable_value():
    base = snap(0, up=5000.0, i=1000)
    assert compute_interface_rates(None, snap(60), 1000) is None                        # first sample
    assert compute_interface_rates(base, snap(0, i=2000), 1000) is None                 # dt == 0
    assert compute_interface_rates(base, snap(-5, i=2000), 1000) is None                # dt < 0
    assert compute_interface_rates(base, snap(901, up=5901.0, i=2000), 1000) is None    # gap > 15 min
    assert compute_interface_rates(base, snap(60, up=10.0, i=2000), 1000) is None       # rebooted
    assert compute_interface_rates(base, snap(60, up=5060.0, i=2000, bits=32), 1000) is None  # source changed
    backwards = compute_interface_rates(snap(0, i=10**12), snap(60, i=5), 1000)          # 64-bit went backwards
    assert backwards is not None and backwards.in_bps is None and backwards.in_util_pct is None
    assert backwards.out_bps == 0                       # the other direction is still reported


def test_rates_32bit_wrap_accepted_only_if_physically_possible():
    prev = snap(0, i=2**32 - 1_000_000, bits=32)
    ok = compute_interface_rates(prev, snap(10, i=4_000_000, bits=32), 1000)   # 5 MB in 10 s = 4 Mbit/s
    assert ok is not None and ok.in_bps == 4_000_000
    prev_slow = snap(0, i=2**32 - 10, bits=32)
    assert compute_interface_rates(prev_slow, snap(1, i=5, bits=32), 10) is not None   # tiny wrap on a 10 Mbit link
    # decrease on a 100 Mbit link that would need ~3.4 Gbit/s -> a reset, not a wrap
    reset = compute_interface_rates(snap(0, i=3_000_000_000, bits=32), snap(10, i=1_000, bits=32), 100)
    assert reset is not None and reset.in_bps is None


def test_rates_glitch_and_unknown_speed_and_clamp():
    assert compute_interface_rates(snap(0, i=0), snap(10, i=10**11), 100).in_bps is None   # > line rate
    r = compute_interface_rates(snap(0, i=0), snap(10, i=1_000_000), None)                  # speed unknown
    assert r.in_bps == 800_000 and r.in_util_pct is None
    r = compute_interface_rates(snap(0, i=0), snap(10, i=1_375_000), 1)    # 1.1 Mbit on a 1 Mbit link (jitter)
    assert r.in_util_pct == 100.0


def test_rates_error_and_discard_deltas():
    r = compute_interface_rates(snap(0, ie=5, oe=1, idc=2, odc=0), snap(60, ie=9, oe=1, idc=2, odc=7), 1000)
    assert (r.in_errors, r.out_errors, r.in_discards, r.out_discards) == (4, 0, 0, 7)
    wrapped = compute_interface_rates(snap(0, ie=2**32 - 2), snap(60, ie=3), 1000)
    assert wrapped.in_errors == 5


# ═══ vendor profiles ════════════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def registry():
    return ProfileRegistry.load()


def test_packaged_profiles_load_and_have_the_expected_shape(registry):
    assert registry.names == ["cisco", "huawei", "nivetti", "generic"]
    assert registry.default.name == "generic"
    for p in registry.profiles:
        assert p.cpu, f"{p.name} has no CPU source"


@pytest.mark.parametrize(("oid", "descr", "expected"), [
    ("1.3.6.1.4.1.9.1.1234", "whatever", "cisco"),
    (".1.3.6.1.4.1.9.1.1234", None, "cisco"),
    ("1.3.6.1.4.1.90.1.1", "x", "generic"),          # enterprise 90 must NOT match enterprise 9
    ("1.3.6.1.4.1.2011.2.100", "Huawei VRP", "huawei"),
    ("1.3.6.1.4.1.99999.1", "Nivetti NiOS 3.2", "nivetti"),
    ("1.3.6.1.4.1.99999.1", "NIVETTI router", "nivetti"),
    ("1.3.6.1.4.1.8072.3.2.10", "Linux box", "generic"),
    (None, None, "generic"),
])
def test_profile_selection(registry, oid, descr, expected):
    assert registry.select(oid, descr).name == expected


def test_nivetti_placeholder_inherits_generic_metrics(registry):
    nivetti, generic = registry.select(None, "Nivetti NiOS"), registry.default
    assert nivetti.cpu == generic.cpu and nivetti.memory == generic.memory


def test_unbounded_sysdescr_is_truncated_before_regex(registry):
    assert registry.select(None, "x" * 100_000 + "nivetti").name == "generic"  # beyond the 512-char window


def _write(tmp_path, text):
    p = tmp_path / "p.toml"
    p.write_text(text, encoding="utf-8")
    return p


GOOD = 'version = 1\n[[profile]]\nname = "g"\ndefault = true\n[[profile.cpu]]\noid = "1.3.6.1.2.1.25.3.3.1.2"\n'


@pytest.mark.parametrize(("body", "needle"), [
    ("not toml ][", "invalid TOML"),
    ('version = 2\n[[profile]]\nname="g"\ndefault=true', "version"),
    ("version = 1\n", "no [[profile]]"),
    (GOOD + '[[profile.cpu]]\noid = "1.3.6"\n', "dotted-numeric"),
    (GOOD + '[[profile.cpu]]\noid = "abc.def.ghi"\n', "dotted-numeric"),
    (GOOD + '[[profile.cpu]]\noid = "1.3.6.1.2.1.25"\nbogus_field = 1\n', "bogus_field"),
    (GOOD + '[[profile.memory]]\n[profile.memory.used]\noid = "1.3.6.1.4.1.1.1"\n', "exactly one of"),
    (GOOD.replace("default = true", "default = false"), "exactly one profile"),
    (GOOD + '[[profile]]\nname = "g"\n', "duplicate"),
    (GOOD + '[[profile]]\nname = "h"\ninherits = "zzz"\n', "unknown profile"),
    (GOOD + '[[profile]]\nname = "h"\nsys_descr_regex = "(unclosed"\n', "regular expression"),
    (GOOD + '[[profile]]\nname = "Bad Name!"\n', "name"),
    (GOOD + '[[profile]]\nname = "h"\nsys_object_id_prefix = "x.y"\n', "sys_object_id_prefix"),
])
def test_invalid_profiles_fail_loudly_with_a_useful_message(tmp_path, body, needle):
    with pytest.raises(ProfileError, match=re.escape(needle)):
        ProfileRegistry.load(_write(tmp_path, body))


def test_missing_profiles_file_is_a_clean_error(tmp_path):
    with pytest.raises(ProfileError, match="cannot read"):
        ProfileRegistry.load(tmp_path / "nope.toml")


def test_chained_inheritance_is_rejected(tmp_path):
    text = GOOD + '[[profile]]\nname = "a"\ninherits = "g"\n[[profile]]\nname = "b"\ninherits = "a"\n'
    with pytest.raises(ProfileError, match="inheriting"):
        ProfileRegistry.load(_write(tmp_path, text))


def src(**kw):
    return MetricSource(oid="1.3.6.1.4.1.1.1", **kw)


def test_reduce_values_aggregates_scales_inverts_and_ignores_zero():
    assert prof.reduce_values(src(aggregate="max"), [10, 50, "30"]) == 50
    assert prof.reduce_values(src(aggregate="min"), [10, 50]) == 10
    assert prof.reduce_values(src(aggregate="avg"), [10, 20, 60]) == 30
    assert prof.reduce_values(src(aggregate="first"), [7, 99]) == 7
    assert prof.reduce_values(src(scale=0.1), [455]) == pytest.approx(45.5)
    assert prof.reduce_values(src(invert_percent=True), [92]) == 8
    assert prof.reduce_values(src(ignore_zero=True), [0, 0, 41]) == 41
    assert prof.reduce_values(src(ignore_zero=True), [0, 0]) is None
    assert prof.reduce_values(src(), [None, "n/a", True]) is None and prof.reduce_values(src(), []) is None


def test_memory_percent_edge_cases():
    assert prof.memory_percent(300, 100) == 75.0
    for used, free in ((None, 1), (1, None), (0, 0), (-1, 5), (5, -1)):
        assert prof.memory_percent(used, free) is None


class FakeReader:
    def __init__(self, scalars=None, walks=None):
        self.scalars, self.walks, self.calls = scalars or {}, walks or {}, []

    async def get_optional(self, oid):
        self.calls.append(oid)
        return self.scalars.get(oid)

    async def walk(self, oid, max_rows=512):
        self.calls.append(oid)
        return [((i,), v) for i, v in enumerate(self.walks.get(oid, []), 1)]


async def test_cpu_uses_first_source_that_answers_else_falls_back(registry):
    generic = registry.default
    cpu_walk, idle = generic.cpu[0].oid, generic.cpu[1].oid
    assert await prof.read_cpu(FakeReader(walks={cpu_walk: [20, 40]}), generic) == 30.0
    r = FakeReader(scalars={idle: 91})                                 # no hrProcessorLoad -> ssCpuIdle
    assert await prof.read_cpu(r, generic) == 9.0
    assert await prof.read_cpu(FakeReader(), generic) is None
    assert await prof.read_cpu(FakeReader(walks={cpu_walk: [250]}), generic) is None   # >100 % is garbage


async def test_memory_all_three_shapes(registry):
    cisco, huawei, generic = (registry.select("1.3.6.1.4.1.9.1.1", None), registry.select("1.3.6.1.4.1.2011.1", None),
                              registry.default)
    used, free = cisco.memory[0].used.oid, cisco.memory[0].free.oid
    assert await prof.read_memory_pct(FakeReader(scalars={used: 300, free: 100}), cisco) == 75.0
    assert await prof.read_memory_pct(FakeReader(walks={huawei.memory[0].percent.oid: [40, 61]}), huawei) == 61.0
    total, avail = generic.memory[0].total.oid, generic.memory[0].available.oid
    assert await prof.read_memory_pct(FakeReader(scalars={total: 8000, avail: 2000}), generic) == 75.0
    assert await prof.read_memory_pct(FakeReader(scalars={total: 1000, avail: 5000}), generic) is None   # nonsense
    assert await prof.read_memory_pct(FakeReader(), generic) is None


async def test_temperature_range_and_zero_handling(registry):
    huawei, cisco = registry.select("1.3.6.1.4.1.2011.1", None), registry.select("1.3.6.1.4.1.9.1.1", None)
    assert await prof.read_temperature(FakeReader(walks={huawei.temperature[0].oid: [0, 0, 45]}), huawei) == 45.0
    assert await prof.read_temperature(FakeReader(walks={huawei.temperature[0].oid: [0, 0]}), huawei) is None
    assert await prof.read_temperature(FakeReader(walks={cisco.temperature[0].oid: [41, 47]}), cisco) == 47.0
    assert await prof.read_temperature(FakeReader(walks={cisco.temperature[0].oid: [9999]}), cisco) is None
    assert await prof.read_temperature(FakeReader(), registry.default) is None   # generic has no temperature


# ═══ SNMPv3 client guards ═══════════════════════════════════════════════════════════════════════
def creds(**kw):
    base = dict(username="nrims", auth_protocol="SHA", auth_key="authkey-123", priv_protocol="AES128",
                priv_key="privkey-123")
    return SnmpV3Credentials(**{**base, **kw})


def test_credentials_validation():
    assert creds().security_level == "authPriv"
    assert creds(priv_protocol=None, priv_key=None).security_level == "authNoPriv"
    for bad in ({"username": ""}, {"username": "u" * 65}, {"auth_protocol": "MD5"}, {"auth_key": "short"},
                {"priv_protocol": "DES"}, {"priv_key": "short"}, {"priv_protocol": None}, {"priv_key": None}):
        with pytest.raises(ValueError):
            creds(**bad)


def test_credentials_never_appear_in_repr_or_str():
    text = repr(creds()) + str(creds())
    assert "authkey-123" not in text and "privkey-123" not in text and "nrims" in text


def test_usm_objects_build_for_every_supported_protocol():
    for a in snmp_v3.AUTH_PROTOCOLS:
        for p in (*snmp_v3.PRIV_PROTOCOLS, None):
            c = creds(auth_protocol=a, priv_protocol=p, priv_key="privkey-123" if p else None)
            assert c.usm() is not None


@pytest.mark.parametrize(("indication", "kind"), [
    (errind.RequestTimedOut(), SnmpErrorKind.TIMEOUT),
    (errind.WrongDigest(), SnmpErrorKind.AUTH),
    (errind.UnknownUserName(), SnmpErrorKind.AUTH),
    (errind.DecryptionError(), SnmpErrorKind.AUTH),
    (errind.UnsupportedSecurityLevel(), SnmpErrorKind.AUTH),
    (errind.NoSuchContext(), SnmpErrorKind.PROTOCOL),
    (errind.TooBig(), SnmpErrorKind.PROTOCOL),
])
def test_error_classification(indication, kind):
    got, message = classify_error(indication)
    assert got is kind and "authkey" not in message


def test_to_python_conversions():
    assert to_python(Counter64(5)) == 5 and to_python(Gauge32(37)) == 37 and to_python(Integer32(2)) == 2
    assert to_python(TimeTicks(123456)) == 123456
    assert to_python(OctetString(b"GigabitEthernet0/1")) == "GigabitEthernet0/1"
    assert to_python(OctetString(b"\x00\x1b\x21")) == "00:1b:21"
    assert to_python(ObjectIdentifier("1.3.6.1.4.1.9.1.1234")) == "1.3.6.1.4.1.9.1.1234"
    assert to_python(NoSuchInstance()) is None


def test_to_python_returns_numeric_oid_for_the_class_seen_on_the_wire():
    """Regression (found by the simulator test): sysObjectID arrives as hlapi ObjectIdentity, whose
    prettyPrint() is symbolic ("SNMPv2-SMI::enterprises.9...") and made every vendor match fail."""

    class ObjectIdentity:  # stand-in with the same class name and API as pysnmp's hlapi object
        def asTuple(self):  # noqa: N802
            return (1, 3, 6, 1, 4, 1, 9, 1, 1234)

        def prettyPrint(self):  # noqa: N802
            return "SNMPv2-SMI::enterprises.9.1.1234"

    assert to_python(ObjectIdentity()) == "1.3.6.1.4.1.9.1.1234"


def test_client_is_read_only_by_construction_sec34():
    tree = ast.parse(Path(inspect.getsourcefile(snmp_v3)).read_text(encoding="utf-8"))
    imported = {a.name.lower() for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module
                and n.module.startswith("pysnmp") for a in n.names}
    assert imported & {"get_cmd", "bulk_walk_cmd"} == {"get_cmd", "bulk_walk_cmd"}
    assert not [n for n in imported if "set" in n.replace("usmaes", "").replace("usmhmac", "")], imported
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not {c for c in called if "set_cmd" in c.lower() or "setcmd" in c.lower()}
    public = {m for m, _ in inspect.getmembers(ReadOnlySnmpClient, inspect.isfunction) if not m.startswith("_")}
    assert public == {"get_optional", "get_many", "walk"}


async def test_poll_refuses_targets_outside_allowlist_without_touching_the_network(registry):
    for host in ("8.8.8.8", "router.example.com", "10.1.2.3/24"):
        sample = await poll_device(host, creds(), registry, mon=MonitoringSettings())
        assert sample.ok is False and sample.error_kind is SnmpErrorKind.NOT_ALLOWED
    narrow = MonitoringSettings(snmp_allowed_cidrs=["10.9.0.0/16"])
    assert (await poll_device("10.8.0.1", creds(), registry, mon=narrow)).error_kind is SnmpErrorKind.NOT_ALLOWED


async def test_client_requires_context_manager():
    c = ReadOnlySnmpClient("127.0.0.1", creds())
    with pytest.raises(RuntimeError, match="context manager"):
        await c.get_optional("1.3.6.1.2.1.1.5.0")


# ═══ model + migration metadata ═════════════════════════════════════════════════════════════════
def test_models_are_registered_on_the_shared_metadata():
    import app.models  # noqa: F401  (the register script must have added the monitoring import)

    for t in ("snmp_credential_profiles", "device_poll_state", "device_metrics", "interface_metrics"):
        assert t in Base.metadata.tables, f"{t} not registered: run scripts/phase3a1_register_models.py"


def test_constraints_are_declared():
    cks = lambda model: {c.name for c in model.__table__.constraints if c.name and c.name.startswith("ck_")}  # noqa: E731
    assert cks(SnmpCredentialProfile) == {"ck_snmp_profiles_security_level", "ck_snmp_profiles_auth_protocol",
                                          "ck_snmp_profiles_priv_protocol", "ck_snmp_profiles_priv_consistent"}
    assert cks(DevicePollState) == {"ck_device_poll_state_failures"}
    assert cks(DeviceMetric) == {"ck_device_metrics_cpu", "ck_device_metrics_mem"}
    assert cks(InterfaceMetric) == {"ck_interface_metrics_in_util", "ck_interface_metrics_out_util"}
    idx = {i.name for i in SnmpCredentialProfile.__table__.indexes}
    assert "uq_snmp_profiles_single_default" in idx


def test_migration_is_chained_after_phase2_with_a_single_head():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    script = ScriptDirectory.from_config(cfg)
    rev = script.get_revision("c4d2a8f61b30")
    assert rev is not None and rev.down_revision == "b7e19c3a5d20"
    assert len(script.get_heads()) == 1
