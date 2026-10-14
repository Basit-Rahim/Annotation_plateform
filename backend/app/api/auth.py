from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import client_ip, get_current_user, login_session, logout_session, verify_password
from app.db import get_db
from app.models import User
from app.schemas import LoginIn, MeOut
from app.services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=MeOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)) -> User:
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        audit.record(db, "login.failure", meta={"email": email}, ip_address=client_ip(request))
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    login_session(request, user)
    audit.record(db, "login.success", user_id=user.id, ip_address=client_ip(request))
    db.commit()
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: Session = Depends(get_db)) -> None:
    user_id = request.session.get("user_id")
    logout_session(request)
    if user_id:
        audit.record(db, "logout", meta={"user_id": user_id}, ip_address=client_ip(request))
        db.commit()


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
