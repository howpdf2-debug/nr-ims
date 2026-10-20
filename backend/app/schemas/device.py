import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
