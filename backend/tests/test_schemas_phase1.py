"""Pure validation tests for the Phase 1 request/response schemas (no DB)."""

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.device import DeviceCategory, DeviceCreate, DeviceDetail, DeviceRead
from app.schemas.topology import DevicePosition, LocalLinkCreate


def _device(**over):
    base = {"hostname": "bsb-sw-3", "ip_address": "10.10.2.99", "category": "switch", "station_code": "BSB"}
    return {**base, **over}


def test_device_create_valid_and_normalised():
    d = DeviceCreate(**_device(hostname="  bsb-sw-3  ", ip_address=" 10.10.2.99 "))
    assert d.hostname == "bsb-sw-3" and d.ip_address == "10.10.2.99"
    assert d.category is DeviceCategory.SWITCH and d.parent_device_id is None


def test_device_create_accepts_ipv6_and_canonicalises():
    assert DeviceCreate(**_device(ip_address="2001:0db8:0000:0000:0000:0000:0000:0001")).ip_address == "2001:db8::1"


@pytest.mark.parametrize("bad_ip", ["999.1.1.1", "router1", "10.0.0", "", "10.0.0.1/24"])
def test_device_create_rejects_bad_ip(bad_ip):
    with pytest.raises(ValidationError):
        DeviceCreate(**_device(ip_address=bad_ip))


@pytest.mark.parametrize("bad_host", ["", " ", "-lead", "has space", "semi;colon", "x" * 256, "<script>"])
def test_device_create_rejects_bad_hostname(bad_host):
    with pytest.raises(ValidationError):
        DeviceCreate(**_device(hostname=bad_host))


def test_device_create_rejects_unknown_category_and_extra_fields():
    with pytest.raises(ValidationError):
        DeviceCreate(**_device(category="toaster"))
    with pytest.raises(ValidationError):
        DeviceCreate(**_device(status="up"))  # clients may not set status


def test_device_create_parent_is_uuid_or_null():
    assert DeviceCreate(**_device(parent_device_id=None)).parent_device_id is None
    pid = uuid.uuid4()
    assert DeviceCreate(**_device(parent_device_id=str(pid))).parent_device_id == pid
    with pytest.raises(ValidationError):
        DeviceCreate(**_device(parent_device_id=""))


def test_every_ui_category_is_accepted():
    for c in ("switch", "counter", "ts", "bts", "modem", "router"):  # StationDetail.tsx picker values
        assert DeviceCreate(**_device(category=c)).category.value == c


def test_local_link_defaults_and_blank_description():
    a, b = uuid.uuid4(), uuid.uuid4()
    lk = LocalLinkCreate(source_device_id=a, destination_device_id=b, description="   ")
    assert lk.media_type == "copper" and lk.description is None
    assert LocalLinkCreate(source_device_id=a, destination_device_id=b, media_type="ofc").media_type == "ofc"


def test_local_link_rejects_bad_media_and_ids():
    a = uuid.uuid4()
    with pytest.raises(ValidationError):
        LocalLinkCreate(source_device_id=a, destination_device_id=a, media_type="wifi")
    with pytest.raises(ValidationError):
        LocalLinkCreate(source_device_id="", destination_device_id=a)


@pytest.mark.parametrize("x,y", [(float("nan"), 0), (float("inf"), 0), (2_000_000, 0), (0, -2_000_000)])
def test_position_rejects_non_finite_and_out_of_range(x, y):
    with pytest.raises(ValidationError):
        DevicePosition(x=x, y=y)


def test_position_accepts_normal_values():
    p = DevicePosition(x=-12.5, y=300)
    assert (p.x, p.y) == (-12.5, 300)


def test_device_detail_contract_shape():
    """The device page destructures exactly these three keys (regression for the blank-page bug)."""
    dev = DeviceRead(id=uuid.uuid4(), external_id="X", hostname="h", ip_address="1.1.1.1", category="router",
                     status="up", station_code="BSB", is_maintenance=False, source_system="t")
    out = DeviceDetail(device=dev).model_dump(mode="json")
    assert set(out) == {"device", "interfaces", "ospf_neighbors"}
    assert out["interfaces"] == [] and out["ospf_neighbors"] == []
