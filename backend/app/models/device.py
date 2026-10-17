import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(100), index=True)  # LibreNMS/Zabbix se aane wala ID
    hostname: Mapped[str] = mapped_column(String(255), index=True)
    ip_address: Mapped[str] = mapped_column(String(50))
    device_type: Mapped[str] = mapped_column(String(50))  # router, switch, server, modem, lan
    status: Mapped[str] = mapped_column(String(20), default="unknown")  # up, down, unknown, disabled
    source_system: Mapped[str] = mapped_column(String(50))  # simulator, librenms, zabbix
    source_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())