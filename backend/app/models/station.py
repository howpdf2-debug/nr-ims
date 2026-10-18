from sqlalchemy import String, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Station(Base):
    __tablename__ = "stations"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    division: Mapped[str] = mapped_column(String(50), index=True)
    zone: Mapped[str] = mapped_column(String(50), default="NR")
    
    tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    station_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    parent_station_code: Mapped[str | None] = mapped_column(ForeignKey("stations.code"), nullable=True)

    # नए फील्ड्स: मैप पर पोजीशन याद रखने के लिए
    position_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_y: Mapped[float | None] = mapped_column(Float, nullable=True)

    devices: Mapped[list["Device"]] = relationship(back_populates="station", cascade="all, delete-orphan")