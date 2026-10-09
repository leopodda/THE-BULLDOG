"""Tradução do domínio do portal para o formato do Bling API v3.

Funções puras: recebem objetos do portal + configurações da conexão, devolvem o JSON.
"""
from __future__ import annotations

from decimal import Decimal

from app.domain.pricing import PAYMENT_METHOD_LABELS, money
from app.erp.base import ErpNotConfigured
from app.models import Customer, Order, ValidationStatus


def build_contact_payload(customer: Customer, settings: dict) -> dict:
    payload: dict = {
        "nome": customer.razao_social,
        "fantasia": customer.nome_fantasia or "",
        "tipo": "J",
        "situacao": "A",
        "numeroDocumento": customer.cnpj,
        "indicadorIe": customer.ie_indicator,
        "ie": customer.ie or "",
        "telefone": customer.phone or "",
        "celular": customer.whatsapp or "",
        "email": customer.email or "",
        "emailNotaFiscal": customer.email_nfe or "",
        "endereco": {
            "geral": {
                "endereco": customer.logradouro,
                "numero": customer.numero,
                "complemento": customer.complemento or "",
                "bairro": customer.bairro,
                "cep": customer.cep,
                "municipio": customer.municipio,
                "uf": customer.uf,
            }
        },
    }
    if customer.contact_name:
        payload["pessoasContato"] = [{"descricao": customer.contact_name}]
    type_id = settings.get("contact_type_customer_id")
    if type_id:
        payload["tiposContato"] = [{"id": int(type_id)}]
    return payload


def technical_unit_value(sku: str, commercial_unit_price: Decimal, settings: dict) -> Decimal:
    """Valor por lata enviado ao Bling. Separado do preço comercial por decisão de projeto:
    o valor-base que a conta da DFJ deve receber (antes/depois de ST) ainda não está definido."""
    if settings.get("technical_price_mode") == "override":
        overrides = settings.get("technical_unit_price_overrides") or {}
        if sku not in overrides:
            raise ErpNotConfigured(f"Valor técnico não configurado para o SKU {sku} (modo override).")
        return Decimal(str(overrides[sku]))
    return Decimal(commercial_unit_price)


def _fmt_money(value: Decimal) -> str:
    return f"R$ {money(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_order_payload(
    *,
    order: Order,
    customer: Customer,
    customer_external_id: str,
    product_external_ids: dict[str, str],
    seller_external_id: str | None,
    seller_name: str | None,
    settings: dict,
) -> dict:
    items: list[dict] = []
    bonus_notes: list[str] = []
    bonus_mode = settings.get("bonus_line_mode", "separate_item")
    bonus_value = Decimal(str(settings.get("bonus_technical_unit_value", "0")))

    for it in order.items:
        ext_id = product_external_ids.get(it.product_id)
        if not ext_id:
            raise ErpNotConfigured(f"Produto {it.sku} sem ID do Bling configurado para esta conexão.")
        if it.units_qty > 0:
            items.append({
                "produto": {"id": int(ext_id)},
                "codigo": it.sku,
                "descricao": it.product_name,
                "unidade": "UN",
                "quantidade": it.units_qty,
                "valor": float(technical_unit_value(it.sku, it.unit_price_commercial, settings)),
            })
        if it.bonus_units > 0:
            if bonus_mode == "separate_item":
                items.append({
                    "produto": {"id": int(ext_id)},
                    "codigo": it.sku,
                    "descricao": f"{it.product_name} - BONIFICAÇÃO",
                    "unidade": "UN",
                    "quantidade": it.bonus_units,
                    "valor": float(bonus_value),
                })
            bonus_notes.append(f"{it.bonus_cases} cx ({it.bonus_units} latas) {it.product_name}")

    if not items:
        raise ErpNotConfigured("Pedido sem itens para enviar.")
    if bonus_mode == "separate_order" and bonus_notes:
        bonus_notes = [n + f" — pedido de bonificação {bonus_order_number(order.order_number)}" for n in bonus_notes]

    obs = [f"Pedido do portal {order.order_number}."]
    if order.notes:
        obs.append(order.notes)

    line_label = "TABACARIA (Smoking Line)" if order.product_line == "tabacaria" else "ENERGÉTICO"
    unit_label = "itens (displays/unidades)" if order.product_line == "tabacaria" else "cx"
    internal = [
        f"Linha: {line_label}.",
        f"Origem: portal ({'vendedor' if order.source == 'seller' else 'cliente/PDV' if order.source == 'customer' else order.source}).",
        f"Pedido portal: {order.order_number} | {order.paid_cases} {unit_label}" + (f" + {order.bonus_cases} cx bônus" if order.bonus_cases else "") + f" | {order.total_units} UN.",
        f"Total comercial: {_fmt_money(order.total_amount)} (preço de tabela do portal, sem considerar impostos destacados na NF-e).",
    ]
    if seller_name:
        internal.append(f"Vendedor: {seller_name}.")
    if bonus_notes:
        how = {"separate_item": " (lançado como item separado)", "separate_order": " (em pedido de bonificação separado)"}.get(bonus_mode, " — LANÇAR MANUALMENTE")
        internal.append("BÔNUS CAMPANHA: " + "; ".join(bonus_notes) + how)
    if order.suggested_payment_terms:
        pref = PAYMENT_METHOD_LABELS.get(order.payment_method_preference or "", order.payment_method_preference or "não informado")
        internal.append(f"Pagamento sugerido: {order.suggested_payment_terms} | meio preferido: {pref}. CONFIRMAR antes de faturar.")
    if order.freight_status:
        internal.append(f"Frete: {'grátis pela regra comercial' if order.freight_status == 'gratis' else 'a combinar'}. Prazo comercial: {order.delivery_estimate or '-'}.")
    if customer.validation_status != ValidationStatus.CONFIRMED:
        internal.append("ATENÇÃO: CLIENTE PENDENTE DE CONFERÊNCIA (CNPJ/IE/endereço) — conferir antes de faturar.")

    payload: dict = {
        "numeroLoja": order.order_number,
        "data": order.created_at.date().isoformat(),
        "contato": {"id": int(customer_external_id)},
        "itens": items,
        "observacoes": " ".join(obs)[:2000],
        "observacoesInternas": "\n".join(internal)[:2000],
    }
    status_id = settings.get("order_initial_status_id")
    if status_id:
        payload["situacao"] = {"id": int(status_id)}
    if settings.get("store_id"):
        payload["loja"] = {"id": int(settings["store_id"])}
    if seller_external_id:
        payload["vendedor"] = {"id": int(seller_external_id)}
    # Cada linha usa SOMENTE a sua natureza. A tabacaria nunca herda a do energético (com ST).
    nature_key = "operation_nature_id_tabacaria" if order.product_line == "tabacaria" else "operation_nature_id"
    nature = settings.get(nature_key)
    if nature:
        payload["naturezaOperacao"] = {"id": int(nature)}
    elif settings.get("require_operation_nature"):
        raise ErpNotConfigured(f"Natureza de operação da linha {line_label} não configurada ({nature_key}). Pedido mantido na fila.")
    if settings.get("freight_payer_code") is not None:
        payload["transporte"] = {"fretePorConta": int(settings["freight_payer_code"])}
    return payload


