# US-003: Profiling estatístico de um dataset

## User story
Como analista de dados, eu quero gerar estatísticas completas de um dataset, para entender sua distribuição e qualidade sem escrever código exploratório manualmente.

## Contexto
Camada 2 da ideia ("Data profiling"), apontada como um dos principais diferenciais do produto.

Implementado em [src/profiling.py](../src/profiling.py) (cálculo das estatísticas por coluna, sem I/O — reutilizável pela futura spec 004) e [src/profiler.py](../src/profiler.py) (leitura do arquivo e impressão no terminal). O módulo foi nomeado `profiler.py`, e não `profile.py`, para não colidir com o módulo `profile` da stdlib do Python. A contagem de duplicidade reaproveita `duplicate_row_count` de [src/quality.py](../src/quality.py) (mesma spec 002).

## Interface proposta
```bash
datatool profile vendas.csv
datatool profile vendas.csv --key cpf
```

## Critérios de aceite
- [x] Para colunas numéricas: min, max, média, mediana, desvio padrão, percentis (25/50/75) e outliers (método IQR)
- [x] Para colunas categóricas/texto: cardinalidade, top-N valores mais frequentes, distribuição das categorias
- [x] Para todas as colunas: contagem e percentual de nulos
- [x] Detecta duplicidade de linhas inteiras e, opcionalmente, por chave informada via `--key`
- [x] Saída legível no terminal (uma seção por coluna)

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestProfileCommand`). Testado manualmente com 200 mil linhas (~0,2s).

## Nota de implementação
- "Colunas numéricas" = qualquer dtype numérico do polars (`dtype.is_numeric()`); as demais (texto, booleano, data) caem no ramo categórico.
- Top-N usa N=5 e cobre ao mesmo tempo "top-N mais frequentes" e "distribuição das categorias" (percentual de cada uma sobre o total de valores não nulos) — não lista a distribuição completa para colunas de alta cardinalidade.
- Percentis (p25/p50/p75) calculados com interpolação linear (`quantile(..., interpolation="linear")`), o mesmo padrão de pandas/numpy. Assim `p50` é sempre igual à mediana. Até a spec [019](019-saida-json.md) o cálculo usava o padrão do polars (`nearest`, que devolve um valor existente na coluna), e `p50` podia divergir da mediana.
- Outliers via IQR: `[Q1 - 1.5*IQR, Q3 + 1.5*IQR]`, com Q1/Q3 = p25/p75 acima.
- `--key` aceita uma ou mais colunas separadas por vírgula; se alguma coluna não existir, retorna erro com exit code != 0.

## Extensão — seleção e limite de colunas (`--columns`, `--max-columns`)
Adicionada ao planejar [020-mcp-server](020-mcp-server.md): um agente que chama `profile` via MCP num dataset largo (muitas colunas) recebe uma resposta grande demais para o contexto do modelo. A extensão é genericamente útil também para uso direto do CLI (relatórios exportados de ERPs com centenas de colunas), então fica no `profile`, não só na camada MCP.

```bash
datatool profile vendas.csv --columns preco,quantidade
datatool profile vendas.csv --max-columns 50
```

### Critérios de aceite da extensão
- [x] `--columns col1,col2` restringe o profiling a essas colunas (mantendo `duplicates`/`duplicates_total`, que são do dataset inteiro, não por coluna); coluna inexistente é erro claro, exit code != 0, igual a `--key`
- [x] `--max-columns N`: se, depois de aplicar `--columns` (quando informado), sobrarem mais de N colunas, só as N primeiras (ordem do dataset) são perfiladas
- [x] Sem `--max-columns`, o comportamento é o de hoje (todas as colunas) — a flag é puramente aditiva, nenhum critério já marcado nesta spec muda
- [x] Em `--format json` (spec [019](019-saida-json.md)), quando há truncamento por `--max-columns`, o documento traz `"columns_returned"` (quantas vieram), `"columns_total"` (quantas existem após `--columns`) e `"truncated_columns"` (nomes das que ficaram de fora, para pedir depois via `--columns`)
- [x] Em `--format text`, quando há truncamento, uma linha ao final avisa quantas colunas ficaram de fora e sugere `--columns`
- [x] `--columns` e `--max-columns` são combináveis com `--key`

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestProfileColumnsFilter`). A saída padrão (sem `--columns`/`--max-columns`) foi comparada com a versão anterior à extensão e é idêntica.

#### Nota de implementação
- `profiling.py`'s `profile(df, key_columns=None, columns=None)` ganhou o parâmetro `columns`: quando informado, só essas colunas viram `ColumnProfile`; `rows`/`columns` (largura) e `duplicates_total` continuam calculados sobre `df` inteiro, não sobre a seleção.
- A ordem final de colunas ignora a ordem digitada em `--columns` — [src/profiler.py](../src/profiler.py) filtra `df.columns` (que já está na ordem do dataset) pelo conjunto pedido, e só então aplica `--max-columns` cortando os N primeiros dessa lista. Isso é o que garante "ordem do dataset" mesmo com `--columns idade,nome` (nome vem antes de idade no dataset de exemplo).
- `--max-columns` com valor menor que 1 é erro claro, exit code 2, por segurança (evita fatiar com índice negativo); a spec original não previa esse valor, mas o comportamento sem essa checagem seria confuso.
- `columns_returned`/`columns_total`/`truncated_columns` só aparecem no JSON quando há truncamento de fato — sem `--max-columns`, ou com `--max-columns` maior que o total de colunas, o documento é idêntico ao de antes desta extensão.

## Fora de escopo
- Exportação em HTML (spec 004)

## Dependências
[001-convert](001-convert.md) para leitura de arquivos. Reaproveita [002-info-diagnostico](002-info-diagnostico.md) para a contagem de linhas duplicadas.
