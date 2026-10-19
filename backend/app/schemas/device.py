from pydantic import BaseModel, ConfigDict
from uuid import UUID

class DeviceRead(BaseModel):
    id: UUID
    hostname: str
    ip_address: str
    category: str
    status: str
    source_system: str
    station_code: str
    is_maintenance: bool # <-- यह जोड़ना अनिवार्य था

    model_config = ConfigDict(from_attributes=True)