import uuid
from sqlalchemy import String, ForeignKey, Uuid, Float, Integer, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Link(Base):
    __tablename__ = "links"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_station: Mapped[str] = mapped_column(ForeignKey("stations.code"))
    destination_station: Mapped[str] = mapped_column(ForeignKey("stations.code"))
    
    provider: Mapped[str] = mapped_column(String(50)) # BSNL, OFC, RAILTEL
    status: Mapped[str] = mapped_column(String(20), default="up") # up, down
    
    # ट्रैफिक और परफॉर्मेंस मेट्रिक्स
    bandwidth_mbps: Mapped[int] = mapped_column(Integer, default=100) 
    utilization_pct: Mapped[float] = mapped_column(Float, default=0.0) 
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    packet_loss_pct: Mapped[float] = mapped_column(Float, default=0.0)
    
    # कॉन्फ़िगरेशन और कंप्लायंस ट्रैकिंग
    is_compliant: Mapped[bool] = mapped_column(Boolean, default=True)
    last_config_change: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    config_version: Mapped[str | None] = mapped_column(String(50), nullable=True)