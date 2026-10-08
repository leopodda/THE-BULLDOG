# RETORNO — Diagnóstico Bling para o Portal Comercial The Bulldog

**Empresa no Bling:** ST NICOLAS 22 BEBIDAS LTDA — CNPJ 62.544.833/0001-70 (contrato Bling desde 17/11/2025)
**Data da leitura:** 08/10/2026
**Método:** somente leitura via integração Bling (API v3 / MCP). Nenhum dado ou configuração foi alterado. Nenhum código foi escrito.

Legenda: **[CONFIRMADO NO BLING]** · **[RECOMENDAÇÃO TÉCNICA]** · **[DECISÃO DE NEGÓCIO PENDENTE]**

---

## RESUMO EXECUTIVO

1. **Não existe nenhum pedido de venda, proposta comercial ou conta a receber na conta.** [CONFIRMADO NO BLING] Toda a operação de saída até hoje (17 NF-e de saída, jun–out/2026) foi feita **emitindo NF-e diretamente**, sem pedido. Ou seja: o portal **não vai "reproduzir" um fluxo de pedido existente — ele vai inaugurar o módulo de Pedidos de Venda**. Isso muda o desenho: o fluxo pedido → nota precisa ser definido do zero.
2. **Catálogo vendável é pequeno e claro:** 2 SKUs de energético (`DRINK-TRAD-269`, `DRINK-ZERO-269`), unidade `UN` (lata), `itensPorCaixa = 24`. Os outros 96 produtos ativos são insumos, embalagens, serviços de industrialização e Smoking Line. [CONFIRMADO NO BLING]
3. **Não há tabela de preço, vendedor, condição de pagamento, forma de pagamento, transportadora ou logística configurados/usados.** O preço cadastrado é R$ 4,20 (base), mas o preço efetivamente faturado variou por cliente (R$ 5,20 a R$ 6,20 por lata no valor final da nota, com ST). [CONFIRMADO NO BLING]
4. **Cadastro de clientes é misturado e pouco padronizado:** 25 contatos ativos, dos quais só ~9 são clientes; os demais são fornecedores, contabilidade, sócio/pessoas e a matriz de Amsterdam. O campo "tipo de contato = Cliente" só está marcado em **1** contato. [CONFIRMADO NO BLING]
5. **Todo o histórico de vendas a cliente final é RJ (interestadual)**, enquanto a estratégia comercial é SP. As únicas notas para SP são as **remessas em consignação para a DFJ**. A regra fiscal de SP (ICMS-ST interno) ainda não foi exercitada em venda ao PDV no Bling. [CONFIRMADO NO BLING]
6. **Bloqueador principal:** o portal depende de decisões fiscais/comerciais que o Bling não responde (natureza de operação por cenário, quem é o vendedor da nota no modelo DFJ-representação, política de preço, condição de pagamento). Detalhes em "RISCOS / BLOQUEADORES".

---

## 1. PRODUTOS E ESTRUTURA DE VENDA

### 1.1 Produtos ativos
[CONFIRMADO NO BLING] 98 produtos ativos, 0 inativos, 0 excluídos. Todos `tipo = P`, `formato = S` (simples). Por categoria:

| Categoria (ID) | O que contém | Vai para o portal? |
|---|---|---|
| Energetico - Produto Acabado (14313306) | os 2 energéticos | **Sim** |
| Insumos - Producao Energetico (14313308) / sem código | açúcar, ácido cítrico, sucralose, premix, latas, tampas, aromas etc. (vários em duplicidade: com e sem código) | Não |
| Embalagens | caixa papelão, filme shrink, etiqueta, palete | Não |
| — | `INDUSTR BULLDOG TRADICIONAL` (16687578635) / `INDUSTR BULLDOG ZERO` (16687578636) — serviço de industrialização Praxis | Não |
| Tabacaria - Caixas Importacao (Venda Distribuidor) (14313303) | `TB-IMP-001` … `TB-IMP-025` (caixas fechadas de importação, preços R$ 422,90 a R$ 8.031,20) | Decisão pendente |
| Tabacaria - Displays (14313304) | `TB-IMP-0XX-D` (displays de PDV, R$ 33,90 a R$ 1.003,90) e `TB-IMP-023-U` (unidade) | Decisão pendente |

### 1.2 Original e Zero Açúcar
[CONFIRMADO NO BLING]

| Campo | Tradicional | Zero Açúcar |
|---|---|---|
| ID | 16647367802 | 16647367813 |
| Código (SKU) | `DRINK-TRAD-269` | `DRINK-ZERO-269` |
| Nome | The Bulldog Energy Drink Tradicional 269ml Lata | The Bulldog Energy Drink Zero Açúcar 269ml Lata |
| Situação | A (ativo) | A (ativo) |
| Unidade | `UN` | `UN` |
| Preço de venda | 4,20 | 4,20 |
| Preço de custo | 0 (não preenchido) | 0 (não preenchido) |
| itensPorCaixa | 24 | 24 |
| GTIN / GTIN embalagem | 0631430730405 / 0631430730405 | 0631430730412 / 0631430730412 |
| NCM / CEST / Origem | 2202.99.00 / 03.013.00 / 5 | 2202.99.00 / 03.013.00 / 5 |
| Peso líq./bruto | 0,269 / 0,3 kg | 0,269 / 0,3 kg |
| Estoque mín./máx. | 1.000 / 100.000 | 500 / 50.000 |
| Validade | 16/10/2027 | 16/10/2027 |
| Variações / composição | nenhuma | nenhuma |
| spedTipoItem | 04 | (vazio) |

