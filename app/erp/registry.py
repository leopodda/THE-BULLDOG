from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.erp import settings as erp_settings
from app.erp.base import ErpAdapter, ErpNotConfigured
from app.models import ErpConnection

MODES = ("disabled", "mock", "bling")

# Permite injetar um httpx.Client nos testes.
_http_factory = None


def set_http_factory(factory) -> None:
    global _http_factory
    _http_factory = factory


def active_connection(db: Session, tenant_id: str) -> ErpConnection | None:
    return db.scalar(select(ErpConnection).where(ErpConnection.tenant_id == tenant_id, ErpConnection.is_active.is_(True)))


def integration_enabled(conn: ErpConnection | None) -> bool:
    return bool(conn and conn.mode in ("mock", "bling"))


def adapter_for(db: Session, conn: ErpConnection) -> ErpAdapter:
    cfg = erp_settings.merged(conn.settings)
    if conn.mode == "mock":
        from app.erp.mock import MockAdapter
        return MockAdapter(conn.id, cfg)
    if conn.mode == "bling":
        from app.erp.bling import BlingAdapter, BlingClient
        http = _http_factory() if _http_factory else None
        return BlingAdapter(BlingClient(db, conn, http=http))
    raise ErpNotConfigured("Integração ERP desativada nesta conexão.")
