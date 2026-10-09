# Prompts para o Lovable

Use **um prompt por vez**, na ordem. Espere cada etapa funcionar antes de mandar a próxima. Construir tudo num prompt só costuma dar errado no Lovable.

**Antes de começar:**
1. Crie o projeto no Lovable e **conecte o Supabase** (botão Supabase no topo). Banco, login e funções do servidor dependem dele.
2. Tenha à mão a pasta `assets/`, para anexar o logo e as fotos quando o prompt pedir.

---

## Prompt 1 — Base, visual e login

> Vou construir o **Portal Comercial The Bulldog**: um portal web mobile-first para pedidos B2B de energético e tabacaria, usado por clientes (bares, tabacarias, postos), vendedores e back-office. Todo o texto da interface em **português do Brasil**, valores em R$ no formato 1.234,56.
>
> **Visual:**
> - Layout branco e limpo, pensado primeiro para celular (390 px).
> - Cores:
>   - botão principal vermelho `#dd1731`
>   - azul `#3458b0`
>   - amarelo `#fddf03` para selos de bônus
>   - texto `#141414`
>   - cinza `#6b6760`
>   - bordas `#e4e0d8`
>   - fundo de campos `#f5f3ee`
> - Cantos arredondados de 12 px.
> - **Logo:** use o arquivo `bulldog.svg` anexado (só o bulldog no círculo azul). Ele fica no topo à esquerda de todas as telas, com a palavra "PEDIDOS" em vermelho ao lado; maior no centro da tela de login; e como favicon.
>
> **Autenticação (Supabase Auth, e-mail e senha):**
> - Perfis: `admin`, `seller` (vendedor), `customer` (cliente/PDV).
> - Tabela `profiles`: role, name, active, customer_id (só para customer), seller_type, commission_rate, must_change_password.
> - Na tela de login: logo grande, e-mail, senha, botão "Entrar", e o texto "Acesso liberado pela equipe The Bulldog".
> - Depois do login, cada perfil vai para uma tela diferente:
>   - customer → "Novo pedido"
>   - seller → "Clientes"
>   - admin → "Pedidos"
> - Tela "Minha conta" com troca de senha, obrigatória quando must_change_password = true.
>
> **Menu superior por perfil:**
> - Cliente: Novo pedido, Meus pedidos, Conta.
> - Vendedor: Clientes, Pedidos, Conta.
> - Admin: Pedidos, Clientes, Comercial, Integração, Usuários, Conta.
>
> Ative **RLS em todas as tabelas** desde já.

---

## Prompt 2 — Catálogo, preços e fotos

> Crie as tabelas `products`, `price_rules` e `campaigns`, e importe os 27 produtos do CSV anexado (`produtos.csv`).
>
> **products:**
> - campos: sku, nome, nome_curto, linha (`energetico` | `tabacaria`), unidade_venda (`caixa` | `display` | `unidade`), unidades_erp_por_unidade_venda (24 no energético, 1 na tabacaria), conteudo_embalagem, ativo, ordem
> - foto em `/produtos/<SKU>.webp`: vou anexar as 27 imagens; coloque em `public/produtos/` com o nome exatamente igual ao SKU
>
> **price_rules:**
> - preço por unidade de venda
> - pode ser geral por linha, por produto, por canal ou por cliente
> - prioridade: cliente > canal > produto > linha
> - energético: regra geral da linha = **R$ 5,90 por lata** (a caixa custa 5,90 × 24 = **R$ 141,60**), com preço sugerido ao consumidor de R$ 9,90
> - tabacaria: uma regra por produto, com o valor da coluna `preco_unitario_venda`
> - **Não existe "referência online" no sistema.**
>
> **campaigns:**
> - campanha "Lançamento 10+1", linha = energetico, compre 10 leve 1, cumulativo
> - região: none | uf | municipio, mais um limite de pedidos com bônus por região (vazio = sem limite)
>
> Leitura do catálogo liberada para usuários logados; edição só para admin (RLS).

---

## Prompt 3 — Tela de novo pedido e cálculo