Observação: o cadastro chama de **"Tradicional"**; o documento do portal chama de "Original". [DECISÃO DE NEGÓCIO PENDENTE] qual nome aparece para o cliente.

### 1.3 / 1.4 / 1.5 Unidade comercial, caixa e conversão
- [CONFIRMADO NO BLING] Unidade comercial = **lata (`UN`)**. Estoque e notas são em latas.
- [CONFIRMADO NO BLING] `itensPorCaixa = 24` está cadastrado, mas é **informativo** — não existe produto "caixa" nem conversão automática de unidade.
- [CONFIRMADO NO BLING] Nas notas emitidas, as quantidades foram sempre múltiplos de 24 (24, 48, 5.496, 5.544), mas **não há regra configurada** que obrigue isso.
- [CONFIRMADO NO BLING] O GTIN da embalagem é igual ao da lata (não há DUN-14 da caixa).
- [RECOMENDAÇÃO TÉCNICA] O portal vende em **caixas** na interface (1 cx = 24 latas) e envia ao Bling **em latas** (`quantidade = caixas × 24`, `unidade = UN`). Assim não é preciso criar produto "caixa" no Bling nem mexer no estoque.

### 1.6 Variações, kits, composições
[CONFIRMADO NO BLING] Nenhuma variação, kit ou composição em nenhum dos 98 produtos. Na Smoking Line, a relação "caixa de importação ↔ display ↔ unidade" (ex.: `TB-IMP-023` → `TB-IMP-023-D` → `TB-IMP-023-U`) é feita com **SKUs separados**, sem vínculo estrutural.

### 1.7 O que expor no portal
- [CONFIRMADO NO BLING] Claramente vendável a PDV: `DRINK-TRAD-269` e `DRINK-ZERO-269`.
- [CONFIRMADO NO BLING] Não expor: insumos, embalagens, `INDUSTR …`, caixas de importação `TB-IMP-0XX` (são venda a distribuidor).
- [RECOMENDAÇÃO TÉCNICA] O portal deve ter uma **lista de produtos liberada ("allowlist") no próprio banco**, com o ID do Bling, em vez de puxar o catálogo inteiro filtrando por categoria.
- [DECISÃO DE NEGÓCIO PENDENTE] Displays da Smoking Line (`-D`) entram no portal na V1? Eles têm outro público (tabacaria) e outra tributação (sem ST; origem 1).

### 1.8 Dados do produto necessários para o pedido
[RECOMENDAÇÃO TÉCNICA] Para criar o item do pedido via API: `produto.id` (obrigatório), `codigo`, `unidade`, `quantidade`, `valor` (unitário), `desconto` (opcional). NCM, CEST, origem e tributação vêm do cadastro do produto + natureza de operação na hora de gerar a nota — o portal **não** deve enviar dados fiscais.

---

## 2. PREÇOS E REGRAS COMERCIAIS

### 2.1 Preços cadastrados
[CONFIRMADO NO BLING] Energéticos: `preco = 4,20` (ambos). Smoking Line: preços cadastrados por SKU (ex.: displays R$ 33,90 a R$ 1.003,90).

### 2.2 / 2.3 Tabelas e diferenciação de preço
- [CONFIRMADO NO BLING] Nenhuma lista/tabela de preço é usada nas notas e nenhum cliente tem vínculo de preço, categoria financeira ou limite de crédito (`financeiro.condicaoPagamento = ""`, `limiteCredito = 0` em todos os contatos lidos).
- Observação: a integração disponível não expõe o recurso "listas de preço" do Bling; não há sinal de uso nas notas, mas a existência de listas cadastradas **não pôde ser verificada 100%**.

### 2.4 Preço efetivamente praticado (nas NF-e)
[CONFIRMADO NO BLING] O valor unitário foi digitado "por dentro" — calculado para chegar a um preço final por lata já com ICMS-ST:

| NF | Data | Cliente (UF) | CFOP | Valor unit. item | Valor final da nota ÷ latas |
|---|---|---|---|---|---|
| 000009 e 000012 (abertas e conferidas; demais de set/26 não abertas) | set/26 | hostel e supermercado (RJ) | 6403 | 4,1544 | **R$ 5,20** |
| 000022 | 06/10 | Drogaria Destaque (RJ) | 6401 | 4,6336 | **R$ 5,80** |
| 000023 | 06/10 | Posto Gallena Lagoa (RJ) | 6401 | 4,9532 | **R$ 6,20** |
| 000021 | 06/10 | DFJ (SP) — consignação | 5917 | 4,20 | (remessa, não é venda) |

Ou seja: **há preço diferente por cliente**, mas ele não está em lugar nenhum do cadastro — está só na cabeça de quem emitiu a nota.

### 2.5 / 2.6 Regras de preço mínimo, desconto máximo, pedido mínimo
[CONFIRMADO NO BLING] Nenhuma configurada/observável. Nenhum desconto aplicado nas notas lidas.

