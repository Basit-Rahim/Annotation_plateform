import uuid

from fastapi import Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.models.user import ROLE_ADMIN, ROLE_ANNOTATOR

SESSION_USER_KEY = "user_id"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def login_session(request: Request, user: User) -> None:
    request.session.clear()
    request.session[SESSION_USER_KEY] = str(user.id)


def logout_session(request: Request) -> None:
    request.session.clear()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    raw_id = request.session.get(SESSION_USER_KEY)
    if not raw_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    try:
        user = db.get(User, uuid.UUID(raw_id))
    except ValueError:
        user = None
    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != ROLE_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


def require_annotator(user: User = Depends(get_current_user)) -> User:
    if user.role != ROLE_ANNOTATOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Annotators only")
    return user
