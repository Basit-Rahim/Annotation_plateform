import uuid
from datetime import datetime

from sqlalchemy import Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._common import TIMESTAMPTZ, utcnow, uuid_pk

ROLE_ADMIN = "admin"
ROLE_ANNOTATOR = "annotator"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    can_layer_1: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_layer_2: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False, default=utcnow)