### 2.7 Que preço o portal deve mandar
- [RECOMENDAÇÃO TÉCNICA] O Bling calcula ICMS-ST e IPI **em cima do `valor` do item** na hora da nota. Se o portal mandar o "preço de prateleira" (ex.: R$ 5,90) como `valor`, o Bling soma ST por cima e a nota sai mais cara que o combinado. Portanto o portal deve guardar, por produto/tabela, o **valor-base (antes de ST/IPI)** que o Bling espera e, no máximo, **exibir** ao cliente um preço final estimado.
- [DECISÃO DE NEGÓCIO PENDENTE] Qual é a política de preço do portal: preço único por lata em SP? Tabela por canal (bar, tabacaria, posto, distribuidor)? Preço negociado por cliente? E esse preço combinado é "final com imposto" ou "base"? (Fora do Bling, foi mencionado R$ 5,90/lata ao bar em SP.)
- [DECISÃO DE NEGÓCIO PENDENTE] Vendedor pode alterar preço/dar desconto no portal? Com que teto e com aprovação de quem?

---

## 3. CLIENTES / CONTATOS

### 3.1 Volume e estrutura
[CONFIRMADO NO BLING] 25 contatos ativos (2 inativos/excluídos fora da listagem). Composição:
- **Clientes que já receberam nota (9):** DFJ DISTRIBUIDORA (18398118658), DROGARIA DESTAQUE DO VIDIGAL (18435320402), POSTO GALLENA LAGOA (18432843307), IPANEMA PRAIA HOSTEL (18362929550), MORE IPANEMA BLUE HOSTEL matriz (18362929641) e filial (18362929891), MORE SO GESTÃO (18362937661), SUPERMERCADO DE JACAREPAGUÁ (18383951867), P4R Turismo (18176080447).
- **Fornecedores/indústria:** Praxis, Ardagh, AZ Embalagens, Carlos Cramer, Doca Insumos, Mastersense, Quantiq.
- **Outros:** Itamaraty (contabilidade), Leidseplein (matriz Amsterdam, sem CNPJ), pessoas físicas/sócio (Fabio C Fabrizzi — recebeu doação, Lima Macs, Marcus, Rhaissa, Alberto), Thiago Augusto e Marjana Muniz (CNPJ com nome de pessoa).
- **Tipo de contato:** só o Posto Gallena tem `tiposContato = Cliente` (ID 14582035035). Todos os outros estão sem tipo.

### 3.2 Campos preenchidos de forma consistente
[CONFIRMADO NO BLING] Sempre: `nome` (razão social), `numeroDocumento`, `tipo` (J/F), endereço `geral`. Quase sempre nos clientes: `ie`, `indicadorIe`, `email`/`emailNotaFiscal`. Raramente: `fantasia` (só DFJ "ADEGA DO FROES" e Drogaria), `telefone`/`celular`. Nunca: endereço de `cobranca`, `vendedor`, `condicaoPagamento`, `pessoasContato`, `codigo`.

### 3.3 Mínimo para um contato utilizável em pedido/nota
[RECOMENDAÇÃO TÉCNICA] Para não travar a NF-e: `nome`, `tipo` (J/F), `numeroDocumento`, `indicadorIe` + `ie` (quando contribuinte), endereço completo (`endereco`, `numero`, `bairro`, `cep`, `municipio`, `uf`), `emailNotaFiscal`. Recomendo também `tiposContato = Cliente` para separar clientes de fornecedores.

### 3.4 Mapeamento de campos (Bling API v3 — `/contatos`)
| Dado do portal | Campo Bling |
|---|---|
| CNPJ/CPF | `numeroDocumento` (só dígitos) |
| Pessoa física/jurídica | `tipo` = `F` / `J` (`E` estrangeiro) |
| Inscrição Estadual | `ie` |
| Indicador de IE | `indicadorIe` |
| Razão social / Nome | `nome` |
| Nome fantasia | `fantasia` |
| Responsável | `pessoasContato[]` (hoje não usado) |
| Telefone / Celular | `telefone` / `celular` |
| E-mail / E-mail NF-e | `email` / `emailNotaFiscal` |
| Endereço | `endereco.geral.{endereco, numero, complemento, bairro, cep, municipio, uf}` |
| Cobrança | `endereco.cobranca.{…}` (hoje vazio) |
| Vendedor da carteira | `vendedor.id` (hoje 0 em todos) |
| Tipo de contato | `tiposContato[].id` (Cliente = 14582035035) |

### 3.5 Contribuinte / isento / não contribuinte
- [CONFIRMADO NO BLING] Valores em uso: `indicadorIe = 1` (contribuinte, com IE numérica — ex.: Gallena, Drogaria, DFJ) e `indicadorIe = 2` (contribuinte isento, `ie = "ISENTO"` — ex.: MORE SO, Ipanema Praia).
- [RECOMENDAÇÃO TÉCNICA] Padrão da API v3: `1` contribuinte ICMS; `2` contribuinte isento; `9` não contribuinte (`ie` vazio). O portal deve oferecer essas 3 opções e validar: `1` → IE obrigatória; `2` → `ie = "ISENTO"`; `9` → `ie` vazia.
- [CONFIRMADO NO BLING] **Já houve erro real**: a NF 000005 (MORE IPANEMA BLUE HOSTEL filial, 01/09) saiu com `ie = ISENTO` e ficou com situação 4 (**rejeitada**); a nota foi reemitida (000009) com IE 15860421. Ou seja, indicador de IE errado já travou faturamento.

