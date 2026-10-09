"""Fila de integração com o ERP (tabela integration_jobs).

Garantias:
- O pedido local é gravado ANTES de qualquer chamada ao ERP e nunca é apagado por falha.
- Reenvio é idempotente: se já existe ExternalRef do pedido, não cria de novo; antes de
  criar, procura no ERP por `numeroLoja` = número do portal (cobre timeout após criar).
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import events
from app.erp import settings as erp_settings
from app.erp.base import ErpError, ErpNotConfigured
from app.erp.mapping import bonus_order_number, build_bonus_order_payload, build_contact_payload, build_order_payload, has_bonus, map_status
from app.erp.registry import adapter_for, integration_enabled
from app.models import (
    Customer,
    ErpConnection,
    ExternalRef,
    IntegrationJob,
    IntegrationStatus,
    Order,
    OrderStatus,
    User,
    ValidationStatus,
    utcnow,
)

MAX_ATTEMPTS = 5
FINAL_STATUSES = (OrderStatus.INVOICED, OrderStatus.CANCELLED)


def get_ref(db: Session, connection_id: str, entity_type: str, entity_id: str) -> ExternalRef | None:
    return db.scalar(select(ExternalRef).where(ExternalRef.connection_id == connection_id, ExternalRef.entity_type == entity_type, ExternalRef.entity_id == entity_id))


def set_ref(db: Session, connection_id: str, entity_type: str, entity_id: str, external_id: str, external_number: str | None = None, data: dict | None = None) -> ExternalRef:
    ref = get_ref(db, connection_id, entity_type, entity_id)
    if ref is None:
        ref = ExternalRef(connection_id=connection_id, entity_type=entity_type, entity_id=entity_id, external_id=str(external_id))
        db.add(ref)
    ref.external_id = str(external_id)
    if external_number is not None:
        ref.external_number = str(external_number)
    if data is not None:
        ref.data = data
    db.flush()
    return ref


def enqueue_order_push(db: Session, order: Order, conn: ErpConnection | None) -> IntegrationJob | None:
    if not integration_enabled(conn):
        order.integration_status = IntegrationStatus.NOT_REQUIRED
        return None
    order.erp_connection_id = conn.id
    order.integration_status = IntegrationStatus.PENDING
    job = db.scalar(select(IntegrationJob).where(IntegrationJob.job_type == "push_order", IntegrationJob.entity_id == order.id, IntegrationJob.connection_id == conn.id))
    if job is None:
        job = IntegrationJob(tenant_id=order.tenant_id, connection_id=conn.id, job_type="push_order", entity_id=order.id)
        db.add(job)
    else:
        job.status = "pending"
        job.next_attempt_at = utcnow()
    db.flush()
    return job


def _push_order(db: Session, job: IntegrationJob) -> None:
    order = db.get(Order, job.entity_id)
    conn = db.get(ErpConnection, job.connection_id)
    if order is None or conn is None:
        raise ErpError("Pedido ou conexão inexistente.", retryable=False)
    cfg = erp_settings.merged(conn.settings)
    customer = db.get(Customer, order.customer_id)

    if customer.validation_status == ValidationStatus.REJECTED:
        raise ErpError("Cliente com cadastro REJEITADO na conferência. Corrija o cadastro e reprocesse.", retryable=False)
    if customer.validation_status == ValidationStatus.PENDING and not cfg.get("send_pending_customers", True):
        raise ErpError("Cliente pendente de conferência; envio bloqueado pela configuração. Confira o cadastro e reprocesse.", retryable=False)

    existing = get_ref(db, conn.id, "order", order.id)
    needs_bonus_order = cfg.get("bonus_line_mode") == "separate_order" and has_bonus(order)
    if needs_bonus_order and not cfg.get("operation_nature_id_bonus"):
        # Falha ANTES de criar qualquer coisa no Bling, para não deixar venda sem a bonificação.
        raise ErpNotConfigured("Natureza de operação da bonificação não configurada (operation_nature_id_bonus). Pedido mantido na fila.")
    if existing and (not needs_bonus_order or get_ref(db, conn.id, "order_bonus", order.id)):
        return  # já enviado (idempotência)

    adapter = adapter_for(db, conn)

    # 1) Cliente
    cref = get_ref(db, conn.id, "customer", customer.id)
    if cref is None:
        ext_id = adapter.find_customer_by_document(customer.cnpj)
        created = False
        if ext_id is None:
            ext_id = adapter.create_customer(build_contact_payload(customer, cfg))
            created = True
        cref = set_ref(db, conn.id, "customer", customer.id, ext_id)
        events.record(db, tenant_id=order.tenant_id, entity_type="customer", entity_id=customer.id, action="customer.erp_linked", actor_user_id=None, payload={"connection_id": conn.id, "external_id": ext_id, "created": created})
        db.commit()

    product_ids = {it.product_id for it in order.items}
    product_refs = {pid: (get_ref(db, conn.id, "product", pid) or None) for pid in product_ids}
    product_ext = {pid: r.external_id for pid, r in product_refs.items() if r}

    if existing:
        _push_bonus_order(db, adapter, conn, cfg, order, cref.external_id, product_ext)
        return

    # 2) Pedido já existe no ERP? (ex.: timeout depois de criar)
    found = adapter.find_order_by_portal_number(order.order_number)
    if found is None:
        seller_ext = None
        seller_name = None
        if order.seller_id:
            seller = db.get(User, order.seller_id)
            seller_name = seller.name if seller else None
            sref = get_ref(db, conn.id, "seller", order.seller_id)
            seller_ext = sref.external_id if sref else None
        payload = build_order_payload(
            order=order,
            customer=customer,
            customer_external_id=cref.external_id,
            product_external_ids=product_ext,
            seller_external_id=seller_ext,
            seller_name=seller_name,
            settings=cfg,
        )
        found = adapter.create_order(payload)
        desired = cfg.get("order_initial_status_id")
        if desired and found.status_id not in (None, int(desired)):
            adapter.set_order_status(found.external_id, int(desired))
            found.status_id = int(desired)

    set_ref(db, conn.id, "order", order.id, found.external_id, found.external_number, {"status_id": found.status_id})
    mapped = map_status(found.status_id, cfg) or OrderStatus.SENT_TO_ERP
    order.status = mapped
    order.integration_status = IntegrationStatus.SUCCESS
    order.integration_error = None
    events.record(db, tenant_id=order.tenant_id, entity_type="order", entity_id=order.id, action="order.erp_sent", actor_user_id=None, payload={"connection_id": conn.id, "external_id": found.external_id, "external_number": found.external_number, "status_id": found.status_id})
    db.commit()
    if needs_bonus_order:
        _push_bonus_order(db, adapter, conn, cfg, order, cref.external_id, product_ext)


def _push_bonus_order(db: Session, adapter, conn: ErpConnection, cfg: dict, order: Order, customer_ext: str, product_ext: dict) -> None:
    """Pedido de bonificação separado (campanha 10+1). Idempotente como o pedido de venda:
    procura por numeroLoja "<número>-B" antes de criar."""
    if not (cfg.get("bonus_line_mode") == "separate_order" and has_bonus(order)):
        return
    if get_ref(db, conn.id, "order_bonus", order.id):
        return
    number = bonus_order_number(order.order_number)
    found = adapter.find_order_by_portal_number(number)
    if found is None:
        found = adapter.create_order(build_bonus_order_payload(order=order, customer_external_id=customer_ext, product_external_ids=product_ext, settings=cfg))
        desired = cfg.get("order_initial_status_id")
        if desired and found.status_id not in (None, int(desired)):
            adapter.set_order_status(found.external_id, int(desired))
            found.status_id = int(desired)
    set_ref(db, conn.id, "order_bonus", order.id, found.external_id, found.external_number, {"status_id": found.status_id})
    events.record(db, tenant_id=order.tenant_id, entity_type="order", entity_id=order.id, action="order.erp_bonus_sent", actor_user_id=None, payload={"connection_id": conn.id, "external_id": found.external_id, "external_number": found.external_number})


def run_job(db: Session, job: IntegrationJob) -> IntegrationJob:
    job.status = "running"
    job.attempts += 1
    db.commit()
    try:
        if job.job_type == "push_order":
            _push_order(db, job)
        else:
            raise ErpError(f"Tipo de job desconhecido: {job.job_type}", retryable=False)
        job.status = "success"
        job.last_error = None
        job.next_attempt_at = None
        db.commit()
    except ErpError as exc:
        db.rollback()
        job = db.get(IntegrationJob, job.id)
        job.last_error = str(exc)
        order = db.get(Order, job.entity_id)
        if exc.retryable and job.attempts < MAX_ATTEMPTS:
            job.status = "pending"
            job.next_attempt_at = utcnow() + timedelta(minutes=2 ** job.attempts)
        else:
            job.status = "error"
            job.next_attempt_at = None
        if order is not None:
            order.integration_status = IntegrationStatus.ERROR
            order.integration_error = str(exc)[:1000]
            events.record(db, tenant_id=order.tenant_id, entity_type="order", entity_id=order.id, action="order.erp_failed", actor_user_id=None, payload={"error": str(exc)[:500], "attempt": job.attempts, "retryable": exc.retryable, "will_retry": job.status == "pending"})
        db.commit()
    except Exception as exc:  # erro inesperado: nunca perde o pedido local
        db.rollback()
        job = db.get(IntegrationJob, job.id)
        job.status = "error"
        job.last_error = f"Erro inesperado: {exc!r}"[:1000]
        order = db.get(Order, job.entity_id)
        if order is not None:
            order.integration_status = IntegrationStatus.ERROR
            order.integration_error = job.last_error
        db.commit()
    return job


def process_pending(db: Session, limit: int = 50) -> list[IntegrationJob]:
    now = utcnow()
    jobs = list(db.scalars(select(IntegrationJob).where(IntegrationJob.status == "pending").order_by(IntegrationJob.created_at).limit(limit)))
    done = []
    for job in jobs:
        nxt = job.next_attempt_at
        if nxt is not None and nxt.tzinfo is None:
            from datetime import timezone
            nxt = nxt.replace(tzinfo=timezone.utc)
        if nxt is not None and nxt > now:
            continue
        done.append(run_job(db, job))
    return done


def process_order_now(db: Session, order_id: str) -> IntegrationJob | None:
    job = db.scalar(select(IntegrationJob).where(IntegrationJob.job_type == "push_order", IntegrationJob.entity_id == order_id).order_by(IntegrationJob.created_at.desc()))
    if job is None or job.status not in ("pending",):
        return job
    return run_job(db, job)


def retry_order(db: Session, order: Order, conn: ErpConnection | None, actor_id: str) -> IntegrationJob | None:
    job = enqueue_order_push(db, order, conn)
    if job is not None:
        job.attempts = 0
        job.last_error = None
    events.record(db, tenant_id=order.tenant_id, entity_type="order", entity_id=order.id, action="order.erp_retry_requested", actor_user_id=actor_id, payload={})
    db.commit()
    return job


def sync_order_statuses(db: Session, conn: ErpConnection, limit: int = 100) -> int:
    """Lê a situação atual dos pedidos no ERP e atualiza o status do portal."""
    if not integration_enabled(conn):
        return 0
    cfg = erp_settings.merged(conn.settings)
    adapter = adapter_for(db, conn)
    refs = list(db.scalars(select(ExternalRef).where(ExternalRef.connection_id == conn.id, ExternalRef.entity_type == "order").limit(limit)))
    changed = 0
    for ref in refs:
        order = db.get(Order, ref.entity_id)
        if order is None or order.status in FINAL_STATUSES:
            continue
        try:
            info = adapter.get_order(ref.external_id)
        except ErpError:
            continue
        new_status = map_status(info.status_id, cfg)
        if info.external_number and ref.external_number != info.external_number:
            ref.external_number = info.external_number
        if new_status and new_status != order.status:
            events.record(db, tenant_id=order.tenant_id, entity_type="order", entity_id=order.id, action="order.status_changed", actor_user_id=None, payload={"from": order.status, "to": new_status, "erp_status_id": info.status_id})
            order.status = new_status
            changed += 1
        ref.data = {**(ref.data or {}), "status_id": info.status_id}
    db.commit()
    return changed
