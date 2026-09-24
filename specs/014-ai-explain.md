# US-014: Explicação em linguagem natural dos problemas do dataset

## User story
Como analista de dados, eu quero um resumo em linguagem natural dos problemas de qualidade do meu dataset, para entender rapidamente o que precisa de atenção sem interpretar tabelas de estatísticas.

## Contexto
Camada de IA opcional da ideia: "A IA interpreta o profiling produzido pela ferramenta" — não é um chatbot livre sobre o arquivo, é uma camada de narrativa sobre dados já calculados deterministicamente.

## Interface proposta
```bash
datatool explain vendas.csv
```

## Critérios de aceite
- [ ] A entrada do modelo de IA é a saída estruturada de [003-profile-estatistico](003-profile-estatistico.md) e [005-clean-detectar-problemas](005-clean-detectar-problemas.md) — a IA não recebe o dataset bruto nem inventa métricas
- [ ] O texto gerado cita números reais do profiling (ex.: "3,2% de duplicidades em customer_id")
- [ ] Sem uma API key de IA configurada, o comando retorna erro claro orientando a configuração, em vez de travar ou falhar silenciosamente
- [ ] Feature **Pro** (ver [016-licenciamento-pro](016-licenciamento-pro.md))

## Dependências
[003-profile-estatistico](003-profile-estatistico.md), [005-clean-detectar-problemas](005-clean-detectar-problemas.md)
