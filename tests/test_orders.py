import uuid

from sqlalchemy import select

from app.erp import jobs
from app.models import Customer, ErpConnection, ExternalRef, IntegrationJob, Order, Product, Role, User
from app.security import hash_password
from tests.conftest import PASSWORD, VALID_CUSTOMER, make_client


def _setup(app, db, tenant):
    s = make_client(app, "seller@test.local")
    cust = s.post("/api/customers", json=VALID_CUSTOMER).json()["customer"]
    prods = {p.sku: p.id for p in db.scalars(select(Product))}
    return s, cust, prods


def _order(client, prods, *, trad=0, zero=0, customer_id=None, key=None, **extra):
    items = [{"product_id": prods["DRINK-TRAD-269"], "cases": trad}, {"product_id": prods["DRINK-ZERO-269"], "cases": zero}]
    body = {"items": [i for i in items if i["cases"]], **extra}
    if customer_id:
        body["customer_id"] = customer_id
    return client.post("/api/orders", json=body, headers={"Idempotency-Key": key or str(uuid.uuid4())})


def test_vendedor_cria_pedido_em_caixas_e_converte_para_latas(app, db, tenant, seller):
    s, cust, prods = _setup(app, db, tenant)
    r = _order(s, prods, trad=3, zero=2, customer_id=cust["id"], payment_method="pix")
    assert r.status_code == 201, r.text
    o = r.json()["order"]
    assert o["order_number"] == "BD-000001"
    assert o["paid_cases"] == 5 and o["total_units"] == 120
    assert o["total_amount"] == "708.00"
    assert o["integration_status"] == "pendente"
    assert o["suggested_payment_terms"] == "50% na compra + 50% em 28 dias"
    assert {i["sku"]: i["units"] for i in o["items"]} == {"DRINK-TRAD-269": 72, "DRINK-ZERO-269": 48}


def test_idempotencia_mesma_chave_nao_duplica(app, db, tenant, seller):
    s, cust, prods = _setup(app, db, tenant)
    key = str(uuid.uuid4())
    r1 = _order(s, prods, trad=1, customer_id=cust["id"], key=key)
    r2 = _order(s, prods, trad=1, customer_id=cust["id"], key=key)
    assert r1.status_code == r2.status_code == 201
    assert r1.json()["order"]["id"] == r2.json()["order"]["id"]
    assert r2.json()["created"] is False
    assert db.scalar(select(Order).where(Order.checkout_key == key)) is not None
    assert len(list(db.scalars(select(Order)))) == 1
    assert len(list(db.scalars(select(IntegrationJob)))) == 1


def test_pdv_so_cria_pedido_para_si(app, db, tenant, seller):
    s, cust, prods = _setup(app, db, tenant)
    other = s.post("/api/customers", json=dict(VALID_CUSTOMER, cnpj="68163961000150", razao_social="Outro")).json()["customer"]
    db.add(User(tenant_id=tenant.id, role=Role.CUSTOMER, name="PDV", email="pdv@test.local", password_hash=hash_password(PASSWORD), customer_id=cust["id"]))
    db.commit()
    p = make_client(app, "pdv@test.local")
    assert _order(p, prods, trad=1, customer_id=other["id"]).status_code == 403
    r = _order(p, prods, trad=1)  # sem customer_id -> usa o próprio
    assert r.status_code == 201
    assert r.json()["order"]["customer"]["id"] == cust["id"]
    # PDV não vê dados de integração nem pedidos de outros
    assert "integration_status" not in r.json()["order"]
    _order(s, prods, trad=2, customer_id=other["id"])
    mine = p.get("/api/orders").json()["items"]
    assert len(mine) == 1 and mine[0]["customer"]["id"] == cust["id"]


def test_pedido_10_mais_1_sem_cobrar_bonus(app, db, tenant, seller):
    s, cust, prods = _setup(app, db, tenant)
    o = _order(s, prods, trad=6, zero=4, customer_id=cust["id"]).json()["order"]
    assert o["paid_cases"] == 10 and o["bonus_cases"] == 1
    assert o["total_amount"] == "1416.00"
    assert o["total_units"] == 264


def test_campanha_limitada_por_regiao(app, db, tenant, seller):
    from app.models import Campaign
    camp = db.scalar(select(Campaign))
    camp.region_scope, camp.max_orders_per_region = "uf", 1
    db.commit()
    s, cust, prods = _setup(app, db, tenant)
    assert _order(s, prods, trad=10, customer_id=cust["id"]).json()["order"]["bonus_cases"] == 1
    assert _order(s, prods, trad=10, customer_id=cust["id"]).json()["order"]["bonus_cases"] == 0


