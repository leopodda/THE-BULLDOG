from __future__ import annotations

import os

os.environ["APP_SKIP_DOTENV"] = "1"
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-not-for-production-0123456789")
os.environ.setdefault("APP_ENCRYPTION_KEY", "N0VH3j7yrdiH3H0uYQ6d6rUQa0Kk3k2xS3wrq5FfM2k=")
os.environ["APP_PROCESS_JOBS_INLINE"] = "0"
os.environ["BLING_MIN_INTERVAL_S"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, make_engine, set_engine
from app.erp import mock
from app.models import Role, User
from app.security import hash_password

PASSWORD = "senha-forte-123"


@pytest.fixture()
def engine(tmp_path):
    eng = make_engine(f"sqlite:///{tmp_path/'test.db'}")
    Base.metadata.create_all(eng)
    set_engine(eng)
    mock.reset()
    from app.api.auth import reset_rate_limit
    reset_rate_limit()
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine) -> Session:
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def tenant(db):
    from app.seed import seed
    return seed(db, admin_email="admin@test.local", admin_password=PASSWORD, st_mode="mock")


@pytest.fixture()
def seller(db, tenant):
    u = User(tenant_id=tenant.id, role=Role.SELLER, name="Vendedora", email="seller@test.local", password_hash=hash_password(PASSWORD), seller_type="dfj")
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def app(engine):
    from app.main import create_app
    return create_app()


def make_client(app, email: str | None = None) -> TestClient:
    c = TestClient(app)
    c.headers.update({"X-Portal-Request": "1"})
    if email:
        r = c.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
    return c


VALID_CUSTOMER = {
    "cnpj": "11.222.333/0001-81",
    "ie_indicator": 1,
    "ie": "110.042.490.114",
    "razao_social": "Bar do Teste Ltda",
    "nome_fantasia": "Bar do Teste",
    "contact_name": "Maria",
    "phone": "(11) 3333-4444",
    "whatsapp": "(11) 99999-0000",
    "email": "contato@bar.test",
    "email_nfe": "nfe@bar.test",
    "cep": "03071-000",
    "logradouro": "Rua Cesário Galero",
    "numero": "10",
    "complemento": None,
    "bairro": "Tatuapé",
    "municipio": "São Paulo",
    "uf": "SP",
    "channel": "bar",
}
