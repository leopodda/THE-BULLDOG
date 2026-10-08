"""Modelo de domínio do portal.

Regras:
- Toda chave primária é UUID interno do portal (string de 36 chars, portável SQLite/Postgres).
- IDs de sistemas externos (Bling, futuramente RD Station) ficam em `external_refs`,
  amarrados à CONEXÃO ERP que os gerou. Trocar a conta Bling (ST Nicolas -> DFJ) não
  mistura IDs de contas diferentes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role:
    ADMIN = "admin"
    SELLER = "seller"
    CUSTOMER = "customer"
    ALL = (ADMIN, SELLER, CUSTOMER)


class ValidationStatus:
    PENDING = "pendente_conferencia"
    CONFIRMED = "conferido"
    REJECTED = "rejeitado"
    ALL = (PENDING, CONFIRMED, REJECTED)


class OrderStatus:
    """Status PRÓPRIO do portal. Mapeado a partir das situações do ERP por configuração."""
    RECEIVED = "recebido"            # gravado no portal
    SENT_TO_ERP = "enviado_erp"      # pedido existe no Bling (ex.: Em digitação)
    IN_REVIEW = "em_conferencia"     # back-office conferindo
    APPROVED = "aprovado"
    INVOICED = "faturado"
    CANCELLED = "cancelado"
    ALL = (RECEIVED, SENT_TO_ERP, IN_REVIEW, APPROVED, INVOICED, CANCELLED)


class IntegrationStatus:
    NOT_REQUIRED = "nao_requerida"   # integração desligada
    PENDING = "pendente"
    SUCCESS = "sucesso"
    ERROR = "erro"


class ProductLine:
    ENERGY = "energetico"
    TOBACCO = "tabacaria"
    ALL = (ENERGY, TOBACCO)
    LABELS = {ENERGY: "Energético", TOBACCO: "Tabacaria (Smoking Line)"}


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str | None] = mapped_column(String(14))
    # Regras comerciais que não pertencem ao ERP (pagamento sugerido, frete, prazos...).
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ErpConnection(Base):
    """Uma conta de ERP ligada a um tenant. Só uma fica ativa por tenant.

    mode: disabled | mock | bling
    credentials_env_prefix: prefixo das variáveis de ambiente com client_id/secret
      (ex.: BLING_STNICOLAS -> BLING_STNICOLAS_CLIENT_ID / _CLIENT_SECRET).
    token_ciphertext: tokens OAuth criptografados (Fernet). Nunca serializados para a API.
    settings: IDs e parâmetros configuráveis (situação inicial, depósito, natureza, loja,
      valor técnico, mapeamento de status, etc.). Ver app/erp/settings.py.
    """
    __tablename__ = "erp_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    provider: Mapped[str] = mapped_column(String(30), default="bling")
    label: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(20), default="disabled")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    credentials_env_prefix: Mapped[str | None] = mapped_column(String(80))
    token_ciphertext: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ExternalRef(Base):
    """Vínculo entre uma entidade interna e seu ID em um sistema externo.

    entity_type: customer | order | product | seller | invoice (futuro: rd_contact, rd_deal)
    """
    __tablename__ = "external_refs"
    __table_args__ = (
        UniqueConstraint("connection_id", "entity_type", "entity_id", name="uq_extref_entity"),
        Index("ix_extref_lookup", "connection_id", "entity_type", "external_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connection_id: Mapped[str] = mapped_column(ForeignKey("erp_connections.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str] = mapped_column(String(36))
    external_id: Mapped[str] = mapped_column(String(64))
    external_number: Mapped[str | None] = mapped_column(String(64))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Somente para role=customer: o cliente (PDV) que este login representa.
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id", use_alter=True, name="fk_users_customer_id"))
    # Preparação para carteira/comissão (sem regra na V1).
    seller_type: Mapped[str | None] = mapped_column(String(30))  # ex.: dfj, st_nicolas, outro
    commission_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("tenant_id", "cnpj", name="uq_customer_tenant_cnpj"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    cnpj: Mapped[str] = mapped_column(String(14))  # somente dígitos, 14 posições
    ie: Mapped[str | None] = mapped_column(String(20))
    ie_indicator: Mapped[int] = mapped_column(Integer)  # 1 contribuinte | 2 isento | 9 não contribuinte
    razao_social: Mapped[str] = mapped_column(String(200))
    nome_fantasia: Mapped[str | None] = mapped_column(String(200))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    whatsapp: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(254))
    email_nfe: Mapped[str | None] = mapped_column(String(254))
    cep: Mapped[str] = mapped_column(String(8))
    logradouro: Mapped[str] = mapped_column(String(200))
    numero: Mapped[str] = mapped_column(String(20))
    complemento: Mapped[str | None] = mapped_column(String(100))
    bairro: Mapped[str] = mapped_column(String(100))
    municipio: Mapped[str] = mapped_column(String(100))
    uf: Mapped[str] = mapped_column(String(2))
    channel: Mapped[str | None] = mapped_column(String(30))  # bar, tabacaria, posto, mercado...
    validation_status: Mapped[str] = mapped_column(String(30), default=ValidationStatus.PENDING)
    validation_notes: Mapped[str | None] = mapped_column(Text)
    assigned_seller_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_sku"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    sku: Mapped[str] = mapped_column(String(60))
    commercial_name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str] = mapped_column(String(60))
    # Linha de produto: define bônus, natureza fiscal e divisão do pedido.
    line: Mapped[str] = mapped_column(String(20), default="energetico", server_default="energetico")
    # Unidade de venda no portal (caixa | display) e quantas unidades do ERP ela representa.
    sale_unit: Mapped[str] = mapped_column(String(20), default="caixa", server_default="caixa")
    units_per_case: Mapped[int] = mapped_column(Integer, default=24)
    # Informativo: itens dentro da embalagem de venda (ex.: display com 34 piteiras).
    pack_contents: Mapped[int | None] = mapped_column(Integer)
    erp_unit: Mapped[str] = mapped_column(String(10), default="UN")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PriceRule(Base):
    """Preço COMERCIAL por lata. Independente do valor técnico enviado ao ERP.

    Especificidade: cliente > canal > geral. Produto nulo = vale para todos.
    """
    __tablename__ = "price_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"))
    product_line: Mapped[str | None] = mapped_column(String(20))  # regra geral de uma linha
    channel: Mapped[str | None] = mapped_column(String(30))
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    suggested_retail_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Campaign(Base):
    """Campanha de bônus em caixas: compre `buy_cases` e leve `bonus_cases`.

    region_scope: none | uf | municipio  (região usada para limitar os "primeiros pedidos")
    max_orders_per_region: quantos pedidos com bônus por região (None = sem limite)
    """
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    product_line: Mapped[str | None] = mapped_column(String(20))  # None = todas as linhas
    buy_cases: Mapped[int] = mapped_column(Integer, default=10)
    bonus_cases: Mapped[int] = mapped_column(Integer, default=1)
    stackable: Mapped[bool] = mapped_column(Boolean, default=True)
    region_scope: Mapped[str] = mapped_column(String(20), default="none")
    max_orders_per_region: Mapped[int | None] = mapped_column(Integer)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OrderCounter(Base):
    __tablename__ = "order_counters"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, default=0)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_number", name="uq_order_number"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_order_idempotency"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    order_number: Mapped[str] = mapped_column(String(30))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    # Um "fechamento" do carrinho pode gerar 1 pedido por linha de produto (energético /
    # tabacaria), porque cada linha tem tratamento fiscal próprio. checkout_key agrupa.
    checkout_key: Mapped[str] = mapped_column(String(80), index=True, default="", server_default="")
    product_line: Mapped[str] = mapped_column(String(20), default="energetico", server_default="energetico")
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    seller_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(20))  # customer | seller | admin
    status: Mapped[str] = mapped_column(String(30), default=OrderStatus.RECEIVED)
    integration_status: Mapped[str] = mapped_column(String(30), default=IntegrationStatus.NOT_REQUIRED)
    integration_error: Mapped[str | None] = mapped_column(Text)
    erp_connection_id: Mapped[str | None] = mapped_column(ForeignKey("erp_connections.id"))
    # Comercial (não fiscal):
    paid_cases: Mapped[int] = mapped_column(Integer)
    bonus_cases: Mapped[int] = mapped_column(Integer, default=0)
    total_units: Mapped[int] = mapped_column(Integer)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))
    region_key: Mapped[str | None] = mapped_column(String(120))
    customer_order_index: Mapped[int] = mapped_column(Integer, default=1)
    payment_method_preference: Mapped[str | None] = mapped_column(String(30))
    suggested_payment_terms: Mapped[str | None] = mapped_column(String(200))
    freight_status: Mapped[str | None] = mapped_column(String(30))  # gratis | a_combinar
    delivery_estimate: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    customer_validation_at_order: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.position")
    customer: Mapped[Customer] = relationship()


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    sku: Mapped[str] = mapped_column(String(60))
    product_name: Mapped[str] = mapped_column(String(200))
    units_per_case: Mapped[int] = mapped_column(Integer)
    cases_qty: Mapped[int] = mapped_column(Integer)
    units_qty: Mapped[int] = mapped_column(Integer)
    bonus_cases: Mapped[int] = mapped_column(Integer, default=0)
    bonus_units: Mapped[int] = mapped_column(Integer, default=0)
    unit_price_commercial: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    case_price_commercial: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order: Mapped[Order] = relationship(back_populates="items")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_entity", "entity_type", "entity_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey("tenants.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(60))
    actor_user_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class IntegrationJob(Base):
    __tablename__ = "integration_jobs"
    __table_args__ = (Index("ix_jobs_status", "status", "next_attempt_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    connection_id: Mapped[str] = mapped_column(ForeignKey("erp_connections.id"))
    job_type: Mapped[str] = mapped_column(String(40))  # push_order
    entity_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|success|error|dead
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
