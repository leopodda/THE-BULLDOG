from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain import events
from app.domain.pricing import PAYMENT_METHOD_LABELS, QuoteError, commercial_settings, quote_for_customer, region_key_for
from app.erp.jobs import enqueue_order_push
from app.erp.registry import active_connection
from app.models import Customer, Order, OrderCounter, OrderItem, Role, Tenant, User, ValidationStatus


class OrderError(ValueError):
    pass


def _next_order_number(db: Session, tenant_id: str) -> str:
    counter = db.get(OrderCounter, tenant_id)
    if counter is None:
        counter = OrderCounter(tenant_id=tenant_id, last_number=0)
        db.add(counter)
        db.flush()
    # incremento atômico no banco
    db.execute(update(OrderCounter).where(OrderCounter.tenant_id == tenant_id).values(last_number=OrderCounter.last_number + 1))
    db.refresh(counter)
    return f"BD-{counter.last_number:06d}"


def find_by_checkout(db: Session, tenant_id: str, key: str) -> list[Order]:
    return list(db.scalars(select(Order).where(Order.tenant_id == tenant_id, Order.checkout_key == key).order_by(Order.order_number)))


def create_order(
    db: Session,
    *,
    tenant: Tenant,
    actor: User,
    customer: Customer,
    requested: dict[str, int],
    bonus_product_id: str | None,
    payment_method: str | None,
    notes: str | None,
    idempotency_key: str,
) -> tuple[list[Order], bool]:
    """Cria o(s) pedido(s) local(is) de um fechamento de carrinho.

    Um pedido por linha de produto (energético / tabacaria). Retorna (pedidos, criados_agora).
    A mesma chave de idempotência devolve os pedidos já existentes sem duplicar.
    """
    if not idempotency_key or len(idempotency_key) > 80:
        raise OrderError("Chave de idempotência ausente ou inválida.")
    existing = find_by_checkout(db, tenant.id, idempotency_key)
    if existing:
        if any(o.customer_id != customer.id for o in existing):
            raise OrderError("Chave de idempotência já usada em outro pedido.")
        return existing, False

    if actor.role == Role.CUSTOMER and actor.customer_id != customer.id:
        raise OrderError("Cliente só pode criar pedido para o próprio cadastro.")
    if customer.tenant_id != tenant.id:
        raise OrderError("Cliente não pertence a esta operação.")
    if customer.validation_status == ValidationStatus.REJECTED:
        raise OrderError("Cadastro do cliente foi rejeitado na conferência. Fale com o back-office.")

    settings = commercial_settings(tenant)
    if payment_method and payment_method not in settings.get("payment_methods", []):
        raise OrderError("Meio de pagamento não aceito.")

    try:
        quote, campaign = quote_for_customer(db, tenant, customer, requested, bonus_product_id)
    except QuoteError as exc:
        raise OrderError(str(exc)) from exc

    source = {Role.CUSTOMER: "customer", Role.SELLER: "seller"}.get(actor.role, "admin")
    seller_id = actor.id if actor.role == Role.SELLER else customer.assigned_seller_id
    clean_notes = (notes or "").strip()[:1000] or None

    orders: list[Order] = []
    try:
        with db.begin_nested():
            for group in quote.groups:
                glines = quote.lines_for(group.line)
                has_bonus = group.bonus_qty > 0
                order = Order(
                    tenant_id=tenant.id,
                    order_number=_next_order_number(db, tenant.id),
                    idempotency_key=f"{idempotency_key}:{group.line}",
                    checkout_key=idempotency_key,
                    product_line=group.line,
                    customer_id=customer.id,
                    seller_id=seller_id,
                    created_by_user_id=actor.id,
                    source=source,
                    paid_cases=group.paid_qty,
                    bonus_cases=group.bonus_qty,
                    total_units=group.total_units,
                    total_amount=group.subtotal,
                    campaign_id=campaign.id if (campaign and has_bonus) else None,
                    region_key=region_key_for(campaign, customer) if (campaign and has_bonus) else None,
                    customer_order_index=quote.customer_order_index,
                    payment_method_preference=payment_method,
                    suggested_payment_terms=quote.suggested_payment_terms,
                    freight_status=group.freight_status,
                    delivery_estimate=group.delivery_estimate,
                    notes=clean_notes,
                    customer_validation_at_order=customer.validation_status,
                )
                for pos, line in enumerate(glines):
                    order.items.append(OrderItem(
                        position=pos,
                        product_id=line.product_id,
                        sku=line.sku,
                        product_name=line.name,
                        units_per_case=line.units_per_case,
                        cases_qty=line.cases,
                        units_qty=line.units,
                        bonus_cases=line.bonus_cases,
                        bonus_units=line.bonus_units,
                        unit_price_commercial=line.unit_price,
                        case_price_commercial=line.case_price,
                        line_total=line.line_total,
                    ))
                db.add(order)
                orders.append(order)
            db.flush()
    except IntegrityError:
        # duas requisições simultâneas com a mesma chave
        existing = find_by_checkout(db, tenant.id, idempotency_key)
        if existing:
            return existing, False
        raise

    conn = active_connection(db, tenant.id)
    numbers = [o.order_number for o in orders]
    for order in orders:
        events.record(db, tenant_id=tenant.id, entity_type="order", entity_id=order.id, action="order.created", actor_user_id=actor.id, payload={
            "order_number": order.order_number,
            "product_line": order.product_line,
            "checkout_orders": numbers,
            "customer_id": customer.id,
            "source": source,
            "paid_qty": order.paid_cases,
            "bonus_cases": order.bonus_cases,
            "total_amount": str(order.total_amount),
            "payment_method": PAYMENT_METHOD_LABELS.get(payment_method or "", payment_method),
        })
        enqueue_order_push(db, order, conn)
    db.commit()
    return orders, True