### 3.6 Pessoa física
[CONFIRMADO NO BLING] Só aparecem PF não clientes (sócio/pessoas). A única nota para PF foi a doação de material promocional (NF 000018, CFOP 6910). [DECISÃO DE NEGÓCIO PENDENTE] o portal aceita cliente PF (ex.: evento, ambulante)? Se sim: CPF, `indicadorIe = 9`, endereço completo, e venda a consumidor final muda a tributação.

### 3.7 Duplicados e padrões que exigem atenção
- [CONFIRMADO NO BLING] Não há CNPJ repetido. Mas há **mesmo nome com CNPJs diferentes** (MORE IPANEMA BLUE HOSTEL matriz `…/0001-81` e filial `…/0002-62`) — são estabelecimentos distintos e corretos.
- [CONFIRMADO NO BLING] Insumos duplicados no cadastro de produtos (mesmo item com e sem código) — não afeta o portal se ele usar allowlist.
- [CONFIRMADO NO BLING] Clientes misturados com fornecedores e pessoas, sem `tiposContato`.

### 3.8 Como detectar CNPJ/CPF existente
[RECOMENDAÇÃO TÉCNICA] Antes de criar: `GET /contatos?numeroDocumento=<só dígitos>`. Comparar pelo **CNPJ completo (14 dígitos)**, nunca pela raiz (8), por causa de matriz/filial. Em paralelo, checar no banco do portal (índice único no documento) para evitar corrida entre dois vendedores cadastrando o mesmo cliente.

### 3.9 Campos extras recomendados
[RECOMENDAÇÃO TÉCNICA] Validação de CNPJ na Receita (situação ativa, razão social, endereço, CNAE) e de IE no Sintegra/CCC antes de gravar no Bling; `emailNotaFiscal` obrigatório; telefone/WhatsApp do responsável; canal do cliente (bar, tabacaria, posto, mercado) guardado no portal — essencial para preço, CRM e análise.

---

## 4. ENDEREÇOS E ENTREGA

- 4.1 [CONFIRMADO NO BLING] Usados: `cep`, `endereco` (logradouro), `numero`, `complemento` (raro), `bairro`, `municipio`, `uf`. Código IBGE do município não aparece no contato (Bling resolve pelo nome/CEP).
- 4.2 [CONFIRMADO NO BLING] Só o endereço `geral` é preenchido. `cobranca` vazio em todos; nenhum endereço de entrega distinto nas notas (`transporte.etiqueta` vazio).
- 4.3 [CONFIRMADO NO BLING] Nenhum cliente com múltiplos endereços. Filiais são contatos separados.
- 4.4 [RECOMENDAÇÃO TÉCNICA] Enviar endereço completo no contato. No pedido, só enviar `transporte.etiqueta` se houver entrega em endereço diferente (fora do MVP). Preencher endereço via consulta de CEP para reduzir erro.

---

## 5. VENDEDORES

- 5.1 / 5.2 [CONFIRMADO NO BLING] Nenhuma nota tem vendedor (`vendedor.id = 0` em todas) e nenhum contato tem vendedor. A integração usada nesta leitura **não expõe** o cadastro de vendedores, então não foi possível listar se existe algum cadastrado. A API v3 tem `GET /vendedores` (cada vendedor é ligado a um contato) e o pedido aceita `vendedor.id`.
- 5.3 [CONFIRMADO NO BLING] Não existe carteira de clientes por vendedor.
- 5.4 / 5.5 [CONFIRMADO NO BLING] Nenhum pedido existe, portanto nenhuma comissão registrada. Regras de comissão não observáveis via integração.
- 5.6 [RECOMENDAÇÃO TÉCNICA] Guardar no portal: `usuario_id` (próprio) ↔ `bling_vendedor_id` ↔ `bling_contato_id` do vendedor, tipo de vendedor (próprio ST / DFJ), percentual de comissão de referência e status ativo.
- [DECISÃO DE NEGÓCIO PENDENTE] Vendedores próprios da ST e vendedores da DFJ vão ser cadastrados como vendedores no Bling? A comissão de 5% da DFJ é calculada no Bling, no portal ou fora dos dois? O cliente fica "preso" a um vendedor (carteira) ou qualquer vendedor atende qualquer cliente?

---

## 6. PEDIDOS DE VENDA

### 6.1 / 6.2 Estrutura real
[CONFIRMADO NO BLING] **Zero pedidos de venda** e **zero propostas comerciais** na conta. Não há estrutura real para analisar. O que existe é o padrão das NF-e emitidas direto:
- Série 1, numeração sequencial (000001 a 000023).
- Itens com `codigo`, `unidade = UN`, `quantidade`, `valor`.
- `transporte.fretePorConta = 1` em todas, `valorFrete = 0`, sem transportador e sem volumes.
- `parcelas = []` em todas (nenhum financeiro gerado).
- `vendedor.id = 0`, `loja.id = 0`, `numeroPedidoLoja` vazio.
- Naturezas de operação usadas (IDs — os nomes não são expostos pela integração): `15110686903` (venda energético, set/26 e Drogaria), `15111651042` (venda Gallena), `15111555404` (remessa consignação energético, CFOP 5917), `15111509787` (remessa consignação Smoking Line, CFOP 5917), `15111560823` (doação, CFOP 6910), `15110640107` (NF 000001, jun/26).

