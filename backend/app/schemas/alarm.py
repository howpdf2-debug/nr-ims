from pydantic import BaseModel, ConfigDict
from uuid import UUID

class AlarmRead(BaseModel):
    id: UUID
    device_id: UUID
    severity: str
    message: str
    status: str
    model_config = ConfigDict(from_attributes=True)
