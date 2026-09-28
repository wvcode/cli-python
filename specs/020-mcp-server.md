# US-020: Servidor MCP sobre o CLI

## User story
Como pessoa que usa um agente de IA (Claude Code, Claude Desktop, Cursor, ...) para trabalhar com dados, eu quero que o agente chame o datatool diretamente como ferramentas, para que ele diagnostique, faça profiling e limpe os meus arquivos com os mesmos cálculos determinísticos do CLI, em vez de escrever pandas/polars na hora e errar em `;`, `cp1252`, datas misturadas ou CPF.

## Contexto
Ideia originada nesta conversa (não vem de [ideia.md](ideia.md) nem do [backlog](backlog-novas-features.md) antes desta spec — ver [F16](backlog-novas-features.md#f16--servidor-mcp-sobre-o-cli), adicionada junto com esta spec).

Hoje, quando um agente de IA precisa entender ou limpar um dataset, ele só tem duas opções: chamar o `datatool` via shell (frágil — precisa parsear texto em pt-BR, ou já descobrir sozinho que existe `--format json`) ou escrever código de análise do zero a cada conversa, reintroduzindo exatamente os problemas que o datatool já resolve (delimitador/encoding do Excel BR, formatos de data misturados, `R$ 1.234,56`, CPF com zero à esquerda). Um servidor [MCP](https://modelcontextprotocol.io/) elimina as duas fricções: expõe os mesmos comandos como ferramentas tipadas, com o JSON de [019-saida-json](019-saida-json.md) como formato de retorno.

Isso só é possível com custo baixo **por causa da 019**: cada comando já produz um documento JSON versionado (`schema_version`), e a 017 já registra em log toda leitura/gravação/erro. O servidor é uma camada fina por cima do que já existe — não deveria durante o desenvolvimento haver lógica de negócio no [src/mcp_server.py](../src/mcp_server.py) (nome do módulo), só orquestração e validação de caminho de arquivo.

**Por que Community, não Pro.** O servidor roda localmente, com o próprio código do usuário; travar seu acesso atrás de licença (016) não é defensável tecnicamente (é hobby quebrar) nem estrategicamente (afasta exatamente o público técnico — devs usando Claude Code/Cursor — que mais rapidamente adotaria e recomendaria a ferramenta). O modelo de monetização não muda: o servidor expõe as ferramentas Community de graça, e cada ferramenta Pro (relatório HTML de [004](004-profile-relatorio-html.md), pipeline de [012](012-pipeline-automacao.md), etc.) verifica a licença de [016-licenciamento-pro](016-licenciamento-pro.md) exatamente como o comando de CLI equivalente, na medida em que essas specs forem implementadas. Nenhuma ferramenta Pro é definida nesta spec porque nenhuma das specs Pro (004, 012, 013, 014, 015) está implementada ainda — ver "Fora de escopo".

## Interface proposta
Um processo `datatool-mcp` (entry point do mesmo pacote Python), falado por stdio, registrado no agente como qualquer outro servidor MCP:

```json
{
  "mcpServers": {
    "datatool": {
      "command": "datatool-mcp",
      "args": ["--root", "/caminho/do/projeto"]
    }
  }
}
```

Ferramentas expostas (nomes com prefixo `datatool_`, conforme convenção de nomenclatura para evitar colisão com outros servidores MCP instalados junto):

| Ferramenta | Espelha | Anotações MCP |
|---|---|---|
| `datatool_info` | `info --format json` | readOnly, idempotent |
| `datatool_profile` | `profile --format json` | readOnly, idempotent |
| `datatool_clean_diagnose` | `clean --format json` (sem flags de operação) | readOnly, idempotent |
| `datatool_clean_apply` | `clean --format json` (com flags de operação) | destructive (grava arquivo) |
| `datatool_convert` | `convert` | destructive (grava arquivo) |

Cada ferramenta recebe como parâmetros os mesmos que a opção de linha de comando equivalente (`filename`, `key`, `columns`, `trim`, `fix_types`, `decimal_separator`, `output`, `sep`, `encoding`, ...), e devolve o mesmo documento JSON de [019](019-saida-json.md) — a ferramenta MCP não inventa um formato próprio.

## Comportamento — sandbox de arquivos
Todo caminho de arquivo (`filename`, `output`, `to_filename`) passado por uma ferramenta é resolvido contra um **diretório raiz** fixado na inicialização do servidor (`--root`, padrão: diretório de trabalho do processo):

1. **Sem fuga do diretório raiz.** O caminho resolvido (absoluto, com `..` expandido) precisa continuar dentro da raiz; caso contrário, erro claro (`"Path escapes the server root"`), sem tocar em nada. Cobre tanto caminho absoluto fora da raiz quanto `../../etc/passwd`.
2. **Nunca sobrescreve a entrada.** Em `datatool_clean_apply`/`datatool_convert`, se `output`/`to_filename` resolver para o mesmo arquivo que `filename`, erro claro, nada é gravado. O CLI continua permitindo isso (é uma restrição só do servidor MCP — ver "Por que não retroalimentar isso na 001/011" abaixo).
3. **Não sobrescreve um arquivo de saída existente por padrão.** Se o caminho de `output`/`to_filename` já existir, erro claro pedindo `overwrite: true`; com `overwrite: true`, grava normalmente. Motivo: um agente autônomo, ao contrário de uma pessoa no terminal, não tem o momento de "vou apertar enter mesmo sabendo que isso substitui o arquivo" — o parâmetro explícito é esse momento.
4. Essas três checagens rodam **antes** de qualquer leitura/gravação, e reaproveitam a mesma validação de extensão (`infer_file_type`) que o CLI já faz.

**Por que isso não é uma mudança nas specs 001/006-011 (convert/clean com `--output`).** O CLI existente é invocado por uma pessoa que digitou o comando deliberadamente; `--output arquivo.csv` sobrescrevendo o próprio arquivo de entrada é raro, mas quando acontece foi uma decisão explícita de quem rodou o comando. Um agente de IA opera sem essa fricção — decide e executa no mesmo passo, possivelmente a partir de uma instrução ambígua ou de uma etapa errada de raciocínio — então o custo de um guardrail a mais compensa. Adicionar essas três checagens ao CLI mudaria um comportamento hoje testado e documentado (specs 001, 006-011) sem um problema real relatado por uso direto do CLI; por isso ficam só na camada MCP.

## Comportamento — privacidade (redação de valores)
Todas as ferramentas chamam os comandos internamente com `redact_values=True` por padrão (a extensão de [019](019-saida-json.md#extensão--ocultar-valores-de-células---redact-values), ver abaixo), diferente do padrão do CLI (`False`). Motivo: o texto que volta para `datatool_profile`/`datatool_info`/`datatool_clean_diagnose` entra no contexto do modelo de IA do agente, que pode ser um provedor de terceiros, ficar em log da conversa, ou ser compartilhado — e diferente de uma pessoa lendo o próprio terminal, isso é uma segunda parte vendo o dado. Cada ferramenta aceita um parâmetro `redact_values` para a pessoa que configurou o agente desligar isso deliberadamente (ex.: sabe que só usa modelos locais).

`redact_values=True` nunca afasta um valor de célula do arquivo em si — `datatool_clean_apply`/`datatool_convert` sempre gravam os dados reais; a redação é só do relatório que volta ao agente.

## Comportamento — tamanho da resposta
`datatool_profile` recebe os parâmetros `columns` e `max_columns` (extensão de [003](003-profile-estatistico.md#extensão--seleção-e-limite-de-colunas---columns---max-columns), ver abaixo), com `max_columns` por padrão **50** nesta ferramenta (diferente do CLI, que não corta por padrão). Um dataset com mais colunas que isso sem `columns` explícito volta com `columns_returned`/`columns_total`/`truncated_columns` no envelope, e a mensagem de erro nenhuma — a ferramenta responde parcialmente e diz o que falta, para o agente pedir o resto com `columns=[...]` em vez de travar.

`datatool_info`/`datatool_clean_diagnose` não recebem `columns`/`max_columns` (a extensão do ponto acima é só de [003](003-profile-estatistico.md), específica do `profile`): a lista de `problems` já é limitada, no pior caso, a uma constante pequena de categorias por coluna, então uma resposta de `info` num dataset de 300 colunas fica na casa de dezenas de KB, não MB — abaixo do que justificaria paginação nesta primeira versão.

## Critérios de aceite
- [ ] `datatool-mcp` inicia um servidor MCP por stdio, instalável a partir do mesmo pacote (`pip install datatool[mcp]` ou equivalente — ver "Nota de implementação" sobre dependência opcional)
- [ ] As cinco ferramentas da tabela acima existem, com nome, descrição, schema de entrada e anotações (`readOnlyHint`/`destructiveHint`/`idempotentHint`) corretos
- [ ] Cada ferramenta devolve exatamente o documento JSON do comando de CLI equivalente (mesmo `schema_version`), como conteúdo estruturado da resposta MCP — não como texto para parsear
- [ ] Um caminho fora do diretório raiz (`--root`), absoluto ou via `..`, é rejeitado em `filename`, `output` e `to_filename`, sem tocar no sistema de arquivos
- [ ] `output`/`to_filename` igual a `filename` (mesmo arquivo resolvido) é rejeitado em `datatool_clean_apply`/`datatool_convert`
- [ ] `output`/`to_filename` apontando para um arquivo já existente é rejeitado sem `overwrite: true`; com `overwrite: true`, grava normalmente
- [ ] Erros (validação de caminho, arquivo inexistente, coluna desconhecida, etc.) voltam como resultado de ferramenta com `isError: true` e o mesmo texto de mensagem do CLI — nunca como exceção de protocolo MCP nem como processo que encerra
- [ ] `redact_values` é `True` por padrão em todas as ferramentas de leitura e no relatório de `datatool_clean_apply`; passar `redact_values: false` explicitamente devolve os valores reais, iguais ao CLI
- [ ] `datatool_profile` aceita `columns`/`max_columns`; sem `columns` e com mais colunas que `max_columns` (padrão 50), a resposta vem truncada com `columns_returned`/`columns_total`/`truncated_columns`
- [ ] Toda chamada de ferramenta é registrada no log de [017](017-csv-delimitador-encoding.md) (arquivo `logs/datatool.log` relativo ao `--root`), com o mesmo formato e as mesmas garantias de privacidade (nenhum valor de célula no log) — o nome do comando no log é prefixado com `mcp` (ex.: `mcp info`, `mcp clean`)
- [ ] Existe pelo menos um teste de integração por ferramenta usando um cliente MCP de teste (ex.: `mcp.client` in-process, sem subprocesso), cobrindo o caminho feliz, um erro de validação (arquivo inexistente) e um caso de sandbox violado

## Fora de escopo
- **Ferramentas Pro.** Nenhuma ferramenta para 004/012/013/014/015 é definida aqui, porque nenhuma dessas specs está implementada. Quando a primeira delas for implementada, uma spec própria (ou uma extensão desta) adiciona a ferramenta MCP correspondente, gated por [016](016-licenciamento-pro.md) do mesmo jeito que o comando de CLI — reaproveitando a checagem de licença, sem reimplementá-la.
- **Transporte remoto (Streamable HTTP), autenticação OAuth, multiusuário.** V1 é só stdio, processo local de um único usuário — o mesmo modelo de uso do CLI hoje. Ver "Sugestão de sequência" do backlog: se houver demanda por uso remoto/compartilhado, isso é uma spec própria, com o modelo de ameaça de autenticação/autorização que stdio local não precisa.
- **Ferramenta de sistema de arquivos genérica.** O servidor não expõe `read_file`/`write_file`/`list_dir` arbitrários — só as operações do datatool. Um agente que precisa navegar o sistema de arquivos usa a ferramenta de arquivo que o próprio host/agente já oferece.
- **Streaming/paginação de linhas de dados.** As ferramentas continuam dentro do envelope de desempenho já validado (~200 mil linhas, specs [002](002-info-diagnostico.md)/[003](003-profile-estatistico.md)); nenhum dado bruto linha a linha volta pela ferramenta (isso já era verdade no CLI — `--output` grava em arquivo, não imprime o dataset inteiro em JSON).
- **`datatool_normalize_documents`/outras ferramentas para specs ainda não implementadas** (018, por exemplo). Aparecem quando as specs correspondentes existirem; o desenho de ferramentas aqui já previu isso (uma ferramenta por comando/modo, não por spec), mas não há trabalho a fazer agora.
- **Publicar em um registro de servidores MCP** (ex.: um marketplace) ou empacotar como imagem Docker — instalação via `pip`/`pipx` do próprio pacote já resolve o uso local, que é o cenário desta spec.
- **Mascaramento permanente de dados (LGPD).** `redact_values` esconde valores só no relatório que volta ao agente; não é o mesmo que [F06](backlog-novas-features.md#f06--mascaramento-de-dados-pessoais-lgpd) (que gera um arquivo de saída com os dados de fato mascarados/hash). São complementares: um projeto que usa o servidor MCP para diagnosticar ainda precisa do F06/`--mask-pii` para efetivamente compartilhar um arquivo anonimizado.

## Nota de implementação
- **SDK e nome do servidor.** SDK oficial Python (`mcp`, `FastMCP`), seguindo a convenção `{serviço}_mcp` → nome interno `datatool_mcp`; módulo novo [src/mcp_server.py](../src/mcp_server.py); entry point de console `datatool-mcp` em `pyproject.toml`/`setup.py`, análogo ao `datatool` do CLI. Dependência do SDK MCP como extra opcional (`datatool[mcp]`), para quem só usa o CLI não precisar instalá-la.
- **Refactor pré-requisito (o "ponto 4" desta discussão): separar montar do imprimir.** Hoje `print_json(command, **fields)` em [src/reporting.py](../src/reporting.py) monta o envelope e já imprime; `fail(...)` idem. Viram:
  - `build_document(command, **fields) -> dict` — monta e sanitiza (`_sanitize`, `NaN`/`inf`/datas), sem imprimir;
  - `print_json(command, **fields)` — vira `print(json.dumps(build_document(...), ...))`, mesmo comportamento de hoje, testes existentes intactos;
  - `build_error(command, message, exit_code) -> dict` / `fail(...)` na mesma relação; `fail` continua chamando `log.error` e decidindo texto vs. JSON no CLI.
  - `info()`, `profile()`, `clean()` (e, para uniformidade, `convert()`, que não tem `--format json` mas ganha o mesmo formato de retorno para uso interno) passam a devolver **`(exit_code, document)`** em vez de só `exit_code`; `document` é o dict (mesmo shape do JSON) quando aplicável, `None` quando o modo é texto sem `--format json` ou quando não há documento a montar (ex.: `clean` imprimindo o DataFrame direto no stdout sem `--output`). [src/main.py](../src/main.py) ignora o segundo valor (`exit_code, _ = file_info(...)`) — nenhuma mudança de comportamento do CLI.
  - Este refactor é **interno**: não muda nenhuma saída do CLI (texto ou JSON) nem os critérios já marcados em [019](019-saida-json.md); por isso não altera os critérios de aceite daquela spec, só é descrito aqui, onde passa a ser necessário.
- **Onde a ferramenta MCP chama o quê.** Cada função `datatool_*` do servidor chama a função Python do comando (`info()`, `profile()`, `clean()`, `convert()`) diretamente — no mesmo processo, sem `subprocess`/shell — com `output_format=OutputFormat.JSON`, aplica as checagens de sandbox antes de chamar, e devolve `document` como `structuredContent` da resposta MCP (mais um resumo curto em texto simples em `content`, para clientes que não renderizam `structuredContent`). Em erro (`document["status"] == "error"`), a resposta vem com `isError: true`.
- **Log via decorator existente.** `@logged(f"mcp {comando}")` de [src/execution_log.py](../src/execution_log.py) envolve cada função de ferramenta, igual a como envolve cada comando Typer em `main.py` — nenhuma mudança no módulo de log.
- **`--root`.** Argumento de linha de comando do processo `datatool-mcp` (não uma ferramenta/parâmetro visível ao agente); resolvido uma vez na inicialização com `Path(root).resolve()`. A checagem de sandbox é `Path(candidato).resolve().is_relative_to(root)` (Python 3.10 já tem `is_relative_to`; ver `pyproject.toml` para o mínimo de versão do projeto).
- **Testes.** O SDK MCP oferece um cliente in-process (sem subir subprocesso/stdio de verdade) para testes; usar isso em vez de `CliRunner` (que é específico do Typer/Click). Arquivo novo `src/test_mcp_server.py`, seguindo o padrão de nomes de `src/test_cli.py`.

## Dependências
[017-csv-delimitador-encoding](017-csv-delimitador-encoding.md) (log), [019-saida-json](019-saida-json.md) (formato de retorno e sua extensão de redação), extensão de [003-profile-estatistico](003-profile-estatistico.md) (`--columns`/`--max-columns`). Indiretamente, todas as specs cujos comandos ganham uma ferramenta (001, 002, 003, 005-011).
