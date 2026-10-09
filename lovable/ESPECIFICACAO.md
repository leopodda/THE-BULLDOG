# Portal Comercial The Bulldog — Especificação V1

> Documento-fonte para reconstruir o portal no Lovable (React + Supabase).
> Consolida tudo o que foi decidido até 08/10/2026. Onde houver conflito com outro documento, vale este.

---

## 1. O que é

Portal web **mobile-first** para pedidos B2B da The Bulldog em São Paulo:

- **Cliente/PDV** (bar, tabacaria, posto…) entra com login próprio e faz o próprio pedido.
- **Vendedor** busca ou cadastra um cliente e faz o pedido em nome dele.
- **Admin (back-office)** confere cadastros e pedidos, configura preços, campanha e integração.

O portal **cria PEDIDOS no Bling**. **Não emite NF-e, não gera contas a receber, não lança estoque.** O back-office confere e fatura manualmente no Bling.

A operação de SP é faturada pela **DFJ** (decidido em 08/10/2026; o estoque já foi enviado pela ST à DFJ em **consignação mercantil**, NFs 000020 e 000021). **O portal conecta somente a conta Bling da DFJ.** A ST Nicolas não recebe pedidos do portal. **Tudo que é do Bling continua configurável por conta**, sem nada fixo no código.

---

## 2. Visual

- **Layout branco**, limpo, pensado para celular (largura ~390 px primeiro).
- **Logo:** só o bulldog dentro do círculo azul, sem textos (`assets/bulldog.svg`). Aparece no topo de todas as telas, maior na tela de login, e como ícone da aba.
- Cores tiradas do logo:
  - vermelho `#dd1731` (botões principais)
  - azul `#3458b0`
  - amarelo `#fddf03` (selo "BÔNUS")
  - texto `#141414`
  - cinza de apoio `#6b6760`
  - bordas `#e4e0d8`
  - fundo de campos `#f5f3ee`
- **Foto de cada produto** ao lado do nome (`assets/produtos/<SKU>.webp`, 240×240, fundo transparente). Aparece no catálogo, no resumo do pedido, no detalhe do pedido e no admin.
- Botão fixo no rodapé do celular com o total e "Revisar pedido".
- Telas de referência do protótipo em `referencia/telas/`.

---

## 3. Perfis e permissões

| Perfil | Pode | Não pode |
|---|---|---|
| **Cliente/PDV** (`customer`) | Ver o próprio cadastro; fazer pedido **só para si**; ver os próprios pedidos e status | Ver outros clientes; ver dados de integração/Bling (exceto o nº do pedido no Bling) |
| **Vendedor** (`seller`) | Buscar clientes; cadastrar cliente novo; editar clientes que ele cadastrou; fazer pedido para qualquer cliente; ver pedidos que criou ou dos clientes dele | Conferir cadastro; mexer em preço/integração/usuários |
| **Admin** (`admin`) | Tudo: conferir cadastros, reprocessar envio ao Bling, preços, campanha, produtos, integração, usuários, histórico | — |

- O login de um cliente/PDV é **vinculado a um cadastro de cliente** (CNPJ).
- Usuário criado pelo admin recebe senha provisória e **troca no primeiro acesso**.
- **Regra de segurança:** no Supabase, isso precisa ser garantido por **RLS** (Row Level Security), não só escondendo botões. Um PDV não pode conseguir ler outro cliente nem pela API.

---

## 4. Catálogo

27 produtos em `dados/produtos.csv` / `dados/produtos.json`.

### 4.1 Energético (linha `energetico`)
- **Tradicional** (`DRINK-TRAD-269`) e **Zero Açúcar** (`DRINK-ZERO-269`), lata 269 ml.
- Na interface o nome é "Tradicional", não "Original".
- **Vendido só em caixa fechada de 24 latas.** Não existe lata avulsa.
- Preço: **R$ 5,90 por lata = R$ 141,60 por caixa**, igual para os dois sabores.
- Preço sugerido ao consumidor: R$ 9,90 por lata. É só informativo e aparece no catálogo.

