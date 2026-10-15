import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._common import TIMESTAMPTZ, utcnow


class TaskDraft(Base):
    """Server-side autosave of an annotator's unfinished work on a task.

    The payload is opaque to the server (the workspace's own state); it is only
    validated on submit. Kept per annotator, so a draft survives a lapsed lease
    and is restored if the same annotator gets the task again.
    """

    __tablename__ = "task_drafts"

    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, default=utcnow)
