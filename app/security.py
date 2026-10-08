from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

SESSION_COOKIE = "bd_session"
CSRF_HEADER = "X-Portal-Request"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def create_session_token(user_id: str, role: str, tenant_id: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "role": role, "tid": tenant_id, "iat": now, "exp": now + timedelta(hours=s.session_hours)}
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def decode_session_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def sign_state(data: dict, minutes: int = 15) -> str:
    """Estado assinado para o fluxo OAuth (protege contra CSRF no callback)."""
    now = datetime.now(timezone.utc)
    return jwt.encode({**data, "exp": now + timedelta(minutes=minutes), "purpose": "oauth"}, get_settings().secret_key, algorithm="HS256")


def verify_state(state: str) -> dict | None:
    data = decode_session_token(state)
    if not data or data.get("purpose") != "oauth":
        return None
    return data


def _fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise RuntimeError("APP_ENCRYPTION_KEY não configurada")
    return Fernet(key.encode("ascii"))


def encrypt_json(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data).encode("utf-8")).decode("ascii")


def decrypt_json(ciphertext: str) -> dict:
    try:
        return json.loads(_fernet().decrypt(ciphertext.encode("ascii")))
    except InvalidToken as exc:  # chave trocada ou dado corrompido
        raise RuntimeError("Não foi possível descriptografar tokens do ERP (APP_ENCRYPTION_KEY mudou?)") from exc
