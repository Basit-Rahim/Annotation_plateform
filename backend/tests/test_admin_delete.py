"""Admin deletion of passages and recordings."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import AnnotationLayer1, AnnotationLayer2, AuditLog, Passage, PassageToken, Recording, Task, TaskDraft
from app.schemas import Layer1Submit
from app.services import annotations, checkout, drafts
from app.seed import seed_admin


@pytest.fixture
def admin(_clean):
    seed_admin()
    client = TestClient(app)
    assert client.post("/api/auth/login", json={"email": "admin@test.local", "password": "admin-password"}).status_code == 200
    return client


def test_unused_passage_can_be_deleted(admin, db, make_passage):
    passage = make_passage()
    listed = admin.get("/api/admin/passages").json()
    assert listed[0]["recording_count"] == 0

    assert admin.delete(f"/api/admin/passages/{passage.id}").status_code == 204
    db.expire_all()
    assert db.query(Passage).count() == 0
    assert db.query(PassageToken).count() == 0
    assert db.query(AuditLog).filter_by(action="passage.delete").count() == 1


def test_passage_in_use_cannot_be_deleted(admin, db, make_recording):
    rec = make_recording()
    assert admin.get("/api/admin/passages").json()[0]["recording_count"] == 1

    r = admin.delete(f"/api/admin/passages/{rec.passage_id}")
    assert r.status_code == 409
    assert "used by 1 recording" in r.json()["detail"]
    db.expire_all()
    assert db.query(Passage).count() == 1


def test_delete_unknown_passage(admin):
    assert admin.delete("/api/admin/passages/00000000-0000-0000-0000-000000000000").status_code == 404


MARKS = {"first_word_mark_seconds": 0.5, "last_word_mark_seconds": 2.25, "boundary_60s_mark_seconds": 2.9}


def test_delete_recording_without_annotations(admin, db, make_user, make_recording, storage_dir):
    rec = make_recording()
    annotator = make_user()
    task = checkout.take_next(db, annotator, "layer_1")
    drafts.save_draft(db, annotator, task.id, {"transcript": "ایک"})
    audio = storage_dir / f"{rec.id}.wav"

    assert admin.delete(f"/api/admin/recordings/{rec.id}").status_code == 204
    db.expire_all()
    assert db.query(Recording).count() == 0
    assert db.query(Task).count() == 0
    assert db.query(TaskDraft).count() == 0
    assert not audio.exists()
    log = db.query(AuditLog).filter_by(action="recording.delete").one()
    assert log.meta["cancelled_checkouts"] == [str(annotator.id)]
    # The annotator's checkout is gone, so they can take new work.
    assert checkout.current_task(db, annotator) is None


def test_recording_with_annotations_needs_force(admin, db, make_user, make_recording, storage_dir):
    rec = make_recording()
    annotator = make_user()
    task = checkout.take_next(db, annotator, "layer_1")
    annotations.submit_layer_1(db, annotator, task.id, Layer1Submit(transcript_urdu="ایک", **MARKS), None)

    r = admin.delete(f"/api/admin/recordings/{rec.id}")
    assert r.status_code == 409
    assert "1 submitted annotation" in r.json()["detail"]
    db.expire_all()
    assert db.query(Recording).count() == 1
    assert (storage_dir / f"{rec.id}.wav").exists()

    assert admin.delete(f"/api/admin/recordings/{rec.id}", params={"force": "true"}).status_code == 204
    db.expire_all()
    assert db.query(Recording).count() == 0
    assert db.query(AnnotationLayer1).count() == 0
    assert db.query(AnnotationLayer2).count() == 0


def test_withdrawn_recording_can_be_deleted_and_frees_its_passage(admin, db, make_recording):
    rec = make_recording()
    assert admin.post(f"/api/admin/recordings/{rec.id}/withdraw", json={"reason": "test"}).status_code == 200
    assert admin.delete(f"/api/admin/recordings/{rec.id}").status_code == 204
    assert admin.delete(f"/api/admin/passages/{rec.passage_id}").status_code == 204


def test_delete_unknown_recording(admin):
    assert admin.delete("/api/admin/recordings/00000000-0000-0000-0000-000000000000").status_code == 404
