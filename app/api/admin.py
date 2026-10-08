from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import current_tenant, require_admin
from app.api.serializers import connection_out, order_out, user_out
from app.db import get_db
from app.domain import events
from app.domain.pricing import DEFAULT_COMMERCIAL_SETTINGS, active_campaign, active_catalog, commercial_settings
from app.domain.images import image_url
from app.erp import jobs as erp_jobs
from app.erp import settings as erp_settings
from app.erp.base import ErpError
from app.erp.registry import MODES, active_connection
from app.models import Campaign, Customer, ErpConnection, Event, IntegrationJob, Order, PriceRule, Product, ProductLine, Role, Tenant, User
from app.security import hash_password, sign_state, verify_state

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------------------------------------------------------------- comercial
class PricingIn(BaseModel):
    unit_price: str | None = None
    suggested_retail_price: str | None = None
    campaign_active: bool | None = None
    campaign_name: str | None = Field(default=None, max_length=200)
    campaign_buy_cases: int | None = Field(default=None, ge=1, le=1000)
    campaign_bonus_cases: int | None = Field(default=None, ge=1, le=1000)
    campaign_stackable: bool | None = None
    campaign_region_scope: str | None = None
    campaign_max_orders_per_region: int | None = Field(default=None, ge=0)
    commercial_settings: dict | None = None


def _dec(value: str, field: str) -> Decimal:
    try:
        d = Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        raise HTTPException(422, f"{field}: valor inválido")
    if d < 0:
        raise HTTPException(422, f"{field}: não pode ser negativo")
    return d


def _general_rule(db: Session, tenant_id: str) -> PriceRule | None:
    """Regra geral do ENERGÉTICO (preço por lata)."""
    return db.scalar(select(PriceRule).where(PriceRule.tenant_id == tenant_id, PriceRule.product_id.is_(None), PriceRule.channel.is_(None), PriceRule.customer_id.is_(None), PriceRule.active.is_(True), or_(PriceRule.product_line == ProductLine.ENERGY, PriceRule.product_line.is_(None))))