> Crie a tela **Novo pedido**.
>
> **Topo:**
> - Cabeçalho com o cliente: nome fantasia, CNPJ formatado, cidade/UF.
> - Duas abas: **Energético** | **Tabacaria (Smoking Line)**.
>
> **Aba Energético:**
> - Cartões dos 2 sabores com a foto à esquerda (88 px), nome curto ("Tradicional", "Zero Açúcar"), "Caixa com 24 latas de 269 ml", "R$ 141,60 / caixa · R$ 5,90 a lata".
> - Stepper − [qtd] +.
> - Abaixo dos cartões: "Preço sugerido ao consumidor: R$ 9,90 a lata" e um selo amarelo "CAMPANHA — Lançamento 10+1: a cada 10 caixas de energético, leve 1 de bônus".
>
> **Aba Tabacaria:**
> - Lista com foto (64 px), nome, "Display com N un · código" (ou "Vendido por unidade" no MaryMill e no Zippo), preço "/ display" ou "/ un", e stepper.
>
> **Cálculo do orçamento:**
> - Fica numa **Edge Function `quote`**: o navegador nunca calcula preço sozinho.
> - Entrada: cliente, itens {produto, quantidade}, sabor do bônus (opcional).
> - Regras (detalhes em ESPECIFICACAO.md, seção 5):
>   - quantidade inteira ≥ 0 e pelo menos 1 item
>   - **bônus 10+1 só com caixas de energético**, somando os sabores, cumulativo e **nunca cobrado**
>   - o sabor do bônus é o escolhido; senão, o sabor com mais caixas
>   - tabacaria não conta para a campanha nem pode ser bônus
>   - o limite por região só vale se estiver configurado
>   - **pagamento sugerido** pelo nº da compra do cliente: 1ª = "50% na compra + 50% em 28 dias"; 2ª e 3ª = "A definir pelo back-office"; 4ª em diante = "30/60 dias"
>   - **frete do energético**: **grátis para todos** no lançamento ("Frete grátis."). No admin: chave "Frete grátis para todos" (ligada por padrão); desligada, usa um mínimo de caixas opcional (vazio = "Frete a combinar com o back-office.")
>   - **frete da tabacaria**: "Frete da tabacaria a combinar com o back-office."
>   - **prazo**: "3 a 5 dias úteis" em SP; "7 a 15 dias" nos demais estados
> - Saída: linhas com foto, grupos por linha com subtotal e frete, total, mensagem da campanha, pagamento sugerido, prazo.
>
> **Resumo (atualiza a cada mudança):**
> - Itens com miniatura, bônus com selo amarelo "BÔNUS" e R$ 0,00, subtotal por linha, total.
> - Se tiver as duas linhas, mostrar o aviso: "Este carrinho vira 2 pedidos, um por linha (energético e tabacaria), porque cada linha sai em nota fiscal própria."
> - Seletor "Sabor da caixa bônus".
>
> **Rodapé fixo:** quantidades + total + botão vermelho **"Revisar pedido"**.

---

## Prompt 4 — Revisão, criação do pedido e listas

> **Tela de Revisão:**
> - resumo, meio de pagamento preferido (Pix, Boleto, Transferência), observações
> - texto: "O pedido é conferido pela equipe The Bulldog antes do faturamento."
> - botões "Confirmar e enviar pedido" e "Voltar e alterar"
>
> **Edge Function `create_order`:**
> - Recebe o cabeçalho **`Idempotency-Key`**, gerado uma vez na tela de revisão.
> - A mesma chave devolve os mesmos pedidos, sem duplicar.
> - Recalcula tudo no servidor.
> - Cria **um pedido por linha de produto**, com número sequencial `BD-000001`, `BD-000002`… (contador atômico).
> - Grava `checkout_key` para agrupar os pedidos do mesmo carrinho. Um carrinho dividido conta como **uma** compra para a regra de pagamento.
> - Grava os itens como **snapshot** (sku, nome, preço do momento).
> - Status inicial `recebido`.
> - Registra o evento `order.created` na tabela `events`.
> - Regras de acesso:
>   - **Cliente/PDV só pode pedir para o próprio cadastro** (validar no servidor, mesmo que o navegador mande outro cliente)
>   - cliente com cadastro **rejeitado** não pode pedir
>
> **Confirmação:** número(s) grande(s) do pedido, quantidade e total de cada um, botões "Acompanhar" e "Fazer outro pedido".
>
> **Telas de pedidos:**
> - **Meus pedidos / Pedidos:**
>   - cliente vê só os dele
>   - vendedor vê os que criou ou dos clientes dele
>   - admin vê todos
>   - mostrar número, status, linha, quantidade, total e data
> - **Detalhe do pedido:** itens com foto, total, pagamento, frete, prazo, observações.
>
> Status: recebido, enviado_erp ("Em conferência"), em_conferencia, aprovado, faturado, cancelado.

