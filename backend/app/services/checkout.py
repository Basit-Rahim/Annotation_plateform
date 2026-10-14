"""Task pool and checkout state machine.

available --take next--> checked_out --submit--> submitted
                              |
                              +--release / lease expiry--> available

Any state --recording withdrawn--> withdrawn
"""

import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import and_, exists, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.config import get_settings
from app.models import Recording, Task, User
from app.models._common import utcnow
from app.models.task import (
    LAYER_1,
    LAYER_2,
    STATUS_AVAILABLE,
    STATUS_CHECKED_OUT,
    STATUS_SUBMITTED,
)
from app.services import audit


def is_eligible(user: User, layer: str) -> bool:
    return (layer == LAYER_1 and user.can_layer_1) or (layer == LAYER_2 and user.can_layer_2)


def expire_leases(db: Session, now: datetime | None = None) -> int:
    """Return every checked-out task whose lease has lapsed to the pool. Commits."""
    now = now or utcnow()
    rows = db.execute(
        update(Task)
        .where(Task.status == STATUS_CHECKED_OUT, Task.lease_expires_at < now)
        .values(status=STATUS_AVAILABLE, checked_out_by=None, checked_out_at=None, lease_expires_at=None)
        .returning(Task.id)
    ).all()
    for (task_id,) in rows:
        audit.record(db, "task.lease_expired", target_type="task", target_id=task_id)
    db.commit()
    return len(rows)


def current_task(db: Session, user: User) -> Task | None:
    return db.scalar(
        select(Task).where(Task.checked_out_by == user.id, Task.status == STATUS_CHECKED_OUT)
    )


def take_next(db: Session, user: User, layer: str, ip: str | None = None) -> Task:
    if not is_eligible(user, layer):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"You are not eligible for {layer}")

    expire_leases(db)
    if current_task(db, user) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a task checked out")

    already_done = aliased(Task)
    candidate = db.scalar(
        select(Task)
        .join(Recording, Recording.id == Task.recording_id)
        .where(
            Task.layer == layer,
            Task.status == STATUS_AVAILABLE,
            Recording.withdrawn_at.is_(None),
            ~exists().where(
                and_(
                    already_done.recording_id == Task.recording_id,
                    already_done.layer == layer,
                    already_done.status == STATUS_SUBMITTED,
                    already_done.checked_out_by == user.id,
                )
            ),
        )
        .order_by(Task.created_at, Task.id)
        .limit(1)
        .with_for_update(of=Task, skip_locked=True)
    )
    if candidate is None:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tasks available")

    now = utcnow()
    candidate.status = STATUS_CHECKED_OUT
    candidate.checked_out_by = user.id
    candidate.checked_out_at = now
    candidate.lease_expires_at = now + timedelta(minutes=get_settings().lease_duration_minutes)
    try:
        # The partial unique index rejects a second concurrent checkout here.
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a task checked out")

    audit.record(
        db, "task.checkout", user_id=user.id, target_type="task", target_id=candidate.id,
        meta={"layer": layer, "recording_id": str(candidate.recording_id)}, ip_address=ip,
    )
    db.commit()
    return candidate


def lock_own_checkout(db: Session, user: User, task_id: uuid.UUID, layer: str | None = None) -> Task:
    """Lock and return a task the user currently holds a live lease on."""
    task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    if task.status != STATUS_CHECKED_OUT or task.checked_out_by != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "This task is not checked out by you")
    if task.lease_expires_at is not None and task.lease_expires_at < utcnow():
        raise HTTPException(status.HTTP_409_CONFLICT, "Your lease on this task has expired")
    if layer is not None and task.layer != layer:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"This is a {task.layer} task")
    return task


def release(db: Session, user: User, task_id: uuid.UUID, ip: str | None = None) -> None:
    task = lock_own_checkout(db, user, task_id)
    task.status = STATUS_AVAILABLE
    task.checked_out_by = None
    task.checked_out_at = None
    task.lease_expires_at = None
    audit.record(db, "task.release", user_id=user.id, target_type="task", target_id=task.id, ip_address=ip)
    db.commit()


def mark_submitted(task: Task) -> None:
    """Close out a locked checkout. checked_out_by is kept as the submitter."""
    task.status = STATUS_SUBMITTED
    task.submitted_at = utcnow()
    task.lease_expires_at = None
