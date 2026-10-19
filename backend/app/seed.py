"""Startup seeding: the admin account and the built-in reading passages. Idempotent."""

import json
from pathlib import Path

from sqlalchemy import func, select

from app.auth import hash_password
from app.config import get_settings
from app.db import SessionLocal
from app.models import AuditLog, Passage, PassageToken, User
from app.models.user import ROLE_ADMIN
from app.services import audit

BUILTIN_PASSAGES = Path(__file__).parent / "data" / "passages.json"


def seed_admin() -> bool:
    settings = get_settings()
    email = settings.admin_email.strip().lower()
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(func.lower(User.email) == email)):
            return False
        admin = User(email=email, password_hash=hash_password(settings.admin_password), role=ROLE_ADMIN)
        db.add(admin)
        db.flush()
        audit.record(db, "user.seed_admin", target_type="user", target_id=admin.id, meta={"email": email})
        db.commit()
        return True


def seed_passages(path: Path = BUILTIN_PASSAGES) -> tuple[list[str], list[str]]:
    """Add each built-in passage once. Returns (created codes, skipped busy codes).

    A passage is seeded at most once per database (tracked in the audit log), so
    one an admin deletes stays deleted. If its code is already taken by another
    passage it is skipped and retried on the next start, once the code is free.
    """
    entries = json.loads(path.read_text(encoding="utf-8"))["passages"]
    created, busy = [], []
    with SessionLocal() as db:
        seeded = {
            meta["code"]
            for meta in db.scalars(select(AuditLog.meta).where(AuditLog.action == "passage.seed"))
            if meta.get("code")
        }
        for entry in entries:
            code = entry["code"]
            if code in seeded:
                continue
            if db.scalar(select(Passage.id).where(Passage.code == code)):
                busy.append(code)
                continue
            # Same tokenisation as POST /api/admin/passages: split on whitespace.
            words = entry["urdu_text"].split()
            passage = Passage(
                code=code,
                title=entry["title"],
                urdu_text=entry["urdu_text"].strip(),
                tokens=[PassageToken(word_index=i, printed_word=w) for i, w in enumerate(words, start=1)],
            )
            db.add(passage)
            db.flush()
            audit.record(
                db, "passage.seed", target_type="passage", target_id=passage.id,
                meta={"code": code, "word_count": len(words)},
            )
            created.append(code)
        db.commit()
    return created, busy


if __name__ == "__main__":
    created = seed_admin()
    print(f"Admin {get_settings().admin_email}: {'created' if created else 'already exists'}")
    added, busy = seed_passages()
    print(f"Built-in passages added: {', '.join(added) or 'none'}")
    if busy:
        print(f"Built-in passages skipped, code already used by another passage: {', '.join(busy)}")
