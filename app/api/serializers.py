"""Saída da API. Nunca inclui tokens, segredos ou hashes."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.documents import IE_INDICATORS, format_cnpj
from app.domain.images import image_url
from app.erp import settings as erp_settings
from app.models import Customer, ErpConnection, Event, ExternalRef, Order, Product, Role, User


def user_out(u: User) -> dict:
    return {
        "id": u.id,
        "role": u.role,
        "name": u.name,
        "email": u.email,
        "active": u.active,
        "customer_id": u.customer_id,
        "seller_type": u.seller_type,
        "commission_rate": str(u.commission_rate) if u.commission_rate is not None else None,
        "must_change_password": u.must_change_password,
    }


def customer_out(c: Customer, *, staff: bool = True) -> dict:
    out = {
        "id": c.id,
        "cnpj": c.cnpj,
        "cnpj_formatted": format_cnpj(c.cnpj),
        "ie": c.ie,
        "ie_indicator": c.ie_indicator,
        "ie_indicator_label": IE_INDICATORS.get(c.ie_indicator),
        "razao_social": c.razao_social,
        "nome_fantasia": c.nome_fantasia,
        "contact_name": c.contact_name,
        "phone": c.phone,
        "whatsapp": c.whatsapp,
        "email": c.email,
        "email_nfe": c.email_nfe,
        "cep": c.cep,
        "logradouro": c.logradouro,
        "numero": c.numero,
        "complemento": c.complemento,
        "bairro": c.bairro,
        "municipio": c.municipio,
        "uf": c.uf,
        "channel": c.channel,
        "validation_status": c.validation_status,
    }
    if staff:
        out.update({"validation_notes": c.validation_notes, "assigned_seller_id": c.assigned_seller_id, "created_at": c.created_at.isoformat() if c.created_at else None})
    return out


def order_out(db: Session, o: Order, *, role: str, with_events: bool = False) -> dict:
    units = {p.id: p.sale_unit for p in db.scalars(select(Product).where(Product.id.in_([i.product_id for i in o.items])))}
    item_units = {units.get(i.product_id) for i in o.items}
    order_unit = item_units.pop() if len(item_units) == 1 else "item"
    erp = None
    if o.erp_connection_id:
        ref = db.scalar(select(ExternalRef).where(ExternalRef.connection_id == o.erp_connection_id, ExternalRef.entity_type == "order", ExternalRef.entity_id == o.id))
        if ref:
            erp = {"order_id": ref.external_id, "order_number": ref.external_number, "status_id": (ref.data or {}).get("status_id")}
    out = {
        "id": o.id,
        "order_number": o.order_number,
        "product_line": o.product_line,
        "sale_unit": order_unit,
        "status": o.status,
        "source": o.source,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "customer": {"id": o.customer.id, "razao_social": o.customer.razao_social, "nome_fantasia": o.customer.nome_fantasia, "cnpj_formatted": format_cnpj(o.customer.cnpj), "municipio": o.customer.municipio, "uf": o.customer.uf},
        "paid_cases": o.paid_cases,
        "bonus_cases": o.bonus_cases,
        "total_units": o.total_units,
        "total_amount": str(o.total_amount),
        "payment_method_preference": o.payment_method_preference,
        "suggested_payment_terms": o.suggested_payment_terms,
        "freight_status": o.freight_status,
        "delivery_estimate": o.delivery_estimate,
        "notes": o.notes,
        "items": [
            {
                "product_id": i.product_id,
                "sku": i.sku,
                "name": i.product_name,
                "units_per_case": i.units_per_case,
                "sale_unit": units.get(i.product_id, "caixa"),
                "image_url": image_url(i.sku),
                "cases": i.cases_qty,
                "units": i.units_qty,
                "bonus_cases": i.bonus_cases,
                "bonus_units": i.bonus_units,
                "unit_price": str(i.unit_price_commercial),
                "case_price": str(i.case_price_commercial),
                "line_total": str(i.line_total),
            }
            for i in o.items
        ],
    }
    if role != Role.CUSTOMER:
        out.update({
            "integration_status": o.integration_status,
            "integration_error": o.integration_error,
            "erp": erp,
            "seller_id": o.seller_id,
            "customer_validation_at_order": o.customer_validation_at_order,
        })
    else:
        out["erp"] = {"order_number": erp["order_number"]} if erp else None
    if with_events and role == Role.ADMIN:
        evs = db.scalars(select(Event).where(Event.entity_type == "order", Event.entity_id == o.id).order_by(Event.created_at))
        out["events"] = [{"action": e.action, "at": e.created_at.isoformat(), "actor_user_id": e.actor_user_id, "payload": e.payload} for e in evs]
    return out


def connection_out(db: Session, c: ErpConnection) -> dict:
    """Sem token_ciphertext. Mostra apenas se a conexão está autorizada."""
    product_refs = {r.entity_id: r.external_id for r in db.scalars(select(ExternalRef).where(ExternalRef.connection_id == c.id, ExternalRef.entity_type == "product"))}
    seller_refs = {r.entity_id: r.external_id for r in db.scalars(select(ExternalRef).where(ExternalRef.connection_id == c.id, ExternalRef.entity_type == "seller"))}
    cfg = erp_settings.merged(c.settings)
    return {
        "id": c.id,
        "provider": c.provider,
        "label": c.label,
        "mode": c.mode,
        "is_active": c.is_active,
        "credentials_env_prefix": c.credentials_env_prefix,
        "authorized": bool(c.token_ciphertext),
        "authorized_at": c.authorized_at.isoformat() if c.authorized_at else None,
        "token_expires_at": c.token_expires_at.isoformat() if c.token_expires_at else None,
        "settings": {k: v for k, v in cfg.items()},
        "pending_for_dfj": [k for k in erp_settings.PENDING_FOR_DFJ if cfg.get(k) in (None, {}) or (isinstance(cfg.get(k), dict) and not any(cfg[k].values()))],
        "product_external_ids": product_refs,
        "seller_external_ids": seller_refs,
    }
