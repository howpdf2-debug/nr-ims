import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    
    # Roles: irca_admin, divisional_admin, tier1_incharge, operator
    role: Mapped[str] = mapped_column(String(50), default="operator")
    
    # Dynamic Scopes: ["LKO", "MB"] या ["BSB"] या ["*"] (IRCA के लिए)
    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())