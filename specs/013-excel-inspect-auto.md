# US-013: Inspeção e limpeza automática de Excel bagunçado

## User story
Como analista que recebe planilhas Excel desorganizadas, eu quero inspecionar o arquivo e aplicar uma limpeza automática com um único comando, para transformar uma planilha bagunçada em um dataset pronto para análise.

## Contexto
Nicho de posicionamento comercial descrito na ideia ("Excel → dados profissionais"), com o exemplo `relatorio_vendas_final_FINAL2.xlsx`.

## Interface proposta
```bash
datatool inspect relatorio_vendas_final_FINAL2.xlsx
datatool clean relatorio_vendas_final_FINAL2.xlsx --auto
```

## Critérios de aceite
- [ ] `inspect` roda os mesmos diagnósticos de [002-info-diagnostico](002-info-diagnostico.md) e [005-clean-detectar-problemas](005-clean-detectar-problemas.md), adaptados a particularidades de Excel (múltiplas abas, cabeçalho fora da primeira linha)
- [ ] `--auto` aplica uma sequência padrão de limpeza (corrigir tipos, tratar nulos, remover duplicidades, normalizar datas, tratar moeda BR) sem exigir flags individuais
- [ ] Gera um arquivo `<nome>_clean.parquet` com o resultado
- [ ] Gera um relatório `<nome>_quality.html` (reaproveita [004-profile-relatorio-html](004-profile-relatorio-html.md))

## Dependências
[002](002-info-diagnostico.md), [005](005-clean-detectar-problemas.md), [006](006-clean-operadores-string.md)-[011](011-clean-colunas.md), [004](004-profile-relatorio-html.md)
