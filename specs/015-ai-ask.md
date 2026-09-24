# US-015: Perguntas em linguagem natural sobre o dataset

## User story
Como analista de dados, eu quero fazer uma pergunta em linguagem natural sobre o meu dataset, para obter uma resposta rápida sem escrever uma query.

## Interface proposta
```bash
datatool ask vendas.csv "quais problemas existem nesse dataset?"
```

## Critérios de aceite
- [ ] Aceita a pergunta como argumento de texto livre
- [ ] A resposta é fundamentada no profiling já calculado ([003-profile-estatistico](003-profile-estatistico.md)), não em execução arbitrária de código sobre o arquivo pela IA
- [ ] Mesmo tratamento de erro de configuração de IA que [014-ai-explain](014-ai-explain.md)
- [ ] Feature **Pro** (ver [016-licenciamento-pro](016-licenciamento-pro.md))

## Fora de escopo
- Perguntas que exigem cálculo não coberto pelo profiling existente (ex.: joins com outro arquivo)

## Dependências
[014-ai-explain](014-ai-explain.md) (reaproveita a camada de integração com o provedor de IA)
