from app.domain.documents import is_valid_cnpj, normalize_ie
from tests.conftest import VALID_CUSTOMER, make_client


def test_cnpj_digito_verificador():
    assert is_valid_cnpj("11.222.333/0001-81")
    assert is_valid_cnpj("68163961000150")  # DFJ
    assert not is_valid_cnpj("11.222.333/0001-82")
    assert not is_valid_cnpj("11111111111111")
    assert not is_valid_cnpj("123")


def test_indicador_ie_estrutural():
    assert normalize_ie(1, "110.042.490.114") == ("110042490114", None)
    assert normalize_ie(1, "")[1] is not None
    assert normalize_ie(1, "ISENTO")[1] is not None  # caso real da NF 000005 rejeitada
    assert normalize_ie(2, "qualquer") == ("ISENTO", None)
    assert normalize_ie(9, "123") == (None, None)
    assert normalize_ie(5, None)[1] is not None


def test_vendedor_cadastra_cliente_pendente_de_conferencia(app, tenant, seller):
    c = make_client(app, "seller@test.local")
    r = c.post("/api/customers", json=VALID_CUSTOMER)
    assert r.status_code == 201, r.text
    body = r.json()["customer"]
    assert body["cnpj"] == "11222333000181"
    assert body["validation_status"] == "pendente_conferencia"
    assert body["assigned_seller_id"] == seller.id


def test_duplicidade_por_cnpj_completo(app, tenant, seller):
    c = make_client(app, "seller@test.local")
    assert c.post("/api/customers", json=VALID_CUSTOMER).status_code == 201
    # mesmo CNPJ com outra pontuação -> 409 com o cliente existente
    dup = dict(VALID_CUSTOMER, cnpj="11222333000181", razao_social="Outro Nome")
    r = c.post("/api/customers", json=dup)
    assert r.status_code == 409
    assert r.json()["detail"]["customer"]["razao_social"] == "BAR DO TESTE LTDA"
    chk = c.get("/api/customers/check-cnpj", params={"cnpj": "11.222.333/0001-81"}).json()
    assert chk["valid"] and chk["exists"]


def test_filial_com_mesma_raiz_nao_e_duplicada(app, tenant, seller):
    c = make_client(app, "seller@test.local")
    assert c.post("/api/customers", json=dict(VALID_CUSTOMER, cnpj="51527924000181")).status_code == 201
    # mesma raiz, outra filial (caso MORE IPANEMA no Bling ST)
    assert c.post("/api/customers", json=dict(VALID_CUSTOMER, cnpj="51527924000262")).status_code == 201


def test_cadastro_rejeita_cnpj_invalido_e_ie_faltando(app, tenant, seller):
    c = make_client(app, "seller@test.local")
    assert c.post("/api/customers", json=dict(VALID_CUSTOMER, cnpj="11222333000182")).status_code == 422
    r = c.post("/api/customers", json=dict(VALID_CUSTOMER, ie=""))
    assert r.status_code == 422 and "Inscrição Estadual" in r.json()["detail"]


def test_cliente_pdv_nao_acessa_lista_de_clientes(app, db, tenant, seller):
    from app.models import Customer, Role, User
    from app.security import hash_password
    from tests.conftest import PASSWORD
    s = make_client(app, "seller@test.local")
    cid = s.post("/api/customers", json=VALID_CUSTOMER).json()["customer"]["id"]
    db.add(User(tenant_id=tenant.id, role=Role.CUSTOMER, name="PDV", email="pdv@test.local", password_hash=hash_password(PASSWORD), customer_id=cid))
    db.commit()
    p = make_client(app, "pdv@test.local")
    assert p.get("/api/customers").status_code == 403
    assert p.post("/api/customers", json=dict(VALID_CUSTOMER, cnpj="68163961000150")).status_code == 403
