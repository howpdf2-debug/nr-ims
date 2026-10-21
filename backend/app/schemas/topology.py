"""Payloads for the station-local (device level) topology API."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocalLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_device_id: uuid.UUID
    destination_device_id: uuid.UUID
    media_type: Literal["copper", "ofc"] = "copper"
    description: str | None = Field(default=None, max_length=255)

    @field_validator("description")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None


class DevicePosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=-1_000_000, le=1_000_000)
    y: float = Field(ge=-1_000_000, le=1_000_000)
