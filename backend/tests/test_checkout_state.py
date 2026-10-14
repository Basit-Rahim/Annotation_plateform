from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import AnnotationLayer1, Task
from app.models._common import utcnow
from app.schemas import Layer1Submit
from app.services import annotations, checkout, ingest

MARKS = {"first_word_mark_seconds": 0.5, "last_word_mark_seconds": 2.25, "boundary_60s_mark_seconds": 2.9}


def _l1(text="ایک لڑکا"):
    return Layer1Submit(transcript_urdu=text, **MARKS)


def test_available_to_checked_out_to_submitted(db, make_user, make_recording):
    make_recording()
    user = make_user()
    task = checkout.take_next(db, user, "layer_1")
    annotations.submit_layer_1(db, user, task.id, _l1(), None)
    db.refresh(task)
    assert task.status == "submitted"
    assert task.submitted_at is not None
    assert task.lease_expires_at is None
    assert task.checked_out_by == user.id


def test_release_returns_to_available_and_saves_nothing(db, make_user, make_recording):
    make_recording()
    user = make_user()
    task = checkout.take_next(db, user, "layer_1")
    checkout.release(db, user, task.id)
    db.refresh(task)
    assert task.status == "available"
    assert task.checked_out_by is None
    assert db.query(AnnotationLayer1).count() == 0


def test_cannot_submit_after_release(db, make_user, make_recording):
    make_recording()
    user = make_user()
    task = checkout.take_next(db, user, "layer_1")
    checkout.release(db, user, task.id)
    with pytest.raises(HTTPException) as exc:
        annotations.submit_layer_1(db, user, task.id, _l1(), None)
    assert exc.value.status_code == 409


def test_cannot_release_or_submit_someone_elses_task(db, make_user, make_recording):
    make_recording()
    owner, intruder = make_user(), make_user()
    task = checkout.take_next(db, owner, "layer_1")
    for action in (
        lambda: checkout.release(db, intruder, task.id),
        lambda: annotations.submit_layer_1(db, intruder, task.id, _l1(), None),
    ):
        with pytest.raises(HTTPException) as exc:
            action()
        assert exc.value.status_code == 409
        db.rollback()


def test_submitted_task_cannot_be_released(db, make_user, make_recording):
    make_recording()
    user = make_user()
    task = checkout.take_next(db, user, "layer_1")
    annotations.submit_layer_1(db, user, task.id, _l1(), None)
    with pytest.raises(HTTPException) as exc:
        checkout.release(db, user, task.id)
    assert exc.value.status_code == 409


def test_cannot_submit_on_expired_lease(db, make_user, make_recording):
    make_recording()
    user = make_user()
    task = checkout.take_next(db, user, "layer_1")
    task.lease_expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        annotations.submit_layer_1(db, user, task.id, _l1(), None)
    assert exc.value.status_code == 409


def test_layer_1_submit_requires_transcript(db, make_user, make_recording):
    make_recording()
    user = make_user()
    task = checkout.take_next(db, user, "layer_1")
    with pytest.raises(HTTPException) as exc:
        annotations.submit_layer_1(db, user, task.id, _l1("   "), None)
    assert exc.value.status_code == 422


def test_withdraw_cancels_checkout(db, make_user, make_recording, storage_dir):
    rec = make_recording()
    admin = make_user(role="admin")
    user = make_user()
    task = checkout.take_next(db, user, "layer_1")
    ingest.withdraw(db, admin, rec.id, "consent withdrawn", None)
    db.refresh(task)
    assert task.status == "withdrawn"
    assert task.checked_out_by is None
    assert checkout.current_task(db, user) is None
    assert not (storage_dir / rec.audio_path).exists()
    assert db.query(Task).filter_by(recording_id=rec.id).filter(Task.status != "withdrawn").count() == 0


def test_db_rejects_two_checkouts_for_one_user(db, make_user, make_recording):
    """The invariant holds even if application code is bypassed."""
    make_recording()
    make_recording()
    user = make_user()
    tasks = db.query(Task).filter_by(layer="layer_1").all()
    for t in tasks:
        t.status, t.checked_out_by = "checked_out", user.id
    with pytest.raises(IntegrityError):
        db.commit()
