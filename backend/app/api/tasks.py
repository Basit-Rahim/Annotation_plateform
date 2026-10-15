import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import client_ip, require_annotator
from app.db import get_db
from app.models import Passage, PassageToken, Recording, Task, User
from app.models.task import LAYER_2
from app.schemas import DraftIn, DraftOut, DraftSaved, Layer, TaskOut, TokenOut
from app.services import checkout, drafts

router = APIRouter(prefix="/api", tags=["annotator: tasks"])


def task_payload(db: Session, task: Task) -> TaskOut:
    recording = db.get(Recording, task.recording_id)
    passage = db.get(Passage, recording.passage_id)
    tokens = None
    if task.layer == LAYER_2:
        tokens = [
            TokenOut.model_validate(t)
            for t in db.scalars(
                select(PassageToken).where(PassageToken.passage_id == passage.id).order_by(PassageToken.word_index)
            )
        ]
    return TaskOut(
        id=task.id,
        layer=task.layer,
        status=task.status,
        checked_out_at=task.checked_out_at,
        lease_expires_at=task.lease_expires_at,
        recording_id=recording.id,
        passage_code=passage.code,
        duration_seconds=float(recording.duration_seconds) if recording.duration_seconds is not None else None,
        audio_url=f"/api/audio/{recording.id}",
        tokens=tokens,
    )


@router.get("/pool/next", response_model=TaskOut)
def take_next(
    request: Request, layer: Layer = Query(...),
    db: Session = Depends(get_db), user: User = Depends(require_annotator),
) -> TaskOut:
    task = checkout.take_next(db, user, layer, client_ip(request))
    return task_payload(db, task)


@router.get("/tasks/current", response_model=TaskOut | None)
def current(db: Session = Depends(get_db), user: User = Depends(require_annotator)) -> TaskOut | None:
    checkout.expire_leases(db)
    task = checkout.current_task(db, user)
    return task_payload(db, task) if task else None


@router.post("/tasks/{task_id}/release", status_code=status.HTTP_204_NO_CONTENT)
def release(
    task_id: uuid.UUID, request: Request,
    db: Session = Depends(get_db), user: User = Depends(require_annotator),
) -> None:
    checkout.release(db, user, task_id, client_ip(request))


@router.get("/tasks/{task_id}/draft", response_model=DraftOut | None)
def get_draft(
    task_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_annotator),
) -> DraftOut | None:
    draft = drafts.get_draft(db, user, task_id)
    return DraftOut(payload=draft.payload, updated_at=draft.updated_at) if draft else None


@router.put("/tasks/{task_id}/draft", response_model=DraftSaved)
def save_draft(
    task_id: uuid.UUID, body: DraftIn, db: Session = Depends(get_db), user: User = Depends(require_annotator),
) -> DraftSaved:
    updated_at, task = drafts.save_draft(db, user, task_id, body.payload)
    return DraftSaved(updated_at=updated_at, lease_expires_at=task.lease_expires_at)
