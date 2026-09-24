# US-008: Tratar valores nulos

## User story
Como analista de dados, eu quero preencher ou remover valores nulos, para que o dataset fique consistente para análise.

## Interface proposta
```bash
datatool clean clientes.csv --fill-null "N/A"
datatool clean clientes.csv --drop-null
```

## Critérios de aceite
- [ ] `--fill-null valor` substitui nulos pelo valor informado; aceita também `coluna:valor` para aplicar por coluna
- [ ] `--drop-null` remove linhas com nulos (todas as colunas por padrão, ou colunas especificadas via `--columns`)
- [ ] Ambas as operações reportam a quantidade de células/linhas afetadas

## Dependências
[001-convert](001-convert.md)
