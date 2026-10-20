from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlarmRead(BaseModel):
    id: UUID
    device_id: UUID
    severity: str
    message: str
    status: str
    model_config = ConfigDict(from_attributes=True)
