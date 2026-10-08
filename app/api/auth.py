from __future__ import annotations

import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.serializers import customer_out, user_out
from app.config import get_settings
from app.db import get_db
from app.domain import events
from app.models import Customer, Role, User, utcnow
from app.security import SESSION_COOKIE, create_session_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Limitador simples em memória (por processo): 10 falhas em 15 min por e-mail+IP.
_fail_lock = threading.Lock()
_failures: dict[str, list[float]] = {}
WINDOW_S, MAX_FAILS = 15 * 60, 10


def _key(email: str, request: Request) -> str:
    ip = request.client.host if request.client else "?"
    return f"{email.lower()}|{ip}"


def _blocked(key: str) -> bool:
    now = time.time()
    with _fail_lock:
        hits = [t for t in _failures.get(key, []) if now - t < WINDOW_S]
        _failures[key] = hits
        return len(hits) >= MAX_FAILS


def _fail(key: str) -> None:
    with _fail_lock:
        _failures.setdefault(key, []).append(time.time())


def reset_rate_limit() -> None:
    with _fail_lock:
        _failures.clear()


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    key = _key(body.email, request)
    if _blocked(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitas tentativas. Aguarde alguns minutos.")
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.strip().lower()))
    if user is None or not user.active or not verify_password(body.password, user.password_hash):
        _fail(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
    token = create_session_token(user.id, user.role, user.tenant_id)
    s = get_settings()
    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=s.cookie_secure, samesite="lax", max_age=s.session_hours * 3600, path="/")
    user.last_login_at = utcnow()
    events.record(db, tenant_id=user.tenant_id, entity_type="user", entity_id=user.id, action="user.login", actor_user_id=user.id)
    db.commit()
    return {"user": user_out(user)}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    out = {"user": user_out(user)}
    if user.role == Role.CUSTOMER and user.customer_id:
        c = db.get(Customer, user.customer_id)
        out["customer"] = customer_out(c, staff=False) if c else None
    return out


@router.post("/change-password")
def change_password(body: ChangePasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Senha atual incorreta.")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    events.record(db, tenant_id=user.tenant_id, entity_type="user", entity_id=user.id, action="user.password_changed", actor_user_id=user.id)
    db.commit()
    return {"ok": True}
