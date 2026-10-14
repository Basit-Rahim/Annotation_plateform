import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import client_ip, require_annotator
from app.db import get_db
from app.models import User
from app.models.task import STATUS_SUBMITTED
from app.schemas import Layer1Submit, Layer2Submit, SubmitOut
from app.services import annotations

router = APIRouter(prefix="/api/tasks", tags=["annotator: annotations"])


@router.post("/{task_id}/submit/layer_1", response_model=SubmitOut)
def submit_layer_1(
    task_id: uuid.UUID, body: Layer1Submit, request: Request,
    db: Session = Depends(get_db), user: User = Depends(require_annotator),
) -> SubmitOut:
    a = annotations.submit_layer_1(db, user, task_id, body, client_ip(request))
    return SubmitOut(annotation_id=a.id, task_id=task_id, status=STATUS_SUBMITTED)


@router.post("/{task_id}/submit/layer_2", response_model=SubmitOut)
def submit_layer_2(
    task_id: uuid.UUID, body: Layer2Submit, request: Request,
    db: Session = Depends(get_db), user: User = Depends(require_annotator),
) -> SubmitOut:
    a = annotations.submit_layer_2(db, user, task_id, body, client_ip(request))
    return SubmitOut(annotation_id=a.id, task_id=task_id, status=STATUS_SUBMITTED)
