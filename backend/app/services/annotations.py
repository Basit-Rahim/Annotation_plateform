import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AnnotationLayer1,
    AnnotationLayer2,
    AnnotationLayer2Insertion,
    AnnotationLayer2Word,
    PassageToken,
    Recording,
    User,
)
from app.models.task import LAYER_1, LAYER_2
from app.schemas import Layer1Submit, Layer2Submit, MarksIn
from app.services import audit, checkout
from app.services.normalisation import NormalisationError, normalise
from app.services.taxonomy import ERROR_CODES, INSERTION_CODE, NON_ERROR_CODES


def _invalid(detail: str) -> HTTPException:
    return HTTPException(422, detail)


def _check_marks(marks: MarksIn) -> None:
    if marks.last_word_mark_seconds < marks.first_word_mark_seconds:
        raise _invalid("The last-word mark must not be before the first-word mark")


def _check_normalisable(text: str) -> None:
    try:
        normalise(text)
    except NormalisationError as exc:
        raise _invalid(str(exc)) from exc


def submit_layer_1(db: Session, user: User, task_id: uuid.UUID, body: Layer1Submit, ip: str | None) -> AnnotationLayer1:
    task = checkout.lock_own_checkout(db, user, task_id, LAYER_1)
    _check_marks(body)
    if not body.transcript_urdu.strip():
        raise _invalid("The transcript is empty")
    _check_normalisable(body.transcript_urdu)

    annotation = AnnotationLayer1(
        task_id=task.id,
        annotator_id=user.id,
        transcript_urdu=body.transcript_urdu,
        first_word_mark_seconds=body.first_word_mark_seconds,
        last_word_mark_seconds=body.last_word_mark_seconds,
        boundary_60s_mark_seconds=body.boundary_60s_mark_seconds,
    )
    db.add(annotation)
    checkout.mark_submitted(task)
    db.flush()
    audit.record(
        db, "annotation.submit", user_id=user.id, target_type="annotation_layer_1", target_id=annotation.id,
        meta={"task_id": str(task.id), "layer": LAYER_1}, ip_address=ip,
    )
    db.commit()
    return annotation


def _check_words(body: Layer2Submit, word_indices: list[int]) -> None:
    submitted = [w.word_index for w in body.words]
    if len(submitted) != len(set(submitted)):
        raise _invalid("A word was judged more than once")
    if sorted(submitted) != word_indices:
        raise _invalid("Every printed word must have exactly one judgement")
    for w in body.words:
        if w.error_tag == INSERTION_CODE:
            raise _invalid(f"Word {w.word_index}: INS belongs on an insertion slot, not a word row")
        if w.is_error and w.error_tag not in ERROR_CODES:
            raise _invalid(f"Word {w.word_index}: an error needs one of {sorted(ERROR_CODES)}")
        if not w.is_error and w.error_tag is not None and w.error_tag not in NON_ERROR_CODES:
            raise _invalid(f"Word {w.word_index}: tag {w.error_tag} counts as an error; mark the word as Error")


def _check_insertions(body: Layer2Submit, word_count: int) -> None:
    seen: set[tuple[int, int]] = set()
    for ins in body.insertions:
        if ins.after_word_index > word_count:
            raise _invalid(f"Insertion slot {ins.after_word_index} is past the end of the passage")
        if not ins.inserted_text.strip():
            raise _invalid("Inserted words must not be empty")
        key = (ins.after_word_index, ins.position_within_slot)
        if key in seen:
            raise _invalid(f"Duplicate insertion position {key}")
        seen.add(key)
        _check_normalisable(ins.inserted_text)


def submit_layer_2(db: Session, user: User, task_id: uuid.UUID, body: Layer2Submit, ip: str | None) -> AnnotationLayer2:
    task = checkout.lock_own_checkout(db, user, task_id, LAYER_2)
    _check_marks(body)
    passage_id = db.scalar(select(Recording.passage_id).where(Recording.id == task.recording_id))
    word_indices = list(
        db.scalars(
            select(PassageToken.word_index).where(PassageToken.passage_id == passage_id).order_by(PassageToken.word_index)
        )
    )
    _check_words(body, word_indices)
    _check_insertions(body, len(word_indices))

    annotation = AnnotationLayer2(
        task_id=task.id,
        annotator_id=user.id,
        first_word_mark_seconds=body.first_word_mark_seconds,
        last_word_mark_seconds=body.last_word_mark_seconds,
        boundary_60s_mark_seconds=body.boundary_60s_mark_seconds,
        words=[
            AnnotationLayer2Word(word_index=w.word_index, is_error=w.is_error, error_tag=w.error_tag)
            for w in body.words
        ],
        insertions=[
            AnnotationLayer2Insertion(
                after_word_index=i.after_word_index,
                inserted_text=i.inserted_text.strip(),
                position_within_slot=i.position_within_slot,
            )
            for i in body.insertions
        ],
    )
    db.add(annotation)
    checkout.mark_submitted(task)
    db.flush()
    audit.record(
        db, "annotation.submit", user_id=user.id, target_type="annotation_layer_2", target_id=annotation.id,
        meta={"task_id": str(task.id), "layer": LAYER_2, "insertions": len(body.insertions)}, ip_address=ip,
    )
    db.commit()
    return annotation
