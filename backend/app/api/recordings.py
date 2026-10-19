import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.auth import client_ip, require_admin
from app.db import get_db
from app.models import AuditLog, Recording, Task, User
from app.models.task import STATUS_AVAILABLE, STATUS_CHECKED_OUT, STATUS_SUBMITTED
from app.models.user import ROLE_ANNOTATOR
from app.schemas import IngestIn, RecordingListItem, RecordingOut, ScanFile, StatsOut, WithdrawIn
from app.services import ingest as ingest_service

router = APIRouter(prefix="/api/admin", tags=["admin: recordings"])


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> StatsOut:
    task_counts = dict(db.execute(select(Task.status, func.count()).group_by(Task.status)).all())
    last_export: datetime | None = db.scalar(
        select(func.max(AuditLog.created_at)).where(AuditLog.action == "export.download")
    )
    return StatsOut(
        recordings_total=db.scalar(select(func.count()).select_from(Recording).where(Recording.withdrawn_at.is_(None))),
        tasks_available=task_counts.get(STATUS_AVAILABLE, 0),
        tasks_in_progress=task_counts.get(STATUS_CHECKED_OUT, 0),
        tasks_submitted=task_counts.get(STATUS_SUBMITTED, 0),
        annotators=db.scalar(select(func.count()).select_from(User).where(User.role == ROLE_ANNOTATOR)),
        last_export_at=last_export,
    )


@router.get("/recordings", response_model=list[RecordingListItem])
def list_recordings(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[RecordingListItem]:
    recordings = db.scalars(
        select(Recording).options(joinedload(Recording.passage)).order_by(Recording.ingested_at.desc())
    ).all()
    statuses: dict[uuid.UUID, dict[str, str]] = {}
    for rec_id, layer, task_status in db.execute(select(Task.recording_id, Task.layer, Task.status)):
        statuses.setdefault(rec_id, {})[layer] = task_status
    return [
        RecordingListItem(
            **RecordingOut.model_validate(r).model_dump(),
            passage_code=r.passage.code,
            task_statuses=statuses.get(r.id, {}),
        )
        for r in recordings
    ]


@router.get("/ingest/scan", response_model=list[ScanFile])
def scan(_: User = Depends(require_admin)) -> list[ScanFile]:
    return ingest_service.scan()


@router.post("/ingest/{filename}", response_model=RecordingOut, status_code=status.HTTP_201_CREATED)
def ingest(
    filename: str, body: IngestIn, request: Request,
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
) -> Recording:
    return ingest_service.ingest(db, admin, filename, body, client_ip(request))


@router.post("/recordings/{recording_id}/withdraw", response_model=RecordingOut)
def withdraw(
    recording_id: uuid.UUID, body: WithdrawIn, request: Request,
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
) -> Recording:
    return ingest_service.withdraw(db, admin, recording_id, body.reason, client_ip(request))


@router.delete("/recordings/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recording(
    recording_id: uuid.UUID, request: Request, force: bool = Query(False),
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
) -> None:
    ingest_service.delete_recording(db, admin, recording_id, force, client_ip(request))
