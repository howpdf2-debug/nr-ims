import uuid
from sqlalchemy import String, ForeignKey, Uuid, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Interface(Base):
    __tablename__ = "interfaces"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="up")
    description: Mapped[str | None] = mapped_column(String(100), nullable=True)
    in_mbps: Mapped[float] = mapped_column(Float, default=0.0)
    out_mbps: Mapped[float] = mapped_column(Float, default=0.0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    device: Mapped["Device"] = relationship(back_populates="interfaces")
