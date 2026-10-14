import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._common import SECONDS, TIMESTAMPTZ, utcnow, uuid_pk
from app.models.passage import Passage

SOURCE_DROP_FOLDER = "drop_folder"
NOISE_LEVELS = ("quiet", "moderate", "noisy")


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[uuid.UUID] = uuid_pk()
    source: Mapped[str] = mapped_column(Text, nullable=False, default=SOURCE_DROP_FOLDER)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    audio_path: Mapped[str] = mapped_column(Text, nullable=False)
    duration_seconds: Mapped[Decimal | None] = mapped_column(SECONDS)
    passage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("passages.id"), nullable=False)
    passage_attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(Text, nullable=False)
    first_language: Mapped[str] = mapped_column(Text, nullable=False)
    school_type: Mapped[str] = mapped_column(Text, nullable=False)
    noise_level: Mapped[str] = mapped_column(Text, nullable=False)
    interruption: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assessor_notes: Mapped[str | None] = mapped_column(Text)
    ingested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, default=utcnow)
    withdrawn_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    withdrawn_reason: Mapped[str | None] = mapped_column(Text)

    passage: Mapped[Passage] = relationship()
