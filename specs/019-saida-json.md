# US-019: Saída estruturada em JSON (`--format json`)

## User story
Como engenheiro de dados que usa o datatool em scripts, notebooks e CI, eu quero que `info`, `profile` e `clean` possam emitir o resultado em JSON, para consumir o diagnóstico, o profiling e o relatório de limpeza sem parsear texto feito para humanos.

## Contexto
Origem: item [F03 do backlog](backlog-novas-features.md#f03--saída-estruturada---format-json).

Hoje os três comandos só imprimem texto em pt-BR, com números formatados (`1.234`), `⚠`, sugestões numeradas e mensagens intercaladas com a tabela do DataFrame. Parsear isso é frágil: qualquer ajuste de texto quebra quem consome.

O trabalho pesado já está feito e separado da impressão:
- [src/profiling.py](../src/profiling.py) devolve um dicionário com `ColumnProfile`s;
- [src/quality.py](../src/quality.py) devolve `Finding`s (`category`, `message`, `column`, `count`).

Esta spec transforma isso num **formato público e versionado**. Ele desbloqueia outras specs, que precisam de uma entrada estruturada:
- relatório HTML ([004](004-profile-relatorio-html.md));
- IA ([014](014-ai-explain.md), cujo critério exige "a saída estruturada de 003 e 005", e [015](015-ai-ask.md));
- quality gate para CI (F05 do backlog).

## Interface proposta
```bash
datatool info vendas.csv --format json | jq '.problems[] | select(.category == "nulls")'
datatool profile vendas.csv --format json > perfil.json
datatool clean vendas.csv --format json                                        # diagnóstico
datatool clean vendas.csv --fix-types --remove-duplicates --output limpo.parquet --format json
```

`--format text|json`, padrão `text`. Com `text`, nada muda em relação a hoje.

## Regras gerais do modo JSON
- O **stdout contém só um documento JSON** (um objeto, UTF-8, indentado com 2 espaços, acentos sem escape). Nenhum `print` de texto é misturado, nem os avisos que hoje saem durante as operações do `clean`.
- **Números são números**: sem formatação pt-BR, sem arredondar para 2 casas. `NaN`/`inf` viram `null`.
- **Valores das células** (top valores do profiling, exemplos de valores não convertidos) saem como string, número ou booleano JSON conforme o tipo; datas em ISO 8601; qualquer outro tipo, com `str()`.
- **Colunas na ordem do dataset**, para a saída ser determinística.
- **Envelope comum** a todos os comandos:

```json
{
  "schema_version": 1,
  "command": "info",
  "status": "ok",
  "file": {"path": "examples/clientes.csv", "format": "csv", "rows": 10, "columns": 6, "size_bytes": 711}
}
```

- **Erros também em JSON**, no stdout, com o mesmo exit code do modo texto. A mensagem é a mesma do modo texto:

```json
{
  "schema_version": 1,
  "command": "profile",
  "status": "error",
  "error": {"exit_code": 2, "message": "Unknown column(s) in --key: naoexiste"}
}
```

- **Versionamento:** `schema_version` começa em `1`. Adicionar campos não muda a versão. Remover ou renomear campos, ou mudar o significado de um campo, incrementa a versão. Isso é o contrato de que 004, 014, 015 e F05 dependem.

## `info --format json`
```json
{
  "schema_version": 1,
  "command": "info",
  "status": "ok",
  "file": {"path": "examples/clientes.csv", "format": "csv", "rows": 10, "columns": 6, "size_bytes": 711},
  "problems": [
    {"category": "nulls", "column": "email", "count": 3, "message": "3 valores nulos em \"email\""},
    {"category": "duplicates", "column": null, "count": 1, "message": "1 linhas duplicadas"},
    {"category": "dates", "column": "data_nascimento", "count": 5, "message": "\"data_nascimento\" contém 5 formatos de data diferentes"},
    {"category": "types", "column": "idade", "count": 9, "message": "\"idade\" está armazenada como texto mas parece numérica"}
  ],
  "suggestions": [
    {"category": "types", "label": "Corrigir tipos", "command": "datatool clean examples/clientes.csv --fix-types"},
    {"category": "duplicates", "label": "Remover duplicidades", "command": "datatool clean examples/clientes.csv --remove-duplicates"},
    {"category": "dates", "label": "Normalizar datas", "command": "datatool clean examples/clientes.csv --normalize-dates"},
    {"category": "nulls", "label": "Tratar valores nulos", "command": "datatool clean examples/clientes.csv --drop-null"}
  ]
}
```

Sem problemas, `problems` e `suggestions` são listas vazias.

**Significado de `count` por categoria** (é o mesmo número que já existe nos `Finding`s):

| `category` | Origem | `column` | `count` |
|------------|--------|----------|---------|
| `nulls` | info | coluna | valores nulos |
| `duplicates` | info | `null` | linhas inteiras duplicadas |
| `dates` | info | coluna | formatos de data distintos |
| `types` | info | coluna | valores **da amostra** (até 2.000) que parecem numéricos |
| `invalid_emails` | clean | coluna | valores com e-mail inválido |
| `phone_format_variance` | clean | coluna | formatos de telefone distintos |
| `whitespace` | clean | coluna | valores com espaços nas bordas |
| `key_duplicates` | clean | coluna | valores duplicados numa coluna que parece chave |
| `case_inconsistency` | clean | coluna | variações de capitalização |

Novas categorias (ex.: as de CPF/CNPJ de [018](018-cpf-cnpj-validacao.md)) entram nessa tabela sem mudar `schema_version`.

**`case_inconsistency`**: hoje a `message` desse `Finding` é a própria lista de variantes, uma por linha. No JSON, `message` passa a ser um resumo (`"4 variações de capitalização"`), e as variantes vão num campo `examples` (lista, até 10). O modo texto continua igual.

## `profile --format json`
```json
{
  "schema_version": 1,
  "command": "profile",
  "status": "ok",
  "file": {"path": "examples/clientes.csv", "format": "csv", "rows": 10, "columns": 6, "size_bytes": 711},
  "duplicates": {"total": 1, "by_key": null},
  "columns": [
    {
      "name": "nome", "dtype": "String", "kind": "categorical",
      "null_count": 0, "null_percent": 0.0,
      "stats": {
        "cardinality": 9,
        "top_values": [
          {"value": "Bruno Costa", "count": 2, "percent": 20.0},
          {"value": "Ana Silva", "count": 1, "percent": 10.0}
        ]
      }
    },
    {
      "name": "cpf", "dtype": "Int64", "kind": "numeric",
      "null_count": 0, "null_percent": 0.0,
      "stats": {"min": 11122233344, "max": 99900011122, "mean": 52222222221.7, "median": 50011122232.5,
                "std": 30544672345.701714, "p25": 22233344455.0, "p50": 55566677788.0, "p75": 77788899900.0,
                "outliers": 0}
    }
  ]
}
```

(Lista de colunas e `top_values` encurtadas; valores reais de [examples/clientes.csv](../examples/clientes.csv).) Com `--key cpf,email`: `"by_key": {"key_columns": ["cpf", "email"], "count": 0}`. `kind` é `numeric` ou `categorical`, como em [003](003-profile-estatistico.md); `dtype` é o nome do tipo polars.

## `clean --format json`
**Modo diagnóstico** (sem flags de operação): mesmo envelope, com `problems` no formato do `info` (as categorias de [005](005-clean-detectar-problemas.md)), sem `suggestions`.

**Modo operação**: uma lista `operations`, na ordem em que foram aplicadas, com os mesmos números que o modo texto imprime, e um objeto `output`:

```json
{
  "schema_version": 1,
  "command": "clean",
  "status": "ok",
  "file": {"path": "vendas.csv", "format": "csv", "rows": 1204, "columns": 8, "size_bytes": 98231},
  "operations": [
    {"operation": "remove_columns", "columns": ["coluna_temp"]},
    {"operation": "rename_columns", "mapping": {"Valor": "valor"}},
    {"operation": "trim"},
    {"operation": "normalize_dates", "columns": [
      {"column": "data_venda", "normalized": 312, "unrecognized_count": 2, "unrecognized_examples": ["ontem", "32/13/2020"]}
    ]},
    {"operation": "fix_types", "columns": [
      {"column": "valor", "type": "float", "failed_count": 1, "failed_examples": ["a combinar"]}
    ]},
    {"operation": "fill_null", "cells_filled": 14},
    {"operation": "drop_null", "rows_removed": 3},
    {"operation": "remove_duplicates", "rows_removed": 12}
  ],
  "output": {"path": "limpo.parquet", "format": "parquet", "rows": 1189, "columns": 7}
}
```

| `operation` | Campos |
|-------------|--------|
| `remove_columns` | `columns` (removidas) |
| `rename_columns` | `mapping` (antigo → novo) |
| `trim`, `lowercase`, `uppercase`, `normalize_case` | nenhum (o modo texto também não reporta contagem) |
| `normalize_dates` | `columns`: `column`, `normalized`, `unrecognized_count`, `unrecognized_examples` (até 10); lista vazia se nenhuma coluna de data foi encontrada |
| `fix_types` | `columns`: `column`, `type` (`int`/`float`), `failed_count`, `failed_examples` (até 10); lista vazia se nenhuma coluna foi encontrada |
| `fill_null` | `cells_filled` |
| `drop_null` | `rows_removed` |
| `remove_duplicates` | `rows_removed` |

**`--output` é obrigatório** no modo operação com `--format json`. Sem ele, o modo texto imprime o DataFrame no stdout, o que não cabe num documento JSON de relatório. Omitir `--output` gera erro (em JSON), exit code 2, sem processar nada. `output` descreve o arquivo gravado.

## Critérios de aceite
- [ ] `info`, `profile` e `clean` aceitam `--format text|json`; `text` é o padrão e produz exatamente a saída de hoje (testes existentes passam sem alteração)
- [ ] Com `--format json`, o stdout é um único documento JSON válido (`json.loads` do stdout inteiro funciona), sem nenhum texto adicional
- [ ] Todo documento tem `schema_version`, `command`, `status` e, quando o arquivo foi lido, `file`
- [ ] `info` emite `problems` e `suggestions`; `profile` emite `duplicates` e `columns` com as estatísticas de [003](003-profile-estatistico.md); `clean` emite `problems` (diagnóstico) ou `operations` + `output` (operação), nos formatos acima
- [ ] Números sem formatação pt-BR nem arredondamento; `NaN`/`inf` como `null`; valores não JSON nativos (datas etc.) serializados sem erro
- [ ] Erros (arquivo inexistente, formato não suportado, coluna desconhecida, etc.) saem como `{"status": "error", "error": {...}}`, com o mesmo exit code do modo texto
- [ ] `clean` em modo operação com `--format json` e sem `--output` gera erro claro, exit code 2, nada gravado
- [ ] `--format` com valor diferente de `text`/`json` é rejeitado pelo CLI com exit code != 0
- [ ] O formato está documentado no README (exemplos de `info`, `profile` e `clean`) e nesta spec

## Fora de escopo
- `--format json` no `convert` (o `--show-stats` é o único relatório dele) e nos comandos-esqueleto.
- Outros formatos (YAML, CSV do relatório, Markdown).
- Publicar um JSON Schema formal. As tabelas desta spec são a referência; um arquivo `schema.json` pode vir junto de 004/014.
- Incluir as linhas do DataFrame resultante no JSON do `clean`. Os dados vão para `--output`, e o JSON é só o relatório.
- Contagem de células alteradas por `--trim`/`--lowercase`/`--uppercase`/`--normalize-case` (não existe nem no modo texto).
- Exportar as linhas problemáticas de cada `problem`. É a extensão natural para quem precisa agir sobre os valores (ex.: CPFs inválidos de [018](018-cpf-cnpj-validacao.md)), mas envolve dados pessoais e merece uma decisão própria.

## Notas para implementação
- **Separar cálculo de apresentação no `clean`.** Hoje cada `_apply_*` de [src/clean.py](../src/clean.py) faz `print` do próprio resumo. Eles passam a devolver `(df, relatório)`, em que o relatório é um dicionário no formato da tabela de `operations`. Um renderizador de texto produz exatamente as linhas de hoje, e um de JSON serializa a lista. [src/info.py](../src/info.py) e [src/profiler.py](../src/profiler.py) já calculam antes de imprimir; só precisam do ramo JSON.
- **Mensagens de erro:** os pontos que hoje fazem `print(mensagem)` e `return código` passam a chamar um helper que imprime em texto ou em JSON, conforme o formato.
- **`Finding`:** ganha um campo opcional `examples` (padrão vazio), usado só por `case_inconsistency`. A `message` de texto desse detector continua sendo montada como hoje, para não mudar o modo texto.
- **Serialização:** `json.dumps(..., ensure_ascii=False, indent=2, default=...)`, com um `default` que trata `date`/`datetime` (ISO) e cai em `str()` para o resto. `NaN`/`inf` tratados antes (o `json` da stdlib gera `NaN`, que não é JSON válido).
- **`--format`:** pode reaproveitar o padrão de `Enum` já usado em [src/structures/](../src/structures/) (`FileType`, `EncodingType`) para o Typer validar os valores.
- **Log de [017](017-csv-delimitador-encoding.md):** não muda; o log continua sem valores de células mesmo quando o JSON do stdout os contém.

## Dependências
[002-info-diagnostico](002-info-diagnostico.md), [003-profile-estatistico](003-profile-estatistico.md), [005-clean-detectar-problemas](005-clean-detectar-problemas.md), operadores de [006](006-clean-operadores-string.md)–[011](011-clean-colunas.md). Desbloqueia [004](004-profile-relatorio-html.md), [014](014-ai-explain.md), [015](015-ai-ask.md) e a F05 do backlog.
