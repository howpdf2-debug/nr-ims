"""Inter-station link read model (replaces returning raw ORM rows)."""

import uuid

from pydantic import BaseModel, ConfigDict


class LinkRead(BaseModel):
    id: uuid.UUID
    source_station: str
    destination_station: str
    provider: str
    status: str
    bandwidth_mbps: int
    latency_ms: float
    packet_loss_pct: float
    crc_errors: int
    is_admin_shutdown: bool
    model_config = ConfigDict(from_attributes=True)
