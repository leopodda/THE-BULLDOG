# Portal Comercial The Bulldog — V1

> **Repositório privado.** Contém dados comerciais e de clientes. Não tornar público.
>
> - Protótipo funcional (Python/FastAPI): raiz deste repositório.
> - **Pacote para reconstruir no Lovable** (React + Supabase): pasta [`lovable/`](lovable/LEIA-ME.md).

Portal web mobile-first para pedidos B2B do energético The Bulldog em SP.
**Cria PEDIDOS no Bling. Não emite NF-e, não gera contas a receber, não lança estoque.**
O back-office confere e fatura manualmente no Bling.

- **Cliente/PDV:** login próprio, pede energético em caixas (Tradicional / Zero Açúcar) e tabacaria (Smoking Line) em displays, vê resumo com bônus, envia e acompanha.
- **Vendedor:** busca/cadastra cliente (CNPJ, IE + indicador, endereço), faz pedido em nome do cliente.
- **Admin (back-office):** confere cadastros, acompanha/reprocessa envio ao Bling, configura preço, campanha, conexões ERP e usuários.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.11+ · FastAPI · SQLAlchemy 2 · Alembic |
| Banco | SQLite (local) · PostgreSQL (produção) |
| Frontend | HTML/CSS/JS puro em `frontend/` (sem build), só chama `/api` do portal |
| ERP | Adapter em `app/erp/` — modos `disabled`, `mock`, `bling` (API v3 OAuth) |
| Testes | pytest + respx (HTTP do Bling simulado) |

## Ver a demonstração (sem programar)

- **Windows:** dois cliques em `rodar-demo-windows.bat`.
- **Mac/Linux:** dois cliques em `rodar-demo.command`.

O script instala o necessário, cria dados de teste e abre http://localhost:8000. Logins (senha `bulldog123`): `admin@demo.local`, `vendedor@demo.local`, `pdv@demo.local`. Bling simulado: nenhum pedido sai para o Bling real.

