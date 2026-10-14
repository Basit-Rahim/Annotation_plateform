import mimetypes
import re
import uuid
from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Recording, Task, User
from app.models._common import utcnow
from app.models.task import STATUS_CHECKED_OUT
from app.models.user import ROLE_ADMIN
from app.services.ingest import storage_dir

router = APIRouter(prefix="/api/audio", tags=["audio"])

CHUNK_SIZE = 64 * 1024
_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")

mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("audio/ogg", ".opus")
mimetypes.add_type("audio/flac", ".flac")
mimetypes.add_type("audio/webm", ".webm")


def _iter_file(path: Path, start: int, length: int) -> Iterator[bytes]:
    with path.open("rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def range_response(path: Path, range_header: str | None) -> Response:
    size = path.stat().st_size
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "private, no-store"}

    if not range_header:
        headers["Content-Length"] = str(size)
        return StreamingResponse(_iter_file(path, 0, size), media_type=media_type, headers=headers)

    m = _RANGE_RE.match(range_header.strip())
    if not m or (not m.group(1) and not m.group(2)):
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    if m.group(1):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
    else:  # suffix range: last N bytes
        start = max(size - int(m.group(2)), 0)
        end = size - 1
    end = min(end, size - 1)
    if start > end or start >= size:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})

    length = end - start + 1
    headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(length)
    return StreamingResponse(
        _iter_file(path, start, length), status_code=206, media_type=media_type, headers=headers
    )


@router.get("/{recording_id}")
def stream_audio(
    recording_id: uuid.UUID, request: Request,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> Response:
    recording = db.get(Recording, recording_id)
    if recording is None or recording.withdrawn_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recording not found")
    if user.role != ROLE_ADMIN:
        has_checkout = db.scalar(
            select(Task.id).where(
                Task.recording_id == recording_id,
                Task.checked_out_by == user.id,
                Task.status == STATUS_CHECKED_OUT,
                Task.lease_expires_at > utcnow(),
            )
        )
        if not has_checkout:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have this recording checked out")
    path = storage_dir() / recording.audio_path
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audio file missing")
    return range_response(path, request.headers.get("range"))
