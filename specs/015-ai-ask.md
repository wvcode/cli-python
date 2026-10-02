# US-015: Perguntas em linguagem natural sobre o dataset

## User story
Como analista de dados, eu quero fazer uma pergunta em linguagem natural sobre o meu dataset, para obter uma resposta rápida sem escrever uma query.

## Contexto
Complemento do [014](014-ai-explain.md): mesma entrada (os documentos JSON de `info`, diagnóstico do `clean` e `profile`, redigidos por padrão), mesmo provedor e mesma configuração, mas com uma pergunta livre no lugar do resumo. Feature **Pro** (ver [016-licenciamento-pro](016-licenciamento-pro.md)).

O limite é o que os documentos contêm. Eles cobrem estatísticas por coluna, duplicidade, nulos e os problemas de qualidade. Não respondem perguntas que exigem cálculo novo sobre as linhas, como "qual o total de vendas por estado?". Para isso, o caminho é um agente conectado ao servidor MCP ([020](020-mcp-server.md)) ou uma ferramenta de consulta.

## Interface proposta
```bash
datatool ask vendas.csv "quais problemas existem nesse dataset?"
datatool ask vendas.csv "a coluna cpf pode ser usada como chave?" --format json
```

Aceita as mesmas opções do `explain` (`--sep`, `--encoding`, `--columns`, `--max-columns`, `--include-values`).

## Comportamento
- **Entrada, privacidade, provedor, configuração, erros e log:** iguais aos do [014](014-ai-explain.md). A pergunta também não vai para o log.
- **Instruções ao modelo:** responder só com base nos documentos. Quando a pergunta exige algo que eles não têm, dizer isso, explicar por quê e, quando fizer sentido, sugerir o comando do `datatool` que ajuda (ex.: `profile --key` para testar uma chave).
- **Uma pergunta por execução:** sem histórico entre chamadas.
- **Saída:** texto no stdout. `--format json` imprime o envelope de 019 com `question`, `answer` e `model`.

## Critérios de aceite
- [ ] Aceita a pergunta como argumento de texto livre
- [ ] O conteúdo enviado ao modelo são os mesmos documentos do `explain`, com as mesmas regras de privacidade, mais a pergunta
- [ ] A IA não executa código nem lê o arquivo: não há ferramenta nem acesso aos dados além dos documentos
- [ ] Mesmo tratamento de erro de configuração e de provedor que o [014](014-ai-explain.md) (exit codes 2 e 1)
- [ ] `--format json` segue o envelope de 019
- [ ] A pergunta e a resposta não aparecem no log
- [ ] Os testes usam um provedor falso (sem rede)
- [ ] Na avaliação manual do 014, entram perguntas fora do alcance dos documentos, e a resposta esperada é dizer que não dá para responder, sem inventar números

## Fora de escopo
- Perguntas que exigem cálculo novo sobre as linhas, ou joins com outro arquivo
- Conversa com histórico
- Ferramenta MCP `datatool_ask`: um agente conectado já faz isso, com mais recursos

## Questões em aberto
1. **Vale a pena como comando separado?** O `ask` responde bem só o que os documentos cobrem, e um agente com o servidor MCP faz o mesmo e mais. Uma alternativa é implementar só o `explain` e reavaliar o `ask` com base no uso.

## Revisão (2026-09-30)
Revisada contra o código da v0.1.0. O que mudou em relação à versão original:
- **Entrada e regras** herdadas do 014 revisado: documentos de 019, redigidos por padrão.
- **O limite ficou explícito:** perguntas que exigem cálculo novo sobre as linhas. A resposta esperada nesses casos é dizer que não dá, sem inventar.
- **Relação com o servidor MCP**, e a questão sobre manter o comando.
- **Saída JSON, log sem conteúdo e testes com provedor falso** definidos.

## Dependências
[014-ai-explain](014-ai-explain.md) (entrada, provedor e configuração), [019-saida-json](019-saida-json.md), [016-licenciamento-pro](016-licenciamento-pro.md) (bloqueio Pro)
