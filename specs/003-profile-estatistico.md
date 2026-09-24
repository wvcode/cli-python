# US-003: Profiling estatístico de um dataset

## User story
Como analista de dados, eu quero gerar estatísticas completas de um dataset, para entender sua distribuição e qualidade sem escrever código exploratório manualmente.

## Contexto
Camada 2 da ideia ("Data profiling"), apontada como um dos principais diferenciais do produto.

## Interface proposta
```bash
datatool profile vendas.csv
```

## Critérios de aceite
- [ ] Para colunas numéricas: min, max, média, mediana, desvio padrão, percentis (25/50/75) e outliers (ex.: método IQR)
- [ ] Para colunas categóricas/texto: cardinalidade, top-N valores mais frequentes, distribuição das categorias
- [ ] Para todas as colunas: contagem e percentual de nulos
- [ ] Detecta duplicidade de linhas inteiras e, opcionalmente, por chave informada via `--key`
- [ ] Saída legível no terminal (tabela por coluna)

## Fora de escopo
- Exportação em HTML (spec 004)

## Dependências
[001-convert](001-convert.md) para leitura de arquivos.
