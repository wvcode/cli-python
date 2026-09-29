# US-020: Servidor MCP sobre o CLI

## User story
Como pessoa que usa um agente de IA (Claude Code, Claude Desktop, Cursor, ...) para trabalhar com dados, eu quero que o agente chame o datatool diretamente como ferramentas, para que ele diagnostique, faça profiling e limpe os meus arquivos com os mesmos cálculos determinísticos do CLI, em vez de escrever pandas/polars na hora e errar em `;`, `cp1252`, datas misturadas ou CPF.

## Contexto
Ideia originada nesta conversa (não vem de [ideia.md](ideia.md) nem do [backlog](backlog-novas-features.md) antes desta spec — ver [F16](backlog-novas-features.md#f16--servidor-mcp-sobre-o-cli), adicionada junto com esta spec).

Hoje, quando um agente de IA precisa entender ou limpar um dataset, ele só tem duas opções: chamar o `datatool` via shell (frágil — precisa parsear texto em pt-BR, ou já descobrir sozinho que existe `--format json`) ou escrever código de análise do zero a cada conversa, reintroduzindo exatamente os problemas que o datatool já resolve (delimitador/encoding do Excel BR, formatos de data misturados, `R$ 1.234,56`, CPF com zero à esquerda). Um servidor [MCP](https://modelcontextprotocol.io/) elimina as duas fricções: expõe os mesmos comandos como ferramentas tipadas, com o JSON de [019-saida-json](019-saida-json.md) como formato de retorno.

Isso só é possível com custo baixo **por causa da 019**: cada comando já produz um documento JSON versionado (`schema_version`), e a 017 já registra em log toda leitura/gravação/erro. O servidor é uma camada fina por cima do que já existe — não deveria durante o desenvolvimento haver lógica de negócio no [src/datatool/mcp_server.py](../src/datatool/mcp_server.py) (nome do módulo), só orquestração e validação de caminho de arquivo.

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
- [x] `datatool-mcp` inicia um servidor MCP por stdio, instalável a partir do mesmo pacote (`pip install datatool[mcp]` ou equivalente — ver "Nota de implementação" sobre dependência opcional)
- [x] As cinco ferramentas da tabela acima existem, com nome, descrição, schema de entrada e anotações (`readOnlyHint`/`destructiveHint`/`idempotentHint`) corretos
- [x] Cada ferramenta devolve exatamente o documento JSON do comando de CLI equivalente (mesmo `schema_version`), como conteúdo estruturado da resposta MCP — não como texto para parsear
- [x] Um caminho fora do diretório raiz (`--root`), absoluto ou via `..`, é rejeitado em `filename`, `output` e `to_filename`, sem tocar no sistema de arquivos
- [x] `output`/`to_filename` igual a `filename` (mesmo arquivo resolvido) é rejeitado em `datatool_clean_apply`/`datatool_convert`
- [x] `output`/`to_filename` apontando para um arquivo já existente é rejeitado sem `overwrite: true`; com `overwrite: true`, grava normalmente
- [x] Erros (validação de caminho, arquivo inexistente, coluna desconhecida, etc.) voltam como resultado de ferramenta com `isError: true` e o mesmo texto de mensagem do CLI — nunca como exceção de protocolo MCP nem como processo que encerra
- [x] `redact_values` é `True` por padrão em todas as ferramentas de leitura e no relatório de `datatool_clean_apply`; passar `redact_values: false` explicitamente devolve os valores reais, iguais ao CLI
- [x] `datatool_profile` aceita `columns`/`max_columns`; sem `columns` e com mais colunas que `max_columns` (padrão 50), a resposta vem truncada com `columns_returned`/`columns_total`/`truncated_columns`
- [x] Toda chamada de ferramenta é registrada no log de [017](017-csv-delimitador-encoding.md) (arquivo `logs/datatool.log` relativo ao `--root`), com o mesmo formato e as mesmas garantias de privacidade (nenhum valor de célula no log) — o nome do comando no log é prefixado com `mcp` (ex.: `mcp info`, `mcp clean`)
- [x] Existe pelo menos um teste de integração por ferramenta usando um cliente MCP de teste (ex.: `mcp.client` in-process, sem subprocesso), cobrindo o caminho feliz, um erro de validação (arquivo inexistente) e um caso de sandbox violado

Coberto por testes em [tests/test_mcp_server.py](../tests/test_mcp_server.py) (26 testes, in-process via `server.call_tool(...)`, sem subir stdio de verdade): as cinco ferramentas, cada uma com caminho feliz, arquivo inexistente e violação de sandbox, mais os guardrails específicos de `datatool_clean_apply`/`datatool_convert` (mesmo arquivo, saída existente, `overwrite`, zero operações), o padrão `redact_values=True`, o padrão `max_columns=50`, as anotações das cinco ferramentas, e o log sem valores de célula. A saída de texto/JSON do CLI (`info`/`profile`/`clean`/`convert`) foi comparada com a versão anterior a esta spec, em 12 cenários — idêntica; o refactor de retorno é só interno.

## Fora de escopo
- **Ferramentas Pro.** Nenhuma ferramenta para 004/012/013/014/015 é definida aqui, porque nenhuma dessas specs está implementada. Quando a primeira delas for implementada, uma spec própria (ou uma extensão desta) adiciona a ferramenta MCP correspondente, gated por [016](016-licenciamento-pro.md) do mesmo jeito que o comando de CLI — reaproveitando a checagem de licença, sem reimplementá-la.
- **Transporte remoto (Streamable HTTP), autenticação OAuth, multiusuário.** V1 é só stdio, processo local de um único usuário — o mesmo modelo de uso do CLI hoje. Ver "Sugestão de sequência" do backlog: se houver demanda por uso remoto/compartilhado, isso é uma spec própria, com o modelo de ameaça de autenticação/autorização que stdio local não precisa.
- **Ferramenta de sistema de arquivos genérica.** O servidor não expõe `read_file`/`write_file`/`list_dir` arbitrários — só as operações do datatool. Um agente que precisa navegar o sistema de arquivos usa a ferramenta de arquivo que o próprio host/agente já oferece.
- **Streaming/paginação de linhas de dados.** As ferramentas continuam dentro do envelope de desempenho já validado (~200 mil linhas, specs [002](002-info-diagnostico.md)/[003](003-profile-estatistico.md)); nenhum dado bruto linha a linha volta pela ferramenta (isso já era verdade no CLI — `--output` grava em arquivo, não imprime o dataset inteiro em JSON).
- **`datatool_normalize_documents`/outras ferramentas para specs ainda não implementadas** (018, por exemplo). Aparecem quando as specs correspondentes existirem; o desenho de ferramentas aqui já previu isso (uma ferramenta por comando/modo, não por spec), mas não há trabalho a fazer agora.
- **Publicar em um registro de servidores MCP** (ex.: um marketplace) ou empacotar como imagem Docker — instalação via `pip`/`pipx` do próprio pacote já resolve o uso local, que é o cenário desta spec.
- **Mascaramento permanente de dados (LGPD).** `redact_values` esconde valores só no relatório que volta ao agente; não é o mesmo que [F06](backlog-novas-features.md#f06--mascaramento-de-dados-pessoais-lgpd) (que gera um arquivo de saída com os dados de fato mascarados/hash). São complementares: um projeto que usa o servidor MCP para diagnosticar ainda precisa do F06/`--mask-pii` para efetivamente compartilhar um arquivo anonimizado.

## Nota de implementação
- **SDK: `MCPServer`, não `FastMCP`.** O pacote `mcp` disponível no momento da implementação já está na major 2 (`mcp==2.2.0`), onde o SDK renomeou `FastMCP` (v1) para `MCPServer` (`from mcp.server.mcpserver import MCPServer`) — a classe usada nesta spec quando foi escrita não existe mais nessa versão. A API de tool (`@server.tool(name=..., annotations=..., description=...)`) e `ToolAnnotations` (`readOnlyHint`/`destructiveHint`/`idempotentHint`/`openWorldHint` na serialização; os atributos Python são snake_case: `read_only_hint` etc.) se mantiveram equivalentes ao desenho original. Nome do servidor: `datatool_mcp`.
- **`CallToolResult` construído à mão, não `ToolError`.** A forma idiomática de sinalizar erro no SDK (`raise ToolError(mensagem)`) prefixa a mensagem com `"Error executing tool <nome>: "`, o que quebraria o critério "o mesmo texto de mensagem do CLI". Em vez disso, cada ferramenta é anotada `-> CallToolResult` e monta o resultado diretamente: `CallToolResult(content=[TextContent(text=mensagem)], structured_content=document, is_error=...)`. Anotar o retorno como `CallToolResult` faz o SDK pular a inferência de schema de saída (`output_schema`), então o dict é devolvido tal como está, sem tentativa de validação — verificado lendo `tools/base.py`/`utilities/func_metadata.py` do SDK instalado.
- **Refactor pré-requisito (separar montar do imprimir) em [src/datatool/reporting.py](../src/datatool/reporting.py):**
  - `build_document(command, **fields) -> dict` — monta e sanitiza (`_sanitize`, `NaN`/`inf`/datas), sem imprimir;
  - `print_document(document)` — imprime um dict já montado (evita sanitizar duas vezes quem já tem o documento, como o servidor MCP);
  - `print_json(command, **fields)` — vira `print_document(build_document(command, **fields))`, mesmo comportamento de hoje;
  - `build_error(command, message, exit_code) -> dict` / `fail(...)` na mesma relação; `fail` devolve `(exit_code, document)` (`document=None` em modo texto), então toda chamada `return fail(...)` já passou a devolver a tupla automaticamente.
  - `info()`, `profile()`, `clean()`, `convert()` passam a devolver **`(exit_code, document)`**; `document` é `None` em modo texto (ou quando `clean` imprime o DataFrame direto sem `--output`). [src/datatool/main.py](../src/datatool/main.py) desempacota (`result, _document = file_info(...)`). `convert()` não tem `--format json` (fora do escopo de [019](019-saida-json.md)) mas ganha um documento próprio (`source`/`target`, via `file_summary`) só para uso interno do servidor MCP — nunca impresso pelo CLI.
  - Interno: a saída do CLI (texto e JSON) foi comparada com a versão anterior a esta spec em 12 cenários e é idêntica; os critérios de [019](019-saida-json.md) não mudam.
- **Onde a ferramenta MCP chama o quê.** Cada função `datatool_*` valida o sandbox, chama a função do comando com `output_format=OutputFormat.JSON` sob `contextlib.redirect_stdout(io.StringIO())` — essencial: `info()`/`profile()`/`clean()`/`convert()` continuam imprimindo no stdout (é o que o CLI usa), e isso corromperia o protocolo MCP por stdio se não fosse abafado — e usa o `document` retornado, nunca o texto impresso.
- **Log via decorator existente.** `@logged(f"mcp {comando}")` de [src/datatool/execution_log.py](../src/datatool/execution_log.py) envolve cada função de ferramenta, sem nenhuma mudança no módulo de log. Limitação aceita: como as ferramentas devolvem erro via `CallToolResult(is_error=True)` em vez de levantar exceção, a linha final do log (`fim — exit code N`) sempre mostra `0` mesmo quando a ferramenta falhou — a falha em si ainda aparece, em nível `ERROR`, na linha que `fail()` já loga via `log.error(message)`. Corrigir isso exigiria mudar `execution_log.py` para entender `CallToolResult`, o que o desenho original desta spec pediu para não fazer.
- **`--root` e o log.** Resolvido uma vez em `main()` com `Path(root).resolve()`; a checagem de sandbox é `resolved == root or root in resolved.parents` (equivalente a `is_relative_to`, disponível a partir do Python 3.10). `main()` também faz `os.chdir(root)` antes de `server.run(...)`: o log de [017](017-csv-delimitador-encoding.md) é relativo ao diretório de trabalho do processo, então sem isso o log cairia em onde o host do agente iniciou o processo, não em `<root>/logs/` como este critério pede. `build_server(root)` em si **não** faz `chdir` — só monta o servidor —, para os testes poderem chamá-la repetidamente sem side effect global entre eles (cada teste usa seu próprio diretório temporário, no mesmo padrão de `isolated_filesystem()` de [tests/test_cli.py](../tests/test_cli.py)).
- **Guardrail extra em `datatool_clean_apply`, além do que a spec pedia.** Chamar a ferramenta sem nenhuma flag de operação (`trim`, `fix_types`, etc.) cairia no modo diagnóstico de `clean()` e **não gravaria nada em `output`**, silenciosamente — mesmo comportamento do CLI (`datatool clean arquivo.csv --output x.csv` sem operação também só imprime o diagnóstico). Para não confundir o agente, a ferramenta rejeita explicitamente uma chamada sem nenhuma operação, apontando para `datatool_clean_diagnose`.
- **Testes.** In-process via `server.call_tool(nome, argumentos)` (não sobe stdio nem subprocesso), em `tests/test_mcp_server.py`, com o mesmo padrão de diretório temporário isolado usado em `tests/test_cli.py`.
- **Empacotamento.** `mcp` como extra opcional (`extras_require={"mcp": ["mcp"]}` em `setup.py`), para quem só usa o CLI não precisar da dependência (pesada: puxa `uvicorn`, `pydantic`, `cryptography`, `starlette`, entre outras). Entry point `datatool-mcp = src.mcp_server:main`, ao lado do `datatool` existente. `mcp` também foi adicionado a `requirements-dev.txt`, necessário para rodar a suíte de testes completa.

## Dependências
[017-csv-delimitador-encoding](017-csv-delimitador-encoding.md) (log), [019-saida-json](019-saida-json.md) (formato de retorno e sua extensão de redação), extensão de [003-profile-estatistico](003-profile-estatistico.md) (`--columns`/`--max-columns`). Indiretamente, todas as specs cujos comandos ganham uma ferramenta (001, 002, 003, 005-011).
