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

## Fora de escopo
- Exportação em HTML (spec 004)

## Dependências
[001-convert](001-convert.md) para leitura de arquivos. Reaproveita [002-info-diagnostico](002-info-diagnostico.md) para a contagem de linhas duplicadas.