@router.get("/pricing")
def get_pricing(user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    rule = _general_rule(db, tenant.id)
    camp = db.scalar(select(Campaign).where(Campaign.tenant_id == tenant.id).order_by(Campaign.created_at))
    return {
        "unit_price": str(rule.unit_price) if rule else None,
        "suggested_retail_price": str(rule.suggested_retail_price) if rule and rule.suggested_retail_price is not None else None,
        "campaign": None if not camp else {
            "id": camp.id, "name": camp.name, "active": camp.active, "buy_cases": camp.buy_cases, "bonus_cases": camp.bonus_cases,
            "stackable": camp.stackable, "region_scope": camp.region_scope, "max_orders_per_region": camp.max_orders_per_region,
        },
        "commercial_settings": commercial_settings(tenant),
    }


@router.put("/pricing")
def put_pricing(body: PricingIn, user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    changes: dict = {}
    rule = _general_rule(db, tenant.id)
    if body.unit_price is not None or body.suggested_retail_price is not None:
        if rule is None:
            rule = PriceRule(tenant_id=tenant.id, product_line=ProductLine.ENERGY, unit_price=Decimal("0"))
            db.add(rule)
        if body.unit_price is not None:
            rule.unit_price = _dec(body.unit_price, "unit_price")
            changes["unit_price"] = str(rule.unit_price)
        if body.suggested_retail_price is not None:
            rule.suggested_retail_price = _dec(body.suggested_retail_price, "suggested_retail_price") if body.suggested_retail_price != "" else None
            changes["suggested_retail_price"] = str(rule.suggested_retail_price)
    camp_fields = {k: v for k, v in body.model_dump().items() if k.startswith("campaign_") and v is not None}
    if camp_fields or body.campaign_max_orders_per_region == 0:
        camp = db.scalar(select(Campaign).where(Campaign.tenant_id == tenant.id).order_by(Campaign.created_at))
        if camp is None:
            camp = Campaign(tenant_id=tenant.id, name="Lançamento 10+1")
            db.add(camp)
        if body.campaign_region_scope is not None and body.campaign_region_scope not in ("none", "uf", "municipio"):
            raise HTTPException(422, "campaign_region_scope deve ser none, uf ou municipio")
        mapping = {"campaign_active": "active", "campaign_name": "name", "campaign_buy_cases": "buy_cases", "campaign_bonus_cases": "bonus_cases", "campaign_stackable": "stackable", "campaign_region_scope": "region_scope"}
        for k, attr in mapping.items():
            if camp_fields.get(k) is not None:
                setattr(camp, attr, camp_fields[k])
        if "campaign_max_orders_per_region" in body.model_fields_set:
            camp.max_orders_per_region = body.campaign_max_orders_per_region or None
        changes["campaign"] = {k: v for k, v in camp_fields.items()}
    if body.commercial_settings is not None:
        unknown = set(body.commercial_settings) - set(DEFAULT_COMMERCIAL_SETTINGS)
        if unknown:
            raise HTTPException(422, f"Configurações desconhecidas: {sorted(unknown)}")
        tenant.settings = {**(tenant.settings or {}), **body.commercial_settings}
        changes["commercial_settings"] = sorted(body.commercial_settings)
    events.record(db, tenant_id=tenant.id, entity_type="tenant", entity_id=tenant.id, action="pricing.changed", actor_user_id=user.id, payload=changes)
    db.commit()
    return get_pricing(user, tenant, db)


# ---------------------------------------------------------------- ERP
class ConnectionIn(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    mode: str | None = None
    credentials_env_prefix: str | None = Field(default=None, max_length=80, pattern=r"^[A-Z][A-Z0-9_]*$")
    settings: dict | None = None
    product_external_ids: dict[str, str | None] | None = None
    seller_external_ids: dict[str, str | None] | None = None


def _conn(db: Session, tenant: Tenant, connection_id: str) -> ErpConnection:
    c = db.get(ErpConnection, connection_id)
    if c is None or c.tenant_id != tenant.id:
        raise HTTPException(404, "Conexão não encontrada.")
    return c


def _apply_refs(db: Session, conn: ErpConnection, entity_type: str, mapping: dict[str, str | None], valid_ids: set[str]) -> None:
    for entity_id, ext in mapping.items():
        if entity_id not in valid_ids:
            raise HTTPException(422, f"{entity_type} desconhecido: {entity_id}")
        ref = erp_jobs.get_ref(db, conn.id, entity_type, entity_id)
        ext = (ext or "").strip()
        if not ext:
            if ref:
                db.delete(ref)
            continue
        if not ext.isdigit():
            raise HTTPException(422, f"ID externo deve ser numérico: {ext}")
        erp_jobs.set_ref(db, conn.id, entity_type, entity_id, ext)


@router.get("/erp")
def get_erp(user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    conns = db.scalars(select(ErpConnection).where(ErpConnection.tenant_id == tenant.id).order_by(ErpConnection.created_at))
    products = [{"id": p.id, "sku": p.sku, "name": p.commercial_name, "line": p.line} for p in db.scalars(select(Product).where(Product.tenant_id == tenant.id).order_by(Product.sort_order))]
    sellers = [user_out(u) for u in db.scalars(select(User).where(User.tenant_id == tenant.id, User.role == Role.SELLER))]
    return {"connections": [connection_out(db, c) for c in conns], "modes": MODES, "products": products, "sellers": sellers, "defaults": erp_settings.DEFAULT_CONNECTION_SETTINGS}


@router.post("/erp/connections", status_code=201)
def create_connection(body: ConnectionIn, user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    if not body.label:
        raise HTTPException(422, "Informe o nome da conexão.")
    mode = body.mode or "disabled"
    if mode not in MODES:
        raise HTTPException(422, "Modo inválido.")
    try:
        cfg = erp_settings.validate(body.settings or {})
    except erp_settings.SettingsError as exc:
        raise HTTPException(422, str(exc))
    conn = ErpConnection(tenant_id=tenant.id, label=body.label, mode=mode, credentials_env_prefix=body.credentials_env_prefix, settings=cfg, is_active=False)
    db.add(conn)
    db.flush()
    events.record(db, tenant_id=tenant.id, entity_type="erp_connection", entity_id=conn.id, action="erp.connection_created", actor_user_id=user.id, payload={"label": conn.label, "mode": mode})
    db.commit()
    return {"connection": connection_out(db, conn)}


@router.put("/erp/connections/{connection_id}")
def update_connection(connection_id: str, body: ConnectionIn, user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    conn = _conn(db, tenant, connection_id)
    changes: dict = {}
    if body.label is not None:
        conn.label = body.label
        changes["label"] = body.label
    if body.mode is not None:
        if body.mode not in MODES:
            raise HTTPException(422, "Modo inválido.")
        conn.mode = body.mode
        changes["mode"] = body.mode
    if body.credentials_env_prefix is not None:
        conn.credentials_env_prefix = body.credentials_env_prefix
        changes["credentials_env_prefix"] = body.credentials_env_prefix
    if body.settings is not None:
        try:
            clean = erp_settings.validate(body.settings)
        except erp_settings.SettingsError as exc:
            raise HTTPException(422, str(exc))
        conn.settings = {**(conn.settings or {}), **clean}
        changes["settings"] = sorted(clean)
    if body.product_external_ids is not None:
        _apply_refs(db, conn, "product", body.product_external_ids, {p.id for p in db.scalars(select(Product).where(Product.tenant_id == tenant.id))})
        changes["product_external_ids"] = body.product_external_ids
    if body.seller_external_ids is not None:
        _apply_refs(db, conn, "seller", body.seller_external_ids, {u.id for u in db.scalars(select(User).where(User.tenant_id == tenant.id, User.role == Role.SELLER))})
        changes["seller_external_ids"] = body.seller_external_ids
    events.record(db, tenant_id=tenant.id, entity_type="erp_connection", entity_id=conn.id, action="erp.config_changed", actor_user_id=user.id, payload=changes)
    db.commit()
    return {"connection": connection_out(db, conn)}


@router.post("/erp/connections/{connection_id}/activate")
def activate_connection(connection_id: str, user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    conn = _conn(db, tenant, connection_id)
    for other in db.scalars(select(ErpConnection).where(ErpConnection.tenant_id == tenant.id)):
        other.is_active = other.id == conn.id
    events.record(db, tenant_id=tenant.id, entity_type="erp_connection", entity_id=conn.id, action="erp.connection_activated", actor_user_id=user.id, payload={"label": conn.label})
    db.commit()
    return {"connection": connection_out(db, conn)}


@router.get("/erp/connections/{connection_id}/oauth/start")
def oauth_start(connection_id: str, user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    from app.erp.bling import authorization_url
    conn = _conn(db, tenant, connection_id)
    try:
        url = authorization_url(conn, sign_state({"cid": conn.id, "uid": user.id}))
    except ErpError as exc:
        raise HTTPException(422, str(exc))
    return {"url": url}


@router.get("/erp/oauth/callback")
def oauth_callback(code: str = Query(max_length=500), state: str = Query(max_length=2000), user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    from app.erp.bling import exchange_code
    data = verify_state(state)
    if not data or data.get("uid") != user.id:
        raise HTTPException(400, "Estado OAuth inválido ou expirado. Tente conectar novamente.")
    conn = _conn(db, tenant, data["cid"])
    try:
        exchange_code(db, conn, code)
    except ErpError as exc:
        raise HTTPException(502, str(exc))
    events.record(db, tenant_id=tenant.id, entity_type="erp_connection", entity_id=conn.id, action="erp.authorized", actor_user_id=user.id, payload={})
    db.commit()
    return RedirectResponse("/#/admin/integracao?autorizado=1", status_code=303)


@router.post("/erp/connections/{connection_id}/sync-status")
def sync_status(connection_id: str, user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    conn = _conn(db, tenant, connection_id)
    try:
        changed = erp_jobs.sync_order_statuses(db, conn)
    except ErpError as exc:
        raise HTTPException(502, str(exc))
    return {"changed": changed}


@router.post("/orders/{order_id}/retry")
def retry(order_id: str, user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None or order.tenant_id != tenant.id:
        raise HTTPException(404, "Pedido não encontrado.")
    conn = active_connection(db, tenant.id)
    job = erp_jobs.retry_order(db, order, conn, user.id)
    if job is not None:
        erp_jobs.run_job(db, job)
    db.refresh(order)
    return {"order": order_out(db, order, role=user.role, with_events=True)}


@router.post("/jobs/process")
def process_jobs(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    done = erp_jobs.process_pending(db)
    return {"processed": len(done), "results": [{"id": j.id, "status": j.status, "error": j.last_error} for j in done]}


@router.get("/jobs")
def list_jobs(user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    jobs = db.scalars(select(IntegrationJob).where(IntegrationJob.tenant_id == tenant.id).order_by(IntegrationJob.created_at.desc()).limit(100))
    return {"items": [{"id": j.id, "type": j.job_type, "entity_id": j.entity_id, "status": j.status, "attempts": j.attempts, "last_error": j.last_error, "next_attempt_at": j.next_attempt_at.isoformat() if j.next_attempt_at else None} for j in jobs]}


# ---------------------------------------------------------------- usuários
class UserIn(BaseModel):
    role: str
    name: str = Field(max_length=200)
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=200)
    customer_id: str | None = Field(default=None, max_length=36)
    seller_type: str | None = Field(default=None, max_length=30)
    commission_rate: str | None = None


class UserPatch(BaseModel):
    active: bool | None = None
    name: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=200)
    seller_type: str | None = Field(default=None, max_length=30)
    commission_rate: str | None = None


@router.get("/users")
def list_users(user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    return {"items": [user_out(u) for u in db.scalars(select(User).where(User.tenant_id == tenant.id).order_by(User.role, User.name))]}


@router.post("/users", status_code=201)
def create_user(body: UserIn, user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    if body.role not in Role.ALL:
        raise HTTPException(422, "Perfil inválido.")
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(422, "E-mail inválido.")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Já existe usuário com este e-mail.")
    if body.role == Role.CUSTOMER:
        c = db.get(Customer, body.customer_id) if body.customer_id else None
        if c is None or c.tenant_id != tenant.id:
            raise HTTPException(422, "Login de cliente exige um cliente cadastrado.")
    elif body.customer_id:
        raise HTTPException(422, "Somente perfil cliente é vinculado a um cadastro de cliente.")
    u = User(
        tenant_id=tenant.id, role=body.role, name=body.name.strip(), email=email, password_hash=hash_password(body.password),
        customer_id=body.customer_id, seller_type=body.seller_type,
        commission_rate=_dec(body.commission_rate, "commission_rate") if body.commission_rate else None,
        must_change_password=True,
    )
    db.add(u)
    db.flush()
    events.record(db, tenant_id=tenant.id, entity_type="user", entity_id=u.id, action="user.created", actor_user_id=user.id, payload={"role": u.role, "email": u.email})
    db.commit()
    return {"user": user_out(u)}


@router.patch("/users/{user_id}")
def patch_user(user_id: str, body: UserPatch, user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None or u.tenant_id != tenant.id:
        raise HTTPException(404, "Usuário não encontrado.")
    if body.active is False and u.id == user.id:
        raise HTTPException(422, "Você não pode desativar o próprio usuário.")
    if body.active is not None:
        u.active = body.active
    if body.name:
        u.name = body.name.strip()
    if body.password:
        u.password_hash = hash_password(body.password)
        u.must_change_password = True
    if body.seller_type is not None:
        u.seller_type = body.seller_type or None
    if body.commission_rate is not None:
        u.commission_rate = _dec(body.commission_rate, "commission_rate") if body.commission_rate else None
    events.record(db, tenant_id=tenant.id, entity_type="user", entity_id=u.id, action="user.updated", actor_user_id=user.id, payload={k: (v if k != "password" else "***") for k, v in body.model_dump(exclude_none=True).items()})
    db.commit()
    return {"user": user_out(u)}


@router.get("/events")
def list_events(entity_id: str | None = Query(default=None, max_length=36), limit: int = Query(default=100, ge=1, le=500), user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    stmt = select(Event).where(Event.tenant_id == tenant.id)
    if entity_id:
        stmt = stmt.where(Event.entity_id == entity_id)
    evs = db.scalars(stmt.order_by(Event.created_at.desc()).limit(limit))
    return {"items": [{"id": e.id, "entity_type": e.entity_type, "entity_id": e.entity_id, "action": e.action, "actor_user_id": e.actor_user_id, "payload": e.payload, "at": e.created_at.isoformat()} for e in evs]}


# ---------------------------------------------------------------- produtos
class ProductPatch(BaseModel):
    id: str = Field(max_length=36)
    active: bool | None = None
    price: str | None = None            # preço por unidade de venda do portal (display) — tabacaria
    suggested_price: str | None = None  # referência ao consumidor/online por display


class ProductsIn(BaseModel):
    items: list[ProductPatch] = Field(max_length=200)
    enabled_lines: list[str] | None = None


def _product_rule(db: Session, tenant_id: str, product_id: str) -> PriceRule | None:
    return db.scalar(select(PriceRule).where(PriceRule.tenant_id == tenant_id, PriceRule.product_id == product_id, PriceRule.customer_id.is_(None), PriceRule.channel.is_(None), PriceRule.active.is_(True)))


@router.get("/products")
def list_products(user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    items = []
    for p in db.scalars(select(Product).where(Product.tenant_id == tenant.id).order_by(Product.sort_order)):
        rule = _product_rule(db, tenant.id, p.id)
        items.append({
            "id": p.id, "sku": p.sku, "name": p.commercial_name, "short_name": p.short_name, "line": p.line,
            "sale_unit": p.sale_unit, "units_per_case": p.units_per_case, "pack_contents": p.pack_contents, "active": p.active,
            "image_url": image_url(p.sku),
            "price": str(rule.unit_price) if rule else None,
            "suggested_price": str(rule.suggested_retail_price) if rule and rule.suggested_retail_price is not None else None,
        })
    return {"items": items, "enabled_lines": commercial_settings(tenant).get("enabled_lines"), "lines": [{"id": l, "label": ProductLine.LABELS[l]} for l in ProductLine.ALL]}


@router.put("/products")
def put_products(body: ProductsIn, user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    changed = []
    for it in body.items:
        p = db.get(Product, it.id)
        if p is None or p.tenant_id != tenant.id:
            raise HTTPException(404, "Produto não encontrado.")
        if it.active is not None:
            p.active = it.active
        if it.price is not None or it.suggested_price is not None:
            rule = _product_rule(db, tenant.id, p.id)
            if it.price in ("", None) and rule is None:
                pass
            else:
                if rule is None:
                    rule = PriceRule(tenant_id=tenant.id, product_id=p.id, unit_price=Decimal("0"))
                    db.add(rule)
                if it.price not in (None, ""):
                    rule.unit_price = _dec(it.price, f"preço {p.sku}")
                if it.suggested_price is not None:
                    rule.suggested_retail_price = _dec(it.suggested_price, f"sugerido {p.sku}") if it.suggested_price != "" else None
        changed.append(p.sku)
    if body.enabled_lines is not None:
        bad = set(body.enabled_lines) - set(ProductLine.ALL)
        if bad:
            raise HTTPException(422, f"Linhas inválidas: {sorted(bad)}")
        tenant.settings = {**(tenant.settings or {}), "enabled_lines": list(body.enabled_lines)}
    events.record(db, tenant_id=tenant.id, entity_type="tenant", entity_id=tenant.id, action="products.changed", actor_user_id=user.id, payload={"skus": changed, "enabled_lines": body.enabled_lines})
    db.commit()
    return list_products(user, tenant, db)