## Rodar localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.cli gen-keys          # cole APP_SECRET_KEY e APP_ENCRYPTION_KEY no .env
# defina SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD (e SEED_DEMO_PASSWORD se quiser demo) no .env
alembic upgrade head                # cria o schema
python -m app.cli seed --demo       # tenant DFJ, 2 produtos, R$ 5,90, campanha 10+1, conexões ERP
uvicorn app.main:create_app --factory --reload --port 8000
```

Abra http://localhost:8000. Com `--demo`: `vendedor@demo.local` e `pdv@demo.local` (senha = `SEED_DEMO_PASSWORD`).
Documentação da API (fora de produção): http://localhost:8000/api/docs

Testes: `pytest -q`

## Regras comerciais (camada `app/domain/pricing.py`, independente do ERP)

- Venda **só em caixa fechada**; 1 caixa = 24 latas (`products.units_per_case`). O backend converte para latas (`UN`) ao enviar ao Bling.
- Preço comercial: **R$ 5,90/lata = R$ 141,60/caixa** (tabela `price_rules`; cliente > canal > geral). Sugerido ao consumidor R$ 9,90 (só informativo).
- Campanha **10+1** (`campaigns`): bônus nunca cobrado; cumulativo por padrão; sabor do bônus escolhido pelo cliente ou, no automático, o de mais caixas; limite opcional de pedidos com bônus por UF/cidade.
- Pagamento **sugerido** por número do pedido do cliente: 1º = 50% + 50% em 28 dias; 4º em diante = 30/60; 2º e 3º = "a definir pelo back-office". Nada vira parcela no Bling.
- Frete (informativo): sempre a combinar; sem frete grátis por caixas (pode ser religado no admin). Frete por conta no Bling: 3 (transporte próprio da DFJ). Prazo: 3–5 dias úteis SP; 7–15 demais.
- Tudo editável em **Admin → Comercial**.

## Tabacaria (Smoking Line)

- 25 itens. Vendidos por **display fechado** (`TB-IMP-0XX-D`, 1 display = 1 UN no Bling), **exceto MaryMill e Zippo, vendidos por unidade** (`TB-IMP-023-U` e `TB-IMP-025-D`, que no Bling já é 1 unidade). O MaryMill em display (`TB-IMP-023-D`) fica inativo no portal.
- Preço = **atacado** do *Catálogo da Distribuidora* de 30/09/2026 (por display, ou por unidade no MaryMill/Zippo). A "referência online" do catálogo **não entra no sistema** (é só sugestão de revenda e não afeta a compra). Editáveis em **Admin → Comercial → Produtos**.
- **Sem campanha 10+1** (a campanha vale só para o energético) e frete "a combinar".
- Carrinho com energético + tabacaria gera **dois pedidos** (dois números BD-…), um por linha, porque cada linha sai em nota própria (energético com ICMS-ST; tabacaria sem ST e com IPI destacado). Para o pagamento sugerido, conta como **uma** compra.
- No Bling, o pedido da tabacaria usa a natureza `operation_nature_id_tabacaria`. Ela **nunca herda** a natureza do energético; se não estiver definida, o pedido vai sem natureza e o back-office escolhe.
- A linha inteira pode ser desligada em **Admin → Comercial → Linhas vendidas no portal** (sem apagar preços nem pedidos) — por exemplo, enquanto a contabilidade não libera a venda.

## Fotos dos produtos

Ficam em `frontend/produtos/<SKU>.webp` (240×240, fundo transparente), geradas a partir da pasta do Drive *Produtos_Fotos_SEM_FUNDO*. Para trocar ou incluir uma foto, salve o arquivo com o SKU como nome; produto sem arquivo aparece sem foto.

## Fluxo do pedido

1. PDV usa o próprio cadastro (o backend ignora/recusa outro `customer_id`); vendedor escolhe o cliente.
2. Quantidades em caixas → `POST /api/orders/quote` calcula preço, bônus, pagamento e frete no servidor.
3. Confirmação envia `POST /api/orders` com cabeçalho `Idempotency-Key` (gerado na tela de revisão). Mesma chave = mesmo pedido, sem duplicar.
4. Pedido é **gravado primeiro no banco do portal** (número `BD-000001`…) e um job `push_order` é enfileirado.
5. Job (em background, ou `python -m app.cli process-jobs`): garante o contato no Bling (procura por CNPJ; cria se não existir), procura pedido com `numeroLoja` = número do portal (evita duplicar após timeout), cria o Pedido de Venda na situação configurada (padrão: **21 – Em digitação**) e guarda ID/número do Bling.
6. Falha do Bling **não apaga o pedido**: fica `integration_status = erro` com a mensagem; erro transitório (429/5xx/rede) é retentado com backoff (até 5 vezes); erro de validação para e espera correção. Admin pode **Reprocessar** no detalhe do pedido.
7. `python -m app.cli sync-status` (ou botão "Sincronizar status") lê a situação no Bling e atualiza o status do portal pelo `status_map`.

Status do portal: `recebido`, `enviado_erp`, `em_conferencia`, `aprovado`, `faturado`, `cancelado` — próprios, mapeados das situações do Bling por configuração.

## Arquitetura

```
frontend/  (SPA)  ──/api──▶  app/api/*  ──▶  app/domain/* (clientes, preço, pedidos, eventos)
                                              │
                                              └──▶ app/erp/jobs.py ──▶ adapter (mock | bling)
                                                                        └─ app/erp/mapping.py (JSON Bling v3)
```

- **Tokens só no backend.** `client_id/secret` vêm de variáveis `<PREFIXO>_CLIENT_ID/_SECRET`; o banco guarda só o prefixo. Access/refresh token ficam **criptografados** (Fernet, `APP_ENCRYPTION_KEY`) e nunca saem na API (há teste para isso).
- **UUID interno** em todas as tabelas. IDs externos ficam em `external_refs (connection_id, entity_type, entity_id, external_id, external_number)` — por **conexão**, então IDs da conta ST Nicolas e da conta DFJ nunca se misturam. `entity_type`: `customer`, `order`, `product`, `seller`, e futuramente `invoice`, `rd_contact`, `rd_deal`.
- **Event log** (`events`): `customer.created/updated/validated/erp_linked`, `order.created/erp_sent/erp_failed/status_changed/erp_retry_requested`, `user.*`, `erp.*`, `pricing.changed`. É a base para integrar RD Station depois (outbox).
- **Segurança:** sessão em cookie `httpOnly` + `SameSite=Lax`; requisições que alteram estado exigem o cabeçalho `X-Portal-Request: 1` (anti-CSRF); CSP restritiva; bcrypt; limite de tentativas de login; PDV não acessa lista de clientes nem dados de integração.

## Conta Bling: DFJ (quem fatura em SP)

Desde 08/10/2026 o seed cria a conexão **DFJ ativa** (modo simulado), já com os IDs dos 28 produtos lidos no Bling da DFJ. A conexão ST Nicolas fica cadastrada, **desativada**.

Para ligar o envio real:
1. No Bling: Central de Extensões → Área do Integrador → criar aplicativo (escopos: contatos, pedidos de venda, produtos, situações, naturezas de operação; **sem NF-e**). Link de redirecionamento = `BLING_REDIRECT_URI`.
2. No servidor: `BLING_DFJ_CLIENT_ID` e `BLING_DFJ_CLIENT_SECRET`; reiniciar.
3. **Admin → Integração → DFJ → Conectar ao Bling** (usuário admin da DFJ).
4. Preencher, quando a Itamaraty definir: natureza do energético, natureza da tabacaria (nunca a mesma), tipo de contato "Cliente", frete por conta, valor técnico.
5. Só então mudar o modo para **Bling real**.

### Campos deixados configuráveis (preencher após diagnóstico da conta DFJ)

| Configuração | Hoje | Observação |
|---|---|---|
| `operation_nature_id` (natureza/CFOP do energético) | vazio, não enviado | Define ST/CFOP da nota. Contabilidade. |
| `operation_nature_id_tabacaria` | vazio, não enviado | Natureza da Smoking Line (sem ST; consignação ou venda conforme o modelo DFJ). |
| `warehouse_id` (depósito) | vazio | Guardado; V1 não lança estoque. |
| `order_initial_status_id` | 21 (ST) | Confirmar ID na DFJ. |
| `product_external_ids` | ST: 16647367802 / 16647367813 + 25 displays `-D` | IDs na DFJ. |
| `payment_method_ids` | vazio | V1 não gera parcelas. |
| `freight_payer_code` | não enviado | `fretePorConta` da NF-e. |
| `technical_price_mode` / `technical_unit_price_overrides` | `commercial` (envia 5,90) | Se a DFJ precisar do valor-base antes de ST, use `override` por SKU. A UI e a regra comercial não mudam. |
| `bonus_line_mode` / `bonus_technical_unit_value` | item separado, valor 0 | Tratamento fiscal da bonificação (CFOP 5.910?) depende da contabilidade. |
| `send_pending_customers` | sim | Cliente pendente de conferência vai ao Bling com alerta nas observações internas. |
| credencial OAuth | `BLING_DFJ_*` | Definir quem é o usuário dono da autorização. |

## Operação

- Cron sugerido: `*/5 * * * * python -m app.cli process-jobs` e `*/15 * * * * python -m app.cli sync-status`.
- Limite do Bling: ~3 req/s e 120.000/dia por conta; o cliente espaça chamadas e faz backoff em 429.
- Token de acesso dura ~6 h e é renovado sozinho; se o refresh token expirar (~30 dias sem uso) ou for revogado, use **Reautorizar no Bling**.
- Produção: HTTPS, `APP_ENV=production`, `APP_COOKIE_SECURE=true`, PostgreSQL, `alembic upgrade head` a cada deploy.

## O que a V1 NÃO faz (de propósito)

Emitir NF-e · gerar parcelas/contas a receber · lançar ou reservar estoque · bloquear por estoque · desconto livre · pessoa física · lata avulsa · unidade/pack avulso da Smoking Line · integração RD Station · busca automática de CEP/CNPJ (exigiria liberar chamadas externas na CSP).

## Testes cobertos

Caixa → 24 latas · preço R$ 5,90 / R$ 141,60 · bônus 10+1 sem cobrança (cumulativo, sabor, limite regional) · pagamento e frete sugeridos · dígito do CNPJ e regra de IE · duplicidade por CNPJ completo (filial com mesma raiz é permitida) · idempotência · PDV só pede para si · falha do ERP mantém pedido e reprocessa · reenvio não duplica no Bling · payload real Bling v3 (contato e pedido) · renovação de token · erro de validação do Bling · troca ST → DFJ por configuração · API não expõe tokens · CSRF · migration Alembic.
