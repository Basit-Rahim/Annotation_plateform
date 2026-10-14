import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._common import TIMESTAMPTZ, utcnow, uuid_pk


class Passage(Base):
    __tablename__ = "passages"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    urdu_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, default=utcnow)

    tokens: Mapped[list["PassageToken"]] = relationship(
        back_populates="passage", order_by="PassageToken.word_index", cascade="all, delete-orphan"
    )


class PassageToken(Base):
    __tablename__ = "passage_tokens"
    __table_args__ = (UniqueConstraint("passage_id", "word_index"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    passage_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("passages.id"), nullable=False)
    word_index: Mapped[int] = mapped_column(Integer, nullable=False)
    printed_word: Mapped[str] = mapped_column(Text, nullable=False)

    passage: Mapped[Passage] = relationship(back_populates="tokens")
