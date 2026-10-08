from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Role, Tenant, User
from app.security import SESSION_COOKIE, decode_session_token


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    data = decode_session_token(token) if token else None
    if not data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Entre novamente.")
    user = db.get(User, data.get("sub"))
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário inativo.")
    return user


def current_tenant(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Tenant:
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None or not tenant.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Operação inativa.")
    return tenant


def require_roles(*roles: str):
    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso não permitido para este perfil.")
        return user
    return checker


require_admin = require_roles(Role.ADMIN)
require_staff = require_roles(Role.ADMIN, Role.SELLER)
