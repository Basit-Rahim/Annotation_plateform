import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import client_ip, hash_password, require_admin
from app.db import get_db
from app.models import User
from app.models.user import ROLE_ADMIN, ROLE_ANNOTATOR
from app.schemas import PasswordReset, UserCreate, UserOut, UserPatch
from app.services import audit

router = APIRouter(prefix="/api/admin/users", tags=["admin: users"])


def _annotator(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.role == ROLE_ADMIN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The admin account is managed through .env")
    return user


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.role, User.created_at)))


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
) -> User:
    email = body.email.strip().lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with that email already exists")
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        role=ROLE_ANNOTATOR,
        can_layer_1=body.can_layer_1,
        can_layer_2=body.can_layer_2,
    )
    db.add(user)
    db.flush()
    audit.record(
        db, "user.create", user_id=admin.id, target_type="user", target_id=user.id,
        meta={"email": email, "can_layer_1": body.can_layer_1, "can_layer_2": body.can_layer_2},
        ip_address=client_ip(request),
    )
    db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID, body: UserPatch, request: Request,
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
) -> User:
    user = _annotator(db, user_id)
    changes = body.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(user, field, value)
    audit.record(
        db, "user.update", user_id=admin.id, target_type="user", target_id=user.id,
        meta=changes, ip_address=client_ip(request),
    )
    db.commit()
    return user


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: uuid.UUID, body: PasswordReset, request: Request,
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
) -> None:
    user = _annotator(db, user_id)
    user.password_hash = hash_password(body.password)
    audit.record(
        db, "user.reset_password", user_id=admin.id, target_type="user", target_id=user.id,
        ip_address=client_ip(request),
    )
    db.commit()