### 4.2 Tabacaria / Smoking Line (linha `tabacaria`)
- 25 itens, vendidos por **display fechado**, **exceto MaryMill e Zippo, vendidos por UNIDADE**.
- Preço = **atacado** do *Catálogo da Distribuidora* de 30/09/2026 (coluna `preco_unitario_venda` do CSV).
- A **"referência online" do catálogo NÃO entra no sistema**: é só sugestão de revenda e não importa na compra.
- O cartão de cada item mostra: foto, nome, "Display com N un" (ou "Vendido por unidade"), código, preço "/ display" ou "/ un", e o stepper de quantidade.

### 4.3 Tela de pedido
- Duas abas no topo: **Energético** | **Tabacaria (Smoking Line)**.
- Stepper (− quantidade +) em cada produto.
- O resumo recalcula a cada mudança. **O cálculo é sempre feito no servidor.**

---

## 5. Regras comerciais

### 5.1 Campanha 10+1 (só energético)
- **A cada 10 caixas de energético pagas, ganha 1 caixa de bônus.**
- **Cumulativo:** 20 caixas dão 2 bônus.
- Soma os dois sabores para contar (ex.: 6 Tradicional + 4 Zero = 10 → 1 bônus).
- **A caixa bônus nunca é cobrada.**
- O cliente escolhe o sabor do bônus. Se não escolher, vai o sabor com mais caixas no pedido.
- Itens da **tabacaria não contam** para a campanha e **não podem ser bônus**.
- Limite configurável de "primeiros pedidos de cada região": região = nenhuma, UF ou cidade, mais o número máximo de pedidos com bônus por região. Hoje está **sem limite**, porque a regra ainda não foi definida.
- Mensagens:
  - abaixo do mínimo: "Lançamento 10+1: faltam X caixa(s) para ganhar bônus."
  - ao atingir: "Lançamento 10+1: N caixa(s) de bônus."

### 5.2 Pagamento sugerido (informativo; não gera parcelas)
Conforme o número da **compra** do cliente:
- 1ª compra: **50% na compra + 50% em 28 dias**
- 2ª e 3ª compra: **"A definir pelo back-office"**
- da 4ª em diante: **30/60 dias**

Meios aceitos, que o cliente escolhe como preferência: **Pix, Boleto, Transferência**.

Um carrinho que gera dois pedidos (energético + tabacaria) conta como **uma** compra.

### 5.3 Frete e prazo (informativo)
- **Energético:**
  - frete grátis a partir de **100 caixas em SP** ou **200 caixas fora de SP**
  - abaixo disso: "Frete a combinar com o back-office. Faltam X caixas para frete grátis."
- **Tabacaria:** "Frete da tabacaria a combinar com o back-office."
- **Prazo:** **3 a 5 dias úteis em SP**; 7 a 15 dias nos demais estados.

### 5.4 Pedido dividido por linha
Se o carrinho tem energético **e** tabacaria, o portal cria **dois pedidos** (dois números `BD-000123`), um por linha, porque cada linha sai em nota fiscal própria:
- energético com ICMS-ST
- tabacaria sem ST e com IPI destacado

O resumo avisa isso antes de confirmar, e a confirmação mostra os dois números.

### 5.5 Sem desconto livre
Vendedor e cliente não alteram preço. Preço especial por cliente ou por canal só via tabela de preço configurada pelo admin. O modelo de dados prevê isso; a V1 usa um preço geral por linha/produto.

---

## 6. Cadastro de cliente

**Só pessoa jurídica (CNPJ) na V1.**

