import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.alarm import Alarm
    from app.models.interface import Interface
    from app.models.station import Station


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(100), index=True)
    hostname: Mapped[str] = mapped_column(String(255), index=True)
    ip_address: Mapped[str] = mapped_column(String(50))
    
    category: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    
    station_code: Mapped[str] = mapped_column(ForeignKey("stations.code", ondelete="CASCADE"), index=True)
    
    parent_device_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    position_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # सही तरीका (text जोड़ दिया गया है)
    is_maintenance: Mapped[bool] = mapped_column(Boolean, server_default=text('false'), nullable=False)
    
    source_system: Mapped[str] = mapped_column(String(50))
    source_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    station: Mapped["Station"] = relationship(back_populates="devices")
    alarms: Mapped[list["Alarm"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    interfaces: Mapped[list["Interface"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    children: Mapped[list["Device"]] = relationship("Device", back_populates="parent")
    parent: Mapped["Device | None"] = relationship("Device", back_populates="children", remote_side=[id])
    

Index("ix_devices_status", Device.status)
