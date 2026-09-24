# US-006: Operadores de limpeza de texto (trim, case)

## User story
Como analista de dados, eu quero normalizar espaços e capitalização de colunas de texto, para eliminar duplicidades causadas por formatação inconsistente (ex.: "Porto Alegre" vs "PORTO ALEGRE").

## Interface proposta
```bash
datatool clean clientes.csv --trim --normalize-case
datatool clean clientes.csv --lowercase
datatool clean clientes.csv --uppercase
```

## Critérios de aceite
- [ ] `--trim` remove espaços extras nas bordas de todos os valores de colunas texto
- [ ] `--lowercase` / `--uppercase` convertem o texto das colunas string
- [ ] `--normalize-case` unifica variações de capitalização (ex.: title case) para um único valor canônico por categoria
- [ ] Flags são combináveis na mesma execução
- [ ] Colunas não-texto não são alteradas

## Dependências
[001-convert](001-convert.md)
