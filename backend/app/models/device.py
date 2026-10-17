import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Uuid, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(100), index=True)
    hostname: Mapped[str] = mapped_column(String(255), index=True)
    ip_address: Mapped[str] = mapped_column(String(50))
    
    category: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    
    station_code: Mapped[str] = mapped_column(ForeignKey("stations.code", ondelete="CASCADE"), index=True)
    
    source_system: Mapped[str] = mapped_column(String(50))
    source_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    station: Mapped["Station"] = relationship(back_populates="devices")
    alarms: Mapped[list["Alarm"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    interfaces: Mapped[list["Interface"]] = relationship(back_populates="device", cascade="all, delete-orphan")