### 6.3 Mínimo para criar pedido via API
[RECOMENDAÇÃO TÉCNICA] `POST /pedidos/vendas`: `contato.id`, `data`, `itens[]` (`produto.id`, `quantidade`, `valor`). Recomendados: `numeroLoja` (número do pedido do portal), `vendedor.id`, `situacao.id`, `observacoes` (visível) e `observacoesInternas`, `dataPrevista`, `parcelas[]` (quando houver condição definida), `transporte.fretePorConta`. Confirmar no schema atual se o pedido aceita natureza de operação; se não, a natureza é escolhida na geração da nota.

### 6.4 Situações existentes (módulo Vendas, ID 98310)
[CONFIRMADO NO BLING]

| ID | Situação |
|---|---|
| 6 | Em aberto |
| 9 | Atendido |
| 12 | Cancelado |
| 15 | Em andamento |
| 18 | Venda Agenciada |
| 21 | Em digitação |
| 24 | Verificado |

Todas as transições entre elas estão ativas e **nenhuma transição tem ação automática** (`acoes = []`). Ações disponíveis no módulo (se forem configuradas no futuro): lançar/estornar estoque, lançar/estornar contas, gerar NF-e, gerar NFC-e, incluir em remessa de postagem. Nenhuma situação personalizada criada.

### 6.5 Situação de entrada do pedido do portal
- [RECOMENDAÇÃO TÉCNICA] Entrar em **21 – Em digitação** (ou 6 – Em aberto). Como hoje nenhuma transição dispara estoque, contas ou nota, nenhuma das duas causa efeito colateral. "Em digitação" deixa mais claro para o back-office que o pedido ainda precisa ser conferido.
- [DECISÃO DE NEGÓCIO PENDENTE] Criar uma situação própria tipo "Portal – aguardando aprovação" (exige alteração no Bling, fora desta etapa). Definir quem aprova o pedido e quem passa para "Atendido"/gera a nota.

### 6.6 Campos a mapear
[RECOMENDAÇÃO TÉCNICA] Número do portal → `numeroLoja`; observação do cliente → `observacoes`; origem (cliente/vendedor, usuário) → `observacoesInternas`; vendedor → `vendedor.id`; cliente → `contato.id`; itens/preço/desconto → `itens[]`; frete → `transporte.fretePorConta` + `transporte.frete`; pagamento → `parcelas[]`.

### 6.7 Identificador a guardar
[RECOMENDAÇÃO TÉCNICA] Guardar `id` do pedido no Bling (para `GET /pedidos/vendas/{id}`) **e** o `numero` (para atendimento humano). Depois que a nota for gerada, guardar também `id` e `numero` da NF-e.

### 6.8 Automações
[CONFIRMADO NO BLING] Nenhuma ação vinculada a transições de situação. Não foi possível verificar, pela integração, configurações gerais do tipo "lançar estoque automaticamente ao criar pedido" nem integrações de terceiros instaladas. [RECOMENDAÇÃO TÉCNICA] Conferir na tela de Preferências > Vendas antes do go-live.

---

## 7. PAGAMENTO

- 7.1 [CONFIRMADO NO BLING] Nenhuma nota tem parcelas e não existe nenhuma conta a receber. A integração não expõe a lista de formas de pagamento cadastradas. O financeiro **não está sendo controlado no Bling**.
- 7.2 / 7.3 [CONFIRMADO NO BLING] Nenhuma condição/prazo usado; nenhuma condição por cliente (`condicaoPagamento` vazio em todos).
- 7.4 [DECISÃO DE NEGÓCIO PENDENTE] Condição de pagamento padrão (à vista, Pix, boleto 7/14/28 dias?), se varia por cliente/canal e se o cliente/vendedor escolhe no portal.
- 7.5 [RECOMENDAÇÃO TÉCNICA] Na API, cada parcela vai como `parcelas[] = {dataVencimento, valor, formaPagamento.id}`. A soma tem que bater com o total do pedido. Para o MVP: uma condição padrão definida pela Bulldog, aplicada pelo backend, sem escolha livre.

---

## 8. FRETE E LOGÍSTICA

- 8.1 [CONFIRMADO NO BLING] Todas as notas: `fretePorConta = 1`, `valorFrete = 0`, sem transportador, sem volumes. Na API v3, `1` corresponde a **frete por conta do destinatário (FOB)** — o que provavelmente não é a realidade de quem entrega em bar (a entrega é feita pela operação Bulldog/DFJ). Vale confirmar com a contabilidade.
- 8.2 [CONFIRMADO NO BLING] Nenhuma transportadora usada e **nenhuma logística integrada** configurada.
- 8.3 [CONFIRMADO NO BLING] Frete nunca foi informado.
- 8.4 [DECISÃO DE NEGÓCIO PENDENTE] Modalidade correta para entrega própria/DFJ (0 = remetente/CIF, 1 = destinatário/FOB, 3/4 = próprio, 9 = sem frete) e se frete é cobrado do PDV.
- 8.5 [RECOMENDAÇÃO TÉCNICA] Sim, o MVP pode criar pedido sem frete. Impacto: o total do pedido = produtos + impostos; se depois houver cobrança de frete, o back-office ajusta no pedido antes da nota. O que **não** pode ficar indefinido é a modalidade (`fretePorConta`) que sai na NF-e.

---

## 9. ESTOQUE

- 9.1 [CONFIRMADO NO BLING] Depósitos: **Geral** (14888496833, padrão) e **RJ** (14888987595). Saldos dos energéticos (todo no Geral; RJ zerado):

| SKU | Saldo físico (Geral) | Saldo RJ |
|---|---|---|
| DRINK-TRAD-269 | 12.788 | 0 |
| DRINK-ZERO-269 | 12.936 | 0 |

