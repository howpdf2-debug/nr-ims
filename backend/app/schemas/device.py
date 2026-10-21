"""Device schemas: read model, create payload, detail composite (device + interfaces + OSPF)."""

import ipaddress
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


class DeviceCategory(StrEnum):
    """Categories accepted when creating a device by hand (matches the UI picker + discovery types)."""

    ROUTER = "router"
    SWITCH = "switch"
    COUNTER = "counter"
    TS = "ts"
    BTS = "bts"
    MODEM = "modem"
    SERVER = "server"
    FIREWALL = "firewall"
    OTHER = "other"


Hostname = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
]


class DeviceRead(BaseModel):
    id: uuid.UUID
    external_id: str
    hostname: str
    ip_address: str
    category: str
    status: str
    station_code: str
    parent_device_id: uuid.UUID | None = None
    position_x: float | None = None
    position_y: float | None = None
    is_maintenance: bool
    source_system: str
    source_timestamp: datetime | None = None
    ingested_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class DeviceCreate(BaseModel):
    """Payload for POST /devices/. Unknown fields are rejected (typo = 422, not silently ignored)."""

    model_config = ConfigDict(extra="forbid")

    hostname: Hostname
    ip_address: str
    category: DeviceCategory
    station_code: str = Field(min_length=1, max_length=10)
    parent_device_id: uuid.UUID | None = None

    @field_validator("ip_address")
    @classmethod
    def _valid_ip(cls, v: str) -> str:
        try:
            return str(ipaddress.ip_address(v.strip()))
        except ValueError:
            raise ValueError("ip_address must be a valid IPv4 or IPv6 address") from None


class InterfaceRead(BaseModel):
    id: uuid.UUID
    name: str
    ip_address: str | None = None
    status: str
    description: str | None = None
    in_mbps: float = 0.0
    out_mbps: float = 0.0
    errors: int = 0
    model_config = ConfigDict(from_attributes=True)


class OspfNeighbor(BaseModel):
    """Placeholder contract: populated by the monitoring engine (roadmap Phase 3)."""

    neighbor_ip: str
    state: str
    interface: str


class DeviceDetail(BaseModel):
    device: DeviceRead
    interfaces: list[InterfaceRead] = Field(default_factory=list)
    ospf_neighbors: list[OspfNeighbor] = Field(default_factory=list)
