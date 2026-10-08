"""Cliente e adaptador Bling API v3.

- OAuth 2.0 authorization code. client_id/secret vêm do ambiente (prefixo da conexão).
- Tokens (access/refresh) são guardados criptografados em erp_connections.token_ciphertext.
- Limite do Bling: ~3 req/s e 120.000/dia por conta. O cliente espaça as chamadas e
  faz retry com backoff em 429/5xx.
- Nada aqui emite NF-e, gera contas a receber ou lança estoque.
"""
from __future__ import annotations

import base64
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.config import erp_credential
from app.erp.base import ErpError, ErpNotConfigured, ErpOrderRef
from app.models import ErpConnection, utcnow
from app.security import decrypt_json, encrypt_json

API_BASE = os.getenv("BLING_API_BASE", "https://api.bling.com.br/Api/v3")
AUTHORIZE_URL = os.getenv("BLING_OAUTH_AUTHORIZE_URL", "https://www.bling.com.br/Api/v3/oauth/authorize")
TOKEN_URL = os.getenv("BLING_OAUTH_TOKEN_URL", "https://api.bling.com.br/Api/v3/oauth/token")
MIN_INTERVAL_S = float(os.getenv("BLING_MIN_INTERVAL_S", "0.35"))
MAX_RETRIES = int(os.getenv("BLING_MAX_RETRIES", "3"))

_throttle_lock = threading.Lock()
_last_call = 0.0


def _throttle() -> None:
    global _last_call
    if MIN_INTERVAL_S <= 0:
        return
    with _throttle_lock:
        wait = _last_call + MIN_INTERVAL_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def _credentials(conn: ErpConnection) -> tuple[str, str]:
    prefix = conn.credentials_env_prefix
    if not prefix:
        raise ErpNotConfigured("Conexão Bling sem prefixo de credenciais (credentials_env_prefix).")
    cid, secret = erp_credential(prefix, "CLIENT_ID"), erp_credential(prefix, "CLIENT_SECRET")
    if not cid or not secret:
        raise ErpNotConfigured(f"Defina {prefix}_CLIENT_ID e {prefix}_CLIENT_SECRET no ambiente do backend.")
    return cid, secret


def redirect_uri() -> str:
    from app.config import get_settings
    return os.getenv("BLING_REDIRECT_URI", get_settings().public_base_url.rstrip("/") + "/api/admin/erp/oauth/callback")


def authorization_url(conn: ErpConnection, state: str) -> str:
    cid, _ = _credentials(conn)
    return AUTHORIZE_URL + "?" + urlencode({"response_type": "code", "client_id": cid, "state": state, "redirect_uri": redirect_uri()})


def _error_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return f"HTTP {resp.status_code}: {resp.text[:300]}"
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        parts = [err.get("message") or err.get("type") or "Erro Bling", err.get("description") or ""]
        for f in err.get("fields") or []:
            msg = f.get("msg") or f.get("message")
            if msg:
                parts.append(f"{f.get('element') or f.get('field') or ''}: {msg}".strip(": "))
        return f"HTTP {resp.status_code}: " + " | ".join(p for p in parts if p)
    return f"HTTP {resp.status_code}: {str(body)[:300]}"


class TokenStore:
    def __init__(self, db: Session, conn: ErpConnection):
        self.db, self.conn = db, conn

    def load(self) -> dict:
        if not self.conn.token_ciphertext:
            raise ErpNotConfigured("Conexão Bling ainda não autorizada. Use 'Conectar ao Bling' no admin.")
        return decrypt_json(self.conn.token_ciphertext)

    def save(self, token_response: dict) -> None:
        expires_in = int(token_response.get("expires_in", 21600))
        data = {
            "access_token": token_response["access_token"],
            "refresh_token": token_response.get("refresh_token") or (self.load().get("refresh_token") if self.conn.token_ciphertext else None),
            "token_type": token_response.get("token_type", "Bearer"),
        }
        self.conn.token_ciphertext = encrypt_json(data)
        self.conn.token_expires_at = utcnow() + timedelta(seconds=expires_in)
        self.db.add(self.conn)
        self.db.commit()


def _token_request(conn: ErpConnection, form: dict, http: httpx.Client) -> dict:
    cid, secret = _credentials(conn)
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    resp = http.post(TOKEN_URL, data=form, headers={"Authorization": f"Basic {basic}", "Accept": "1.0", "Content-Type": "application/x-www-form-urlencoded"})
    if resp.status_code >= 400:
        retry = resp.status_code >= 500
        raise ErpError("Falha ao obter token do Bling: " + _error_message(resp), retryable=retry, status_code=resp.status_code)
    return resp.json()


