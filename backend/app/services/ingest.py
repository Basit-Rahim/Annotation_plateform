"""Drop-folder audio ingestion and recording withdrawal."""

import shutil
import uuid
from decimal import Decimal
from pathlib import Path

import mutagen
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Passage, Recording, Task, User
from app.models._common import utcnow
from app.models.recording import SOURCE_DROP_FOLDER
from app.models.task import LAYERS, STATUS_CHECKED_OUT, STATUS_WITHDRAWN
from app.schemas import IngestIn, ScanFile
from app.services import audit

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".oga", ".opus", ".flac", ".webm", ".aac"}


def drop_dir() -> Path:
    return Path(get_settings().audio_drop_dir)


def storage_dir() -> Path:
    return Path(get_settings().audio_storage_dir)


def audio_duration(path: Path) -> float | None:
    try:
        info = mutagen.File(path)
    except Exception:
        return None
    if info is None or getattr(info, "info", None) is None:
        return None
    return round(float(info.info.length), 3)


def _drop_files() -> list[Path]:
    folder = drop_dir()
    if not folder.is_dir():
        return []
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in AUDIO_EXTENSIONS
    )


def scan() -> list[ScanFile]:
    return [
        ScanFile(filename=p.name, size_bytes=p.stat().st_size, duration_seconds=audio_duration(p))
        for p in _drop_files()
    ]


def ingest(db: Session, admin: User, filename: str, body: IngestIn, ip: str | None) -> Recording:
    # The filename is only used to look the file up in the listing; the stored
    # path is always derived from the new recording id.
    source = next((p for p in _drop_files() if p.name == filename), None)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{filename!r} is not in the drop folder")
    if db.get(Passage, body.passage_id) is None:
        raise HTTPException(422, "Unknown passage")

    recording_id = uuid.uuid4()
    stored_name = f"{recording_id}{source.suffix.lower()}"
    duration = audio_duration(source)

    recording = Recording(
        id=recording_id,
        source=SOURCE_DROP_FOLDER,
        source_ref=source.name,
        audio_path=stored_name,
        duration_seconds=Decimal(str(duration)) if duration is not None else None,
        ingested_by=admin.id,
        **body.model_dump(),
    )
    db.add(recording)
    db.flush()
    for layer in LAYERS:
        db.add(Task(recording_id=recording_id, layer=layer))
    audit.record(
        db, "recording.ingest", user_id=admin.id, target_type="recording", target_id=recording_id,
        meta={"source_ref": source.name, "stored_as": stored_name}, ip_address=ip,
    )

    target = storage_dir() / stored_name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    try:
        db.commit()
    except Exception:
        db.rollback()
        shutil.move(str(target), str(source))
        raise
    return recording


def withdraw(db: Session, admin: User, recording_id: uuid.UUID, reason: str, ip: str | None) -> Recording:
    recording = db.scalar(select(Recording).where(Recording.id == recording_id).with_for_update())
    if recording is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recording not found")
    if recording.withdrawn_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Recording is already withdrawn")

    recording.withdrawn_at = utcnow()
    recording.withdrawn_reason = reason
    tasks = db.scalars(select(Task).where(Task.recording_id == recording_id).with_for_update()).all()
    cancelled_checkouts = []
    for task in tasks:
        if task.status == STATUS_CHECKED_OUT:
            cancelled_checkouts.append(str(task.checked_out_by))
            task.checked_out_by = None
            task.checked_out_at = None
        task.status = STATUS_WITHDRAWN
        task.lease_expires_at = None
    audit.record(
        db, "recording.withdraw", user_id=admin.id, target_type="recording", target_id=recording_id,
        meta={"reason": reason, "cancelled_checkouts": cancelled_checkouts}, ip_address=ip,
    )
    db.commit()
    (storage_dir() / recording.audio_path).unlink(missing_ok=True)
    return recording