- [CONFIRMADO NO BLING] Em 06/10 foi emitida a remessa em consignação NF 000021 para a DFJ: 5.496 Tradicional + 5.544 Zero (11.040 latas). Não há depósito "DFJ" e não é possível afirmar, pela integração, se essas latas saíram do saldo acima. **O saldo do Bling pode não representar o que está fisicamente disponível para venda** (fábrica vs. DFJ).
- 9.2 [DECISÃO DE NEGÓCIO PENDENTE] Bloquear pedido sem estoque ou só avisar? Com volume de ~25 mil latas e produção ditada pela fábrica, a recomendação técnica seria **mostrar disponibilidade e só avisar**, mas a regra é de negócio.
- 9.3 / 9.4 [CONFIRMADO NO BLING] Como não há pedidos e nenhuma transição lança estoque, hoje o estoque só se move pela NF-e. Criar um pedido em qualquer situação **não reserva nem baixa estoque** com a configuração atual de transições (sujeito à checagem das Preferências citada em 6.8).
- [RECOMENDAÇÃO TÉCNICA] Antes do portal: decidir de qual depósito sai a venda em SP (criar depósito "DFJ/SP" ou "Filial SP") e manter o saldo do Bling fiel ao físico — senão a consulta de estoque do portal mostra número errado.

---

## 10. INTEGRAÇÃO / API DO BLING

- 10.1 [CONFIRMADO NO BLING] A integração atual permite consultar produtos, contatos, pedidos, NF-e, estoque, depósitos, situações e transições; e criar contatos e pedidos de venda (além de produtos, propostas, contas e NF-e). Vendedores, formas de pagamento e listas de preço **não** estão expostos nesta integração, mas existem na API v3 pública.
- 10.2 [RECOMENDAÇÃO TÉCNICA] Endpoints do MVP (API v3, `https://api.bling.com.br/Api/v3`):
  - `GET /produtos/{id}` (só os IDs da allowlist) e `GET /estoques/saldos?idsProdutos[]=`
  - `GET /contatos?numeroDocumento=` / `GET /contatos/{id}` / `POST /contatos` / `PUT /contatos/{id}`
  - `GET /vendedores`
  - `GET /formas-pagamentos`
  - `POST /pedidos/vendas` / `GET /pedidos/vendas/{id}` / `PATCH /pedidos/vendas/{id}/situacoes/{idSituacao}` (este último só se o portal for mudar situação)
  - `GET /situacoes/modulos/98310` (mapa de situações)
- 10.3 [RECOMENDAÇÃO TÉCNICA] OAuth 2.0 (authorization code) com app criado na Central de Extensões do Bling. Access token dura ~6 h; refresh token ~30 dias, renovado a cada uso. Se o refresh expirar ou for revogado, é preciso reautorizar com um usuário admin do Bling — **definir quem é o dono da autorização** (hoje o admin da conta não é o Leonardo). Verificar em developer.bling.com.br se houve mudança recente.
- 10.4 [RECOMENDAÇÃO TÉCNICA] Limites conhecidos: **3 requisições/segundo e 120.000/dia** por conta; o Bling não devolve cabeçalhos de cota. O backend precisa de fila com retry/backoff no HTTP 429. Volume do MVP fica muito abaixo disso.
- 10.5 [RECOMENDAÇÃO TÉCNICA] Webhooks úteis (API v3, configurados no app): pedido de venda (criado/alterado/situação), NF-e (autorizada/cancelada), estoque (saldo alterado), produto e contato. Uso: atualizar status do pedido no portal sem ficar consultando. Como fallback, consulta periódica por `dataAlteracaoInicial`.
- 10.6 / 10.7 Limitações que afetam o desenho:
  - [CONFIRMADO NO BLING] A API não devolve o **preço final com ST** antes da nota; o pedido mostra só valor de produtos. Preço final exibido ao cliente terá que ser **estimado pelo portal** ou aceito como "valor sem impostos".
  - [CONFIRMADO NO BLING] Natureza de operação aparece só como ID; nomes e regras fiscais não são legíveis pela integração.
  - [RECOMENDAÇÃO TÉCNICA] Criar o pedido não emite nota. A geração da NF-e continua manual no Bling (recomendado no MVP).

---

## 11. SEGURANÇA E IDENTIFICADORES

- 11.1 [RECOMENDAÇÃO TÉCNICA] IDs do Bling a guardar: `bling_contato_id` (cliente), `bling_vendedor_id`, `bling_produto_id` (allowlist), `bling_deposito_id`, `bling_pedido_id` + `numero`, `bling_situacao_id`, `bling_nfe_id` + `numero` + chave de acesso (quando houver), `bling_forma_pagamento_id`.
- 11.2 [RECOMENDAÇÃO TÉCNICA] Confirmado: o portal deve ter **IDs internos próprios (UUID)** como chave primária; IDs do Bling ficam como colunas de referência externa (`bling_*_id`), com índice único.
- 11.3 [RECOMENDAÇÃO TÉCNICA] Só no backend: client_id, client_secret, access token, refresh token do Bling, e qualquer chave de API de consulta CNPJ/CEP. Nunca no app/celular. Tokens criptografados em repouso.
- 11.4 [RECOMENDAÇÃO TÉCNICA] Riscos:
  - Cliente/PDV só pode ver **o próprio** cadastro e pedidos — o portal nunca repassa consultas abertas ao Bling a partir do front.
  - Vendedor não pode navegar a base de contatos do Bling (ela tem fornecedores, sócios e pessoas físicas com CPF). A busca de cliente deve ser feita no banco do portal, que só contém clientes.
  - Preço e quantidade recalculados no backend (não confiar no valor que vem do celular).
  - Links de DANFE/XML do Bling são URLs assinadas e públicas por tempo limitado — não expor indiscriminadamente.
  - LGPD: CPF, telefone e e-mail de PF.

