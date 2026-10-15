"""Server-side drafts: autosave of in-progress annotation work.

Saving a draft also renews the task lease, so the lease only lapses after
LEASE_DURATION_MINUTES without any edit, never while someone is working.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Task, TaskDraft, User
from app.models._common import utcnow
from app.services import checkout

MAX_DRAFT_BYTES = 512 * 1024


def get_draft(db: Session, user: User, task_id: uuid.UUID) -> TaskDraft | None:
    checkout.own_checkout(db, user, task_id)
    return db.get(TaskDraft, (task_id, user.id))


def save_draft(db: Session, user: User, task_id: uuid.UUID, payload: dict[str, Any]) -> tuple[datetime, Task]:
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > MAX_DRAFT_BYTES:
        raise HTTPException(413, "Draft is too large")
    task = checkout.lock_own_checkout(db, user, task_id)
    now = utcnow()
    db.execute(
        insert(TaskDraft)
        .values(task_id=task_id, user_id=user.id, payload=payload, updated_at=now)
        .on_conflict_do_update(index_elements=["task_id", "user_id"], set_={"payload": payload, "updated_at": now})
    )
    task.lease_expires_at = now + timedelta(minutes=get_settings().lease_duration_minutes)
    db.commit()
    return now, task


def discard(db: Session, user_id: uuid.UUID, task_id: uuid.UUID) -> None:
    """Stage deletion of a draft; committed with the caller's transaction."""
    db.execute(delete(TaskDraft).where(TaskDraft.task_id == task_id, TaskDraft.user_id == user_id))