def test_envio_mock_cria_cliente_e_pedido_em_digitacao(app, db, tenant, seller):
    s, cust, prods = _setup(app, db, tenant)
    o = _order(s, prods, trad=10, customer_id=cust["id"]).json()["order"]
    done = jobs.process_pending(db)
    assert [j.status for j in done] == ["success"]
    db.expire_all()
    order = db.get(Order, o["id"])
    assert order.integration_status == "sucesso"
    assert order.status == "enviado_erp"
    ref = db.scalar(select(ExternalRef).where(ExternalRef.entity_type == "order", ExternalRef.entity_id == order.id))
    assert ref and ref.external_number and (ref.data or {}).get("status_id") == 21
    cref = db.scalar(select(ExternalRef).where(ExternalRef.entity_type == "customer", ExternalRef.entity_id == cust["id"]))
    assert cref is not None
    # reprocessar não duplica
    jobs.retry_order(db, order, db.get(ErpConnection, order.erp_connection_id), "x")
    jobs.process_pending(db)
    assert len(list(db.scalars(select(ExternalRef).where(ExternalRef.entity_type == "order")))) == 1


def test_falha_do_erp_nao_apaga_pedido_e_permite_reprocessar(app, db, tenant, seller):
    conn = db.scalar(select(ErpConnection).where(ErpConnection.is_active.is_(True)))
    conn.settings = {**conn.settings, "mock_fail": True}
    db.commit()
    s, cust, prods = _setup(app, db, tenant)
    o = _order(s, prods, trad=2, customer_id=cust["id"]).json()["order"]
    jobs.process_pending(db)
    db.expire_all()
    order = db.get(Order, o["id"])
    assert order is not None
    assert order.integration_status == "erro" and "Falha simulada" in order.integration_error
    job = db.scalar(select(IntegrationJob))
    assert job.status == "pending" and job.attempts == 1  # erro transitório: vai tentar de novo

    conn.settings = {**conn.settings, "mock_fail": False}
    db.commit()
    a = make_client(app, "admin@test.local")
    r = a.post(f"/api/admin/orders/{o['id']}/retry")
    assert r.status_code == 200, r.text
    assert r.json()["order"]["integration_status"] == "sucesso"
    actions = [e["action"] for e in r.json()["order"]["events"]]
    assert "order.created" in actions and "order.erp_failed" in actions and "order.erp_sent" in actions


def test_integracao_desligada_pedido_fica_local(app, db, tenant, seller):
    conn = db.scalar(select(ErpConnection).where(ErpConnection.is_active.is_(True)))
    conn.mode = "disabled"
    db.commit()
    s, cust, prods = _setup(app, db, tenant)
    o = _order(s, prods, trad=1, customer_id=cust["id"]).json()["order"]
    assert o["integration_status"] == "nao_requerida"
    assert not list(db.scalars(select(IntegrationJob)))


def test_troca_de_conta_st_para_dfj_por_configuracao(app, db, tenant, seller):
    a = make_client(app, "admin@test.local")
    erp = a.get("/api/admin/erp").json()
    dfj = next(c for c in erp["connections"] if c["label"].startswith("DFJ"))
    prods = {p["sku"]: p["id"] for p in erp["products"]}
    r = a.put(f"/api/admin/erp/connections/{dfj['id']}", json={
        "mode": "mock",
        "settings": {"order_initial_status_id": 77, "technical_price_mode": "override", "technical_unit_price_overrides": {"DRINK-TRAD-269": "4.20", "DRINK-ZERO-269": "4.20"}},
        "product_external_ids": {prods["DRINK-TRAD-269"]: "111", prods["DRINK-ZERO-269"]: "222"},
    })
    assert r.status_code == 200, r.text
    assert a.post(f"/api/admin/erp/connections/{dfj['id']}/activate").status_code == 200

    s, cust, _ = _setup(app, db, tenant)
    o = _order(s, prods, trad=1, customer_id=cust["id"]).json()["order"]
    jobs.process_pending(db)
    db.expire_all()
    order = db.get(Order, o["id"])
    assert order.erp_connection_id == dfj["id"]
    from app.erp import mock
    sent = mock._bucket(dfj["id"])["orders"][order.order_number]["raw"]["payload"]
    assert sent["situacao"] == {"id": 77}
    assert sent["itens"][0]["produto"] == {"id": 111}
    assert sent["itens"][0]["valor"] == 4.20 and sent["itens"][0]["quantidade"] == 24


def test_csrf_header_obrigatorio(app, tenant):
    from fastapi.testclient import TestClient
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": "admin@test.local", "password": PASSWORD})
    assert r.status_code == 403


# ------------------------------------------------------------------ tabacaria
def _tob(db, sku):
    return db.scalar(select(Product).where(Product.sku == sku))