| Campo | Regra |
|---|---|
| CNPJ | obrigatório; validar dígito verificador; guardar só dígitos; máscara 00.000.000/0000-00 |
| Indicador de IE | 1 = Contribuinte ICMS · 2 = Contribuinte isento · 9 = Não contribuinte |
| Inscrição Estadual | obrigatória se indicador = 1 (não pode ser "ISENTO"); indicador 2 grava "ISENTO"; indicador 9 deixa vazio |
| Razão social | obrigatória (gravar em maiúsculas) |
| Nome fantasia | opcional |
| Responsável/contato | opcional |
| Telefone / WhatsApp | ao menos um |
| E-mail / **E-mail NF-e** | e-mail NF-e obrigatório |
| CEP, logradouro, número, complemento, bairro, cidade, UF | todos obrigatórios, exceto complemento |
| Canal | bar, balada, tabacaria, posto, mercado, adega, distribuidor, evento, outro |

Outras regras do cadastro:
- **Duplicidade pelo CNPJ completo (14 dígitos)**, nunca pela raiz: matriz e filial são clientes diferentes.
  - Ao sair do campo CNPJ, o sistema avisa se já existe e mostra link para o cadastro existente.
- Todo cliente cadastrado pelo vendedor nasce **"Pendente de conferência"**. O admin marca **Conferido** ou **Rejeitado**, com nota.
  - Cliente **rejeitado** não pode fazer pedido.
  - Se o vendedor alterar dados fiscais (CNPJ, IE, endereço), o cliente volta para pendente.
- **Não inventar validação fiscal de IE.** Ela fica para o back-office, no Cadesp/Sintegra.
  - IE errada já causou rejeição de NF-e (NF 000005).
  - A IE **não aparece no cartão CNPJ**: consulta-se no Cadesp (cadesp.fazenda.sp.gov.br) ou no CCC.

---

## 7. Fluxo do pedido

1. PDV usa o próprio cadastro; vendedor escolhe o cliente.
2. Escolhe quantidades. O servidor calcula preço, bônus, pagamento sugerido e frete.
3. **Revisão:** resumo por linha, sabor do bônus, meio de pagamento preferido, observações.
4. **Confirmar** envia com uma **chave de idempotência** gerada na revisão. Reenviar o mesmo carrinho (clique duplo, internet caindo) **não duplica** o pedido.
5. O pedido é **gravado primeiro no banco do portal**, com número próprio `BD-000001…`.
6. Se a integração estiver ligada, um **job** envia ao Bling:
   - procura o contato pelo CNPJ e cria se não existir
   - procura pedido com `numeroLoja` = número do portal (para não duplicar depois de um timeout)
   - cria o Pedido de Venda na situação configurada (**21 = "Em digitação"**, situação padrão do Bling; conferir na conta da DFJ ao conectar)
   - guarda o ID e o número do Bling
7. **Se o Bling falhar, o pedido NÃO é apagado.**
   - Fica "Erro no Bling" com a mensagem do erro.
   - Erro temporário (429, 5xx, rede) tenta de novo com espera crescente, até 5 vezes.
   - Erro de validação para e espera correção.
   - O admin tem botão **"Reprocessar envio ao Bling"**.
8. **Nada de NF-e.** O back-office confere e fatura no Bling.
9. Um processo periódico (ou botão "Sincronizar status") lê a situação no Bling e atualiza o status do portal.

**Status do portal** (próprios; mapeados das situações do Bling por configuração):

| Status | Situações Bling (conta ST) |
|---|---|
| `recebido` | — |
| `enviado_erp` ("Em conferência") | 21 |
| `em_conferencia` | 6, 15 |
| `aprovado` | 24, 18 |
| `faturado` | 9 |
| `cancelado` | 12 |

**Status da integração:** `nao_requerida` (integração desligada), `pendente`, `sucesso`, `erro`.

---

## 8. Integração Bling (API v3)

### 8.1 Arquitetura obrigatória no Lovable/Supabase
- **Toda chamada ao Bling roda numa Supabase Edge Function.** O navegador nunca fala com o Bling.
- `client_id`, `client_secret`, access token e refresh token ficam **só no servidor**:
  - credenciais em Supabase Secrets
  - tokens criptografados em tabela acessível só pela service role
