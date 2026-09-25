# US-008: Tratar valores nulos

## User story
Como analista de dados, eu quero preencher ou remover valores nulos, para que o dataset fique consistente para análise.

## Contexto
Implementado em [src/clean.py](../src/clean.py), como mais duas flags de operação do comando `clean` (junto das de [006](006-clean-operadores-string.md)/[007](007-clean-remover-duplicidades.md)).

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

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestCleanFillNull`, `TestCleanDropNull`).

## Nota de implementação
- `--fill-null` é repetível (`--fill-null "N/A" --fill-null "idade:0"`) e cada ocorrência é uma destas duas formas:
  - **sem `:`** — valor global, aplicado só às colunas de texto (`Utf8`). Colunas numéricas/data são preservadas: um valor de texto arbitrário não é um "número" ou "data" válido para preencher essas colunas, então o padrão evita converter a coluna inteira para texto silenciosamente.
  - **`coluna:valor`** — aplica só a essa coluna; o valor é convertido para `int`/`float` quando a coluna é numérica (ex.: `idade:0`), senão usado como string. Coluna inexistente é erro claro, exit code != 0, nada é gravado.
- `--drop-null` usa `df.drop_nulls(subset=...)`; sem `--columns`, considera nulos em qualquer coluna. Coluna inexistente em `--columns` é erro claro, exit code != 0.
- Ambas reportam a contagem no stdout (`"N células preenchidas"` / `"N linhas removidas"`), mesmo quando o resultado é gravado em arquivo via `--output`.
- Combinável com as flags de [006](006-clean-operadores-string.md)/[007](007-clean-remover-duplicidades.md); ordem de aplicação: operadores de texto → `--fill-null` → `--drop-null` → `--remove-duplicates`.

## Dependências
[001-convert](001-convert.md), [006-clean-operadores-string](006-clean-operadores-string.md), [007-clean-remover-duplicidades](007-clean-remover-duplicidades.md)
