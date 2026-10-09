"""Adaptador Bling contra respostas HTTP simuladas (respx). Nenhuma chamada real."""
import json
from datetime import timedelta

import httpx
import respx
from sqlalchemy import select

from app.erp import bling, jobs
from app.erp.registry import set_http_factory
from app.models import Customer, ErpConnection, ExternalRef, Order, Product, ValidationStatus, utcnow
from app.security import encrypt_json
from tests.conftest import VALID_CUSTOMER, make_client

API = bling.API_BASE


def _live_connection(db, monkeypatch, expired=False):
    monkeypatch.setenv("BLING_DFJ_CLIENT_ID", "cid")
    monkeypatch.setenv("BLING_DFJ_CLIENT_SECRET", "csecret")
    conn = db.scalar(select(ErpConnection).where(ErpConnection.is_active.is_(True)))
    conn.mode = "bling"
    conn.token_ciphertext = encrypt_json({"access_token": "AT-OLD", "refresh_token": "RT-1"})
    conn.token_expires_at = utcnow() + (timedelta(seconds=-10) if expired else timedelta(hours=5))
    db.commit()
    set_http_factory(lambda: httpx.Client())
    return conn


def _make_order(app, db):
    s = make_client(app, "seller@test.local")
    cust = s.post("/api/customers", json=VALID_CUSTOMER).json()["customer"]
    prods = {p.sku: p.id for p in db.scalars(select(Product))}
    r = s.post("/api/orders", json={"customer_id": cust["id"], "items": [{"product_id": prods["DRINK-TRAD-269"], "cases": 10}], "notes": "Entregar à tarde"}, headers={"Idempotency-Key": "k-1"})
    assert r.status_code == 201, r.text
    return r.json()["order"], cust


@respx.mock
def test_push_order_payload_real_do_bling(app, db, tenant, seller, monkeypatch):
    conn = _live_connection(db, monkeypatch)
    order, cust = _make_order(app, db)

    respx.get(f"{API}/contatos").mock(return_value=httpx.Response(200, json={"data": []}))
    contact_route = respx.post(f"{API}/contatos").mock(return_value=httpx.Response(201, json={"data": {"id": 555}}))
    respx.get(f"{API}/pedidos/vendas").mock(return_value=httpx.Response(200, json={"data": []}))
    order_route = respx.post(f"{API}/pedidos/vendas").mock(side_effect=[httpx.Response(201, json={"data": {"id": 9001}}), httpx.Response(201, json={"data": {"id": 9002}})])
    respx.get(f"{API}/pedidos/vendas/9001").mock(return_value=httpx.Response(200, json={"data": {"id": 9001, "numero": 1, "numeroLoja": order["order_number"], "situacao": {"id": 21, "valor": 0}}}))
    respx.get(f"{API}/pedidos/vendas/9002").mock(return_value=httpx.Response(200, json={"data": {"id": 9002, "numero": 2, "numeroLoja": order["order_number"] + "-B", "situacao": {"id": 21, "valor": 0}}}))

    done = jobs.process_pending(db)
    assert done[0].status == "success", done[0].last_error

    contact = json.loads(contact_route.calls[0].request.content)
    assert contact["numeroDocumento"] == "11222333000181"
    assert contact["indicadorIe"] == 1 and contact["ie"] == "110042490114"
    assert "tiposContato" not in contact  # tipo "Cliente" da DFJ ainda não configurado
    assert contact["endereco"]["geral"]["uf"] == "SP"

    req = order_route.calls[0].request
    assert req.headers["Authorization"] == "Bearer AT-OLD"
    payload = json.loads(req.content)
    assert payload["numeroLoja"] == order["order_number"]
    assert payload["contato"] == {"id": 555}
    assert payload["situacao"] == {"id": 21}
    (paid,) = payload["itens"]  # venda só com as caixas pagas
    assert paid["produto"] == {"id": 16717138941} and paid["quantidade"] == 240 and paid["valor"] == 5.9 and paid["unidade"] == "UN"
    assert "parcelas" not in payload  # V1 não gera parcelas
    assert all(i["naturezaOperacao"] == {"id": 15111666374} for i in payload["itens"]) and "naturezaOperacao" not in payload  # natureza por item

    # Bonificação 10+1 em pedido próprio, com natureza de bonificação
    bonus_payload = json.loads(order_route.calls[1].request.content)
    assert bonus_payload["numeroLoja"] == order["order_number"] + "-B"
    assert bonus_payload["itens"][0]["naturezaOperacao"] == {"id": 15111666382}
    (bonus,) = bonus_payload["itens"]
    assert bonus["produto"] == {"id": 16717138941} and bonus["quantidade"] == 24 and bonus["valor"] == 5.9 and "BONIFICAÇÃO" in bonus["descricao"]
    assert "parcelas" not in bonus_payload
    assert "PENDENTE DE CONFERÊNCIA" in payload["observacoesInternas"]
    assert "Entregar à tarde" in payload["observacoes"]

    db.expire_all()
    o = db.get(Order, order["id"])
    assert o.status == "enviado_erp" and o.integration_status == "sucesso"
    ref = db.scalar(select(ExternalRef).where(ExternalRef.entity_type == "order"))
    assert ref.external_id == "9001" and ref.external_number == "1"


