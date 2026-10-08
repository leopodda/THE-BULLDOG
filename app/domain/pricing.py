"""Camada COMERCIAL de preço, bônus, pagamento sugerido e frete.

Esta camada não conhece o ERP. O valor que vai para o item do pedido no Bling
(valor técnico) é decidido no adaptador ERP (app/erp/mapping.py), por configuração,
sem alterar a regra comercial nem a interface.

Linhas de produto:
- energetico: vendido em CAIXA (24 latas). Campanha 10+1. Frete grátis por nº de caixas.
- tabacaria (Smoking Line): vendida em DISPLAY. Preço por display (catálogo do
  distribuidor). Sem campanha 10+1. Frete a combinar.
Um carrinho com as duas linhas vira DOIS pedidos (um por linha), porque cada linha
tem tratamento fiscal próprio na nota.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models import Campaign, Customer, Order, OrderStatus, PriceRule, Product, ProductLine, Tenant

CENT = Decimal("0.01")

DEFAULT_COMMERCIAL_SETTINGS: dict = {
    "home_uf": "SP",
    "free_freight_min_cases_home": 100,
    "free_freight_min_cases_other": 200,
    "delivery_estimate_home": "3 a 5 dias úteis",
    "delivery_estimate_other": "7 a 15 dias",
    "tabacaria_freight_message": "Frete da tabacaria a combinar com o back-office.",
    # Faixas por número do pedido do cliente (1 = primeiro pedido). to_order None = em diante.
    "payment_terms": [
        {"from_order": 1, "to_order": 1, "label": "50% na compra + 50% em 28 dias"},
        {"from_order": 4, "to_order": None, "label": "30/60 dias"},
    ],
    "payment_terms_fallback": "A definir pelo back-office",
    "payment_methods": ["pix", "boleto", "transferencia"],
    "max_cases_per_item": 5000,
    # Linhas vendidas no portal. Tirar "tabacaria" esconde a Smoking Line sem apagar nada.
    "enabled_lines": ["energetico", "tabacaria"],
}

PAYMENT_METHOD_LABELS = {"pix": "Pix", "boleto": "Boleto", "transferencia": "Transferência"}
SALE_UNIT_LABELS = {"caixa": ("caixa", "caixas", "cx"), "display": ("display", "displays", "disp."), "unidade": ("unidade", "unidades", "un"), "item": ("item", "itens", "it.")}


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def commercial_settings(tenant: Tenant) -> dict:
    merged = dict(DEFAULT_COMMERCIAL_SETTINGS)
    merged.update(tenant.settings or {})
    return merged


def unit_word(sale_unit: str, qty: int) -> str:
    one, many, _ = SALE_UNIT_LABELS.get(sale_unit, (sale_unit, sale_unit + "s", sale_unit))
    return one if qty == 1 else many


class QuoteError(ValueError):
    pass


@dataclass
class CatalogItem:
    product_id: str
    sku: str
    name: str
    units_per_case: int
    sort_order: int = 0
    line: str = ProductLine.ENERGY
    sale_unit: str = "caixa"


@dataclass
class CampaignRule:
    campaign_id: str
    name: str
    buy_cases: int
    bonus_cases: int
    stackable: bool = True
    product_line: str | None = ProductLine.ENERGY


@dataclass
class QuoteLine:
    product_id: str
    sku: str
    name: str
    units_per_case: int
    cases: int
    units: int
    bonus_cases: int
    bonus_units: int
    unit_price: Decimal
    case_price: Decimal
    line_total: Decimal
    line: str = ProductLine.ENERGY
    sale_unit: str = "caixa"

    def as_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "sku": self.sku,
            "name": self.name,
            "line": self.line,
            "sale_unit": self.sale_unit,
            "units_per_case": self.units_per_case,
            "cases": self.cases,
            "units": self.units,
            "bonus_cases": self.bonus_cases,
            "bonus_units": self.bonus_units,
            "unit_price": str(self.unit_price),
            "case_price": str(self.case_price),
            "line_total": str(self.line_total),
        }


@dataclass
class QuoteGroup:
    """Parte do carrinho que vira UM pedido (uma linha de produto)."""
    line: str
    label: str
    sale_unit: str
    paid_qty: int
    bonus_qty: int
    total_units: int
    subtotal: Decimal
    freight_status: str
    freight_message: str
    delivery_estimate: str

    def as_dict(self) -> dict:
        return {
            "line": self.line,
            "label": self.label,
            "sale_unit": self.sale_unit,
            "paid_qty": self.paid_qty,
            "bonus_qty": self.bonus_qty,
            "total_units": self.total_units,
            "subtotal": str(self.subtotal),
            "freight_status": self.freight_status,
            "freight_message": self.freight_message,
            "delivery_estimate": self.delivery_estimate,
        }


@dataclass
class Quote:
    lines: list[QuoteLine]
    groups: list[QuoteGroup]
    paid_cases: int
    bonus_cases: int
    total_units: int
    total_amount: Decimal
    campaign: CampaignRule | None
    campaign_applied: bool
    campaign_message: str | None
    customer_order_index: int
    suggested_payment_terms: str
    freight_status: str
    freight_message: str
    delivery_estimate: str
    warnings: list[str] = field(default_factory=list)

    def lines_for(self, line: str) -> list[QuoteLine]:
        return [l for l in self.lines if l.line == line]

    def as_dict(self) -> dict:
        return {
            "lines": [l.as_dict() for l in self.lines],
            "groups": [g.as_dict() for g in self.groups],
            "paid_cases": self.paid_cases,
            "bonus_cases": self.bonus_cases,
            "total_units": self.total_units,
            "total_amount": str(self.total_amount),
            "campaign": None if not self.campaign else {"id": self.campaign.campaign_id, "name": self.campaign.name, "buy_cases": self.campaign.buy_cases, "bonus_cases": self.campaign.bonus_cases, "product_line": self.campaign.product_line},
            "campaign_applied": self.campaign_applied,
            "campaign_message": self.campaign_message,
            "customer_order_index": self.customer_order_index,
            "suggested_payment_terms": self.suggested_payment_terms,
            "freight_status": self.freight_status,
            "freight_message": self.freight_message,
            "delivery_estimate": self.delivery_estimate,
            "split_orders": len(self.groups) > 1,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Funções puras (testáveis sem banco)
# ---------------------------------------------------------------------------

def cases_to_units(cases: int, units_per_case: int) -> int:
    if cases < 0:
        raise QuoteError("Quantidade não pode ser negativa.")
    if units_per_case <= 0:
        raise QuoteError("Produto sem quantidade por embalagem configurada.")
    return cases * units_per_case


def bonus_for(paid_cases: int, rule: CampaignRule | None) -> int:
    """Compre `buy_cases`, leve `bonus_cases`. Cumulativo se `stackable`.
    A caixa bônus NUNCA entra no valor cobrado."""
    if not rule or rule.buy_cases <= 0 or rule.bonus_cases <= 0 or paid_cases < rule.buy_cases:
        return 0
    if rule.stackable:
        return (paid_cases // rule.buy_cases) * rule.bonus_cases
    return rule.bonus_cases


def payment_terms_for(order_index: int, settings: dict) -> str:
    for band in settings.get("payment_terms", []):
        lo = band.get("from_order") or 1
        hi = band.get("to_order")
        if order_index >= lo and (hi is None or order_index <= hi):
            return band["label"]
    return settings.get("payment_terms_fallback", "A definir pelo back-office")


def _delivery(uf: str, settings: dict) -> str:
    return settings["delivery_estimate_home"] if uf.upper() == (settings.get("home_uf") or "SP").upper() else settings["delivery_estimate_other"]


def freight_for(paid_cases: int, uf: str, settings: dict) -> tuple[str, str, str]:
    """Frete do ENERGÉTICO (regra por nº de caixas)."""
    home = (settings.get("home_uf") or "SP").upper()
    if uf.upper() == home:
        minimum = int(settings["free_freight_min_cases_home"])
        where = home
    else:
        minimum = int(settings["free_freight_min_cases_other"])
        where = "fora de " + home
    estimate = _delivery(uf, settings)
    if paid_cases >= minimum:
        return "gratis", f"Frete grátis ({where}: a partir de {minimum} caixas).", estimate
    missing = minimum - paid_cases
    return "a_combinar", f"Frete a combinar com o back-office. Faltam {missing} caixas para frete grátis ({where}).", estimate


def compute_quote(
    *,
    catalog: list[CatalogItem],
    requested: dict[str, int],
    unit_prices: dict[str, Decimal],
    campaign: CampaignRule | None,
    campaign_eligible: bool,
    bonus_product_id: str | None,
    customer_order_index: int,
    customer_uf: str,
    settings: dict,
) -> Quote:
    by_id = {c.product_id: c for c in catalog}
    if any(pid not in by_id for pid in requested):
        raise QuoteError("Produto não disponível no portal.")
    max_qty = int(settings.get("max_cases_per_item", 5000))
    for qty in requested.values():
        if not isinstance(qty, int) or isinstance(qty, bool):
            raise QuoteError("Quantidade deve ser um número inteiro.")
        if qty < 0:
            raise QuoteError("Quantidade não pode ser negativa.")
        if qty > max_qty:
            raise QuoteError(f"Quantidade acima do limite de {max_qty} por produto.")
    paid_total = sum(requested.values())
    if paid_total <= 0:
        raise QuoteError("Escolha ao menos um produto.")

    # ---- campanha: só conta a linha da campanha
    def in_campaign(item: CatalogItem) -> bool:
        return campaign is not None and (campaign.product_line is None or item.line == campaign.product_line)

    campaign_paid = sum(q for pid, q in requested.items() if in_campaign(by_id[pid]))
    bonus_total = bonus_for(campaign_paid, campaign) if (campaign and campaign_eligible) else 0
    campaign_message: str | None = None
    if campaign and campaign_paid > 0:
        if not campaign_eligible:
            campaign_message = f"Campanha {campaign.name} indisponível para este pedido."
        elif bonus_total:
            campaign_message = f"{campaign.name}: {bonus_total} caixa(s) de bônus."
        else:
            campaign_message = f"{campaign.name}: faltam {campaign.buy_cases - campaign_paid} caixa(s) para ganhar bônus."

    bonus_target: str | None = None
    if bonus_total:
        if bonus_product_id:
            if bonus_product_id not in by_id or not in_campaign(by_id[bonus_product_id]):
                raise QuoteError("Sabor escolhido para o bônus não participa da campanha.")
            bonus_target = bonus_product_id
        else:
            ordered = sorted((c for c in catalog if requested.get(c.product_id, 0) > 0 and in_campaign(c)), key=lambda c: (-requested[c.product_id], c.sort_order))
            bonus_target = ordered[0].product_id

    lines: list[QuoteLine] = []
    for item in sorted(catalog, key=lambda c: c.sort_order):
        qty = requested.get(item.product_id, 0)
        bonus = bonus_total if item.product_id == bonus_target else 0
        if qty == 0 and bonus == 0:
            continue
        if item.product_id not in unit_prices:
            raise QuoteError(f"Produto {item.name} sem preço configurado.")
        unit_price = Decimal(unit_prices[item.product_id])
        case_price = money(unit_price * item.units_per_case)
        lines.append(QuoteLine(
            item.product_id, item.sku, item.name, item.units_per_case, qty,
            cases_to_units(qty, item.units_per_case), bonus, cases_to_units(bonus, item.units_per_case),
            unit_price, case_price, money(case_price * qty), item.line, item.sale_unit,
        ))

    groups: list[QuoteGroup] = []
    for line in ProductLine.ALL:
        gl = [l for l in lines if l.line == line]
        if not gl:
            continue
        paid = sum(l.cases for l in gl)
        if line == ProductLine.ENERGY:
            fs, fm, est = freight_for(paid, customer_uf, settings)
        else:
            fs, fm, est = "a_combinar", settings.get("tabacaria_freight_message") or "Frete a combinar.", _delivery(customer_uf, settings)
        groups.append(QuoteGroup(
            line=line, label=ProductLine.LABELS[line], sale_unit=gl[0].sale_unit if len({l.sale_unit for l in gl}) == 1 else "item", paid_qty=paid,
            bonus_qty=sum(l.bonus_cases for l in gl), total_units=sum(l.units + l.bonus_units for l in gl),
            subtotal=money(sum((l.line_total for l in gl), Decimal("0"))), freight_status=fs, freight_message=fm, delivery_estimate=est,
        ))

    main = next((g for g in groups if g.line == ProductLine.ENERGY), groups[0])
    return Quote(
        lines=lines,
        groups=groups,
        paid_cases=paid_total,
        bonus_cases=bonus_total,
        total_units=sum(g.total_units for g in groups),
        total_amount=money(sum((g.subtotal for g in groups), Decimal("0"))),
        campaign=campaign,
        campaign_applied=bonus_total > 0,
        campaign_message=campaign_message,
        customer_order_index=customer_order_index,
        suggested_payment_terms=payment_terms_for(customer_order_index, settings),
        freight_status=main.freight_status,
        freight_message=main.freight_message,
        delivery_estimate=main.delivery_estimate,
    )


# ---------------------------------------------------------------------------
# Resolução a partir do banco
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _in_window(valid_from, valid_to, now) -> bool:
    vf, vt = _aware(valid_from), _aware(valid_to)
    return (vf is None or vf <= now) and (vt is None or vt >= now)


def active_catalog(db: Session, tenant: Tenant | str) -> list[Product]:
    """Produtos ativos das linhas habilitadas (tenant.settings.enabled_lines)."""
    if isinstance(tenant, str):
        tenant_obj = db.get(Tenant, tenant)
    else:
        tenant_obj = tenant
    enabled = commercial_settings(tenant_obj).get("enabled_lines") or list(ProductLine.ALL)
    stmt = select(Product).where(Product.tenant_id == tenant_obj.id, Product.active.is_(True), Product.line.in_(enabled))
    return list(db.scalars(stmt.order_by(Product.sort_order)))


def resolve_unit_price(db: Session, tenant_id: str, product: Product, customer: Customer | None) -> Decimal | None:
    now = _now()
    rules = [r for r in db.scalars(select(PriceRule).where(PriceRule.tenant_id == tenant_id, PriceRule.active.is_(True))) if _in_window(r.valid_from, r.valid_to, now)]
    best: tuple[int, PriceRule] | None = None
    for r in rules:
        if r.product_id and r.product_id != product.id:
            continue
        if r.product_line and r.product_line != product.line:
            continue
        if not r.product_id and not r.product_line and product.line != ProductLine.ENERGY:
            continue  # regra totalmente genérica (legado) só vale para o energético
        if r.customer_id and (not customer or r.customer_id != customer.id):
            continue
        if r.channel and (not customer or (customer.channel or "") != r.channel):
            continue
        score = (100 if r.customer_id else 0) + (10 if r.channel else 0) + (2 if r.product_id else 1 if r.product_line else 0)
        if best is None or score > best[0]:
            best = (score, r)
    return Decimal(best[1].unit_price) if best else None


def suggested_retail_price_for(db: Session, tenant_id: str, product: Product) -> Decimal | None:
    """Preço de referência ao consumidor/online por unidade de venda do portal (lata ou display)."""
    rules = list(db.scalars(select(PriceRule).where(PriceRule.tenant_id == tenant_id, PriceRule.active.is_(True), PriceRule.customer_id.is_(None), PriceRule.channel.is_(None))))
    for r in rules:
        if r.product_id == product.id and r.suggested_retail_price is not None:
            return Decimal(r.suggested_retail_price)
    for r in rules:
        if r.product_id is None and r.product_line in (product.line, None) and r.suggested_retail_price is not None and (r.product_line or product.line == ProductLine.ENERGY):
            return Decimal(r.suggested_retail_price)
    return None


def suggested_retail_price(db: Session, tenant_id: str) -> Decimal | None:
    """Preço sugerido ao consumidor do energético (por lata)."""
    for r in db.scalars(select(PriceRule).where(PriceRule.tenant_id == tenant_id, PriceRule.active.is_(True), PriceRule.customer_id.is_(None), PriceRule.channel.is_(None), PriceRule.product_id.is_(None))):
        if r.suggested_retail_price is not None and r.product_line in (None, ProductLine.ENERGY):
            return Decimal(r.suggested_retail_price)
    return None


def active_campaign(db: Session, tenant_id: str) -> Campaign | None:
    now = _now()
    for c in db.scalars(select(Campaign).where(Campaign.tenant_id == tenant_id, Campaign.active.is_(True)).order_by(Campaign.created_at)):
        if _in_window(c.valid_from, c.valid_to, now):
            return c
    return None


def region_key_for(campaign: Campaign | None, customer: Customer) -> str | None:
    if not campaign or campaign.region_scope == "none":
        return None
    if campaign.region_scope == "uf":
        return customer.uf.upper()
    return f"{customer.uf.upper()}/{customer.municipio.strip().upper()}"


def campaign_is_eligible(db: Session, campaign: Campaign | None, customer: Customer, exclude_order_id: str | None = None) -> bool:
    if not campaign:
        return False
    if not campaign.max_orders_per_region:
        return True
    key = region_key_for(campaign, customer)
    stmt = select(func.count(Order.id)).where(
        Order.tenant_id == campaign.tenant_id,
        Order.campaign_id == campaign.id,
        Order.bonus_cases > 0,
        Order.status != OrderStatus.CANCELLED,
    )
    if key is not None:
        stmt = stmt.where(Order.region_key == key)
    if exclude_order_id:
        stmt = stmt.where(Order.id != exclude_order_id)
    used = db.scalar(stmt) or 0
    return used < campaign.max_orders_per_region


def customer_next_order_index(db: Session, customer: Customer) -> int:
    """Nº da compra do cliente. Um carrinho dividido em 2 pedidos conta como UMA compra."""
    count = db.scalar(select(func.count(distinct(Order.checkout_key))).where(Order.customer_id == customer.id, Order.status != OrderStatus.CANCELLED)) or 0
    return count + 1


def catalog_items(products: list[Product]) -> list[CatalogItem]:
    return [CatalogItem(p.id, p.sku, p.commercial_name, p.units_per_case, p.sort_order, p.line, p.sale_unit) for p in products]


def quote_for_customer(db: Session, tenant: Tenant, customer: Customer, requested: dict[str, int], bonus_product_id: str | None) -> tuple[Quote, Campaign | None]:
    products = active_catalog(db, tenant)
    prices: dict[str, Decimal] = {}
    for p in products:
        price = resolve_unit_price(db, tenant.id, p, customer)
        if price is not None:
            prices[p.id] = price
    campaign = active_campaign(db, tenant.id)
    rule = CampaignRule(campaign.id, campaign.name, campaign.buy_cases, campaign.bonus_cases, campaign.stackable, campaign.product_line) if campaign else None
    quote = compute_quote(
        catalog=catalog_items(products),
        requested=dict(requested),
        unit_prices=prices,
        campaign=rule,
        campaign_eligible=campaign_is_eligible(db, campaign, customer),
        bonus_product_id=bonus_product_id,
        customer_order_index=customer_next_order_index(db, customer),
        customer_uf=customer.uf,
        settings=commercial_settings(tenant),
    )
    return quote, campaign
