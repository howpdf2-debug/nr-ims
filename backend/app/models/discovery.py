import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DiscoveredDevice(Base):
    __tablename__ = "discovered_devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ip_address: Mapped[str] = mapped_column(String(50), unique=True)
    mac_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    detected_type: Mapped[str] = mapped_column(String(50), default="unknown")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    is_rogue: Mapped[bool] = mapped_column(Boolean, default=False)
    location_guess: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())