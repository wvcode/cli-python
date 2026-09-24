# US-007: Remover duplicidades

## User story
Como analista de dados, eu quero remover registros duplicados, para garantir que cada entidade apareça uma única vez no dataset.

## Interface proposta
```bash
datatool clean clientes.csv --remove-duplicates
datatool clean clientes.csv --remove-duplicates --key cpf
```

## Critérios de aceite
- [ ] Por padrão remove linhas totalmente duplicadas (todas as colunas iguais)
- [ ] `--key coluna1,coluna2` permite deduplicar por subconjunto de colunas
- [ ] Reporta a quantidade de linhas removidas
- [ ] Mantém a primeira ocorrência por padrão (comportamento documentado)

## Dependências
[001-convert](001-convert.md)
