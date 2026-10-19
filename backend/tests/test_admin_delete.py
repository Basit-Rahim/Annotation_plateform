"""Admin deletion of passages and recordings."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import AnnotationLayer1, AuditLog, Passage, PassageToken
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
