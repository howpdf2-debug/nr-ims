from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Station(Base):
    __tablename__ = "stations"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    division: Mapped[str] = mapped_column(String(50), index=True)
    zone: Mapped[str] = mapped_column(String(50), default="NR")
    
    # ये दो नई फील्ड्स जोड़नी हैं
    tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    station_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    devices: Mapped[list["Device"]] = relationship(back_populates="station", cascade="all, delete-orphan")