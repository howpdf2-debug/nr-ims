import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class RemoteAction(Base):
    __tablename__ = "remote_actions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    interface_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="success")
    output_log: Mapped[str | None] = mapped_column(String, nullable=True)
    performed_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