---

## 12. PREPARAÇÃO PARA RD STATION CRM

- 12.1 [RECOMENDAÇÃO TÉCNICA] Modelo: entidade **Cliente** do portal (UUID) como centro, com tabela de vínculos externos `cliente_vinculo_externo (cliente_id, sistema, id_externo)` — sistema = `bling` hoje, `rdstation` depois (organização + contato + oportunidade). O mesmo vale para Vendedor (usuário do RD) e Pedido (oportunidade/negócio do RD).
- 12.2 [RECOMENDAÇÃO TÉCNICA] Eventos internos desde o início (tabela de eventos/outbox): `cliente.criado`, `cliente.atualizado`, `pedido.criado`, `pedido.enviado_ao_bling`, `pedido.aprovado`, `pedido.faturado` (NF autorizada), `pedido.cancelado`, `visita.registrada` (futuro). Cada evento com timestamp, autor e payload.
- 12.3 [RECOMENDAÇÃO TÉCNICA] Acoplamentos a evitar: usar ID do Bling como ID do cliente; usar situação do Bling como status do pedido no portal (manter status próprio e mapear); depender do cadastro do Bling para dados comerciais (canal, responsável, WhatsApp, carteira) que o Bling não guarda e que o CRM vai precisar.

---

## 13. QUALIDADE DOS DADOS ATUAIS

### Críticos para o MVP
1. [CONFIRMADO NO BLING] **Nenhum fluxo de pedido existe** — tudo é NF-e direta. Processo pedido → nota precisa ser desenhado e testado.
2. [CONFIRMADO NO BLING] **Preço praticado não está cadastrado** (varia de R$ 5,20 a R$ 6,20 final/lata, digitado na nota).
3. [CONFIRMADO NO BLING] **Clientes misturados** com fornecedores/pessoas e sem `tiposContato`; o portal não consegue separar "clientes" de forma confiável a partir do Bling.
4. [CONFIRMADO NO BLING] **Indicador de IE errado já gerou nota rejeitada** (NF 000005).
5. [CONFIRMADO NO BLING] **Estoque do Bling possivelmente não reflete a consignação na DFJ** (sem depósito DFJ).
6. [CONFIRMADO NO BLING] Sem vendedor, sem condição de pagamento, sem forma de pagamento usadas.

### Melhorias para depois
- [CONFIRMADO NO BLING] Insumos duplicados (com e sem código) e insumos sem SKU.
- [CONFIRMADO NO BLING] `precoCusto = 0` nos energéticos; dimensões zeradas; GTIN da caixa = GTIN da lata.
- [CONFIRMADO NO BLING] Notas de set/26 saíram com `origem 0`; o cadastro hoje está `origem 5` (já corrigido para as notas novas).
- [CONFIRMADO NO BLING] `spedTipoItem` vazio no Zero (preenchido "04" no Tradicional).
- [CONFIRMADO NO BLING] Telefone e nome fantasia faltando na maioria dos clientes.
- [CONFIRMADO NO BLING] Unidade do Zippo saiu "pçs" na NF 000018 vs. "UN" no cadastro.

---

## 14. DECISÕES QUE O BLING NÃO RESPONDE

| # | Decisão | Por que é necessária | Opções razoáveis |
|---|---|---|---|
| 1 | **Quem emite a nota da venda ao PDV em SP** (ST Nicolas matriz, futura filial SP, DFJ?) e com qual natureza/CFOP | Define natureza de operação, depósito, ICMS-ST e em qual conta Bling o pedido entra | Matriz ST vendendo direto (DFJ só representante); filial SP; DFJ revendendo da consignação |
| 2 | Política de preço | Sem isso o portal não sabe o `valor` a enviar | Preço único SP; tabela por canal; preço por cliente; preço "final com ST" vs. "base" |
| 3 | Desconto/edição de preço pelo vendedor | Risco de margem | Proibido; até X% sem aprovação; qualquer desconto com aprovação |
| 4 | Pedido mínimo e múltiplo | Logística e custo de entrega | Mínimo de 1 cx; mínimo em R$; múltiplo de 24 obrigatório ou permitir latas avulsas |
| 5 | Condição e forma de pagamento | Parcelas no pedido e financeiro | À vista/Pix; boleto com prazo; por cliente; escolha no portal ou fixa |
| 6 | Frete: modalidade e cobrança | Sai na NF-e | Entrega própria sem cobrança; frete cobrado por entrega; FOB |
| 7 | Estoque: bloquear ou avisar | Experiência e risco de venda sem produto | Bloqueia; só avisa; ignora no MVP |
| 8 | Depósito de origem da venda | Saldo correto | Geral; criar "DFJ/SP"; filial |
| 9 | Vendedores no Bling e comissão | Relatório e pagamento de comissão | Cadastrar todos no Bling; só no portal; ST e DFJ separados |
| 10 | Carteira de clientes | Visibilidade e comissão | Cliente fixo por vendedor; livre; por região |
| 11 | Aprovação do pedido | Evitar nota com erro | Pedido entra direto; back-office aprova; aprovação só para cliente novo |
| 12 | Cadastro de cliente novo pelo vendedor | Risco fiscal (IE/CNPJ) | Entra direto no Bling; fica pendente de validação; validação automática Receita/Sintegra |
| 13 | Cliente PF | Tributação diferente | Não aceitar no MVP; aceitar com regras |
| 14 | Smoking Line no portal | Público e tributação diferentes | Só energético na V1; incluir displays; portal separado |
| 15 | Nome dos produtos ("Tradicional" x "Original") | Consistência de marca | Manter Bling; nome comercial só no portal |
| 16 | Quem é dono da autorização OAuth do Bling | Se o token cair, o portal para | Usuário admin atual; usuário técnico dedicado |
| 17 | Cliente PDV acessa como? | Segurança | Convite por vendedor; autocadastro com aprovação; login por CNPJ + código |

