from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import current_tenant, require_admin, require_staff
from app.api.serializers import customer_out
from app.db import get_db
from app.domain import customers as svc
from app.domain.documents import is_valid_cnpj, only_digits
from app.models import Customer, Role, Tenant, User

router = APIRouter(prefix="/api/customers", tags=["customers"])


class CustomerIn(BaseModel):
    cnpj: str = Field(max_length=20)
    ie_indicator: int
    ie: str | None = Field(default=None, max_length=20)
    razao_social: str = Field(max_length=200)
    nome_fantasia: str | None = Field(default=None, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    whatsapp: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=254)
    email_nfe: str | None = Field(default=None, max_length=254)
    cep: str = Field(max_length=10)
    logradouro: str = Field(max_length=200)
    numero: str = Field(max_length=20)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str = Field(max_length=100)
    municipio: str = Field(max_length=100)
    uf: str = Field(max_length=2)
    channel: str | None = Field(default=None, max_length=30)

    def to_input(self) -> svc.CustomerInput:
        return svc.CustomerInput(**self.model_dump())


class ValidationIn(BaseModel):
    status: str
    notes: str | None = Field(default=None, max_length=1000)


def _get(db: Session, tenant: Tenant, customer_id: str) -> Customer:
    c = db.get(Customer, customer_id)
    if c is None or c.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente não encontrado.")
    return c


@router.get("")
def list_customers(q: str | None = Query(default=None, max_length=100), user: User = Depends(require_staff), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    return {"items": [customer_out(c) for c in svc.search(db, tenant.id, q)]}


@router.get("/check-cnpj")
def check_cnpj(cnpj: str = Query(max_length=20), user: User = Depends(require_staff), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    digits = only_digits(cnpj)
    valid = is_valid_cnpj(digits)
    existing = svc.find_by_cnpj(db, tenant.id, digits) if valid else None
    return {"cnpj": digits, "valid": valid, "exists": existing is not None, "customer": customer_out(existing) if existing else None}


@router.post("", status_code=201)
def create(body: CustomerIn, user: User = Depends(require_staff), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    try:
        c = svc.create_customer(db, tenant_id=tenant.id, data=body.to_input(), actor=user)
    except svc.DuplicateCustomer as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": str(exc), "customer": customer_out(exc.existing)})
    except svc.CustomerError as exc:
        raise HTTPException(422, str(exc))
    db.commit()
    return {"customer": customer_out(c)}


@router.get("/{customer_id}")
def get_one(customer_id: str, user: User = Depends(require_staff), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    return {"customer": customer_out(_get(db, tenant, customer_id))}


@router.put("/{customer_id}")
def update(customer_id: str, body: CustomerIn, user: User = Depends(require_staff), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    c = _get(db, tenant, customer_id)
    if user.role == Role.SELLER and c.created_by_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vendedor só edita clientes que cadastrou. Peça ao back-office.")
    try:
        svc.update_customer(db, customer=c, data=body.to_input(), actor=user)
    except svc.DuplicateCustomer as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, {"message": str(exc), "customer": customer_out(exc.existing)})
    except svc.CustomerError as exc:
        raise HTTPException(422, str(exc))
    db.commit()
    return {"customer": customer_out(c)}


@router.post("/{customer_id}/validation")
def validate(customer_id: str, body: ValidationIn, user: User = Depends(require_admin), tenant: Tenant = Depends(current_tenant), db: Session = Depends(get_db)):
    c = _get(db, tenant, customer_id)
    try:
        svc.set_validation(db, customer=c, status=body.status, notes=body.notes, actor=user)
    except svc.CustomerError as exc:
        raise HTTPException(422, str(exc))
    db.commit()
    return {"customer": customer_out(c)}
