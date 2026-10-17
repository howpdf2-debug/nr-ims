from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class Station(Base):
    __tablename__ = "stations"

    # Station Code (जैसे NDLS, GZB, LKO)
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    
    # Division: DLI, MB, LKO, UMB, JAT, FZR
    division: Mapped[str] = mapped_column(String(50), index=True) 
    
    # Zone: Northern Railway (NR)
    zone: Mapped[str] = mapped_column(String(50), default="NR")
    
    # Relationships
    devices: Mapped[list["Device"]] = relationship(back_populates="station", cascade="all, delete-orphan")