- **A API e as telas nunca devolvem tokens.**
- OAuth 2.0 authorization code. A tela de admin tem o botão "Conectar ao Bling", com `state` assinado para evitar CSRF no retorno.
- Access token dura ~6 h e é renovado sozinho pelo refresh token (~30 dias). Em 401, renova uma vez e tenta de novo.
- Limite: ~3 requisições/s e 120.000/dia. Espaçar as chamadas e fazer backoff em 429.

### 8.2 Conexões por conta (ativa: DFJ)
Tabela `erp_connections`: uma por conta Bling, **só uma ativa**. Campos:
- modo: desligada / simulada / Bling real
- prefixo das credenciais
- tokens (criptografados)
- configurações (tabela abaixo)

Situação da conta Bling da **DFJ**, lida em 08/10/2026:

| Configuração | DFJ |
|---|---|
| IDs dos 27 produtos | **OK** — coluna `bling_id_conta_dfj` de `produtos.csv` (mesmos SKUs do portal; preços conferidos) |
| Unidade no Bling | energético em UN = 1 lata (portal envia caixas ×24); tabacaria "-D" = 1 UN = 1 display; MaryMill `TB-IMP-023-U` = 1 unidade |
| Estoque | entrou por "Entrada em consignação mercantil" (NFs 000020/000021 da ST); MaryMill já desmembrado (24 un., display zerado) |
| Depósito | só existe "Geral" (padrão) — não precisa enviar |
| Situação inicial do pedido | 21 (Em digitação) — conferir via API ao conectar |
| Tipo de contato "Cliente" | buscar via API ao conectar (`GET /contatos/tipos`) |
| "Gerar NF-e ao incluir pedido" | **desativado** na DFJ (correto) |
| Natureza de operação — energético | **PENDENTE (Itamaraty)** — ver observação abaixo |
| Natureza de operação — tabacaria | **PENDENTE (Itamaraty)**. **Nunca herdar a do energético.** |
| Caixa bônus | item separado, valor 0; existe a natureza "Saída em bonificação" na DFJ, uso a confirmar com a Itamaraty |
| Frete por conta (`fretePorConta`) | PENDENTE |
| Vendedores | nenhum cadastrado (opcional) |
| Formas de pagamento | não usadas na V1 |
| Valor técnico do item | igual ao preço de tabela, salvo orientação da Itamaraty sobre ICMS-ST |
| Enviar cliente pendente de conferência | sim (com alerta nas observações internas) |

**Atenção às naturezas da DFJ:** a natureza **padrão de venda** da conta é "Venda de mercadoria a **não contribuinte**", que é errada para bares e tabacarias com IE. Por isso o portal **sempre envia a natureza configurada por linha** e, sem configuração, segura o pedido na fila com erro claro. Também não existe na DFJ uma natureza específica de "venda de mercadoria recebida em consignação"; a Itamaraty precisa dizer qual usar (ou criar).

A conexão "ST Nicolas" pode existir cadastrada, **desativada**, só como histórico.

**IDs externos** ficam numa tabela `external_refs (connection_id, entity_type, entity_id, external_id, external_number)`, ligados à conexão. Assim os IDs da ST e da DFJ nunca se misturam. A chave primária de tudo no portal é **UUID próprio**, nunca o ID do Bling.

