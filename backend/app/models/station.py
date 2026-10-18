from sqlalchemy import String, ForeignKey
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
    
    # नया फील्ड: पैरेंट स्टेशन (जैसे KEH का पैरेंट BSB है)
    parent_station_code: Mapped[str | None] = mapped_column(ForeignKey("stations.code"), nullable=True)

    devices: Mapped[list["Device"]] = relationship(back_populates="station", cascade="all, delete-orphan")