---

## Prompt 5 — Clientes (vendedor e admin)

> **Tela Clientes:**
> - busca por nome, fantasia, cidade ou CNPJ
> - botão "+ Novo cliente"
> - cartão mostra fantasia, razão social, CNPJ, cidade/UF e o selo de conferência
>
> **Cadastro/edição de cliente** — só CNPJ (sem pessoa física), seguindo ESPECIFICACAO.md seção 6:
> - **CNPJ:**
>   - máscara e validação do dígito verificador
>   - ao sair do campo, avisar se o CNPJ já existe e mostrar link para o cadastro existente
>   - duplicidade pelo **CNPJ completo** (filial é outro cliente)
>   - restrição única (tenant, cnpj) no banco
> - **Indicador de IE:**
>   - 1 Contribuinte ICMS → IE obrigatória, não pode ser "ISENTO"
>   - 2 Contribuinte isento → grava "ISENTO"
>   - 9 Não contribuinte → IE vazia
>   - abaixo do campo: "Na dúvida sobre a IE, deixe como está: o back-office confere antes do faturamento."
> - **Demais campos:**
>   - razão social (maiúsculas) e nome fantasia
>   - responsável
>   - telefone e/ou WhatsApp
>   - e-mail e e-mail NF-e (obrigatório)
>   - CEP, logradouro, número, complemento, bairro, cidade, UF
>   - canal (bar, balada, tabacaria, posto, mercado, adega, distribuidor, evento, outro)
> - **Regras de conferência e edição:**
>   - todo cliente novo nasce "Pendente de conferência"
>   - o vendedor só edita os clientes que ele cadastrou
>   - se mudar dado fiscal, o cliente volta para pendente
>
> **Tela do cliente:**
> - dados e botão "Fazer pedido para este cliente"
> - **admin** vê o bloco "Conferência do cadastro":
>   - nota opcional e botões Conferido / Voltar a pendente / Rejeitar
>   - texto: "Confira CNPJ, IE e endereço (Receita/Sintegra) antes de marcar como conferido. IE errada já causou rejeição de NF-e."

---

## Prompt 6 — Admin: comercial, produtos e usuários

> **Admin → Comercial:**
> - preço do energético por lata e preço sugerido
> - campanha: ativa, nome, compre X / leve Y, cumulativo, região (sem limite, UF, cidade), limite de pedidos com bônus por região
> - frete grátis opcional (vazio = desligado) e prazos
> - **Linhas vendidas no portal:** checkboxes Energético / Tabacaria. Desmarcar esconde a linha do portal sem apagar nada.
> - **Produtos:** foto, nome, código, ativo/inativo e, na tabacaria, "Atacado por display (R$)" ou "Atacado por unidade (R$)"
>
> **Admin → Usuários:**
> - criar vendedor, cliente/PDV (escolhendo o cliente vinculado) ou admin, com senha provisória (a pessoa troca no 1º acesso)
> - ativar/desativar usuários; o admin não pode desativar a si mesmo
>
> Registre em `events` todas as alterações de preço, produto, campanha e usuário.

---

## Prompt 7 — Integração com o Bling (fazer por último)

