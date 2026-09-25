# US-006: Operadores de limpeza de texto (trim, case)

## User story
Como analista de dados, eu quero normalizar espaços e capitalização de colunas de texto, para eliminar duplicidades causadas por formatação inconsistente (ex.: "Porto Alegre" vs "PORTO ALEGRE").

## Contexto
Implementado em [src/clean.py](../src/clean.py), estendendo o comando `clean` da spec 005: sem nenhuma das flags abaixo, o comportamento continua sendo o diagnóstico somente-leitura de [005-clean-detectar-problemas](005-clean-detectar-problemas.md); com pelo menos uma flag de operação, o comando passa a transformar os dados e apresenta o resultado via `--output` (grava em arquivo, formato inferido pela extensão, mesma infraestrutura de [001-convert](001-convert.md)) ou, se omitido, imprime o DataFrame resultante no stdout — nada é gravado por padrão.

## Interface proposta
```bash
datatool clean clientes.csv --trim --normalize-case --output clientes_limpo.csv
datatool clean clientes.csv --lowercase --output clientes_limpo.csv
datatool clean clientes.csv --uppercase --output clientes_limpo.csv
```

## Critérios de aceite
- [x] `--trim` remove espaços extras nas bordas de todos os valores de colunas texto
- [x] `--lowercase` / `--uppercase` convertem o texto das colunas string
- [x] `--normalize-case` unifica variações de capitalização (ex.: title case) para um único valor canônico por categoria
- [x] Flags são combináveis na mesma execução
- [x] Colunas não-texto não são alteradas

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestCleanStringOperators`).

## Nota de implementação
- As flags são aplicadas nesta ordem, apenas em colunas de tipo texto (`Utf8`): `--trim` → `--lowercase` → `--uppercase` → `--normalize-case`. Combinar `--lowercase` e `--uppercase` na mesma execução não é um erro; como ambas operam sobre a coluna inteira, a última da ordem acima "vence".
- `--normalize-case` aplica title case a cada valor (`"PORTO ALEGRE"`/`"porto alegre"`/`"Porto Alegre"` → `"Porto Alegre"`); não há agrupamento por categoria com escolha de forma mais frequente — o valor canônico é sempre o resultado do title case.
- `--output` reaproveita `infer_file_type`/`save_function` de [001-convert](001-convert.md): mesma inferência por extensão e mesmos erros (extensão não suportada, diretório sem permissão de escrita).

## Dependências
[001-convert](001-convert.md), [005-clean-detectar-problemas](005-clean-detectar-problemas.md)
