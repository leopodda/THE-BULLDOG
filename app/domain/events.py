"""Event log de auditoria e base para integrações futuras (RD Station etc.).

Ações padronizadas: customer.created, customer.updated, customer.validated,
order.created, order.erp_sent, order.erp_failed, order.status_changed,
user.created, user.login, erp.config_changed, erp.authorized.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Event


def record(db: Session, *, tenant_id: str | None, entity_type: str, entity_id: str | None, action: str, actor_user_id: str | None, payload: dict | None = None) -> Event:
    ev = Event(tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id, action=action, actor_user_id=actor_user_id, payload=payload or {})
    db.add(ev)
    return ev