---

## 15. RECOMENDAÇÃO DE MVP

### Obrigatório para V1
- Catálogo fixo com os 2 energéticos (allowlist), venda em caixa de 24, envio ao Bling em latas.
- Preço vindo de **tabela do portal** (valor-base), sem edição pelo vendedor; preço final exibido como "estimado".
- Vendedor: buscar cliente no banco do portal; cadastrar cliente novo com CNPJ, IE + indicador (1/2/9), endereço via CEP, e-mail NF-e; checagem de duplicidade por CNPJ completo; gravação no Bling com `tiposContato = Cliente`.
- Cliente/PDV: login próprio, vê só o seu cadastro, monta pedido, envia.
- Pedido criado no Bling em **21 – Em digitação**, com `numeroLoja`, `vendedor.id` (quando houver), observações e condição de pagamento padrão; **sem gerar nota e sem mexer em estoque**.
- Portal guarda `bling_pedido_id`/`numero` e mostra status (consulta periódica ou webhook).
- Back-office continua conferindo e emitindo a NF-e no Bling.
- Tokens só no backend; IDs internos UUID; tabela de eventos.

### Recomendável logo depois
- Webhooks de pedido/NF-e para status em tempo real e link da DANFE para o cliente.
- Indicador de estoque disponível.
- Validação automática de CNPJ (Receita) e IE (Sintegra/CCC).
- Carteira por vendedor e relatório simples de vendas/comissão.
- Histórico de pedidos e "repetir último pedido".

### Futuro
- Integração RD Station CRM (cliente, oportunidade, visita).
- Tabelas de preço por canal/cliente e descontos com aprovação.
- Smoking Line (displays) no portal.
- Geração de NF-e automática a partir do pedido aprovado.
- Frete calculado e agendamento de entrega.

---

## RISCOS / BLOQUEADORES

1. **Modelo fiscal de SP indefinido (bloqueador).** O Bling só tem venda interestadual RJ e remessa em consignação SP. A venda ao PDV em SP com ICMS-ST nunca foi feita no Bling, e o modelo DFJ mudou várias vezes (consignação → representação → filial em estudo). Sem saber quem fatura e com qual natureza, o pedido do portal não sabe em que conta/depósito/regra entrar.
2. **Preço não está no sistema.** Se o portal for construído antes da política de preço, ele vai reproduzir a improvisação atual.
3. **Pedidos nunca foram usados.** Primeiro pedido → nota precisa ser testado com a contabilidade antes de liberar para vendedor/cliente (inclusive se a nota gerada a partir do pedido herda natureza, ST e origem corretamente).
4. **Estoque pode não refletir o físico** (consignação sem depósito DFJ).
5. **Dependência de um único admin do Bling** para autorizar o app e alterar configurações.
6. **Cadastro de cliente com IE errada trava faturamento** — já aconteceu uma vez.

---

## PERGUNTAS PARA LEONARDO/CHATGPT

1. Na venda ao PDV em SP, quem emite a nota (ST matriz, filial SP ou DFJ) e qual natureza de operação/CFOP a Itamaraty definiu?
2. Qual a política de preço do portal (único, por canal ou por cliente) e o valor combinado é final com impostos ou valor-base?
3. Vendedor pode alterar preço ou dar desconto? Até quanto e com aprovação de quem?
4. Existe pedido mínimo? Venda só em caixa fechada de 24 ou aceita lata avulsa?
5. Qual a condição e forma de pagamento padrão? Varia por cliente? Quem escolhe?
6. Frete: quem paga, qual modalidade sai na nota e se é cobrado do PDV?
7. Estoque: o portal bloqueia ou só avisa quando não houver saldo? De qual depósito sai a venda em SP?
8. Vendedores da ST e da DFJ serão cadastrados como vendedores no Bling? Onde a comissão (incl. 5% da DFJ) é calculada?
9. Cliente pertence a um vendedor (carteira) ou é livre?
10. Pedido do portal precisa de aprovação antes de virar nota? Quem aprova?
11. Cliente novo cadastrado pelo vendedor entra direto no Bling ou fica pendente de validação?
12. O portal aceita cliente pessoa física?
13. Smoking Line entra na V1?
14. Nome exibido: "Tradicional" (como no Bling) ou "Original"?
15. Quem será o usuário dono da autorização da integração no Bling?
16. Como o cliente/PDV ganha acesso ao portal (convite, autocadastro com aprovação, outro)?
