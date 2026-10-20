"""SQLAlchemy models — import all so Base.metadata is fully populated.

CRITICAL: missing imports here cause `alembic revision --autogenerate` to
produce empty migrations. Every model module MUST be imported below.
"""
from app.models.action import RemoteAction
from app.models.alarm import Alarm
from app.models.audit import AuditEvent
from app.models.configuration_change import ConfigurationChange
from app.models.device import Device
from app.models.device_link import DeviceLink
from app.models.discovery import DiscoveredDevice
from app.models.interface import Interface
from app.models.link import Link
from app.models.station import Station
from app.models.user import User

__all__ = [
    "User",
    "Station",
    "Device",
    "Alarm",
    "AuditEvent",
    "Link",
    "Interface",
    "RemoteAction",
    "ConfigurationChange",
    "DeviceLink",
    "DiscoveredDevice",
]