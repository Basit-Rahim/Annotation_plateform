from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.models import TaskDraft
from app.models._common import utcnow
from app.schemas import Layer1Submit
from app.services import annotations, checkout, drafts

MARKS = {"first_word_mark_seconds": 0.5, "last_word_mark_seconds": 2.25, "boundary_60s_mark_seconds": 2.9}
PAYLOAD = {"transcript": "ایک لڑکا", "marks": {"first": 0.5, "last": None, "boundary": None}}


def test_save_and_load_round_trip(db, make_user, make_recording):
    make_recording()
    user = make_user()
    task = checkout.take_next(db, user, "layer_1")
    assert drafts.get_draft(db, user, task.id) is None

    drafts.save_draft(db, user, task.id, PAYLOAD)
    drafts.save_draft(db, user, task.id, {**PAYLOAD, "transcript": "ایک لڑکا اسکول"})
    assert drafts.get_draft(db, user, task.id).payload["transcript"] == "ایک لڑکا اسکول"
    assert db.query(TaskDraft).count() == 1


def test_saving_renews_the_lease(db, make_user, make_recording):
    make_recording()
    user = make_user()
    task = checkout.take_next(db, user, "layer_1")
    task.lease_expires_at = utcnow() + timedelta(minutes=1)
    db.commit()

    _, renewed = drafts.save_draft(db, user, task.id, PAYLOAD)
    assert renewed.lease_expires_at > utcnow() + timedelta(minutes=100)


def test_only_the_holder_can_save(db, make_user, make_recording):
    make_recording()
    holder, other = make_user(), make_user()
    task = checkout.take_next(db, holder, "layer_1")
    with pytest.raises(HTTPException) as exc:
        drafts.save_draft(db, other, task.id, PAYLOAD)
    assert exc.value.status_code == 409


def test_draft_survives_lapsed_lease_and_holder_gets_task_back_first(db, make_user, make_recording):
    first_rec = make_recording()
    make_recording()  # a second, newer task in the same pool
    user = make_user()
    task = checkout.take_next(db, user, "layer_1")
    assert task.recording_id == first_rec.id
    drafts.save_draft(db, user, task.id, PAYLOAD)

    # Simulate the lease lapsing after a long break.
    task.lease_expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert checkout.expire_leases(db) == 1

    again = checkout.take_next(db, user, "layer_1")
    assert again.id == task.id
    assert drafts.get_draft(db, user, again.id).payload == PAYLOAD


def test_own_draft_beats_older_tasks(db, make_user, make_recording):
    make_recording()
    make_recording()
    user, other = make_user(), make_user()
    older = checkout.take_next(db, other, "layer_1")
    newer = checkout.take_next(db, user, "layer_1")
    drafts.save_draft(db, user, newer.id, PAYLOAD)
    checkout.release(db, other, older.id)
    newer.lease_expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    checkout.expire_leases(db)

    assert checkout.take_next(db, user, "layer_1").id == newer.id


def test_submit_and_release_clear_the_draft(db, make_user, make_recording):
    make_recording()
    make_recording()
    user = make_user()
    task = checkout.take_next(db, user, "layer_1")
    drafts.save_draft(db, user, task.id, PAYLOAD)
    annotations.submit_layer_1(db, user, task.id, Layer1Submit(transcript_urdu="ایک لڑکا", **MARKS), None)
    assert db.query(TaskDraft).count() == 0

    task = checkout.take_next(db, user, "layer_1")
    drafts.save_draft(db, user, task.id, PAYLOAD)
    checkout.release(db, user, task.id)
    assert db.query(TaskDraft).count() == 0


def test_oversized_draft_rejected(db, make_user, make_recording):
    make_recording()
    user = make_user()
    task = checkout.take_next(db, user, "layer_1")
    with pytest.raises(HTTPException) as exc:
        drafts.save_draft(db, user, task.id, {"transcript": "x" * (drafts.MAX_DRAFT_BYTES + 1)})
    assert exc.value.status_code == 413
