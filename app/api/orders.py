from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import current_tenant, current_user
from app.api.serializers import order_out
from app.config import get_settings
from app.db import SessionLocal, get_db
from app.domain import orders as order_svc
from app.domain.pricing import (
    PAYMENT_METHOD_LABELS,
    QuoteError,
    active_campaign,
    active_catalog,
    commercial_settings,
    money,
    quote_for_customer,
    resolve_unit_price,
    suggested_retail_price,
    suggested_retail_price_for,
)
from app.domain.images import image_url
from app.erp.jobs import process_order_now
from app.models import Customer, Order, ProductLine, Role, Tenant, User

router = APIRouter(prefix="/api", tags=["orders"])


class ItemIn(BaseModel):
    product_id: str = Field(max_length=36)
    cases: int = Field(ge=0, le=100000)


class QuoteIn(BaseModel):
    customer_id: str | None = Field(default=None, max_length=36)
    items: list[ItemIn] = Field(max_length=20)
    bonus_product_id: str | None = Field(default=None, max_length=36)


class OrderIn(QuoteIn):
    payment_method: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)


def _resolve_customer(db: Session, user: User, tenant: Tenant, customer_id: str | None) -> Customer:
    if user.role == Role.CUSTOMER:
        # PDV só pode usar o próprio cadastro, independente do que vier no corpo.
        if customer_id and customer_id != user.customer_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Você só pode fazer pedidos para o seu próprio cadastro.")
        customer_id = user.customer_id
    if not customer_id:
        raise HTTPException(422, "Selecione o cliente.")
    c = db.get(Customer, customer_id)
    if c is None or c.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente não encontrado.")
    return c


def _requested(items: list[ItemIn]) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        out[it.product_id] = out.get(it.product_id, 0) + it.cases
    return out


@router.get("/catalog")
def catalog(customer_id: str | None = Query(default=None, max_length=36), user: User = Depends(current_user), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    customer = None
    if user.role == Role.CUSTOMER:
        customer = db.get(Customer, user.customer_id) if user.customer_id else None
    elif customer_id:
        customer = db.get(Customer, customer_id)
        if customer and customer.tenant_id != tenant.id:
            customer = None
    settings = commercial_settings(tenant)
    products = []
    for p in active_catalog(db, tenant):
        unit = resolve_unit_price(db, tenant.id, p, customer)
        srp_p = suggested_retail_price_for(db, tenant.id, p)
        products.append({
            "id": p.id,
            "sku": p.sku,
            "name": p.commercial_name,
            "short_name": p.short_name,
            "line": p.line,
            "sale_unit": p.sale_unit,
            "units_per_case": p.units_per_case,
            "pack_contents": p.pack_contents,
            "image_url": image_url(p.sku),
            "unit_price": str(money(unit)) if unit is not None else None,
            "case_price": str(money(unit * p.units_per_case)) if unit is not None else None,
            "suggested_retail_price": str(money(srp_p)) if srp_p is not None else None,
        })
    camp = active_campaign(db, tenant.id)
    srp = suggested_retail_price(db, tenant.id)
    return {
        "products": products,
        "suggested_retail_price": str(srp) if srp is not None else None,
        "campaign": {"name": camp.name, "buy_cases": camp.buy_cases, "bonus_cases": camp.bonus_cases, "stackable": camp.stackable, "product_line": camp.product_line} if camp else None,
        "lines": [{"id": l, "label": ProductLine.LABELS[l]} for l in ProductLine.ALL if l in (settings.get("enabled_lines") or ProductLine.ALL)],
        "payment_methods": [{"id": m, "label": PAYMENT_METHOD_LABELS.get(m, m)} for m in settings.get("payment_methods", [])],
        "freight": {"home_uf": settings["home_uf"], "min_cases_home": settings["free_freight_min_cases_home"], "min_cases_other": settings["free_freight_min_cases_other"], "delivery_home": settings["delivery_estimate_home"], "delivery_other": settings["delivery_estimate_other"]},
    }


@router.post("/orders/quote")
def quote(body: QuoteIn, user: User = Depends(current_user), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    customer = _resolve_customer(db, user, tenant, body.customer_id)
    try:
        q, _ = quote_for_customer(db, tenant, customer, _requested(body.items), body.bonus_product_id)
    except QuoteError as exc:
        raise HTTPException(422, str(exc))
    out = q.as_dict()
    for line in out["lines"]:
        line["image_url"] = image_url(line["sku"])
    return {"quote": out}


def _process_in_background(order_id: str) -> None:
    db = SessionLocal()
    try:
        process_order_now(db, order_id)
    finally:
        db.close()


@router.post("/orders", status_code=201)
def create_order(
    body: OrderIn,
    background: BackgroundTasks,
    idempotency_key: str = Header(alias="Idempotency-Key", max_length=80),
    user: User = Depends(current_user),
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    customer = _resolve_customer(db, user, tenant, body.customer_id)
    try:
        orders, created = order_svc.create_order(
            db,
            tenant=tenant,
            actor=user,
            customer=customer,
            requested=_requested(body.items),
            bonus_product_id=body.bonus_product_id,
            payment_method=body.payment_method,
            notes=body.notes,
            idempotency_key=idempotency_key.strip(),
        )
    except order_svc.OrderError as exc:
        raise HTTPException(422, str(exc))
    if created and get_settings().process_jobs_inline:
        for o in orders:
            if o.integration_status == "pendente":
                background.add_task(_process_in_background, o.id)
    out = [order_out(db, o, role=user.role) for o in orders]
    return {"orders": out, "order": out[0], "created": created}


def _visible_orders_stmt(user: User, tenant: Tenant):
    stmt = select(Order).where(Order.tenant_id == tenant.id)
    if user.role == Role.CUSTOMER:
        stmt = stmt.where(Order.customer_id == user.customer_id)
    elif user.role == Role.SELLER:
        stmt = stmt.where(or_(Order.seller_id == user.id, Order.created_by_user_id == user.id))
    return stmt


@router.get("/orders")
def list_orders(
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    integration: str | None = Query(default=None, max_length=30),
    customer_id: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(current_user),
    tenant: Tenant = Depends(current_tenant),
    db: Session = Depends(get_db),
):
    stmt = _visible_orders_stmt(user, tenant)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    if integration and user.role != Role.CUSTOMER:
        stmt = stmt.where(Order.integration_status == integration)
    if customer_id and user.role != Role.CUSTOMER:
        stmt = stmt.where(Order.customer_id == customer_id)
    orders = db.scalars(stmt.order_by(Order.created_at.desc()).limit(limit))
    return {"items": [order_out(db, o, role=user.role) for o in orders]}


@router.get("/orders/{order_id}")
def get_order(order_id: str, user: User = Depends(current_user), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    o = db.scalar(_visible_orders_stmt(user, tenant).where(Order.id == order_id))
    if o is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado.")
    return {"order": order_out(db, o, role=user.role, with_events=True)}