@respx.mock
def test_reaproveita_contato_e_pedido_existentes(app, db, tenant, seller, monkeypatch):
    _live_connection(db, monkeypatch)
    order, _ = _make_order(app, db)
    respx.get(f"{API}/contatos").mock(return_value=httpx.Response(200, json={"data": [{"id": 777, "numeroDocumento": "11.222.333/0001-81"}]}))
    create_contact = respx.post(f"{API}/contatos")
    respx.get(f"{API}/pedidos/vendas").mock(return_value=httpx.Response(200, json={"data": [
        {"id": 4242, "numero": 9, "numeroLoja": order["order_number"], "situacao": {"id": 21}},
        {"id": 4243, "numero": 10, "numeroLoja": order["order_number"] + "-B", "situacao": {"id": 21}},
    ]}))
    create_order = respx.post(f"{API}/pedidos/vendas")
    done = jobs.process_pending(db)
    assert done[0].status == "success", done[0].last_error
    assert not create_contact.called and not create_order.called  # timeout anterior não duplica no Bling


@respx.mock
def test_token_expirado_e_renovado(app, db, tenant, seller, monkeypatch):
    conn = _live_connection(db, monkeypatch, expired=True)
    order, _ = _make_order(app, db)
    token_route = respx.post(bling.TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "AT-NEW", "refresh_token": "RT-2", "expires_in": 21600, "token_type": "Bearer"}))
    respx.get(f"{API}/contatos").mock(return_value=httpx.Response(200, json={"data": [{"id": 1, "numeroDocumento": "11222333000181"}]}))
    respx.get(f"{API}/pedidos/vendas").mock(return_value=httpx.Response(200, json={"data": []}))
    order_route = respx.post(f"{API}/pedidos/vendas").mock(return_value=httpx.Response(201, json={"data": {"id": 5}}))
    respx.get(f"{API}/pedidos/vendas/5").mock(return_value=httpx.Response(200, json={"data": {"id": 5, "numero": 2, "situacao": {"id": 21}}}))
    assert jobs.process_pending(db)[0].status == "success"
    assert token_route.called
    assert "grant_type=refresh_token" in token_route.calls[0].request.content.decode()
    assert order_route.calls[0].request.headers["Authorization"] == "Bearer AT-NEW"
    db.expire_all()
    from app.security import decrypt_json
    assert decrypt_json(db.get(ErpConnection, conn.id).token_ciphertext)["refresh_token"] == "RT-2"


@respx.mock
def test_erro_de_validacao_do_bling_nao_retenta_e_mostra_mensagem(app, db, tenant, seller, monkeypatch):
    _live_connection(db, monkeypatch)
    order, _ = _make_order(app, db)
    respx.get(f"{API}/contatos").mock(return_value=httpx.Response(200, json={"data": [{"id": 1, "numeroDocumento": "11222333000181"}]}))
    respx.get(f"{API}/pedidos/vendas").mock(return_value=httpx.Response(200, json={"data": []}))
    respx.post(f"{API}/pedidos/vendas").mock(return_value=httpx.Response(400, json={"error": {"type": "VALIDATION_ERROR", "message": "Não foi possível salvar", "fields": [{"element": "itens", "msg": "Produto inválido"}]}}))
    job = jobs.process_pending(db)[0]
    assert job.status == "error"
    db.expire_all()
    o = db.get(Order, order["id"])
    assert o.integration_status == "erro" and "Produto inválido" in o.integration_error
    assert db.get(Order, order["id"]) is not None


def test_api_nunca_expoe_tokens(app, db, tenant, seller, monkeypatch):
    _live_connection(db, monkeypatch)
    a = make_client(app, "admin@test.local")
    raw = a.get("/api/admin/erp").text
    assert "AT-OLD" not in raw and "RT-1" not in raw and "token_ciphertext" not in raw and "csecret" not in raw
    data = a.get("/api/admin/erp").json()
    assert any(c["authorized"] for c in data["connections"])


def test_alembic_migration_aplica(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = f"sqlite:///{tmp_path/'mig.db'}"
    command.upgrade(cfg, "head")