### 8.3 Payload do Pedido de Venda (`POST /pedidos/vendas`)
```json
{
  "numeroLoja": "BD-000123",
  "data": "2026-10-08",
  "contato": {"id": 555},
  "situacao": {"id": 21},
  "itens": [
    {"produto": {"id": 16647367802}, "codigo": "DRINK-TRAD-269", "descricao": "...", "unidade": "UN", "quantidade": 240, "valor": 5.90},
    {"produto": {"id": 16647367802}, "codigo": "DRINK-TRAD-269", "descricao": "... - BONIFICAÇÃO", "unidade": "UN", "quantidade": 24, "valor": 0}
  ],
  "observacoes": "Pedido do portal BD-000123. <obs do cliente>",
  "observacoesInternas": "Linha: ENERGÉTICO. Origem: portal (vendedor). ... Pagamento sugerido ... CONFIRMAR antes de faturar. ATENÇÃO: CLIENTE PENDENTE DE CONFERÊNCIA ..."
}
```
- **Caixas são convertidas em latas** (1 cx = 24 UN). Display e unidade da tabacaria: 1 = 1 UN.
- **Sem `parcelas`** na V1.
- Opcionais, só se configurados: `naturezaOperacao` (por linha), `loja`, `vendedor`, `transporte.fretePorConta`.
- Antes de criar: `GET /pedidos/vendas?numerosLojas[]=BD-000123` para não duplicar.
- Se a situação devolvida for diferente da configurada: `PATCH /pedidos/vendas/{id}/situacoes/{idSituacao}`.

### 8.4 Contato (`POST /contatos`)
Campos enviados:
- `nome`, `fantasia`, `tipo: "J"`, `situacao: "A"`, `numeroDocumento` (só dígitos)
- `indicadorIe`, `ie`, `telefone`, `celular`, `email`, `emailNotaFiscal`
- `endereco.geral{endereco, numero, complemento, bairro, cep, municipio, uf}`
- `tiposContato:[{id}]`

Antes de criar: `GET /contatos?numeroDocumento=<cnpj>`.

---

## 9. Telas

1. **Login** — logo grande, e-mail, senha. Limite de tentativas.
2. **Minha conta** — dados e troca de senha (obrigatória no 1º acesso).
3. **Novo pedido**:
   - cabeçalho do cliente
   - abas Energético/Tabacaria
   - cartões com foto e stepper
   - selo da campanha
   - resumo
   - botão fixo "Revisar pedido"
4. **Revisão** — resumo por linha, aviso de pedido dividido, sabor do bônus, meio de pagamento, observações, "Confirmar e enviar pedido".
5. **Confirmação** — número(s) do pedido grande(s), botões "Acompanhar" e "Fazer outro pedido".
6. **Meus pedidos / Pedidos** — lista com número, status, linha, quantidade, total.
   - Equipe interna vê também o status da integração e o nº no Bling.
   - Filtros: "Com erro no Bling" e "Enviando".
7. **Detalhe do pedido** — itens com foto, totais, pagamento, frete, prazo, observações, nº no Bling.
   - Admin vê também: erro do Bling, botão reprocessar, histórico de eventos.
8. **Clientes** (vendedor/admin) — busca por nome, fantasia, cidade ou CNPJ, e botão "+ Novo cliente".
9. **Cliente** — dados e "Fazer pedido para este cliente". Admin: bloco "Conferência do cadastro" (Conferido / Voltar a pendente / Rejeitar + nota).
10. **Cadastro/edição de cliente** — formulário da seção 6, com aviso de CNPJ duplicado.
11. **Admin → Comercial**:
    - preço do energético por lata e preço sugerido
    - campanha: ativa, nome, compre X leve Y, cumulativo, região, limite
    - frete e prazos
    - linhas vendidas no portal (desligar a tabacaria com um clique, sem apagar nada)
    - produtos: ativo/inativo e preço de atacado de cada item da tabacaria
12. **Admin → Integração** — conexão Bling da DFJ (ativa, começa em modo simulado):
    - modo, prefixo de credenciais, IDs de produtos e vendedores, configurações da seção 8.2
    - botões "Conectar ao Bling", "Tornar ativa", "Sincronizar status", "Processar fila"
    - aviso dos campos ainda pendentes para a DFJ
13. **Admin → Usuários** — criar vendedor, cliente/PDV (vinculado a um cliente) ou admin; ativar/desativar.

---

## 10. Modelo de dados (Postgres/Supabase)

