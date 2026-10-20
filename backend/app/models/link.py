import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Link(Base):
    __tablename__ = "links"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_station: Mapped[str] = mapped_column(ForeignKey("stations.code"))
    destination_station: Mapped[str] = mapped_column(ForeignKey("stations.code"))
    
    provider: Mapped[str] = mapped_column(String(50)) 
    status: Mapped[str] = mapped_column(String(20), default="up") 
    bandwidth_mbps: Mapped[int] = mapped_column(Integer, default=100)
    
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    packet_loss_pct: Mapped[float] = mapped_column(Float, default=0.0)
    crc_errors: Mapped[int] = mapped_column(Integer, default=0)
    
    is_admin_shutdown: Mapped[bool] = mapped_column(Boolean, default=False)

Index("ix_links_source_station", Link.source_station)
Index("ix_links_destination_station", Link.destination_station)
