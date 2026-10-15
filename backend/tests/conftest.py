"""Test fixtures. Tests run against a real Postgres database named <POSTGRES_DB>_test,
created on demand, because the pool relies on FOR UPDATE SKIP LOCKED and a
partial unique index that only Postgres provides."""

import os
import shutil
import socket
import tempfile
import uuid
from pathlib import Path

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"


def _project_database_url() -> str:
    """The repo's .env wins over a machine-wide DATABASE_URL; inside the
    container there is no .env file and the compose environment is used."""
    for candidate in (Path(".env"), Path(__file__).parents[2] / ".env"):
        if candidate.is_file():
            url = dotenv_values(candidate).get("DATABASE_URL")
            if url:
                return Settings(database_url=url).sqlalchemy_url
    return Settings().sqlalchemy_url


def _test_database_url() -> str:
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    url = make_url(_project_database_url())
    host = url.host or "localhost"
    try:
        socket.gethostbyname(host)
    except OSError:
        host = "localhost"  # running on the host against the compose Postgres
    return url.set(host=host, database=f"{url.database}_test").render_as_string(hide_password=False)


TEST_DB_URL = _test_database_url()
_TMP = Path(tempfile.mkdtemp(prefix="annot-tests-"))
os.environ.update(
    DATABASE_URL=TEST_DB_URL,
    AUDIO_DROP_DIR=str(_TMP / "incoming"),
    AUDIO_STORAGE_DIR=str(_TMP / "audio"),
    SCHEDULER_ENABLED="false",
    SECRET_KEY="test-secret",
    ADMIN_EMAIL="admin@test.local",
    ADMIN_PASSWORD="admin-password",
)


def _create_database() -> None:
    url = make_url(TEST_DB_URL)
    server = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}):
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    server.dispose()


def _reset_schema() -> None:
    from alembic import command
    from alembic.config import Config

    engine = create_engine(make_url(TEST_DB_URL))
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    engine.dispose()
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def _database():
    _create_database()
    _reset_schema()
    yield
    shutil.rmtree(_TMP, ignore_errors=True)


TABLES = (
    "annotation_layer_2_insertion, annotation_layer_2_word, annotation_layer_2, annotation_layer_1, "
    "task_drafts, tasks, recordings, passage_tokens, passages, audit_log, users"
)


@pytest.fixture
def _clean(_database):
    from app.db import engine

    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    for sub in ("incoming", "audio"):
        d = _TMP / sub
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    yield


@pytest.fixture
def db(_clean):
    from app.db import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def drop_dir(_clean) -> Path:
    return _TMP / "incoming"


@pytest.fixture
def storage_dir(_clean) -> Path:
    return _TMP / "audio"


# --- factories ----------------------------------------------------------------

@pytest.fixture
def make_user(db):
    from app.auth import hash_password
    from app.models import User

    def _make(role="annotator", l1=True, l2=True, email=None, password="password123"):
        user = User(
            email=email or f"{uuid.uuid4().hex[:8]}@test.local",
            password_hash=hash_password(password),
            role=role,
            can_layer_1=l1,
            can_layer_2=l2,
        )
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture
def make_passage(db):
    from app.models import Passage, PassageToken

    def _make(text_="ایک لڑکا اسکول گیا", code=None):
        words = text_.split()
        passage = Passage(
            code=code or f"P{uuid.uuid4().hex[:4]}",
            title="Test passage",
            urdu_text=text_,
            tokens=[PassageToken(word_index=i, printed_word=w) for i, w in enumerate(words, 1)],
        )
        db.add(passage)
        db.commit()
        return passage

    return _make


@pytest.fixture
def make_recording(db, make_passage, make_user, storage_dir):
    """Create a recording with one task per layer, bypassing the drop folder."""
    from app.models import Recording, Task

    def _make(passage=None, admin=None):
        passage = passage or make_passage()
        admin = admin or make_user(role="admin")
        rec_id = uuid.uuid4()
        shutil.copy(FIXTURES / "sample.wav", storage_dir / f"{rec_id}.wav")
        rec = Recording(
            id=rec_id, source="drop_folder", source_ref="sample.wav", audio_path=f"{rec_id}.wav",
            duration_seconds=3, passage_id=passage.id, passage_attempt=1, grade=2, gender="female",
            first_language="Urdu", school_type="public", noise_level="quiet", interruption=False,
            ingested_by=admin.id,
        )
        db.add(rec)
        db.flush()
        db.add_all([Task(recording_id=rec_id, layer="layer_1"), Task(recording_id=rec_id, layer="layer_2")])
        db.commit()
        return rec

    return _make
