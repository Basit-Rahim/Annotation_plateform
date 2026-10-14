"""JSON export of submitted annotations, with Annex E.4 normalisation applied."""

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AnnotationLayer1, AnnotationLayer2, Passage, Recording, Task, User
from app.models._common import utcnow
from app.models.task import STATUS_SUBMITTED
from app.services.normalisation import NORMALISATION_VERSION, NormalisationError, normalise
from app.services.taxonomy import ERROR_TAGS

EXPORT_SCHEMA_VERSION = "1.0.0"


def _num(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _normalised(text: str) -> dict[str, Any]:
    try:
        return {"normalised": normalise(text), "normalisation_error": None}
    except NormalisationError as exc:
        return {"normalised": None, "normalisation_error": str(exc)}


def _marks(a: AnnotationLayer1 | AnnotationLayer2) -> dict[str, float | None]:
    return {
        "first_word_mark_seconds": _num(a.first_word_mark_seconds),
        "last_word_mark_seconds": _num(a.last_word_mark_seconds),
        "boundary_60s_mark_seconds": _num(a.boundary_60s_mark_seconds),
    }


def build_export(db: Session) -> dict[str, Any]:
    emails = dict(db.execute(select(User.id, User.email)).all())
    passages = {p.id: p for p in db.scalars(select(Passage).options(selectinload(Passage.tokens)))}

    l1_rows = db.execute(
        select(AnnotationLayer1, Task)
        .join(Task, Task.id == AnnotationLayer1.task_id)
        .where(Task.status == STATUS_SUBMITTED)
    ).all()
    l2_rows = db.execute(
        select(AnnotationLayer2, Task)
        .join(Task, Task.id == AnnotationLayer2.task_id)
        .where(Task.status == STATUS_SUBMITTED)
        .options(selectinload(AnnotationLayer2.words), selectinload(AnnotationLayer2.insertions))
    ).all()

    by_recording: dict[Any, dict[str, list]] = {}
    for a, task in l1_rows:
        by_recording.setdefault(task.recording_id, {"layer_1": [], "layer_2": []})["layer_1"].append(
            {
                "annotation_id": str(a.id),
                "task_id": str(task.id),
                "annotator_id": str(a.annotator_id),
                "annotator_email": emails.get(a.annotator_id),
                "submitted_at": a.submitted_at.isoformat(),
                **_marks(a),
                "transcript_raw": a.transcript_urdu,
                "transcript_normalised": (n := _normalised(a.transcript_urdu))["normalised"],
                "normalisation_error": n["normalisation_error"],
            }
        )
    for a, task in l2_rows:
        by_recording.setdefault(task.recording_id, {"layer_1": [], "layer_2": []})["layer_2"].append(
            {
                "annotation_id": str(a.id),
                "task_id": str(task.id),
                "annotator_id": str(a.annotator_id),
                "annotator_email": emails.get(a.annotator_id),
                "submitted_at": a.submitted_at.isoformat(),
                **_marks(a),
                "words": [
                    {"word_index": w.word_index, "is_error": w.is_error, "error_tag": w.error_tag} for w in a.words
                ],
                "insertions": [
                    {
                        "after_word_index": i.after_word_index,
                        "position_within_slot": i.position_within_slot,
                        "error_tag": "INS",
                        "inserted_text_raw": i.inserted_text,
                        "inserted_text_normalised": _normalised(i.inserted_text)["normalised"],
                    }
                    for i in a.insertions
                ],
            }
        )

    recordings = db.scalars(
        select(Recording)
        .where(Recording.id.in_(list(by_recording)), Recording.withdrawn_at.is_(None))
        .order_by(Recording.ingested_at)
    ).all()

    out_recordings = []
    for r in recordings:
        passage = passages[r.passage_id]
        out_recordings.append(
            {
                "recording_id": str(r.id),
                "source": r.source,
                "source_ref": r.source_ref,
                "duration_seconds": _num(r.duration_seconds),
                "passage_code": passage.code,
                "passage_attempt": r.passage_attempt,
                "grade": r.grade,
                "gender": r.gender,
                "first_language": r.first_language,
                "school_type": r.school_type,
                "noise_level": r.noise_level,
                "interruption": r.interruption,
                "assessor_notes": r.assessor_notes,
                "ingested_at": r.ingested_at.isoformat(),
                "annotations": by_recording[r.id],
            }
        )

    used_passages = {r.passage_id for r in recordings}
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "normalisation_version": NORMALISATION_VERSION,
        "exported_at": utcnow().isoformat(),
        "error_tags": [{"code": t.code, "label": t.label, "counts_as_error": t.counts_as_error} for t in ERROR_TAGS],
        "passages": [
            {
                "passage_id": str(p.id),
                "code": p.code,
                "title": p.title,
                "tokens": [
                    {
                        "word_index": t.word_index,
                        "printed_word": t.printed_word,
                        "printed_word_normalised": _normalised(t.printed_word)["normalised"],
                    }
                    for t in p.tokens
                ],
            }
            for p in passages.values()
            if p.id in used_passages
        ],
        "recordings": out_recordings,
    }
