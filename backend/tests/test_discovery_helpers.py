"""Discovery pure helpers + CSV formula-injection guard."""

from app.api.v1.reports import _csv_safe
from app.workers.discovery import _classify, _expand_targets, _pick_mac


def test_expand_single_ip_and_dedupe():
    assert _expand_targets("10.0.0.1, 10.0.0.1 ,10.0.0.2") == ["10.0.0.1", "10.0.0.2"]


def test_expand_cidr_excludes_network_and_broadcast():
    out = _expand_targets("192.168.1.0/30")
    assert out == ["192.168.1.1", "192.168.1.2"]


def test_expand_respects_limit():
    assert len(_expand_targets("10.0.0.0/16", limit=50)) == 50


def test_expand_skips_garbage_and_blank():
    assert _expand_targets(" , ,not an ip/zz") == []


def test_classify_by_interface_count_then_descr():
    assert _classify("anything", [{}] * 8) == "switch"
    assert _classify("Linux 5.15", []) == "server"
    assert _classify("FortiGate-100", []) == "firewall"
    assert _classify("Cisco IOS", []) == "router"
    assert _classify(None, []) == "unknown"


def test_pick_mac_skips_loopback_and_short_values():
    ifs = [
        {"ifDescr": "lo", "ifPhysAddress": "00:00:00:00:00:00"},
        {"ifDescr": "eth0", "ifPhysAddress": "ab"},
        {"ifDescr": "eth1", "ifPhysAddress": "aa:bb:cc:dd:ee:ff"},
    ]
    assert _pick_mac(ifs) == "aa:bb:cc:dd:ee:ff"
    assert _pick_mac([]) is None


def test_csv_safe_neutralises_formulas():
    for bad in ("=1+1", "+cmd", "-2", "@SUM(A1)", "\tx", "\rx"):
        assert _csv_safe(bad).startswith("'")
    assert _csv_safe("router down") == "router down"
    assert _csv_safe(42) == "42"