> Integre com o **Bling API v3** usando **Supabase Edge Functions**. Siga ESPECIFICACAO.md, seção 8.
>
> **Segurança (obrigatório):**
> - `client_id` e `client_secret` em **Supabase Secrets**
> - access e refresh token **criptografados**, numa tabela que só a service role lê
> - **nada disso pode chegar ao navegador**
> - OAuth authorization code com `state` assinado
> - renovação automática do token (renovar uma vez em caso de 401)
> - espaçar chamadas em ~3 por segundo, com backoff em 429 e 5xx
>
> **Tabelas:**
> - `erp_connections`: label, modo (desligada | simulada | bling), ativa (só uma), prefixo das credenciais, tokens, settings em JSON
> - `external_refs`: connection_id, entity_type, entity_id, external_id, external_number; IDs do Bling **por conexão**, nunca como chave primária
> - `integration_jobs`: fila com tentativas e último erro
>
> **Conexões iniciais:**
> - **Somente "DFJ"** (é quem fatura em SP), ativa, em modo **simulada**, com:
>   - situação inicial 21 (conferir via API ao conectar)
>   - os 27 IDs de produto da coluna `bling_id_conta_dfj` (ignorar a coluna `bling_id_conta_st_nicolas`)
>   - naturezas: energético **15111666374** ("Venda de mercadoria com ST"), tabacaria **15111666371** ("Venda de mercadoria"), bonificação **15111666382** ("Saída em bonificação"); natureza obrigatória: sem ela, o pedido da linha fica na fila com erro claro (nunca usar a natureza padrão da conta, que é "a não contribuinte")
>   - **caixa bônus em PEDIDO SEPARADO**: `numeroLoja` = `<nº>-B`, natureza de bonificação, valor R$ 5,90/lata, sem parcelas, observação "Bonificação da campanha 10+1 referente ao pedido X. Sem cobrança". O pedido de venda leva só as caixas pagas. Antes de criar, procurar pelo `numeroLoja` para não duplicar. Se a natureza de bonificação faltar, não criar nem a venda
>   - frete por conta = **3** (transporte próprio do remetente) no pedido de venda e no de bonificação
>   - valor do item = preço de tabela (R$ 5,90/lata): o ICMS-ST já foi retido na remessa da ST para a DFJ, então nada é somado e o bar paga R$ 5,90 final
>   - tipo de contato "Cliente": buscar pela API depois de conectar
> - Não criar conexão da ST Nicolas.
>
> **Envio de pedido** (job disparado ao criar o pedido):
> 1. Achar o contato por CNPJ (`GET /contatos?numeroDocumento=`) ou criar (`POST /contatos`).
> 2. Procurar pedido com `numeroLoja` = número do portal; se já existir, só vincular.
> 3. Criar `POST /pedidos/vendas` conforme o exemplo da seção 8.3:
>    - caixas convertidas em latas (×24)
>    - bônus em **pedido de bonificação separado** (`<nº>-B`), ver acima
>    - **sem parcelas**
>    - observações internas com origem, vendedor, pagamento sugerido, frete e alerta de cliente pendente de conferência
>    - natureza de operação **separada por linha, enviada em cada item (`itens[].naturezaOperacao.id`) — no nível do pedido o Bling ignora**; a tabacaria **nunca usa a do energético**; sem configuração, não enviar
> 4. Garantir a situação inicial; se vier diferente, `PATCH .../situacoes/{id}`.
> 5. Guardar o ID e o número do Bling.
>
> **Se falhar:**
> - **o pedido nunca é apagado**; marcar integração = erro com a mensagem
> - repetir só erros temporários, até 5 vezes
>
> **Não emitir NF-e, não gerar contas, não mexer em estoque.**
>
> **Admin → Integração:**
> - cartões das conexões, com modo, "autorizada / não autorizada" e um aviso dos campos ainda pendentes para a DFJ
> - formulário de configuração:
>   - IDs dos produtos e vendedores
>   - situação inicial, loja
>   - natureza do energético e da tabacaria
>   - depósito, frete por conta, tipo de contato
>   - valor técnico por SKU (padrão: igual ao preço de tabela)
>   - tratamento do bônus
>   - "enviar clientes pendentes de conferência"
> - botões: "Conectar ao Bling", "Tornar ativa", "Sincronizar status", "Processar fila agora"
>
> **No detalhe do pedido (admin):** status da integração, ID/nº no Bling, mensagem de erro, botão **"Reprocessar envio ao Bling"** e histórico de eventos.
>
> **Sincronização:** função agendada a cada 15 min, que lê a situação no Bling e atualiza o status do portal pelo mapa: 21→enviado_erp, 6/15→em_conferencia, 24/18→aprovado, 9→faturado, 12→cancelado.

---

## Depois de pronto: testes

Peça ao Lovable para conferir, um por um, os testes da seção 11 da ESPECIFICACAO.md. Os mais importantes:
- 10 caixas → 1 bônus sem cobrar
- carrinho misto → 2 pedidos
- mesma chave → sem duplicar
- PDV não lê outro cliente
- falha do Bling não apaga o pedido