- `tenants` — operação (DFJ – SP) e configurações comerciais em JSON (frete, prazos, pagamento, linhas habilitadas).
- `profiles` / `users` — perfil (admin/seller/customer), nome, e-mail, ativo, `customer_id` (só PDV), `seller_type`, `commission_rate` (preparado, sem regra na V1), `must_change_password`.
- `customers` — campos da seção 6, `validation_status`, `validation_notes`, `assigned_seller_id`, `created_by`.
  - **Único por (tenant, CNPJ).**
- `products` — sku, nome, nome curto, **linha**, **unidade de venda** (caixa/display/unidade), unidades ERP por unidade de venda (24 ou 1), conteúdo da embalagem, ativo, ordem.
- `price_rules` — preço por unidade de venda; por produto, por linha, por canal ou por cliente; vigência.
  - Prioridade: cliente > canal > produto > linha.
- `campaigns` — nome, **linha** (energético), compre X, leve Y, cumulativo, escopo de região, limite por região, vigência, ativa.
- `orders`:
  - `order_number` (BD-000001, sequencial atômico)
  - `idempotency_key` e `checkout_key` (agrupa os pedidos do mesmo carrinho)
  - `product_line`, customer, seller, created_by, origem
  - status, status/erro de integração, conexão ERP
  - quantidades pagas e de bônus, total de unidades, total
  - campanha, chave de região, nº da compra do cliente
  - pagamento preferido e sugerido, frete, prazo, observações
  - status de conferência do cliente no momento do pedido
- `order_items` — snapshot de sku, nome, unidades por embalagem, quantidade, unidades, bônus, preço unitário, preço da embalagem, total da linha.
- `erp_connections` e `external_refs` — ver seção 8.
- `integration_jobs` — tipo, entidade, status (pending/running/success/error), tentativas, último erro, próxima tentativa.
- `events` — log de auditoria (quem, quando, ação, payload). Ações:
  - `customer.created`, `customer.updated`, `customer.validated`, `customer.erp_linked`
  - `order.created`, `order.erp_sent`, `order.erp_failed`, `order.status_changed`, `order.erp_retry_requested`
  - `user.*`, `erp.*`, `pricing.changed`, `products.changed`

  Serve de base para integrar o RD Station CRM no futuro.

Prever, sem implementar: `rdstation_contact_id` e `rdstation_deal_id` em `external_refs`.

---

## 11. Testes que precisam passar

**Regras comerciais:**
- 1 caixa = 24 latas no envio ao Bling.
- Preço R$ 5,90/lata e R$ 141,60/caixa.
- 10 caixas → 1 bônus, sem cobrar. 20 caixas → 2 bônus. 9 caixas → nenhum.
- Mix 6+4 → bônus no sabor com mais caixas, ou no escolhido.
- Tabacaria não ganha bônus nem conta para a campanha.
- Pagamento sugerido por nº da compra: 1 / 2–3 / 4+.
- Frete grátis com 100 cx em SP e 200 fora.

**Tabacaria:**
- Preço por display; MaryMill e Zippo por unidade.
- Carrinho misto vira 2 pedidos; a mesma chave devolve os mesmos 2.

**Cadastro e permissões:**
- CNPJ inválido é recusado; duplicado pelo CNPJ completo; filial com a mesma raiz é aceita.
- IE obrigatória no indicador 1.
- PDV só pede para si e não lê outros clientes. Testar a RLS também.

**Integração:**
- Falha do Bling mantém o pedido e permite reprocessar; reenvio não duplica no Bling.
- Tabacaria nunca herda a natureza do energético.
- API não expõe tokens.

---

## 12. Fora da V1 (de propósito)

- NF-e, parcelas e contas a receber, lançamento ou reserva de estoque, bloqueio por estoque
- desconto livre, pessoa física, lata avulsa, pack da tabacaria
- RD Station
- consulta automática de CNPJ/CEP (pode entrar logo depois)
