import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Alarm(Base):
    __tablename__ = "alarms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(100))
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"))
    
    severity: Mapped[str] = mapped_column(String(20))  # critical, major, minor, warning, info
    message: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, acknowledged, resolved
    
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_system: Mapped[str] = mapped_column(String(50))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship (Future use ke liye)
    device: Mapped["Device"] = relationship()