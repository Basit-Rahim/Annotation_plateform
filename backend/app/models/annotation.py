import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._common import SECONDS, TIMESTAMPTZ, utcnow, uuid_pk


class AnnotationLayer1(Base):
    __tablename__ = "annotation_layer_1"

    id: Mapped[uuid.UUID] = uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), unique=True, nullable=False)
    annotator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    transcript_urdu: Mapped[str] = mapped_column(Text, nullable=False)
    first_word_mark_seconds: Mapped[Decimal] = mapped_column(SECONDS, nullable=False)
    last_word_mark_seconds: Mapped[Decimal] = mapped_column(SECONDS, nullable=False)
    boundary_60s_mark_seconds: Mapped[Decimal] = mapped_column(SECONDS, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, default=utcnow)


class AnnotationLayer2(Base):
    __tablename__ = "annotation_layer_2"

    id: Mapped[uuid.UUID] = uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), unique=True, nullable=False)
    annotator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    first_word_mark_seconds: Mapped[Decimal] = mapped_column(SECONDS, nullable=False)
    last_word_mark_seconds: Mapped[Decimal] = mapped_column(SECONDS, nullable=False)
    boundary_60s_mark_seconds: Mapped[Decimal] = mapped_column(SECONDS, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, default=utcnow)

    words: Mapped[list["AnnotationLayer2Word"]] = relationship(
        order_by="AnnotationLayer2Word.word_index", cascade="all, delete-orphan"
    )
    insertions: Mapped[list["AnnotationLayer2Insertion"]] = relationship(
        order_by="[AnnotationLayer2Insertion.after_word_index, AnnotationLayer2Insertion.position_within_slot]",
        cascade="all, delete-orphan",
    )


class AnnotationLayer2Word(Base):
    __tablename__ = "annotation_layer_2_word"

    id: Mapped[uuid.UUID] = uuid_pk()
    annotation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("annotation_layer_2.id"), nullable=False)
    word_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_error: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_tag: Mapped[str | None] = mapped_column(Text)


class AnnotationLayer2Insertion(Base):
    __tablename__ = "annotation_layer_2_insertion"

    id: Mapped[uuid.UUID] = uuid_pk()
    annotation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("annotation_layer_2.id"), nullable=False)
    after_word_index: Mapped[int] = mapped_column(Integer, nullable=False)
    inserted_text: Mapped[str] = mapped_column(Text, nullable=False)
    position_within_slot: Mapped[int] = mapped_column(Integer, nullable=False)
