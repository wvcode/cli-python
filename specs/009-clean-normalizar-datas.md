# US-009: Normalizar formatos de data

## User story
Como analista de dados, eu quero normalizar colunas de data que estão em formatos diferentes, para um único formato consistente.

## Contexto
Exemplo citado na ideia: `data_nascimento` com 18 formatos diferentes.

## Interface proposta
```bash
datatool clean clientes.csv --normalize-dates
datatool clean clientes.csv --normalize-dates --date-columns data_nascimento,data_cadastro
```

## Critérios de aceite
- [ ] Detecta automaticamente colunas candidatas a data quando `--date-columns` não é informado
- [ ] Reconhece ao menos os formatos comuns: `dd/mm/yyyy`, `mm/dd/yyyy`, `yyyy-mm-dd`, `dd-mm-yy`
- [ ] Converte todos os valores reconhecidos para ISO 8601 (`yyyy-mm-dd`)
- [ ] Valores não reconhecíveis são reportados na saída, não descartados silenciosamente

## Dependências
[001-convert](001-convert.md)