def bonus_order_number(order_number: str) -> str:
    return f"{order_number}-B"


def has_bonus(order: Order) -> bool:
    return any(it.bonus_units > 0 for it in order.items)


def build_bonus_order_payload(
    *,
    order: Order,
    customer_external_id: str,
    product_external_ids: dict[str, str],
    settings: dict,
) -> dict:
    """Pedido de BONIFICAÇÃO (campanha 10+1) separado do pedido de venda.
    O Bling usa uma natureza por pedido, e a bonificação tem natureza/CFOP próprios (x910).
    Não gera cobrança: o cliente paga somente o pedido de venda."""
    nature = settings.get("operation_nature_id_bonus")
    if not nature:
        raise ErpNotConfigured("Natureza de operação da bonificação não configurada (operation_nature_id_bonus).")
    fixed = Decimal(str(settings.get("bonus_technical_unit_value", "0")))
    items = []
    for it in order.items:
        if it.bonus_units <= 0:
            continue
        ext_id = product_external_ids.get(it.product_id)
        if not ext_id:
            raise ErpNotConfigured(f"Produto {it.sku} sem ID do Bling configurado para esta conexão.")
        value = fixed if fixed > 0 else technical_unit_value(it.sku, it.unit_price_commercial, settings)
        items.append({
            "produto": {"id": int(ext_id)},
            "codigo": it.sku,
            "descricao": f"{it.product_name} - BONIFICAÇÃO",
            "unidade": "UN",
            "quantidade": it.bonus_units,
            "valor": float(value),
        })
    if not items:
        raise ErpNotConfigured("Pedido sem bônus para enviar.")
    number = bonus_order_number(order.order_number)
    payload: dict = {
        "numeroLoja": number,
        "data": order.created_at.date().isoformat(),
        "contato": {"id": int(customer_external_id)},
        "itens": items,
        "naturezaOperacao": {"id": int(nature)},
        "observacoes": f"Bonificação da campanha 10+1 referente ao pedido {order.order_number}. Sem cobrança.",
        "observacoesInternas": (
            f"BONIFICAÇÃO — campanha 10+1, vinculada ao pedido de venda {order.order_number}.\n"
            f"{order.bonus_cases} cx ({sum(i.bonus_units for i in order.items)} latas). NÃO gerar contas a receber."
        ),
    }
    status_id = settings.get("order_initial_status_id")
    if status_id:
        payload["situacao"] = {"id": int(status_id)}
    if settings.get("store_id"):
        payload["loja"] = {"id": int(settings["store_id"])}
    return payload


def map_status(status_id: int | None, settings: dict) -> str | None:
    if status_id is None:
        return None
    return (settings.get("status_map") or {}).get(str(status_id))
