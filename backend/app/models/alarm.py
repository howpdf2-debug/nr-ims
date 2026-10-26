import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.device import Device


class Alarm(Base):
    __tablename__ = "alarms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(100))

    # Foreign Key to Device
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)

    # Severity: critical, major, minor, warning, info
    severity: Mapped[str] = mapped_column(String(20), index=True)
    message: Mapped[str] = mapped_column(String(500))

    # Status: active, acknowledged, resolved ("resolved" is the exact stored value; the poller relies on it)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)

    # Audit Fields for NOC Operator
    acked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ack_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Lifecycle (Phase 2): how often the same open fault was re-reported, and who closed it, when and why.
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolve_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # the name reports.py and the UI read
    resolution_note: Mapped[str | None] = synonym("resolve_note")  # alias: same column, second name

    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    device: Mapped["Device"] = relationship(back_populates="alarms")

Index("ix_alarms_first_seen", Alarm.first_seen)