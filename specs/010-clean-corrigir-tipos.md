# US-010: Corrigir tipos de colunas

## User story
Como analista de dados, eu quero que colunas numéricas armazenadas como texto sejam convertidas para o tipo correto, incluindo valores monetários em formato brasileiro, para poder fazer cálculos sobre elas.

## Contexto
Exemplo citado na ideia: coluna "Valor" contendo `R$` e separadores brasileiros (`1.234,56`).

## Interface proposta
```bash
datatool clean relatorio.xlsx --fix-types
```

## Critérios de aceite
- [ ] Detecta colunas que são numéricas mas estão armazenadas como string
- [ ] Remove símbolo de moeda (`R$`) e normaliza separador de milhar/decimal brasileiro (`1.234,56` → `1234.56`)
- [ ] Converte a coluna para tipo numérico apropriado (`int`/`float`)
- [ ] Reporta quais colunas foram convertidas e quantos valores falharam na conversão (sem interromper o processamento das demais)

## Dependências
[001-convert](001-convert.md)
