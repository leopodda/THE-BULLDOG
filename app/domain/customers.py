from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain import events
from app.domain.documents import UFS, is_valid_cnpj, normalize_ie, only_digits
from app.models import Customer, User, ValidationStatus

CHANNELS = ("bar", "balada", "tabacaria", "posto", "mercado", "adega", "distribuidor", "evento", "outro")


class CustomerError(ValueError):
    pass


class DuplicateCustomer(CustomerError):
    def __init__(self, existing: Customer):
        super().__init__("Já existe cliente com este CNPJ.")
        self.existing = existing


@dataclass
class CustomerInput:
    cnpj: str
    ie_indicator: int
    ie: str | None
    razao_social: str
    nome_fantasia: str | None
    contact_name: str | None
    phone: str | None
    whatsapp: str | None
    email: str | None
    email_nfe: str | None
    cep: str
    logradouro: str
    numero: str
    complemento: str | None
    bairro: str
    municipio: str
    uf: str
    channel: str | None = None


def find_by_cnpj(db: Session, tenant_id: str, cnpj: str) -> Customer | None:
    digits = only_digits(cnpj)
    return db.scalar(select(Customer).where(Customer.tenant_id == tenant_id, Customer.cnpj == digits))


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


def validate_input(data: CustomerInput) -> dict:
    cnpj = only_digits(data.cnpj)
    if not is_valid_cnpj(cnpj):
        raise CustomerError("CNPJ inválido (confira os 14 dígitos).")
    ie, err = normalize_ie(int(data.ie_indicator), data.ie)
    if err:
        raise CustomerError(err)
    uf = (data.uf or "").strip().upper()
    if uf not in UFS:
        raise CustomerError("UF inválida.")
    cep = only_digits(data.cep)
    if len(cep) != 8:
        raise CustomerError("CEP deve ter 8 dígitos.")
    required = {"razão social": data.razao_social, "logradouro": data.logradouro, "número": data.numero, "bairro": data.bairro, "cidade": data.municipio}
    missing = [k for k, v in required.items() if not _clean(v)]
    if missing:
        raise CustomerError("Campos obrigatórios: " + ", ".join(missing) + ".")
    if not _clean(data.email_nfe):
        raise CustomerError("E-mail para NF-e é obrigatório.")
    if not (_clean(data.phone) or _clean(data.whatsapp)):
        raise CustomerError("Informe telefone ou WhatsApp.")
    channel = (data.channel or "").strip().lower() or None
    if channel and channel not in CHANNELS:
        raise CustomerError("Canal inválido.")
    return {
        "cnpj": cnpj,
        "ie_indicator": int(data.ie_indicator),
        "ie": ie,
        "razao_social": _clean(data.razao_social).upper(),
        "nome_fantasia": _clean(data.nome_fantasia),
        "contact_name": _clean(data.contact_name),
        "phone": only_digits(data.phone) or None,
        "whatsapp": only_digits(data.whatsapp) or None,
        "email": (_clean(data.email) or "").lower() or None,
        "email_nfe": _clean(data.email_nfe).lower(),
        "cep": cep,
        "logradouro": _clean(data.logradouro),
        "numero": _clean(data.numero),
        "complemento": _clean(data.complemento),
        "bairro": _clean(data.bairro),
        "municipio": _clean(data.municipio),
        "uf": uf,
        "channel": channel,
    }


def create_customer(db: Session, *, tenant_id: str, data: CustomerInput, actor: User) -> Customer:
    values = validate_input(data)
    existing = find_by_cnpj(db, tenant_id, values["cnpj"])
    if existing:
        raise DuplicateCustomer(existing)
    customer = Customer(
        tenant_id=tenant_id,
        validation_status=ValidationStatus.PENDING,
        created_by_user_id=actor.id,
        assigned_seller_id=actor.id if actor.role == "seller" else None,
        **values,
    )
    try:
        with db.begin_nested():
            db.add(customer)
            db.flush()
    except IntegrityError:
        # corrida entre dois cadastros simultâneos do mesmo CNPJ (constraint única no banco)
        existing = find_by_cnpj(db, tenant_id, values["cnpj"])
        if existing:
            raise DuplicateCustomer(existing)
        raise
    events.record(db, tenant_id=tenant_id, entity_type="customer", entity_id=customer.id, action="customer.created", actor_user_id=actor.id, payload={"cnpj": customer.cnpj, "source": actor.role})
    return customer


def update_customer(db: Session, *, customer: Customer, data: CustomerInput, actor: User) -> Customer:
    values = validate_input(data)
    if values["cnpj"] != customer.cnpj:
        other = find_by_cnpj(db, customer.tenant_id, values["cnpj"])
        if other and other.id != customer.id:
            raise DuplicateCustomer(other)
    changed = {k: v for k, v in values.items() if getattr(customer, k) != v}
    for k, v in changed.items():
        setattr(customer, k, v)
    fiscal_fields = {"cnpj", "ie", "ie_indicator", "razao_social", "cep", "logradouro", "numero", "bairro", "municipio", "uf"}
    if actor.role != "admin" and fiscal_fields & changed.keys():
        customer.validation_status = ValidationStatus.PENDING
    events.record(db, tenant_id=customer.tenant_id, entity_type="customer", entity_id=customer.id, action="customer.updated", actor_user_id=actor.id, payload={"fields": sorted(changed)})
    return customer


def set_validation(db: Session, *, customer: Customer, status: str, notes: str | None, actor: User) -> Customer:
    if status not in ValidationStatus.ALL:
        raise CustomerError("Status de conferência inválido.")
    customer.validation_status = status
    customer.validation_notes = notes
    events.record(db, tenant_id=customer.tenant_id, entity_type="customer", entity_id=customer.id, action="customer.validated", actor_user_id=actor.id, payload={"status": status})
    return customer


def search(db: Session, tenant_id: str, q: str | None, limit: int = 30) -> list[Customer]:
    stmt = select(Customer).where(Customer.tenant_id == tenant_id)
    if q:
        q = q.strip()
        digits = only_digits(q)
        like = f"%{q.lower()}%"
        conds = [Customer.razao_social.ilike(like), Customer.nome_fantasia.ilike(like), Customer.municipio.ilike(like)]
        if len(digits) >= 3:
            conds.append(Customer.cnpj.like(f"%{digits}%"))
        stmt = stmt.where(or_(*conds))
    return list(db.scalars(stmt.order_by(Customer.razao_social).limit(limit)))
