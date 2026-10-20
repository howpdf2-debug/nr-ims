import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConfigurationChange(Base):
    __tablename__ = "configuration_changes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    change_type: Mapped[str] = mapped_column(String(50)) # e.g., "VLAN_UPDATE", "ACL_MODIFICATION"
    old_config: Mapped[str] = mapped_column(String)
    new_config: Mapped[str] = mapped_column(String)
    performed_by: Mapped[str] = mapped_column(String(100))
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())