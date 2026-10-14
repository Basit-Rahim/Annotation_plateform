import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Numeric, Uuid
from sqlalchemy.orm import mapped_column

TIMESTAMPTZ = DateTime(timezone=True)
# Timing marks and durations: numeric with millisecond precision, never float.
SECONDS = Numeric(10, 3)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_pk():
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
