import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    action: str,
    *,
    user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Stage an audit row; it is committed with the caller's transaction."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            meta=meta or {},
            ip_address=ip_address,
        )
    )
