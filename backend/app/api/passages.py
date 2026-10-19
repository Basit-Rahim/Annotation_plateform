import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth import client_ip, require_admin
from app.db import get_db
from app.models import Passage, PassageToken, Recording, User
from app.schemas import PassageCreate, PassageOut
from app.services import audit

router = APIRouter(prefix="/api/admin/passages", tags=["admin: passages"])


@router.get("", response_model=list[PassageOut])
def list_passages(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[PassageOut]:
    usage = dict(db.execute(select(Recording.passage_id, func.count()).group_by(Recording.passage_id)).all())
    passages = db.scalars(select(Passage).options(selectinload(Passage.tokens)).order_by(Passage.code))
    return [
        PassageOut.model_validate(p).model_copy(update={"recording_count": usage.get(p.id, 0)}) for p in passages
    ]


@router.post("", response_model=PassageOut, status_code=status.HTTP_201_CREATED)
def create_passage(
    body: PassageCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> Passage:
    code = body.code.strip()
    if db.scalar(select(Passage.id).where(Passage.code == code)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Passage {code} already exists")
    words = body.urdu_text.split()
    if not words:
        raise HTTPException(422, "The passage text has no words")
    passage = Passage(
        code=code,
        title=body.title.strip(),
        urdu_text=body.urdu_text.strip(),
        tokens=[PassageToken(word_index=i, printed_word=w) for i, w in enumerate(words, start=1)],
    )
    db.add(passage)
    db.flush()
    audit.record(
        db, "passage.create", user_id=admin.id, target_type="passage", target_id=passage.id,
        meta={"code": code, "word_count": len(words)}, ip_address=client_ip(request),
    )
    db.commit()
    return passage


@router.delete("/{passage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_passage(
    passage_id: uuid.UUID, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> None:
    # The row lock makes a concurrent ingest against this passage wait, so the
    # usage count below cannot go stale before the delete commits.
    passage = db.scalar(select(Passage).where(Passage.id == passage_id).with_for_update())
    if passage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Passage not found")
    used = db.scalar(select(func.count()).select_from(Recording).where(Recording.passage_id == passage_id))
    if used:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Passage {passage.code} is used by {used} recording(s); delete those recordings first",
        )
    audit.record(
        db, "passage.delete", user_id=admin.id, target_type="passage", target_id=passage.id,
        meta={"code": passage.code, "word_count": len(passage.tokens)}, ip_address=client_ip(request),
    )
    db.delete(passage)
    db.commit()
