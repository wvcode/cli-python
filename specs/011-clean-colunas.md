# US-011: Renomear e remover colunas

## User story
Como analista de dados, eu quero renomear ou remover colunas de um dataset, para padronizar o schema antes de usá-lo em outra ferramenta.

## Contexto
Implementado em [src/clean.py](../src/clean.py), como mais duas flags de operação do comando `clean` (junto das de [006](006-clean-operadores-string.md)–[010](010-clean-corrigir-tipos.md)).

## Interface proposta
```bash
datatool clean vendas.csv --rename-columns old_name:new_name,foo:bar
datatool clean vendas.csv --remove-columns coluna_interna,coluna_temp
```

## Critérios de aceite
- [x] `--rename-columns` renomeia as colunas especificadas preservando os dados
- [x] `--remove-columns` remove as colunas especificadas
- [x] Erro claro (sem alterar o arquivo) se uma coluna referenciada não existir no dataset

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestCleanColumns`).

## Nota de implementação
- Ordem: `--remove-columns` → `--rename-columns` → demais operações (texto → `--normalize-dates` → `--fix-types` → `--fill-null` → `--drop-null` → `--remove-duplicates`). Consequências:
  - `--key`, `--columns`, `--date-columns` e `--fill-null coluna:valor` referenciam os nomes **depois** da renomeação;
  - colunas removidas não entram na deduplicação por linha inteira nem nos relatórios de `--fix-types`/`--normalize-dates`;
  - `--rename-columns` não pode referenciar uma coluna removida na mesma execução.
- Erros, todos com exit code != 0 e sem gravar nada: coluna inexistente (em qualquer das duas flags), entrada de `--rename-columns` sem `:` ou com nome vazio, e renomeação que geraria colunas com o mesmo nome (ex.: `nome:email` quando `email` já existe).
- Nomes de coluna com `,` ou `:` não podem ser referenciados por essas flags.
- Reporta no stdout `N colunas removidas` / `N colunas renomeadas`, mesmo quando o resultado é gravado via `--output`.

## Dependências
[001-convert](001-convert.md), [006-clean-operadores-string](006-clean-operadores-string.md)
