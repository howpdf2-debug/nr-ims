import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.user import User


def record_audit(db: AsyncSession, user: User | None, action: str, target_type: str,
                 target_id: object, payload: dict | None = None) -> None:
    """Add an audit row to the current transaction (committed with the change itself)."""
    db.add(AuditEvent(id=uuid.uuid4(), actor_id=user.id if user else None, action=action,
                      target_type=target_type, target_id=str(target_id), payload=payload))
