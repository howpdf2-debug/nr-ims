import uuid

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DeviceLink(Base):
    __tablename__ = "device_links"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    destination_device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    
    # 'copper' या 'ofc'
    media_type: Mapped[str] = mapped_column(String(20), default="copper")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)