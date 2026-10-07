# US-008: Tratar valores nulos

## User story
Como analista de dados, eu quero preencher ou remover valores nulos, para que o dataset fique consistente para análise.

## Contexto
Implementado em [src/datatool/clean.py](../src/datatool/clean.py), como mais duas flags de operação do comando `clean` (junto das de [006](006-clean-operadores-string.md)/[007](007-clean-remover-duplicidades.md)).

## Interface proposta
```bash
datatool clean clientes.csv --fill-null "N/A"
datatool clean clientes.csv --fill-null "idade:0"
datatool clean clientes.csv --drop-null
datatool clean clientes.csv --drop-null --columns email
```

## Critérios de aceite
- [x] `--fill-null valor` substitui nulos pelo valor informado; aceita também `coluna:valor` para aplicar por coluna
- [x] `--drop-null` remove linhas com nulos (todas as colunas por padrão, ou colunas especificadas via `--columns`)
- [x] Ambas as operações reportam a quantidade de células/linhas afetadas

Coberto por testes em [tests/test_cli.py](../tests/test_cli.py) (`TestCleanFillNull`, `TestCleanDropNull`).

## Nota de implementação
- `--fill-null` é repetível (`--fill-null "N/A" --fill-null "idade:0"`) e cada ocorrência é uma destas duas formas:
  - **sem `:`** — valor global, aplicado só às colunas de texto (`Utf8`). Colunas numéricas/data são preservadas: um valor de texto arbitrário não é um "número" ou "data" válido para preencher essas colunas, então o padrão evita converter a coluna inteira para texto silenciosamente.
  - **`coluna:valor`** — aplica só a essa coluna; o valor é convertido para `int`/`float` quando a coluna é numérica (ex.: `idade:0`), senão usado como string. Coluna inexistente é erro claro, exit code != 0, nada é gravado.
- `--drop-null` usa `df.drop_nulls(subset=...)`; sem `--columns`, considera nulos em qualquer coluna. Coluna inexistente em `--columns` é erro claro, exit code != 0.
- Ambas reportam a contagem no stdout (`"N células preenchidas"` / `"N linhas removidas"`), mesmo quando o resultado é gravado em arquivo via `--output`.
- Combinável com as flags de [006](006-clean-operadores-string.md)/[007](007-clean-remover-duplicidades.md); ordem de aplicação: operadores de texto → `--fill-null` → `--drop-null` → `--remove-duplicates`.

## Extensão — `--null-values` (2026-10-07)
Adicionada junto com o débito técnico DT49, que fez o `--fix-types` deixar de converter colunas com valores que não são números. Antes, uma coluna de idades com `N/D` virava número, e o `N/D`, nulo; depois do DT49, ela fica como texto, e faltava um jeito explícito de dizer que `N/D` é "sem dado".

```bash
datatool clean dados.csv --null-values "N/D,-" --fix-types
```

- [x] `--null-values v1,v2` troca por nulo, em todas as colunas de texto, as células iguais a um desses valores, comparadas sem os espaços nas pontas e diferenciando maiúsculas de minúsculas; colunas de outros tipos não mudam
- [x] Roda antes de todas as operações de valor (inclusive `--trim` e `--lowercase`), então `--fix-types`, `--fill-null` e `--drop-null` já recebem os nulos
- [x] Reporta `N células trocadas por nulo` (`cells_replaced` no JSON); `null_values` no `datatool_clean_apply` do servidor MCP
- [x] Quando o `--fix-types` deixa uma coluna sem converter, o texto sugere `--null-values`

Coberto por testes em [tests/test_clean_operations.py](../tests/test_clean_operations.py) (`TestCleanNullValues`) e [tests/test_mcp_server.py](../tests/test_mcp_server.py).

## Dependências
[001-convert](001-convert.md), [006-clean-operadores-string](006-clean-operadores-string.md), [007-clean-remover-duplicidades](007-clean-remover-duplicidades.md)
