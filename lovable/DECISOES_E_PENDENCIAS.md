# Decisões e pendências — histórico da conversa (07–08/10/2026)

## Como chegamos até aqui
1. **Diagnóstico do Bling (conta ST Nicolas)**, somente leitura. Relatório completo em `referencia/RETORNO_DIAGNOSTICO_PORTAL_COMERCIAL_BULLDOG.md`. Principais achados:
   - não existe **nenhum pedido de venda** no Bling; toda venda foi por NF-e direta
   - preço praticado não está cadastrado (variou de R$ 5,20 a R$ 6,20 por lata no valor final)
   - clientes misturados com fornecedores e pessoas; só 1 marcado como "Cliente"
   - a NF 000005 foi rejeitada por IE errada (cliente marcado como "ISENTO")
   - todo o histórico de venda é RJ; a venda ao PDV em SP com ICMS-ST nunca passou pelo Bling
2. **Brief V1** (ChatGPT/Leonardo): portal cria pedidos, sem NF-e; integração desacoplada por conta (ST hoje, DFJ amanhã); R$ 5,90/lata; 10+1; pagamento e frete informativos.
3. **Protótipo funcional** construído em Python (FastAPI) + HTML/JS, com 44 testes automáticos. Está em `referencia/codigo-referencia-python.zip`; use como referência das regras, não para rodar no Lovable.

## Decisões tomadas (em ordem)
| # | Decisão |
|---|---|
| 1 | Portal cria só pedidos; NF-e manual no Bling |
| 2 | Integração configurável por conta Bling (ST Nicolas = base técnica; DFJ = definitiva) |
| 3 | Energético: Tradicional e Zero Açúcar, só caixa de 24, R$ 5,90/lata = R$ 141,60/caixa |
| 4 | Campanha 10+1 só para energético, cumulativa, bônus nunca cobrado |
| 5 | Pagamento sugerido: 1ª compra 50%+50% em 28 dias; 4ª em diante 30/60; 2ª–3ª a definir |
| 6 | Frete grátis ≥ 100 cx SP / ≥ 200 cx fora; **prazo SP 3 a 5 dias úteis**; demais 7–15 dias |
| 7 | Só CNPJ (sem pessoa física); duplicidade pelo CNPJ completo; cliente novo fica pendente de conferência |
| 8 | **Layout branco**; logo = **só o bulldog com o círculo azul**, sem textos |
| 9 | **Tabacaria incluída**: 25 itens com preço de **atacado** do Catálogo da Distribuidora de 30/09/2026 |
| 10 | Tabacaria vendida por **display**, exceto **MaryMill e Zippo, vendidos por unidade** |
| 11 | **Referência online removida do sistema** (é só sugestão de revenda, não importa na compra) |
| 12 | Carrinho misto vira **2 pedidos** (um por linha), porque cada linha tem nota própria |
| 13 | A tabacaria **nunca herda** a natureza de operação do energético |
| 14 | **Fotos sem fundo** de todos os produtos, da pasta do Drive *Produtos_Fotos_SEM_FUNDO* |
| 15 | **A DFJ fatura em SP.** O estoque foi enviado pela ST em consignação mercantil (NFs 000020 e 000021, entradas em 08/10/2026). **O portal conecta só o Bling da DFJ** |

## Pendências (não travam o desenvolvimento, mas travam o primeiro faturamento)
1. **Natureza de operação/CFOP na DFJ** para o energético e para a tabacaria, considerando que a mercadoria foi recebida em **consignação** (Itamaraty). Hoje a natureza padrão de venda da DFJ é "a não contribuinte", errada para bar/tabacaria com IE, e não existe natureza de venda de mercadoria consignada.
2. **Valor técnico do item no Bling.** Se a nota somar ICMS-ST em cima de R$ 5,90, o bar paga mais que R$ 5,90. É preciso definir o valor-base.
3. **Bonificação (caixa bônus)** na nota: a DFJ tem a natureza "Saída em bonificação"; a Itamaraty confirma se é ela.
4. **Acerto do consignado ST → DFJ:** como e quando a ST fatura para a DFJ o que foi vendido (o portal pode gerar o relatório mensal por SKU).
5. **Campanha "primeiros pedidos de cada região":** quantos pedidos, e se região é UF ou cidade.
6. **Pagamento da 2ª e da 3ª compra.**
7. **Liberação da Smoking Line pela Sara/Itamaraty** e correção da NF 000002. Até lá, deixar a tabacaria desligada no admin.
8. **Quem autoriza o OAuth:** usuário administrador do Bling da DFJ.

### Resolvido em 08/10/2026 (lido no Bling da DFJ)
- Quem fatura em SP: **DFJ**.
- Produtos cadastrados na DFJ com os mesmos SKUs e preços do portal; IDs na coluna `bling_id_conta_dfj`.
- MaryMill já desmembrado na DFJ (`TB-IMP-023-U` = 24 un.; display zerado).
- Depósito único "Geral"; "Gerar NF-e ao incluir pedido" desativado; nenhum pedido de venda ainda (próximo número 1).

## Pontos de atenção de cadastro
- A IE **não aparece no cartão CNPJ**. Consulte no Cadesp (cadesp.fazenda.sp.gov.br → Consulta Pública ao Cadastro) ou no CCC. Exemplo pendente: NEO CONVENIENCIA LTDA (NEO TOBACCO), CNPJ 59.389.125/0001-06, ainda sem IE localizada.
- Nunca cadastrar como "isento" ou "não contribuinte" só para conseguir salvar.

## Fotos: o que conferir
- Dichavador plant-based: a foto "Branco" é bem creme.
- Seda em rolo Silver: a caixa da foto parece dizer "5 meters", mas o catálogo diz 4 m.
- Latas do energético vieram de *Energy_sem_fundo* (bulldog_normal / bulldog_zero).
