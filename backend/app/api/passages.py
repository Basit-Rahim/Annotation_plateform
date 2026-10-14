from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import client_ip, require_admin
from app.db import get_db
from app.models import Passage, PassageToken, User
from app.schemas import PassageCreate, PassageOut
from app.services import audit

router = APIRouter(prefix="/api/admin/passages", tags=["admin: passages"])


@router.get("", response_model=list[PassageOut])
def list_passages(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[Passage]:
    return list(db.scalars(select(Passage).options(selectinload(Passage.tokens)).order_by(Passage.code)))


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
