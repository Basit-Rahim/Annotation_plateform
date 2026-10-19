import json

from app.models import Passage, PassageToken
from app.seed import BUILTIN_PASSAGES, seed_passages


def _builtin():
    return json.loads(BUILTIN_PASSAGES.read_text(encoding="utf-8"))["passages"]


def test_builtin_data_is_well_formed():
    entries = _builtin()
    codes = [e["code"] for e in entries]
    assert len(codes) == len(set(codes)) == 16
    for e in entries:
        assert e["title"] and e["urdu_text"].strip()
        assert len(e["urdu_text"].split()) == e["word_count"]


def test_seeds_every_passage_with_tokens(db):
    created, busy = seed_passages()
    assert busy == []
    assert created == [e["code"] for e in _builtin()]
    p01 = db.query(Passage).filter_by(code="P01").one()
    entry = _builtin()[0]
    assert [t.printed_word for t in p01.tokens] == entry["urdu_text"].split()
    assert db.query(PassageToken).count() == sum(e["word_count"] for e in _builtin())


def test_idempotent_and_deleted_passages_stay_deleted(db):
    seed_passages()
    assert seed_passages() == ([], [])
    db.delete(db.query(Passage).filter_by(code="P02").one())
    db.commit()
    assert seed_passages() == ([], [])
    assert db.query(Passage).filter_by(code="P02").count() == 0


def test_busy_code_is_skipped_then_seeded_when_free(db, make_passage):
    mine = make_passage(code="P01")
    created, busy = seed_passages()
    assert busy == ["P01"] and "P01" not in created
    db.delete(mine)
    db.commit()
    assert seed_passages() == (["P01"], [])