def test_tabacaria_preco_por_display_do_catalogo(app, db, tenant, seller):
    s, cust, prods = _setup(app, db, tenant)
    filtro = _tob(db, "TB-IMP-001-D")
    zippo = _tob(db, "TB-IMP-025-D")
    cat = s.get(f"/api/catalog?customer_id={cust['id']}").json()
    by_sku = {p["sku"]: p for p in cat["products"]}
    assert len([p for p in cat["products"] if p["line"] == "tabacaria"]) == 25
    assert by_sku["TB-IMP-001-D"]["case_price"] == "220.66" and by_sku["TB-IMP-001-D"]["pack_contents"] == 34
    # MaryMill e Zippo: por unidade; demais: por display
    assert "TB-IMP-023-D" not in by_sku
    assert by_sku["TB-IMP-023-U"]["sale_unit"] == "unidade" and by_sku["TB-IMP-023-U"]["case_price"] == "119.90"
    assert by_sku["TB-IMP-025-D"]["sale_unit"] == "unidade" and by_sku["TB-IMP-025-D"]["case_price"] == "649.90"
    # referência online não existe no sistema
    assert all(p["suggested_retail_price"] is None for p in cat["products"] if p["line"] == "tabacaria")
    assert {p["sku"] for p in cat["products"] if p["sale_unit"] == "unidade"} == {"TB-IMP-023-U", "TB-IMP-025-D"}
    assert all(p["sale_unit"] == "display" for p in cat["products"] if p["line"] == "tabacaria" and p["sku"] not in ("TB-IMP-023-U", "TB-IMP-025-D"))
    assert by_sku["DRINK-TRAD-269"]["case_price"] == "141.60"  # energético intacto
    r = s.post("/api/orders", json={"customer_id": cust["id"], "items": [{"product_id": filtro.id, "cases": 2}, {"product_id": zippo.id, "cases": 1}]}, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert r.status_code == 201, r.text
    o = r.json()["order"]
    assert o["product_line"] == "tabacaria"
    assert o["total_amount"] == "1091.22"  # 2 x 220,66 + 649,90
    assert o["total_units"] == 3 and o["bonus_cases"] == 0


def test_tabacaria_nao_ganha_bonus_10_mais_1(app, db, tenant, seller):
    s, cust, prods = _setup(app, db, tenant)
    seda = _tob(db, "TB-IMP-016-D")
    q = s.post("/api/orders/quote", json={"customer_id": cust["id"], "items": [{"product_id": seda.id, "cases": 30}]}).json()["quote"]
    assert q["bonus_cases"] == 0 and q["campaign_message"] is None
    # 9 caixas de energético + 5 displays: não completa 10 caixas da campanha
    q = s.post("/api/orders/quote", json={"customer_id": cust["id"], "items": [{"product_id": prods["DRINK-TRAD-269"], "cases": 9}, {"product_id": seda.id, "cases": 5}]}).json()["quote"]
    assert q["bonus_cases"] == 0 and "faltam 1" in q["campaign_message"]
    # bônus não pode ir para a tabacaria
    r = s.post("/api/orders/quote", json={"customer_id": cust["id"], "items": [{"product_id": prods["DRINK-TRAD-269"], "cases": 10}], "bonus_product_id": seda.id})
    assert r.status_code == 422


def test_carrinho_misto_vira_dois_pedidos_e_idempotencia_devolve_os_dois(app, db, tenant, seller):
    s, cust, prods = _setup(app, db, tenant)
    seda = _tob(db, "TB-IMP-016-D")
    body = {"customer_id": cust["id"], "items": [{"product_id": prods["DRINK-TRAD-269"], "cases": 10}, {"product_id": seda.id, "cases": 3}]}
    key = str(uuid.uuid4())
    r1 = s.post("/api/orders", json=body, headers={"Idempotency-Key": key})
    r2 = s.post("/api/orders", json=body, headers={"Idempotency-Key": key})
    assert r1.status_code == r2.status_code == 201
    o1, o2 = r1.json()["orders"], r2.json()["orders"]
    assert [o["product_line"] for o in o1] == ["energetico", "tabacaria"]
    assert [o["id"] for o in o1] == [o["id"] for o in o2] and r2.json()["created"] is False
    energy, tob = o1
    assert energy["total_amount"] == "1416.00" and energy["bonus_cases"] == 1
    assert tob["total_amount"] == "300.00" and tob["bonus_cases"] == 0
    assert energy["suggested_payment_terms"] == tob["suggested_payment_terms"] == "50% na compra + 50% em 28 dias"
    assert len(list(db.scalars(select(Order)))) == 2
    # próxima compra conta como 2ª (o carrinho dividido foi UMA compra)
    q = s.post("/api/orders/quote", json={"customer_id": cust["id"], "items": [{"product_id": seda.id, "cases": 1}]}).json()["quote"]
    assert q["customer_order_index"] == 2


def test_pedido_tabacaria_no_bling_usa_natureza_propria(app, db, tenant, seller):
    from app.erp import mock
    conn = db.scalar(select(ErpConnection).where(ErpConnection.is_active.is_(True)))
    conn.settings = {**conn.settings, "operation_nature_id": 111, "operation_nature_id_tabacaria": 222}
    db.commit()
    s, cust, prods = _setup(app, db, tenant)
    seda = _tob(db, "TB-IMP-016-D")
    body = {"customer_id": cust["id"], "items": [{"product_id": prods["DRINK-ZERO-269"], "cases": 1}, {"product_id": seda.id, "cases": 2}]}
    orders = s.post("/api/orders", json=body, headers={"Idempotency-Key": str(uuid.uuid4())}).json()["orders"]
    jobs.process_pending(db)
    sent = {o["product_line"]: mock._bucket(conn.id)["orders"][o["order_number"]]["raw"]["payload"] for o in orders}
    assert sent["energetico"]["naturezaOperacao"] == {"id": 111}
    assert sent["tabacaria"]["naturezaOperacao"] == {"id": 222}
    item = sent["tabacaria"]["itens"][0]
    assert item["produto"] == {"id": 16717136788} and item["quantidade"] == 2 and item["valor"] == 100.0


def test_tabacaria_sem_natureza_propria_nao_herda_a_do_energetico(app, db, tenant, seller):
    from app.erp import mock
    conn = db.scalar(select(ErpConnection).where(ErpConnection.is_active.is_(True)))
    conn.settings = {**conn.settings, "operation_nature_id": 111}
    db.commit()
    s, cust, prods = _setup(app, db, tenant)
    seda = _tob(db, "TB-IMP-016-D")
    o = s.post("/api/orders", json={"customer_id": cust["id"], "items": [{"product_id": seda.id, "cases": 1}]}, headers={"Idempotency-Key": str(uuid.uuid4())}).json()["order"]
    jobs.process_pending(db)
    assert "naturezaOperacao" not in mock._bucket(conn.id)["orders"][o["order_number"]]["raw"]["payload"]


def test_admin_desliga_linha_tabacaria(app, db, tenant, seller):
    a = make_client(app, "admin@test.local")
    r = a.put("/api/admin/products", json={"items": [], "enabled_lines": ["energetico"]})
    assert r.status_code == 200, r.text
    s, cust, prods = _setup(app, db, tenant)
    cat = s.get(f"/api/catalog?customer_id={cust['id']}").json()
    assert {p["line"] for p in cat["products"]} == {"energetico"}
    seda = _tob(db, "TB-IMP-016-D")
    r = s.post("/api/orders/quote", json={"customer_id": cust["id"], "items": [{"product_id": seda.id, "cases": 1}]})
    assert r.status_code == 422


def test_admin_altera_preco_de_display(app, db, tenant, seller):
    a = make_client(app, "admin@test.local")
    seda = _tob(db, "TB-IMP-016-D")
    r = a.put("/api/admin/products", json={"items": [{"id": seda.id, "price": "105,50"}]})
    assert r.status_code == 200, r.text
    assert float(next(p for p in r.json()["items"] if p["id"] == seda.id)["price"]) == 105.5
    s, cust, prods = _setup(app, db, tenant)
    q = s.post("/api/orders/quote", json={"customer_id": cust["id"], "items": [{"product_id": seda.id, "cases": 2}]}).json()["quote"]
    assert q["total_amount"] == "211.00"


def test_marymill_por_unidade_vai_ao_bling_com_id_da_unidade(app, db, tenant, seller):
    from app.erp import mock
    s, cust, prods = _setup(app, db, tenant)
    mary = _tob(db, "TB-IMP-023-U")
    o = s.post("/api/orders", json={"customer_id": cust["id"], "items": [{"product_id": mary.id, "cases": 3}]}, headers={"Idempotency-Key": str(uuid.uuid4())}).json()["order"]
    assert o["total_amount"] == "359.70" and o["sale_unit"] == "unidade"
    jobs.process_pending(db)
    conn = db.scalar(select(ErpConnection).where(ErpConnection.is_active.is_(True)))
    item = mock._bucket(conn.id)["orders"][o["order_number"]]["raw"]["payload"]["itens"][0]
    assert item["produto"] == {"id": 16717305116} and item["quantidade"] == 3 and item["valor"] == 119.9


def test_todos_os_produtos_tem_foto(app, db, tenant, seller):
    s, cust, prods = _setup(app, db, tenant)
    cat = s.get(f"/api/catalog?customer_id={cust['id']}").json()
    sem_foto = [p["sku"] for p in cat["products"] if not p["image_url"]]
    assert sem_foto == []
    assert s.get(cat["products"][0]["image_url"]).status_code == 200
