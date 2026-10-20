import uuid
from datetime import datetime
from sqlalchemy import Index, String, DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class RemoteAction(Base):
    __tablename__ = "remote_actions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    action_type: Mapped[str] = mapped_column(String(50)) # PING, REBOOT, RESTART_PORT
    status: Mapped[str] = mapped_column(String(20), default="success")
    output_log: Mapped[str | None] = mapped_column(String, nullable=True)
    performed_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

Index("ix_remote_actions_device_id_created_at", RemoteAction.device_id, RemoteAction.created_at.desc())
