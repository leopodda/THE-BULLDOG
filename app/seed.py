"""Dados iniciais: tenant DFJ (operação SP), energéticos, tabacaria, regra comercial,
campanha 10+1 e conexões ERP.

A DFJ é quem fatura em SP (decisão de 08/10/2026; estoque recebido da ST em consignação
mercantil, NFs 000020 e 000021). Por isso a conexão ATIVA é a da conta Bling da DFJ,
com os IDs de produto lidos no Bling da DFJ em 08/10/2026. A conexão "ST Nicolas" fica
cadastrada, porém desativada, só como histórico/base técnica.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.erp.jobs import set_ref
from app.models import Campaign, ErpConnection, PriceRule, Product, ProductLine, Role, Tenant, User
from app.security import hash_password

ST_NICOLAS_SETTINGS = {
    "order_initial_status_id": 21,          # Em digitação (conta ST Nicolas)
    "contact_type_customer_id": 14582035035,  # tipo de contato "Cliente" (conta ST Nicolas)
    "technical_price_mode": "commercial",
    "bonus_line_mode": "separate_item",
    "bonus_technical_unit_value": "0",
}
ST_NICOLAS_PRODUCT_IDS = {
    "DRINK-TRAD-269": "16647367802", "DRINK-ZERO-269": "16647367813",
    # Displays da Smoking Line na conta ST Nicolas (SKU "-D" = 1 UN no Bling = 1 display)
    "TB-IMP-001-D": "16694084645", "TB-IMP-002-D": "16694084646", "TB-IMP-003-D": "16694084643",
    "TB-IMP-004-D": "16694084621", "TB-IMP-005-D": "16694084637", "TB-IMP-006-D": "16694084639",
    "TB-IMP-007-D": "16694084625", "TB-IMP-008-D": "16694084627", "TB-IMP-009-D": "16694084630",
    "TB-IMP-010-D": "16694084642", "TB-IMP-011-D": "16694084623", "TB-IMP-012-D": "16694084622",
    "TB-IMP-013-D": "16694084614", "TB-IMP-014-D": "16694084610", "TB-IMP-015-D": "16694084611",
    "TB-IMP-016-D": "16694084612", "TB-IMP-017-D": "16694084613", "TB-IMP-018-D": "16694084617",
    "TB-IMP-019-D": "16694084620", "TB-IMP-020-D": "16694084616", "TB-IMP-021-D": "16694084618",
    "TB-IMP-022-D": "16694084640", "TB-IMP-023-D": "16694084648", "TB-IMP-024-D": "16694084633",
    "TB-IMP-025-D": "16710330063",
    "TB-IMP-023-U": "16710890006",  # MaryMill vendido por unidade
}

# Conta Bling da DFJ (lida em 08/10/2026). Mesmos SKUs do portal; "-D" = 1 UN = 1 display,
# energético em UN = 1 lata (o portal envia caixas x 24).
DFJ_SETTINGS = {
    "order_initial_status_id": 21,      # "Em digitação" (situação padrão do Bling) — conferir via API ao conectar
    "contact_type_customer_id": None,   # buscar o tipo "Cliente" da DFJ pela API ao conectar
    "technical_price_mode": "commercial",  # bar paga R$ 5,90 final: ICMS-ST já foi retido pela ST Nicolas na remessa
    # Naturezas da conta DFJ (decisão de 09/10/2026, conferidas no Bling da DFJ):
    "operation_nature_id": 15111666374,            # energético: "Venda de mercadoria com ST" (5.405 SP / CSOSN 500)
    "operation_nature_id_tabacaria": 15111666371,  # tabacaria: "Venda de mercadoria" (x102 / CSOSN 101)
    "operation_nature_id_bonus": 15111666382,      # caixa bônus: "Saída em bonificação" (x910)
    "require_operation_nature": True,
    "freight_payer_code": 3,               # 3 = transporte próprio por conta do remetente (DFJ entrega com veículo próprio)
    "bonus_line_mode": "separate_order",   # Bling = 1 natureza por pedido -> bonificação em pedido próprio "<nº>-B"
    "bonus_technical_unit_value": "0",     # 0 = usa o preço por lata (5,90) como valor da bonificação
}
DFJ_PRODUCT_IDS = {
    "DRINK-TRAD-269": "16717138941", "DRINK-ZERO-269": "16717138942",
    "TB-IMP-001-D": "16717136762", "TB-IMP-002-D": "16717136765", "TB-IMP-003-D": "16717136766",
    "TB-IMP-004-D": "16717136767", "TB-IMP-005-D": "16717136770", "TB-IMP-006-D": "16717136772",
    "TB-IMP-007-D": "16717136773", "TB-IMP-008-D": "16717136775", "TB-IMP-009-D": "16717136778",
    "TB-IMP-010-D": "16717136780", "TB-IMP-011-D": "16717136781", "TB-IMP-012-D": "16717136782",
    "TB-IMP-013-D": "16717136785", "TB-IMP-014-D": "16717136786", "TB-IMP-015-D": "16717136787",
    "TB-IMP-016-D": "16717136788", "TB-IMP-017-D": "16717136790", "TB-IMP-018-D": "16717136792",
    "TB-IMP-019-D": "16717136793", "TB-IMP-020-D": "16717136795", "TB-IMP-021-D": "16717136797",
    "TB-IMP-022-D": "16717136799", "TB-IMP-023-D": "16717136800", "TB-IMP-024-D": "16717136801",
    "TB-IMP-025-D": "16717136804",
    "TB-IMP-023-U": "16717305116",  # MaryMill por unidade (estoque já desmembrado na DFJ)
}

ENERGY_PRODUCTS = [
    ("DRINK-TRAD-269", "The Bulldog Energy Drink Tradicional 269 ml", "Tradicional"),
    ("DRINK-ZERO-269", "The Bulldog Energy Drink Zero Açúcar 269 ml", "Zero Açúcar"),
]

# Catálogo da Distribuidora (30/09/2026) — tabela "Smoking Line":
# (SKU portal/Bling, nome, unidades no display, ATACADO, referência online do catálogo — NÃO usada
#  no portal, mantida só como registro[, unidade de venda])
# Por padrão a venda é por DISPLAY. Exceções vendidas por UNIDADE: MaryMill e Zippo
# (preço = atacado/referência "por un." do catálogo).
TOBACCO_PRODUCTS = [
    ("TB-IMP-001-D", "Filtros de Acetato 6×15mm", 34, "220.66", "284.90"),
    ("TB-IMP-002-D", "Filtros de Acetato 6×22mm", 30, "206.40", "271.90"),
    ("TB-IMP-003-D", "Filtros Biodegradáveis de Celulose", 10, "74.90", "96.90"),
    ("TB-IMP-004-D", "Cones Reefer 6 Não Alvejados (6 cones)", 30, "296.40", "411.90"),
    ("TB-IMP-005-D", "Cinzeiro de Vidro Preto e Branco", 1, "49.88", "70.90"),
    ("TB-IMP-006-D", "Cinzeiro de Vidro Colorido", 1, "49.88", "70.90"),
    ("TB-IMP-007-D", "Dichavador de Metal 2 Partes", 12, "449.88", "611.90"),
    ("TB-IMP-008-D", "Dichavador de Metal 3 Partes", 12, "604.92", "822.90"),
    ("TB-IMP-009-D", "Dichavador de Metal 4 Partes", 6, "360.90", "490.90"),
    ("TB-IMP-010-D", "Piteiras de Papel Silver", 50, "156.00", "211.90"),
    ("TB-IMP-011-D", "Dichavador Plant-Based Vermelho", 24, "390.00", "530.90"),
    ("TB-IMP-012-D", "Dichavador Plant-Based Branco", 24, "390.00", "530.90"),
    ("TB-IMP-013-D", "Seda 1¼ Silver + Piteiras (50+50)", 24, "131.76", "155.90"),
    ("TB-IMP-014-D", "Seda King Size Slim + Piteiras Edição Old Skool", 24, "252.00", "347.90"),
    ("TB-IMP-015-D", "Seda King Size Regular Não Alvejada", 50, "273.00", "370.90"),
    ("TB-IMP-016-D", "Seda King Size Slim Não Alvejada", 25, "100.00", "148.90"),
    ("TB-IMP-017-D", "Seda King Size Slim Silver + Piteiras (32+32)", 24, "132.00", "160.90"),
    ("TB-IMP-018-D", "Seda em Rolo Slim Silver 4 m", 24, "124.56", "198.90"),
    ("TB-IMP-019-D", "Seda em Rolo Slim Não Alvejada, 5 m", 24, "165.60", "255.90"),
    ("TB-IMP-020-D", "Seda Short Size Silver", 25, "74.75", "89.90"),
    ("TB-IMP-021-D", "Seda Short Size White", 25, "57.25", "89.90"),
    ("TB-IMP-022-D", "Porta-Cigarro Metálico x JaySafe", 6, "329.40", "505.90"),
    ("TB-IMP-023-U", "Dichavador x MaryMill 2 em 1", None, "119.90", "209.90", "unidade"),
    ("TB-IMP-024-D", "Cinzeiro de Lata Preto", 30, "447.00", "549.90"),
    ("TB-IMP-025-D", "Isqueiro Zippo Amsterdam Gravado", None, "649.90", "1017.90", "unidade"),
]


def seed(db: Session, *, admin_email: str | None = None, admin_password: str | None = None, st_mode: str = "mock") -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == "dfj"))
    if tenant is None:
        tenant = Tenant(slug="dfj", name="DFJ — Operação The Bulldog SP", cnpj="68163961000150", settings={})
        db.add(tenant)
        db.flush()

    products = {}
    for order, (sku, name, short) in enumerate(ENERGY_PRODUCTS):
        p = db.scalar(select(Product).where(Product.tenant_id == tenant.id, Product.sku == sku))
        if p is None:
            p = Product(tenant_id=tenant.id, sku=sku, commercial_name=name, short_name=short, line=ProductLine.ENERGY, sale_unit="caixa", units_per_case=24, pack_contents=24, erp_unit="UN", sort_order=order)
            db.add(p)
            db.flush()
        products[sku] = p

    if not db.scalar(select(PriceRule).where(PriceRule.tenant_id == tenant.id, PriceRule.product_id.is_(None))):
        db.add(PriceRule(tenant_id=tenant.id, product_line=ProductLine.ENERGY, unit_price=Decimal("5.90"), suggested_retail_price=Decimal("9.90")))

    catalog_skus = set()
    for order, row in enumerate(TOBACCO_PRODUCTS, start=100):
        sku, name, contents, price, ref = row[:5]
        sale_unit = row[5] if len(row) > 5 else "display"
        catalog_skus.add(sku)
        p = db.scalar(select(Product).where(Product.tenant_id == tenant.id, Product.sku == sku))
        if p is None:
            p = Product(tenant_id=tenant.id, sku=sku, commercial_name=name, short_name=name, line=ProductLine.TOBACCO, sale_unit=sale_unit, units_per_case=1, pack_contents=contents, erp_unit="UN", sort_order=order)
            db.add(p)
            db.flush()
            db.add(PriceRule(tenant_id=tenant.id, product_id=p.id, unit_price=Decimal(price)))
        elif p.sale_unit != sale_unit:
            # mudança de unidade de venda (ex.: Zippo display -> unidade): ajusta unidade e preço
            p.sale_unit, p.pack_contents = sale_unit, contents
            rule = db.scalar(select(PriceRule).where(PriceRule.tenant_id == tenant.id, PriceRule.product_id == p.id, PriceRule.customer_id.is_(None), PriceRule.channel.is_(None)))
            if rule:
                rule.unit_price = Decimal(price)
        products[sku] = p
    # Referência online não é usada no portal (é só sugestão de revenda): limpa se existir
    for rule in db.scalars(select(PriceRule).join(Product, PriceRule.product_id == Product.id).where(PriceRule.tenant_id == tenant.id, Product.line == ProductLine.TOBACCO)):
        rule.suggested_retail_price = None
    # SKUs de tabacaria que saíram do catálogo do portal (ex.: MaryMill em display) ficam inativos
    for p in db.scalars(select(Product).where(Product.tenant_id == tenant.id, Product.line == ProductLine.TOBACCO)):
        if p.sku not in catalog_skus:
            p.active = False

    if not db.scalar(select(Campaign).where(Campaign.tenant_id == tenant.id)):
        db.add(Campaign(tenant_id=tenant.id, name="Lançamento 10+1", product_line=ProductLine.ENERGY, buy_cases=10, bonus_cases=1, stackable=True, region_scope="uf", max_orders_per_region=None))

    from app.erp.jobs import get_ref

    # Conexão ATIVA: conta Bling da DFJ (quem fatura em SP).
    dfj = db.scalar(select(ErpConnection).where(ErpConnection.tenant_id == tenant.id, ErpConnection.label.like("DFJ%")))
    if dfj is None:
        dfj = ErpConnection(tenant_id=tenant.id, provider="bling", label="DFJ (conta que fatura em SP)", mode=st_mode, is_active=True, credentials_env_prefix="BLING_DFJ", settings=dict(DFJ_SETTINGS))
        db.add(dfj)
        db.flush()
    elif not dfj.settings:  # banco antigo: conexão DFJ vazia -> preenche e ativa
        dfj.label = "DFJ (conta que fatura em SP)"
        dfj.settings = dict(DFJ_SETTINGS)
        dfj.mode = st_mode
        dfj.is_active = True
    for sku, ext in DFJ_PRODUCT_IDS.items():
        if sku in products and get_ref(db, dfj.id, "product", products[sku].id) is None:
            set_ref(db, dfj.id, "product", products[sku].id, ext)

    # Conexão ST Nicolas: só histórico/base técnica, desativada.
    st = db.scalar(select(ErpConnection).where(ErpConnection.tenant_id == tenant.id, ErpConnection.label.like("ST Nicolas%")))
    if st is None:
        st = ErpConnection(tenant_id=tenant.id, provider="bling", label="ST Nicolas (desativada — não fatura em SP)", mode="disabled", is_active=False, credentials_env_prefix="BLING_STNICOLAS", settings=dict(ST_NICOLAS_SETTINGS))
        db.add(st)
        db.flush()
    elif dfj.is_active:
        st.is_active = False
    for sku, ext in ST_NICOLAS_PRODUCT_IDS.items():
        if sku in products and get_ref(db, st.id, "product", products[sku].id) is None:
            set_ref(db, st.id, "product", products[sku].id, ext)

    if admin_email and admin_password and not db.scalar(select(User).where(User.email == admin_email.lower())):
        db.add(User(tenant_id=tenant.id, role=Role.ADMIN, name="Administrador", email=admin_email.lower(), password_hash=hash_password(admin_password), must_change_password=False))

    db.commit()
    return tenant


def seed_demo(db: Session, tenant: Tenant, password: str) -> None:
    """Usuários e cliente de demonstração (apenas desenvolvimento)."""
    from app.domain.customers import CustomerInput, create_customer, find_by_cnpj
    from app.models import ValidationStatus

    seller = db.scalar(select(User).where(User.email == "vendedor@demo.local"))
    if seller is None:
        seller = User(tenant_id=tenant.id, role=Role.SELLER, name="Vendedor Demo", email="vendedor@demo.local", password_hash=hash_password(password), seller_type="dfj")
        db.add(seller)
        db.flush()
    cust = find_by_cnpj(db, tenant.id, "11222333000181")
    if cust is None:
        cust = create_customer(db, tenant_id=tenant.id, actor=seller, data=CustomerInput(
            cnpj="11.222.333/0001-81", ie_indicator=1, ie="110042490114", razao_social="Bar Demonstração Ltda", nome_fantasia="Bar Demo",
            contact_name="Fulano", phone="11999990000", whatsapp="11999990000", email="bar@demo.local", email_nfe="nfe@demo.local",
            cep="03071000", logradouro="Rua Exemplo", numero="100", complemento=None, bairro="Tatuapé", municipio="São Paulo", uf="SP", channel="bar",
        ))
        cust.validation_status = ValidationStatus.CONFIRMED
    if not db.scalar(select(User).where(User.email == "pdv@demo.local")):
        db.add(User(tenant_id=tenant.id, role=Role.CUSTOMER, name="Bar Demo", email="pdv@demo.local", password_hash=hash_password(password), customer_id=cust.id))
    db.commit()
