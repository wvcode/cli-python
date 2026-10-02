# US-014: Explicação em linguagem natural dos problemas do dataset

## User story
Como analista de dados, eu quero um resumo em linguagem natural dos problemas de qualidade do meu dataset, para entender rapidamente o que precisa de atenção sem interpretar tabelas de estatísticas.

## Contexto
Camada de IA opcional da ideia: "A IA interpreta o profiling produzido pela ferramenta". Não é um chatbot livre sobre o arquivo; é uma narrativa sobre dados já calculados de forma determinística. Feature **Pro** (ver [016-licenciamento-pro](016-licenciamento-pro.md)).

Os dados calculados já existem em formato próprio para máquina: os documentos JSON de [019](019-saida-json.md), gerados por `info.to_document`, `clean.diagnosis_document` e `profiler.to_document`. O `explain` monta esses três documentos para o arquivo, entrega ao modelo e imprime o texto que ele devolve. A IA recebe contagens e estatísticas, nunca as linhas do arquivo.

**Relação com o servidor MCP ([020](020-mcp-server.md)).** Quem usa um agente (Claude Code, Claude Desktop, Cursor) já consegue esse resultado: o agente chama `datatool_info` e `datatool_profile` e explica com as próprias palavras. O `explain` é para quem está no terminal sem agente, ou num script que precisa do resumo em texto.

## Interface proposta
```bash
datatool explain vendas.csv
datatool explain vendas.csv --format json
datatool explain vendas.csv --include-values     # envia também os valores de exemplo
```

Aceita `--sep`, `--encoding`, `--columns` e `--max-columns`, como o `profile`.

## Comportamento
- **Entrada do modelo:** os documentos do `info`, do diagnóstico do `clean` e do `profile`, **redigidos por padrão** (`redact_values=True`). O provedor de IA recebe contagens e estatísticas, mas nenhum valor de célula: nem valores mais frequentes, nem exemplos de datas ou documentos não reconhecidos. `--include-values` envia a versão completa, para quem aceita mandar esses valores ao provedor.
- **Tamanho:** a entrada cresce com o número de colunas, não com o de linhas. `--max-columns`, com padrão 50 como no servidor MCP, limita o custo em arquivos largos.
- **Instruções ao modelo:**
  - responder em português;
  - citar os números dos documentos (ex.: "3,2% de linhas duplicadas por `customer_id`");
  - não inventar métricas que não estejam neles;
  - terminar com os comandos `clean` que o `info` já sugere.
- **Provedor:** API da Anthropic, pelo SDK oficial (`anthropic`), num extra opcional `[ai]`, para quem não usa IA não instalar nada a mais.
  - O modelo padrão é o Claude Sonnet 5 (`claude-sonnet-5`), configurável por `DATATOOL_AI_MODEL`.
  - A chave vem de `ANTHROPIC_API_KEY`.
- **Sem configuração:** sem o extra instalado ou sem a chave, erro claro dizendo o que falta (`pip install "datatool-cli[ai]"` ou `export ANTHROPIC_API_KEY=...`), exit code 2, sem tentar a chamada. Falha do provedor (rede, limite de uso, chave inválida) sai com exit code 1 e a mensagem do provedor.
- **Saída:** texto no stdout. `--format json` imprime `{"schema_version": 1, "command": "explain", "status": "ok", "file": {...}, "model": "...", "explanation": "..."}`, com os erros no formato de 019.
- **Log:** registra modelo, tokens de entrada e saída e duração, **nunca** o conteúdo enviado ou recebido. O texto gerado pode citar valores quando `--include-values` está ligado.

## Critérios de aceite
- [ ] O conteúdo enviado ao modelo são só os documentos de `info`, diagnóstico do `clean` e `profile`, redigidos por padrão; um teste confere que nenhum valor de célula do arquivo aparece na requisição sem `--include-values`
- [ ] Com `--include-values`, os documentos vão completos
- [ ] Sem o extra `[ai]` ou sem `ANTHROPIC_API_KEY`, o comando sai com exit code 2 e uma mensagem que diz como configurar, sem fazer requisição
- [ ] Erro do provedor sai com exit code 1, em texto e em JSON
- [ ] `--format json` segue o envelope de 019
- [ ] O log não contém o prompt nem a resposta
- [ ] Os testes usam um provedor falso (sem rede) e verificam o que é enviado e como a resposta é impressa
- [ ] A qualidade da explicação (citar números reais, não inventar métricas) é avaliada à parte, com um conjunto pequeno de arquivos de exemplo e uma revisão manual antes de cada release que mude o prompt. Isso não é verificável por teste unitário.

## Fora de escopo
- Outros provedores de IA (OpenAI, modelos locais), ver questão 1
- Conversa com várias perguntas ([015](015-ai-ask.md) cobre uma pergunta por vez)
- Ferramenta MCP `datatool_explain`: um agente conectado ao servidor MCP já faz esse papel

## Questões em aberto
1. **Só Anthropic ou vários provedores?** A proposta começa com um provedor, atrás de uma interface pequena (enviar os documentos e receber o texto) que permita acrescentar outros. Suportar vários desde o início multiplica configuração e testes.
2. **Ainda vale como Pro?** Com o servidor MCP gratuito, quem já tem um agente consegue o mesmo resultado. O `explain` continua útil no terminal sem agente, mas o argumento de venda enfraqueceu desde que a ideia foi escrita.

## Revisão (2026-09-30)
Revisada contra o código da v0.1.0. O que mudou em relação à versão original:
- **Entrada do modelo definida:** os documentos JSON de 019 (`info`, diagnóstico do `clean`, `profile`), que não existiam quando a spec foi escrita. A versão original falava em "saída estruturada" de forma genérica.
- **Privacidade:** documentos redigidos por padrão, com `--include-values` opcional, na mesma linha do `redact_values` ligado por padrão no servidor MCP.
- **Relação com o servidor MCP** explicada, com a questão sobre o plano Pro.
- **Provedor, extra `[ai]`, configuração e códigos de saída definidos.** Também foram definidos o log sem conteúdo e os testes com provedor falso.
- **Critério reescrito:** "o texto cita números reais" deixou de ser teste unitário e virou avaliação manual, porque depende do modelo.

## Dependências
[003-profile-estatistico](003-profile-estatistico.md), [005-clean-detectar-problemas](005-clean-detectar-problemas.md), [019-saida-json](019-saida-json.md) (documentos enviados ao modelo), [016-licenciamento-pro](016-licenciamento-pro.md) (bloqueio Pro)
