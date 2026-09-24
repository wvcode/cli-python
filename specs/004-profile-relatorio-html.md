# US-004: Relatório de profiling em HTML

## User story
Como analista de dados, eu quero exportar o profiling como um relatório HTML, para compartilhar um resultado visual com outras pessoas do time.

## Contexto
Citado explicitamente na ideia como algo "muito mais útil do que simplesmente imprimir estatísticas no terminal". Candidato natural a feature **Pro** (ver [016-licenciamento-pro](016-licenciamento-pro.md)).

## Interface proposta
```bash
datatool profile vendas.csv --output report.html
```

## Critérios de aceite
- [ ] Gera um arquivo HTML autocontido (sem dependência de rede em runtime para abrir)
- [ ] Contém as mesmas métricas de [003-profile-estatistico](003-profile-estatistico.md), em formato visual (tabelas e/ou gráficos)
- [ ] Abre corretamente em navegador, sem erros de console
- [ ] Funciona para datasets de até ~200 mil linhas sem travar o navegador

## Fora de escopo
- Customização de tema/branding do relatório

## Dependências
[003-profile-estatistico](003-profile-estatistico.md)
