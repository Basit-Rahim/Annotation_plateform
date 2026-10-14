import threading
from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.db import SessionLocal
from app.models import Task, User
from app.models._common import utcnow
from app.services import checkout


def _take(db, user, layer):
    return checkout.take_next(db, db.merge(user), layer)


def test_take_next_picks_oldest_available(db, make_user, make_recording):
    first = make_recording()
    make_recording()
    user = make_user()
    task = _take(db, user, "layer_1")
    assert task.recording_id == first.id
    assert task.status == "checked_out"
    assert task.checked_out_by == user.id
    assert task.lease_expires_at - task.checked_out_at == timedelta(minutes=120)


def test_take_next_respects_layer(db, make_user, make_recording):
    make_recording()
    task = _take(db, make_user(), "layer_2")
    assert task.layer == "layer_2"


def test_take_next_rejects_ineligible_layer(db, make_user, make_recording):
    make_recording()
    only_l1 = make_user(l1=True, l2=False)
    with pytest.raises(HTTPException) as exc:
        _take(db, only_l1, "layer_2")
    assert exc.value.status_code == 403


def test_second_checkout_is_409(db, make_user, make_recording):
    make_recording()
    make_recording()
    user = make_user()
    _take(db, user, "layer_1")
    with pytest.raises(HTTPException) as exc:
        _take(db, user, "layer_2")
    assert exc.value.status_code == 409


def test_empty_pool_is_404(db, make_user):
    with pytest.raises(HTTPException) as exc:
        _take(db, make_user(), "layer_1")
    assert exc.value.status_code == 404


def test_skips_withdrawn_recordings(db, make_user, make_recording):
    withdrawn = make_recording()
    live = make_recording()
    withdrawn.withdrawn_at = utcnow()
    db.commit()
    assert _take(db, make_user(), "layer_1").recording_id == live.id


def test_skips_layer_already_submitted_by_user(db, make_user, make_recording):
    rec = make_recording()
    user = make_user()
    # Simulate a second layer_1 task (Phase 2 double annotation) for a recording
    # this user has already transcribed.
    done = db.query(Task).filter_by(recording_id=rec.id, layer="layer_1").one()
    done.status, done.checked_out_by = "submitted", user.id
    db.add(Task(recording_id=rec.id, layer="layer_1"))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        _take(db, user, "layer_1")
    assert exc.value.status_code == 404


def test_concurrent_take_next_never_double_assigns(make_user, make_recording):
    make_recording()  # exactly one layer_1 task
    users = [make_user() for _ in range(6)]
    barrier = threading.Barrier(len(users))
    results: list[object] = []

    def worker(u: User):
        with SessionLocal() as s:
            barrier.wait()
            try:
                results.append(checkout.take_next(s, s.merge(u), "layer_1").id)
            except HTTPException as e:
                results.append(e.status_code)

    threads = [threading.Thread(target=worker, args=(u,)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    task_ids = [r for r in results if not isinstance(r, int)]
    assert len(task_ids) == 1
    assert sorted(r for r in results if isinstance(r, int)) == [404] * 5


def test_concurrent_take_next_same_user_gets_one_task(make_user, make_recording):
    for _ in range(4):
        make_recording()
    user = make_user()
    barrier = threading.Barrier(4)

    def worker():
        with SessionLocal() as s:
            barrier.wait()
            try:
                checkout.take_next(s, s.merge(user), "layer_1")
            except HTTPException:
                pass

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with SessionLocal() as s:
        assert s.query(Task).filter_by(checked_out_by=user.id, status="checked_out").count() == 1


def test_lease_expiry_returns_task_to_pool(db, make_user, make_recording):
    make_recording()
    holder, other = make_user(), make_user()
    task = _take(db, holder, "layer_1")
    task.lease_expires_at = utcnow() - timedelta(seconds=1)
    db.commit()

    assert checkout.expire_leases(db) == 1
    db.refresh(task)
    assert task.status == "available"
    assert task.checked_out_by is None and task.checked_out_at is None
    assert _take(db, other, "layer_1").id == task.id


def test_unexpired_lease_is_kept(db, make_user, make_recording):
    make_recording()
    task = _take(db, make_user(), "layer_1")
    assert checkout.expire_leases(db) == 0
    db.refresh(task)
    assert task.status == "checked_out"