def exchange_code(db: Session, conn: ErpConnection, code: str, http: httpx.Client | None = None) -> None:
    http = http or httpx.Client(timeout=30)
    token = _token_request(conn, {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri()}, http)
    conn.token_ciphertext = None
    TokenStore(db, conn).save(token)
    conn.authorized_at = utcnow()
    db.commit()


class BlingClient:
    def __init__(self, db: Session, conn: ErpConnection, http: httpx.Client | None = None):
        self.db, self.conn = db, conn
        self.http = http or httpx.Client(timeout=30)
        self.tokens = TokenStore(db, conn)

    def _access_token(self, force_refresh: bool = False) -> str:
        data = self.tokens.load()
        exp = self.conn.token_expires_at
        if exp is not None and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        expired = exp is None or exp <= datetime.now(timezone.utc) + timedelta(seconds=60)
        if force_refresh or expired or not data.get("access_token"):
            if not data.get("refresh_token"):
                raise ErpNotConfigured("Sem refresh token. Reautorize a conexão Bling.")
            token = _token_request(self.conn, {"grant_type": "refresh_token", "refresh_token": data["refresh_token"]}, self.http)
            self.tokens.save(token)
            return token["access_token"]
        return data["access_token"]

    def request(self, method: str, path: str, *, params=None, json=None) -> dict | None:
        refreshed = False
        for attempt in range(MAX_RETRIES + 1):
            _throttle()
            token = self._access_token()
            try:
                resp = self.http.request(method, API_BASE + path, params=params, json=json, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            except httpx.TransportError as exc:
                if attempt < MAX_RETRIES:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise ErpError(f"Bling indisponível: {exc}", retryable=True) from exc
            if resp.status_code == 401 and not refreshed:
                refreshed = True
                self._access_token(force_refresh=True)
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < MAX_RETRIES:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise ErpError(_error_message(resp), retryable=True, status_code=resp.status_code)
            if resp.status_code >= 400:
                raise ErpError(_error_message(resp), retryable=False, status_code=resp.status_code)
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()
        raise ErpError("Bling: tentativas esgotadas.", retryable=True)


def _parse_order(data: dict) -> ErpOrderRef:
    situacao = data.get("situacao") or {}
    return ErpOrderRef(
        external_id=str(data["id"]),
        external_number=str(data["numero"]) if data.get("numero") not in (None, "") else None,
        status_id=int(situacao["id"]) if situacao.get("id") is not None else None,
        raw={"numero": data.get("numero"), "numeroLoja": data.get("numeroLoja"), "situacao": situacao},
    )


class BlingAdapter:
    def __init__(self, client: BlingClient):
        self.client = client

    def find_customer_by_document(self, cnpj: str) -> str | None:
        body = self.client.request("GET", "/contatos", params={"numeroDocumento": cnpj, "limite": 5}) or {}
        for c in body.get("data") or []:
            if (c.get("numeroDocumento") or "").replace(".", "").replace("/", "").replace("-", "") == cnpj:
                return str(c["id"])
        return None

    def create_customer(self, payload: dict) -> str:
        body = self.client.request("POST", "/contatos", json=payload) or {}
        data = body.get("data") or {}
        if "id" not in data:
            raise ErpError("Bling não retornou o ID do contato criado.", retryable=False)
        return str(data["id"])

    def find_order_by_portal_number(self, portal_number: str) -> ErpOrderRef | None:
        body = self.client.request("GET", "/pedidos/vendas", params={"numerosLojas[]": [portal_number], "limite": 5}) or {}
        for o in body.get("data") or []:
            if str(o.get("numeroLoja") or "") == portal_number:
                return _parse_order(o)
        return None

    def create_order(self, payload: dict) -> ErpOrderRef:
        body = self.client.request("POST", "/pedidos/vendas", json=payload) or {}
        data = body.get("data") or {}
        if "id" not in data:
            raise ErpError("Bling não retornou o ID do pedido criado.", retryable=False)
        try:
            return self.get_order(str(data["id"]))
        except ErpError:
            # pedido criado; número/situação serão lidos na próxima sincronização
            return ErpOrderRef(external_id=str(data["id"]))

    def get_order(self, external_id: str) -> ErpOrderRef:
        body = self.client.request("GET", f"/pedidos/vendas/{external_id}") or {}
        return _parse_order(body.get("data") or {"id": external_id})

    def set_order_status(self, external_id: str, status_id: int) -> None:
        self.client.request("PATCH", f"/pedidos/vendas/{external_id}/situacoes/{int(status_id)}")
