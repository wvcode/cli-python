# US-007: Remover duplicidades

## User story
Como analista de dados, eu quero remover registros duplicados, para garantir que cada entidade apareça uma única vez no dataset.

## Contexto
Implementado em [src/clean.py](../src/clean.py), como mais uma flag de operação do comando `clean` (junto das de [006-clean-operadores-string](006-clean-operadores-string.md)). `--key` reaproveita o mesmo parsing/validação de coluna-chave do `--key` de [003-profile-estatistico](003-profile-estatistico.md).

## Interface proposta
```bash
datatool clean clientes.csv --remove-duplicates
datatool clean clientes.csv --remove-duplicates --key cpf
```

## Critérios de aceite
- [x] Por padrão remove linhas totalmente duplicadas (todas as colunas iguais)
- [x] `--key coluna1,coluna2` permite deduplicar por subconjunto de colunas
- [x] Reporta a quantidade de linhas removidas
- [x] Mantém a primeira ocorrência por padrão (comportamento documentado)

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestCleanRemoveDuplicates`).

## Nota de implementação
- Implementado com `df.unique(subset=key_columns, keep="first", maintain_order=True)` — mantém a primeira ocorrência e preserva a ordem original das linhas remanescentes.
- Quando combinado com as flags de [006](006-clean-operadores-string.md) (`--trim`, `--lowercase`, `--uppercase`, `--normalize-case`), essas são aplicadas **antes** da remoção de duplicidades — assim, linhas que só diferiam por espaços/capitalização também são deduplicadas depois de normalizadas. Essa ordem segue o pipeline de exemplo da `ideia.md` (`--trim --normalize-case --deduplicate --fix-types`).
- Coluna inexistente em `--key` retorna erro claro e exit code != 0, sem gravar nada (mesma validação de [003](003-profile-estatistico.md)).
- A quantidade de linhas removidas é sempre impressa no stdout, mesmo quando o resultado é gravado em arquivo via `--output`.

## Dependências
[001-convert](001-convert.md), [006-clean-operadores-string](006-clean-operadores-string.md)
