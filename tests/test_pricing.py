from decimal import Decimal

import pytest

from app.domain.pricing import (
    DEFAULT_COMMERCIAL_SETTINGS,
    CampaignRule,
    CatalogItem,
    QuoteError,
    bonus_for,
    cases_to_units,
    compute_quote,
    freight_for,
    payment_terms_for,
)

CAT = [CatalogItem("trad", "DRINK-TRAD-269", "Tradicional", 24, 0), CatalogItem("zero", "DRINK-ZERO-269", "Zero Açúcar", 24, 1)]
PRICES = {"trad": Decimal("5.90"), "zero": Decimal("5.90")}
RULE = CampaignRule("c1", "Lançamento 10+1", 10, 1, True)


def q(requested, *, campaign=RULE, eligible=True, bonus=None, index=1, uf="SP"):
    return compute_quote(catalog=CAT, requested=requested, unit_prices=PRICES, campaign=campaign, campaign_eligible=eligible, bonus_product_id=bonus, customer_order_index=index, customer_uf=uf, settings=dict(DEFAULT_COMMERCIAL_SETTINGS))


def test_caixa_vira_24_latas():
    assert cases_to_units(1, 24) == 24
    assert cases_to_units(7, 24) == 168
    quote = q({"trad": 3, "zero": 2})
    by = {l.product_id: l for l in quote.lines}
    assert by["trad"].units == 72 and by["zero"].units == 48
    assert quote.total_units == 120


def test_preco_comercial_590_lata_14160_caixa():
    quote = q({"trad": 1})
    line = quote.lines[0]
    assert line.unit_price == Decimal("5.90")
    assert line.case_price == Decimal("141.60")
    assert quote.total_amount == Decimal("141.60")
    assert q({"trad": 2, "zero": 3}).total_amount == Decimal("708.00")


def test_bonus_10_mais_1_nao_cobra_caixa_bonus():
    quote = q({"trad": 10})
    assert quote.bonus_cases == 1
    assert quote.paid_cases == 10
    assert quote.total_amount == Decimal("1416.00")  # 10 x 141,60 — bônus fora do valor
    assert quote.total_units == 11 * 24
    line = quote.lines[0]
    assert line.bonus_cases == 1 and line.bonus_units == 24 and line.line_total == Decimal("1416.00")


def test_bonus_abaixo_de_10_nao_aplica():
    quote = q({"trad": 9})
    assert quote.bonus_cases == 0
    assert "faltam 1" in quote.campaign_message


def test_bonus_cumulativo_e_nao_cumulativo():
    assert bonus_for(25, RULE) == 2
    assert bonus_for(25, CampaignRule("c", "x", 10, 1, stackable=False)) == 1


def test_bonus_misto_vai_para_sabor_com_mais_caixas_ou_escolhido():
    quote = q({"trad": 4, "zero": 6})
    assert {l.product_id: l.bonus_cases for l in quote.lines} == {"trad": 0, "zero": 1}
    quote = q({"trad": 4, "zero": 6}, bonus="trad")
    assert {l.product_id: l.bonus_cases for l in quote.lines} == {"trad": 1, "zero": 0}


def test_bonus_de_sabor_nao_pedido_gera_linha_so_bonus():
    quote = q({"trad": 10}, bonus="zero")
    zero = next(l for l in quote.lines if l.product_id == "zero")
    assert zero.cases == 0 and zero.bonus_cases == 1 and zero.line_total == Decimal("0.00")
    assert quote.total_amount == Decimal("1416.00")


def test_campanha_inelegivel_nao_da_bonus():
    assert q({"trad": 20}, eligible=False).bonus_cases == 0


def test_sem_lata_avulsa_e_validacoes():
    with pytest.raises(QuoteError):
        q({"trad": 0})
    with pytest.raises(QuoteError):
        q({"trad": -1})
    with pytest.raises(QuoteError):
        q({"outro": 1})


def test_pagamento_sugerido_por_numero_do_pedido():
    s = DEFAULT_COMMERCIAL_SETTINGS
    assert payment_terms_for(1, s) == "50% na compra + 50% em 28 dias"
    assert payment_terms_for(2, s) == "A definir pelo back-office"
    assert payment_terms_for(3, s) == "A definir pelo back-office"
    assert payment_terms_for(4, s) == "30/60 dias"
    assert payment_terms_for(10, s) == "30/60 dias"


def test_lancamento_frete_gratis_para_todos():
    s = DEFAULT_COMMERCIAL_SETTINGS
    assert freight_for(1, "SP", s)[:2] == ("gratis", "Frete grátis.")
    assert freight_for(1, "RJ", s)[0] == "gratis"


def test_sem_frete_gratis_quando_desligado():
    s = {**DEFAULT_COMMERCIAL_SETTINGS, "free_freight_all": False}
    assert freight_for(500, "SP", s)[:2] == ("a_combinar", "Frete a combinar com o back-office.")
    assert freight_for(500, "RJ", s)[0] == "a_combinar"


def test_frete_gratis_se_religado_no_admin():
    s = {**DEFAULT_COMMERCIAL_SETTINGS, "free_freight_all": False, "free_freight_min_cases_home": 100, "free_freight_min_cases_other": 200}
    assert freight_for(100, "SP", s)[0] == "gratis"
    assert freight_for(99, "SP", s)[0] == "a_combinar"
    assert freight_for(150, "RJ", s)[0] == "a_combinar"
    assert freight_for(200, "RJ", s)[0] == "gratis"


def test_linhas_separadas_no_orcamento():
    cat = CAT + [CatalogItem("seda", "TB-IMP-016-D", "Seda", 1, 100, "tabacaria", "display")]
    q = compute_quote(catalog=cat, requested={"trad": 10, "seda": 4}, unit_prices={**PRICES, "seda": Decimal("100.00")}, campaign=RULE, campaign_eligible=True, bonus_product_id=None, customer_order_index=1, customer_uf="SP", settings=dict(DEFAULT_COMMERCIAL_SETTINGS))
    groups = {g.line: g for g in q.groups}
    assert groups["energetico"].subtotal == Decimal("1416.00") and groups["energetico"].bonus_qty == 1
    assert groups["tabacaria"].subtotal == Decimal("400.00") and groups["tabacaria"].bonus_qty == 0
    assert groups["tabacaria"].freight_status == "a_combinar"
    assert q.total_amount == Decimal("1816.00")
