import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._common import TIMESTAMPTZ, utcnow, uuid_pk
from app.models.recording import Recording

LAYER_1 = "layer_1"
LAYER_2 = "layer_2"
LAYERS = (LAYER_1, LAYER_2)

STATUS_AVAILABLE = "available"
STATUS_CHECKED_OUT = "checked_out"
STATUS_SUBMITTED = "submitted"
STATUS_WITHDRAWN = "withdrawn"


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # DB-level guarantee of the one-active-checkout-per-annotator invariant.
        Index(
            "uq_tasks_one_checkout_per_user",
            "checked_out_by",
            unique=True,
            postgresql_where=text("status = 'checked_out'"),
        ),
        Index("ix_tasks_pool", "layer", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    recording_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recordings.id"), nullable=False)
    layer: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=STATUS_AVAILABLE)
    checked_out_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    checked_out_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    lease_expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    submitted_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, default=utcnow)

    recording: Mapped[Recording] = relationship()
