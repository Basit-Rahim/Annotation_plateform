"""Create the admin account from ADMIN_EMAIL / ADMIN_PASSWORD. Idempotent."""

from sqlalchemy import func, select

from app.auth import hash_password
from app.config import get_settings
from app.db import SessionLocal
from app.models import User
from app.models.user import ROLE_ADMIN
from app.services import audit


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


if __name__ == "__main__":
    created = seed_admin()
    print(f"Admin {get_settings().admin_email}: {'created' if created else 'already exists'}")
