# Pacote para o Lovable — Portal Comercial The Bulldog

## O que tem aqui
| Arquivo / pasta | Para quê |
|---|---|
| `PROMPTS_LOVABLE.md` | **Comece por aqui.** São 7 prompts, para colar no Lovable um por vez, na ordem |
| `ESPECIFICACAO.md` | Especificação completa: regras, telas, banco, integração com o Bling, testes |
| `DECISOES_E_PENDENCIAS.md` | Histórico das decisões e o que ainda falta definir |
| `assets/bulldog.svg` | Logo (só o bulldog no círculo azul) |
| `assets/produtos/*.webp` | 27 fotos sem fundo, com o nome do arquivo igual ao SKU |
| `dados/produtos.csv` / `.json` | Os 27 produtos: linha, unidade, preço, ID no Bling (conta ST) e foto |
| `referencia/RETORNO_DIAGNOSTICO_...md` | Diagnóstico da conta Bling da ST Nicolas |
| `referencia/telas/` | Telas do protótipo, como referência visual |
| raiz do repositório (`app/`, `frontend/`, `tests/`) | Protótipo funcional em Python, que serve de referência para as regras |

## Importante antes de começar
- **O Lovable não roda o protótipo em Python.** Ele gera o portal em React + Supabase. Por isso o pacote leva a especificação e os dados, e o código vai só como referência.
- **Conecte o Supabase** no projeto do Lovable antes do prompt 1.
- **Não construa tudo num prompt só.** Siga os 7 prompts na ordem e teste cada etapa.
- **O Bling vem por último** (prompt 7), e começa em modo **simulado**. Não ligue o modo "Bling real" sem antes resolver as pendências fiscais de `DECISOES_E_PENDENCIAS.md`.
- **Credenciais do Bling** (client id/secret) vão em **Supabase Secrets**, nunca no código nem no chat do Lovable.

## Como anexar no Lovable
- O Lovable aceita imagens anexadas no chat. Anexe o `bulldog.svg` no prompt 1 e as fotos de `assets/produtos/` no prompt 2. Se ele não aceitar 27 de uma vez, mande em lotes.
- O conteúdo do CSV pode ser colado no chat, ou anexado se ele aceitar.
- Se o seu projeto do Lovable estiver ligado ao GitHub, também dá para subir a pasta `assets/` direto no repositório (em `public/`).
