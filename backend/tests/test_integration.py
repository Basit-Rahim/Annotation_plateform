"""End-to-end API flow: admin sets up, annotator scores Layer 2, admin exports."""

import json
import shutil

from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed_admin
from tests.conftest import FIXTURES

# Printed passage uses Arabic kaf/heh/yeh so the export must show normalisation.
PASSAGE = "ایک لڑکا كتاب پڑھ رها تھا۔"
MARKS = {"first_word_mark_seconds": 0.4, "last_word_mark_seconds": 2.6, "boundary_60s_mark_seconds": 2.95}


def _login(client: TestClient, email: str, password: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def test_full_flow(drop_dir, storage_dir):
    seed_admin()
    assert seed_admin() is False  # idempotent

    admin = TestClient(app)
    assert _login(admin, "admin@test.local", "admin-password")["role"] == "admin"

    # Passage creation tokenises on whitespace.
    r = admin.post("/api/admin/passages", json={"code": "P01", "title": "Test", "urdu_text": PASSAGE})
    assert r.status_code == 201, r.text
    passage = r.json()
    assert [t["word_index"] for t in passage["tokens"]] == [1, 2, 3, 4, 5, 6]

    # Annotator account.
    r = admin.post(
        "/api/admin/users",
        json={"email": "Teacher@Test.local", "password": "teacher-pass", "can_layer_1": True, "can_layer_2": True},
    )
    assert r.status_code == 201, r.text

    # Drop-folder ingestion.
    shutil.copy(FIXTURES / "sample.wav", drop_dir / "child 01.wav")
    scan = admin.get("/api/admin/ingest/scan").json()
    assert scan[0]["filename"] == "child 01.wav"
    assert abs(scan[0]["duration_seconds"] - 3.0) < 0.01
    r = admin.post(
        "/api/admin/ingest/child 01.wav",
        json={
            "passage_id": passage["id"], "passage_attempt": 1, "grade": 2, "gender": "female",
            "first_language": "Urdu", "school_type": "public", "noise_level": "quiet", "interruption": False,
        },
    )
    assert r.status_code == 201, r.text
    recording = r.json()
    assert not (drop_dir / "child 01.wav").exists()
    assert (storage_dir / f"{recording['id']}.wav").exists()
    stats = admin.get("/api/admin/stats").json()
    assert stats["tasks_available"] == 2 and stats["recordings_total"] == 1

    # Path traversal is refused.
    assert admin.post("/api/admin/ingest/..%2F..%2Fetc%2Fpasswd", json={}).status_code in (404, 422)

    # Annotator flow.
    annot = TestClient(app)
    _login(annot, "teacher@test.local", "teacher-pass")
    assert annot.get("/api/admin/users").status_code == 403
    assert annot.get(f"/api/audio/{recording['id']}").status_code == 403  # no checkout yet

    r = annot.get("/api/pool/next", params={"layer": "layer_2"})
    assert r.status_code == 200, r.text
    task = r.json()
    assert task["layer"] == "layer_2"
    assert [t["printed_word"] for t in task["tokens"]][0] == "ایک"
    assert annot.get("/api/pool/next", params={"layer": "layer_1"}).status_code == 409
    assert annot.get("/api/tasks/current").json()["id"] == task["id"]

    # Range requests work for seeking.
    r = annot.get(task["audio_url"], headers={"Range": "bytes=0-99"})
    assert r.status_code == 206
    assert r.headers["content-range"] == "bytes 0-99/48044"
    assert len(r.content) == 100
    full = annot.get(task["audio_url"])
    assert full.status_code == 200 and full.headers["accept-ranges"] == "bytes"

    # Incomplete judgements are rejected.
    partial = {**MARKS, "words": [{"word_index": 1, "is_error": False}], "insertions": []}
    assert annot.post(f"/api/tasks/{task['id']}/submit/layer_2", json=partial).status_code == 422

    words = [
        {"word_index": 1, "is_error": False, "error_tag": None},
        {"word_index": 2, "is_error": True, "error_tag": "SUB"},
        {"word_index": 3, "is_error": False, "error_tag": "SC"},
        {"word_index": 4, "is_error": True, "error_tag": "MIS"},
        {"word_index": 5, "is_error": False, "error_tag": None},
        {"word_index": 6, "is_error": False, "error_tag": "HES"},
    ]
    insertions = [{"after_word_index": 2, "inserted_text": "كا", "position_within_slot": 1}]
    r = annot.post(
        f"/api/tasks/{task['id']}/submit/layer_2", json={**MARKS, "words": words, "insertions": insertions}
    )
    assert r.status_code == 200, r.text
    assert annot.get("/api/tasks/current").json() is None

    # Layer 1 on the same recording.
    task1 = annot.get("/api/pool/next", params={"layer": "layer_1"}).json()
    r = annot.post(
        f"/api/tasks/{task1['id']}/submit/layer_1",
        json={**MARKS, "transcript_urdu": "ایک لڑکا  كتاب [unintelligible] رها تھا۔"},
    )
    assert r.status_code == 200, r.text

    # Export.
    r = admin.get("/api/admin/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    data = json.loads(r.content.decode("utf-8"))
    assert data["normalisation_version"] == "1.1.0"
    assert data["schema_version"]
    [rec] = data["recordings"]
    [l2] = rec["annotations"]["layer_2"]
    assert l2["words"][1] == {"word_index": 2, "is_error": True, "error_tag": "SUB"}
    assert l2["first_word_mark_seconds"] == 0.4
    assert l2["insertions"] == [
        {
            "after_word_index": 2, "position_within_slot": 1, "error_tag": "INS",
            "inserted_text_raw": "كا", "inserted_text_normalised": "کا",
        }
    ]
    [l1] = rec["annotations"]["layer_1"]
    assert l1["transcript_normalised"] == "ایک لڑکا کتاب [unintelligible] رہا تھا"
    tokens = data["passages"][0]["tokens"]
    assert tokens[2]["printed_word_normalised"] == "کتاب"
    assert admin.get("/api/admin/stats").json()["last_export_at"] is not None

    # Audit trail captured the key actions.
    from app.db import SessionLocal
    from app.models import AuditLog

    with SessionLocal() as s:
        actions = {a for (a,) in s.query(AuditLog.action)}
    assert {"login.success", "passage.create", "recording.ingest", "task.checkout",
            "annotation.submit", "export.download"} <= actions
