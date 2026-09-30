# Débito técnico — datatool

Revisão do código em `src/datatool/` (commit `cbc1be8`, 2026-09-29). Estado de partida: 202 testes passando, `ruff check` limpo, `ruff format --check` falhando.

Itens marcados com **(reproduzido)** foram confirmados executando o CLI. Features ainda não implementadas (aba de Excel F04, modo lazy F12 etc.) estão em [backlog-novas-features.md](backlog-novas-features.md) e não se repetem aqui.

Esforço: **P** = horas · **M** = 1–2 dias · **G** = vários dias. ✅ = resolvido · ◐ = resolvido em parte (ver a nota "Resolução" no item).

Os itens DT01–DT27 vêm da primeira revisão e estão todos resolvidos. Os itens DT28–DT36 vêm da [segunda revisão](#segunda-revisão-2026-09-30), feita depois deles.

## Resumo

| ID | Item | Área | Severidade | Esforço |
|----|------|------|------------|---------|
| DT01 ✅ | `--fill-null col:valor` troca o tipo da coluna sem avisar | clean | Alta | P |
| DT02 ✅ | Job de lint do CI quebrado (`ruff format`) | CI | Alta | P |
| DT03 ✅ | Licença contraditória: MIT no `setup.py`, GPLv3 no `LICENSE` | Packaging | Alta | P |
| DT04 ✅ | Servidor MCP não é thread-safe (stdout e log globais) | MCP | Alta | M |
| DT05 ✅ | SQLite: identificadores sem escape e `DROP TABLE` silencioso | IO | Alta | P |
| DT06 ✅ | Comandos-esqueleto publicados saem com sucesso sem fazer nada | CLI | Alta | P |
| DT07 ✅ | `info` e `clean` usam heurísticas divergentes (datas e números) | quality/clean | Média | M |
| DT08 ✅ | Lógica de negócio acoplada a `print` | Arquitetura | Média | G |
| DT09 ✅ | Imports duplos `try/except ImportError` em todo módulo | Arquitetura | Média | P |
| DT10 ✅ | Carga e validação de entrada duplicadas em 4 comandos | Arquitetura | Média | M |
| DT11 ✅ | Adicionar uma operação de `clean` exige editar 6 lugares | clean/MCP | Média | M |
| DT12 ✅ | `clean` depende de funções privadas de `quality` | Arquitetura | Média | P |
| DT13 ✅ | 23 argumentos posicionais de `main.clean` → `file_clean` | CLI | Média | P |
| DT14 ✅ | Mensagens de erro erradas ou inconsistentes | UX | Média | P |
| DT15 ✅ | Flags conflitantes aceitas sem erro | clean | Média | P |
| DT16 ✅ | Log gravado em `./logs` do diretório corrente | Log | Média | P |
| DT17 ✅ | `datatool-mcp` quebra com traceback sem o extra `[mcp]` | Packaging | Média | P |
| DT18 ✅ | Dependências sem versão mínima; metadados divididos | Packaging | Média | P |
| DT19 ✅ | `convert` fora do padrão dos demais comandos | convert | Baixa | M |
| DT20 ✅ | Contrato do `Finding` ambíguo | quality | Baixa | M |
| DT21 ✅ | Detecção de documentos recalculada várias vezes | Performance | Baixa | P |
| DT22 ✅ | `utils encode/decode`: ofuscação caseira sem propósito claro | CLI | Baixa | P |
| DT23 ✅ | Nomes confusos de módulos e funções | Legibilidade | Baixa | P |
| DT24 ✅ | Aviso do polars sobre a 2.0 na leitura de xlsx | IO | Baixa | P |
| DT25 ✅ | Testes: arquivo monolítico, sem cobertura e fixando stubs | Testes | Baixa | M |
| DT26 ✅ | Sem type hints/checker; ruff com poucas regras | Qualidade | Baixa | M |
| DT27 ✅ | Arquivo solto `src/file.txt` versionado | Repo | Baixa | P |

---

## Alta

### DT01 — `--fill-null col:valor` troca o tipo da coluna sem avisar **(reproduzido)**
[clean.py:397-423](../src/datatool/clean.py#L397-L423)

`_cast_fill_value` tenta `int(value)`/`float(value)` e, se falhar, devolve a string original. O polars então promove a coluna inteira para texto.

```
idade (i64): 30, null  →  datatool clean t.csv --fill-null idade:abc --output o.csv
o.csv: idade = "30", "abc"   exit 0, "1 células preenchidas"
```

**Resolução:** depois do `fill_null`, se o dtype da coluna mudou, o `clean` falha com `Invalid value in --fill-null coluna:valor` (exit 2) e não grava nada. Isso também cobre colunas date/bool, que o polars converteria para texto com qualquer valor string.

### DT02 — Job de lint do CI quebrado **(reproduzido)**
[ci.yml](../.github/workflows/ci.yml) roda `ruff format --check src/ tests/`, e 6 arquivos não estão formatados (ex.: [main.py:83-85](../src/datatool/main.py#L83-L85), [clean.py:417-419](../src/datatool/clean.py#L417-L419)). Todo push em `main` fica vermelho, o que acostuma o time a ignorar o CI.

**Resolução:** `ruff format` aplicado; `ruff format --check` e `ruff check` passam. O hook de pre-commit não foi adicionado.

### DT03 — Licença contraditória
[setup.py:21](../setup.py#L21) declara `License :: OSI Approved :: MIT License`, mas [LICENSE](../LICENSE) é GPLv3. O pacote vai para o PyPI com metadado legal errado.

**Resolução:** decidido GPLv3. O classifier do `setup.py` e o site (`website/index.html`, que também dizia MIT) foram alinhados.

### DT04 — Servidor MCP não é thread-safe
[mcp_server.py:89-94](../src/datatool/mcp_server.py#L89-L94), [execution_log.py:43-62](../src/datatool/execution_log.py#L43-L62)

O SDK `mcp` executa ferramentas síncronas em threads (`anyio.to_thread.run_sync`). Dois problemas:

1. `contextlib.redirect_stdout` troca o `sys.stdout` **do processo**. Com duas chamadas simultâneas, quando a primeira termina ela restaura o stdout real enquanto a segunda ainda imprime. Esses `print` vão para o canal JSON-RPC do stdio e corrompem o protocolo.
2. `logged` adiciona um handler ao logger global a cada chamada. Com chamadas simultâneas, cada registro é gravado uma vez por handler ativo, com o `run_id` errado.

**Correção:** resolver DT08 (as funções deixam de imprimir, e o redirect some). No log, usar `contextvars` para o `run_id`/comando e um único handler fixo.

**Resolução (parcial):** o problema 1 está resolvido. Com o DT08, nenhuma função de domínio imprime, e o `redirect_stdout` foi removido; o teste `TestNoStdoutWrites` garante que as ferramentas não escrevem no stdout. **Pendente:** o problema 2 (handler de log por chamada), que exige mexer em `execution_log.py`.

**Resolução do problema 2:** o `run_id` e o comando da execução corrente vêm de um `contextvars.ContextVar`. Há um único handler por arquivo de log, compartilhado pelas execuções simultâneas (contagem de referências com trava) e fechado quando a última termina, e ele só aceita registros de execuções que o abriram. Cada registro sai uma vez, com o `run_id` de quem o emitiu. Os testes `test_concurrent_runs_log_each_record_once_with_own_run_id` e `TestConcurrentCalls` (MCP, 4 chamadas em paralelo) falham na versão anterior e passam na nova.

### DT05 — SQLite: identificadores sem escape e `DROP TABLE` silencioso **(reproduzido)**
[structures/sqlite.py:33-51](../src/datatool/structures/sqlite.py#L33-L51)

- Nomes de tabela e coluna são interpolados como `"{nome}"` sem escapar `"`. Uma coluna chamada `a"b` gera `unrecognized token`. O nome da tabela vem do nome do arquivo, que no MCP é controlado pelo agente.
- `write_sqlite` faz `DROP TABLE IF EXISTS` num `.db` que pode já conter outras tabelas: sobrescreve dados sem avisar.
- `CREATE TABLE` não declara tipos, e `read_sqlite` carrega tudo via `fetchall()` em Python.

**Resolução:** identificadores escapados; tipos declarados (`INTEGER`/`REAL`/`BLOB`/`TEXT`); `DROP`+`CREATE`+`INSERT` numa única transação. A revisão achou algo pior que o listado: o sqlite3 commitava o `DROP` na hora, então uma gravação que falhava **apagava** a tabela existente (confirmado: 3 linhas → 0). Decidido **substituir** a tabela, como os outros formatos sobrescrevem o arquivo, em vez de recusar. A proteção contra sobrescrita no CLI fica no DT19, para todos os formatos.

### DT06 — Comandos-esqueleto publicados **(reproduzido)**
[main.py:262-356](../src/datatool/main.py#L262-L356)

`excel`, `dataset translate|explain|transform|decode` só imprimem os argumentos e saem com **exit 0**. Um script ou agente conclui que a operação funcionou. Os testes em [test_cli.py:2300+](../tests/test_cli.py#L2300) fixam esse comportamento. Os enums `EncodingType`, `Language` e `OnErrorType` só existem para eles.

A seção "Reconciliar comandos-esqueleto" do backlog trata do destino final. **Débito imediato:** esconder os comandos (`hidden=True`) ou fazê-los falhar com "não implementado" (exit ≠ 0).

**Resolução:** as duas coisas. Os comandos ficam ocultos no `--help` e saem com exit 1 e `Command '...' is not implemented yet.`. As assinaturas foram mantidas, e os testes agora verificam a falha.

---

## Média

### DT07 — `info` e `clean` usam heurísticas divergentes **(reproduzido)**
Datas: [quality.py:20-30](../src/datatool/quality.py#L20-L30) (regex) vs. [clean.py:56-64](../src/datatool/clean.py#L56-L64) (`strptime`). Números: [quality.py:32-35](../src/datatool/quality.py#L32-L35) vs. [clean.py:67-70](../src/datatool/clean.py#L67-L70).

Com `data = 20240115, 2024-01-16, ...` e `valor = "R$ 1.234,56", ...`:
- `info` acusa "2 formatos de data" e sugere `--normalize-dates`, mas o `clean --normalize-dates` responde "Nenhuma coluna de data encontrada" (`yyyymmdd` não está nos formatos do `clean`).
- `info` não acusa `valor` como número em texto (a regex não trata `R$`), mas o `clean --fix-types` converte a coluna.

**Correção:** um único módulo de inferência (formatos de data e parser numérico), usado pelo diagnóstico e pela correção. Acrescentar um teste que garanta que toda sugestão do `info` tem efeito no `clean`.

**Resolução:** o novo `inference.py` é a fonte única para datas (uma lista de formatos com `strptime`, que valida a data, mais um pré-filtro por regex para não pagar o `strptime` em colunas que nem têm forma de data), números em texto (`parse_number` e `numeric_text_columns`) e colunas de CPF/CNPJ. Diagnóstico e correção usam as mesmas funções. Resultados:
- `R$ 1.234,56` agora aparece no `info`;
- `yyyymmdd` deixou de contar como data no `info`, alinhado à decisão da spec 009;
- datas inválidas (`20261301`) não contam mais como formato: em `examples/clientes.csv`, de 5 para 4 formatos;
- códigos com zero à esquerda (CEP em texto) não são mais apontados como números, porque o `--fix-types` os ignora;
- colunas de data não são convertidas pelo `--fix-types`.

`TestDiagnosisMatchesCorrection` roda cada sugestão do `info` no `clean` e exige efeito nas mesmas colunas; os 5 testes falham na versão anterior. Custo: o `info` num CSV de 200 mil linhas e 10 colunas foi de 0,30 s para 0,58 s.

### DT08 — Lógica de negócio acoplada a `print`
`info()`, `profile()`, `clean()` e `convert()` validam, calculam, imprimem texto **e** montam o JSON, devolvendo `(exit_code, document)`. Consequências: o MCP precisa abafar o stdout (DT04), `convert` monta um documento que nunca imprime, e não há API Python reutilizável.

**Correção:** as funções de domínio devolvem um resultado estruturado (ou levantam uma exceção tipada), e a camada CLI renderiza texto ou JSON. É a mudança que destrava DT04, DT10 e DT19.

**Resolução:** cada comando agora tem uma função de domínio que devolve um resultado ou levanta `CommandError` (`info.diagnose`, `profiler.run`, `clean.diagnose`/`clean.apply_operations`, `convert.convert`), mais funções separadas para o documento JSON e para o texto. O CLI (`main._emit`) e o MCP (`mcp_server._run_tool`) só escolhem o formato. Com isso, o MCP deixou de devolver "Unknown error" sem documento quando o `convert` falhava. A saída do CLI foi comparada byte a byte com a versão anterior em 72 cenários: só mudaram as duas mensagens de extensão desconhecida do `convert`, que agora listam as extensões aceitas, como os demais comandos. O log também foi comparado: só mudou o nome do argumento `columns=` para `drop_null_columns=`.

### DT09 — Imports duplos em todos os módulos
Todo módulo abre com `try: from clean import ... except ImportError: from .clean import ...` ([main.py:8-37](../src/datatool/main.py#L8-L37) e outros 8 arquivos). Problemas:
- mascara `ImportError` legítimos (uma dependência faltando cai no ramo relativo e gera um erro confuso);
- nomes genéricos (`utils`, `info`, `structures`, `profiling`) podem pegar um módulo homônimo de terceiros que esteja no `sys.path`;
- o mesmo arquivo pode ser carregado duas vezes, com dois objetos `log`.

**Correção:** só imports relativos, com a execução via `python -m datatool.main` ou pelo entry point.

**Resolução:** todos os módulos usam só imports relativos. `python src/datatool/main.py` deixa de funcionar; o README já documentava `python -m datatool.main`.

### DT10 — Carga e validação de entrada duplicadas
O bloco "existe? → é arquivo? → infere tipo → `csv_options_error` → `read_file` com try" está copiado em [convert.py:33-61](../src/datatool/convert.py#L33-L61), [info.py:65-99](../src/datatool/info.py#L65-L99), [profiler.py:102-139](../src/datatool/profiler.py#L102-L139) e [clean.py:748-782](../src/datatool/clean.py#L748-L782). As cópias já divergiram (ver DT14). O mesmo vale para "parse de lista de colunas + `Unknown column(s) in --x`", repetido umas 8 vezes, embora `_parse_column_list` já exista.

**Correção:** extrair `load_input(...)` e `resolve_columns(df, spec, option_name)`.

**Resolução:** o novo `loading.py` tem `load_input`, `output_file_type`, `write_output`, `parse_column_list` e `resolve_columns`, todos levantando `CommandError`. O resumo do arquivo de entrada é tirado na leitura, para que o JSON continue certo mesmo se a saída sobrescrever a entrada. Uma diferença de detalhe: com várias colunas desconhecidas em `profile --columns`, a mensagem agora as lista na ordem digitada, e não em ordem alfabética.

### DT11 — Adicionar uma operação de `clean` exige editar 6 lugares
Nova operação = `_apply_*` + a tupla `has_operations` ([clean.py:726](../src/datatool/clean.py#L726)) + a **cópia** dessa tupla no MCP ([mcp_server.py:291](../src/datatool/mcp_server.py#L291)) + `_print_report` + `_log_report` + `_EXAMPLE_FIELD_BY_OPERATION`, além da ordem fixa em `clean()`. Esquecer a cópia do MCP faz a ferramenta recusar a operação nova.

**Correção:** um registro de operações (nome, flag, função, formatter de texto/log, campo de exemplos) iterado por `clean()`, pelos relatórios e pelo MCP.

**Resolução:** `_COLUMN_OPERATIONS`/`_VALUE_OPERATIONS` em `clean.py`, onde cada entrada tem `apply`, `print_text`, `log` e `examples_field`. Uma operação nova é uma entrada no registro mais um campo de mesmo nome em `CleanOptions` (e a flag no CLI/MCP). `CleanOptions.has_operations()` substitui as duas tuplas, e um teste garante que registro e `CleanOptions` não divergem.

### DT12 — `clean` depende de funções privadas de `quality`
[clean.py:11-23](../src/datatool/clean.py#L11-L23) importa `_DATE_MATCH_RATIO`, `_NUMERIC_MATCH_RATIO`, `_document_shape_for`, `_mask_document`, `_sample_values` e `_validate_document`. A fronteira entre os módulos é só nominal.

**Correção:** extrair `documents.py` (CPF/CNPJ) e o módulo de inferência de DT07, com API pública. `format_int_ptbr`, usado por todos os comandos, vai para um módulo de formatação.

**Resolução:** `documents.py` (formato, dígito verificador, máscara e contagem de CPF/CNPJ), `inference.py` (DT07) e `formatting.py`, todos com API pública. O `clean` não importa mais nenhum nome com `_` de outro módulo.

### DT13 — 23 argumentos posicionais em `main.clean` → `file_clean`
[main.py:230-254](../src/datatool/main.py#L230-L254) (e `profile`, [main.py:145-154](../src/datatool/main.py#L145-L154)). Vários são `str | None`, então trocar a ordem de dois deles não gera erro, só comportamento errado.

**Correção:** passar por keyword (como o MCP já faz) ou usar uma dataclass `CleanOptions`.

**Resolução:** o CLI e o MCP montam uma `CleanOptions` (dataclass imutável) por nome; `profile` e `convert` também são chamados por keyword.

### DT14 — Mensagens de erro erradas ou inconsistentes **(reproduzido)**
- [clean.py:766](../src/datatool/clean.py#L766) sugere `--from-type`, que o `clean` **não tem**.
- [info.py:83](../src/datatool/info.py#L83) e [profiler.py:123](../src/datatool/profiler.py#L123) dizem "Supported formats: csv, json, xlsx, parquet", mas há 8 formatos.
- O enum vaza na mensagem: `Could not save file q.db as FileType.SQLITE`.
- Idiomas misturados: erros em inglês, relatórios e sugestões em pt-BR.

**Resolução (parcial):** `clean` não sugere mais `--from-type`; `info`, `profile` e `clean` (entrada e saída) listam as extensões a partir de `SUPPORTED_EXTENSIONS`; as mensagens de load/save usam `.value`. **Pendente:** unificar o idioma (decidido adiar: muda o texto que agentes leem no JSON) e centralizar as mensagens, que depende do DT10.

**Resolução do restante:** toda saída voltada ao usuário está em pt-BR: erros no texto e no JSON (`error.message`), erros do sandbox do MCP, a mensagem de dependência ausente do `datatool-mcp`, comandos não implementados e as linhas do `--show-stats`. Nomes de opções continuam como na linha de comando (`--key`, `--overwrite`, `overwrite=true`). Ficam em inglês:
- textos que vêm das bibliotecas e entram como `{error}` nas mensagens (ex.: erros de leitura do polars);
- os erros de uso do Typer/Click ("Missing argument", "No such option"), que exigiriam traduzir o próprio framework.

Sobre centralizar: as mensagens repetidas já foram centralizadas no `loading.py` pelo DT10 (entrada, destino, extensões, colunas). As que sobraram aparecem uma única vez, junto da regra que validam, e movê-las para um catálogo só acrescentaria indireção. Se um dia houver tradução para outros idiomas, esse é o momento de criar o catálogo.

### DT15 — Flags conflitantes aceitas sem erro **(reproduzido)**
`clean --lowercase --uppercase` aplica as duas, e a última vence em silêncio. O mesmo vale para `--normalize-case` junto com qualquer uma delas. Além disso, `--columns` significa "alvo do `--drop-null`" no `clean` e "seleção de colunas" no `profile`.

**Resolução:** exclusão mútua validada antes de qualquer operação (exit 2). `--drop-null-columns` é o nome novo no CLI, e `--columns` continua aceito. **Pendente:** o parâmetro `columns` da ferramenta MCP `datatool_clean_apply` mantém o nome antigo, para não quebrar clientes.

### DT16 — Log gravado em `./logs` do diretório corrente
[execution_log.py:13](../src/datatool/execution_log.py#L13): cada execução cria `logs/` onde o usuário estiver, inclusive dentro de pastas de dados e de outros repositórios. Não há como desligar nem redirecionar. O MCP faz `os.chdir(root)` ([mcp_server.py:406](../src/datatool/mcp_server.py#L406)) só por causa disso, um efeito colateral global.

**Correção:** usar o diretório de log do usuário (`platformdirs`), com a variável `DATATOOL_LOG_DIR` e uma opção para desligar.

**Resolução:**
- O log vai para `platformdirs.user_log_dir("datatool")` (ex.: `~/Library/Logs/datatool`). `DATATOOL_LOG_DIR` escolhe outro diretório (relativo ao atual, se não for absoluto), e `DATATOOL_NO_LOG=1` desliga o log.
- O `datatool-mcp` usa `execution_log.set_default_log_dir(<root>/logs)` em vez de `os.chdir(root)`, e o env continua tendo prioridade.
- Nos testes, um fixture em `conftest.py` aponta `DATATOOL_LOG_DIR` para `./logs` do diretório temporário de cada teste, para não gravar no diretório real do usuário.
- Isso muda a decisão da spec 017 (log em `./logs`), que ganhou uma nota; quem quiser o comportamento antigo usa `DATATOOL_LOG_DIR=logs`.

### DT17 — `datatool-mcp` quebra sem o extra `[mcp]`
O entry point é instalado sempre ([setup.py:39](../setup.py#L39)), mas `mcp` é opcional e importado no topo do módulo ([mcp_server.py:18](../src/datatool/mcp_server.py#L18)). Quem instalou só `datatool-cli` recebe um traceback de `ModuleNotFoundError`.

**Resolução:** o import do `mcp` fica protegido (só `ModuleNotFoundError` do próprio `mcp`); as `ToolAnnotations` foram para dentro de `build_server`; `main()` sai com a mensagem de instalação. O `--help` continua funcionando sem o extra.

### DT18 — Dependências sem versão mínima; metadados divididos
- `polars`, `typer` e `mcp` estão sem limite de versão, mas o código usa APIs recentes (`str.strip_chars`, `replace_strict`, `mcp.server.mcpserver`, que é do SDK v2). Uma instalação num ambiente com versões antigas quebra em runtime.
- `requirements.txt` duplica o `install_requires`.
- `typing_extensions` é desnecessário (`Annotated` está em `typing` desde o 3.9, e o projeto exige ≥ 3.10).
- A versão `0.1.0` está fixa no `setup.py`, sem `__version__`, sem `datatool --version` e sem vínculo com a tag do release. O workflow de publicação ([publish-pypi.yml](../.github/workflows/publish-pypi.yml)) não roda testes antes de publicar.

**Correção:** migrar os metadados para `[project]` no `pyproject.toml`, definir limites mínimos, gerar a versão a partir da tag (`setuptools-scm`) e rodar os testes no workflow de publicação.

**Resolução:**
- `setup.py`, `requirements.txt` e `requirements-dev.txt` saíram. Tudo está no `[project]` do `pyproject.toml`, com os extras `mcp` e `dev`, e a licença como SPDX (`GPL-3.0-only`, a mesma do classifier "GPLv3" anterior). `typing_extensions` saiu.
- Os mínimos foram verificados rodando a suíte no Python 3.10 com `uv pip install --resolution lowest-direct` (novo job `test-minimum` no CI): `polars>=1.0`, `fastexcel>=0.10`, `typer>=0.16`, `xlsxwriter>=3.0`, `platformdirs>=3.0` e `mcp>=2.0`.
- Essa verificação achou um bug real: com `typer` 0.12–0.15 e o `click` atual (≥ 8.2), `datatool --help` quebrava (`make_metavar() missing ... 'ctx'`). Por isso o mínimo é 0.16. Para os testes, também `click>=8.2.1`, porque o `CliRunner` do 8.2.0 não captura o stderr.
- A versão vem da tag do git (`setuptools-scm`, com `fallback_version`). `datatool.__version__` e `datatool --version` a expõem.
- O workflow de publicação roda lint e testes antes do build (`needs: test`) e faz checkout com o histórico completo, para a versão sair da tag.

---

## Baixa

### DT19 — `convert` fora do padrão dos demais comandos
[convert.py](../src/datatool/convert.py):
- não tem `--format json` (o documento montado serve só ao MCP);
- sobrescreve a saída em silêncio no CLI (o MCP protege);
- com `--show-stats`, relê o destino fora de `try`, então uma falha vira traceback;
- sem destino, faz `print(df)`, que o polars trunca. O mesmo acontece no `clean` sem `--output`. Não serve para pipe;
- tem atribuições mortas (`df = None`, `df2 = None`).

**Atualização:** as atribuições mortas saíram com o DT08.

**Resolução:**
- `convert --format json` imprime o documento que já existia para o MCP (`source`/`target`). Ele exige `TO_FILENAME` e recusa `--show-stats`, que não tem lugar no JSON.
- `convert` e `clean --output` recusam um destino existente (exit 2) sem `--overwrite`, como o MCP já fazia. A checagem é feita antes de processar. Com `--overwrite`, o destino pode ser o próprio arquivo de entrada (limpeza no lugar); o MCP continua proibindo isso.
- A releitura do `--show-stats` falha com mensagem clara (exit 1) em vez de traceback.
- Sem destino, `convert` e `clean` imprimem o dataset inteiro em CSV no stdout. As mensagens (estatísticas do `--show-stats`, relatório das operações do `clean`) vão para o stderr, e um dado que não cabe em CSV (listas, structs) vira erro claro. Para isso, os formatadores de relatório do `clean` passaram a devolver linhas em vez de imprimir.
- **Quebra de compatibilidade:** scripts que regravam o mesmo destino precisam de `--overwrite`, e quem lia a prévia do polars no stdout passa a receber CSV.

### DT20 — Contrato do `Finding` ambíguo
[quality.py:8](../src/datatool/quality.py#L8):
- em `case_inconsistency`, o `message` é a própria lista de valores, o que exige casos especiais em `finding_to_dict` e `display_message`;
- `count` muda de significado conforme a categoria: linhas, número de formatos, ou `2` fixo em `document_format_variance` ([quality.py:318](../src/datatool/quality.py#L318)).

Quem consome o JSON (schema 019) não sabe o que `count` significa.

**Resolução:** o `Finding` ganhou `count_unit` (`rows`/`values`/`formats`/`variants`), que também vai no JSON como campo aditivo, sem mudar `schema_version`. `message` agora é sempre um resumo, e os valores ficam em `examples`. Com isso, `finding_to_dict` perdeu o caso especial, e `display_message` lista `examples` para qualquer categoria. A saída de texto é idêntica; a tabela de `count` da spec 019 inclui a unidade e as categorias de CPF/CNPJ. O `2` de `document_format_variance` continua fixo, mas agora documentado: são sempre dois formatos, com e sem máscara.

### DT21 — Detecção de documentos recalculada várias vezes
`analyze()` chama `detect_documents` (que chama `detect_document_columns`) e depois chama `detect_document_columns` de novo ([quality.py:614-615](../src/datatool/quality.py#L614-L615)). `--fix-types` repete o cálculo ([clean.py:329](../src/datatool/clean.py#L329)). Cada chamada valida o dígito verificador de uma amostra de todas as colunas. Hoje o custo é pequeno, mas cresce com a largura do arquivo.

**Atualização (DT07):** o problema mudou de lugar mas continua. `inference.numeric_text_columns` calcula `document_columns` e `date_columns` a cada chamada, e `analyze` também calcula as formas de data e as colunas de documento nos próprios detectores. Um cache por DataFrame, ou uma classificação única das colunas passada adiante, resolveria.

**Resolução:** a classificação passou a ser feita uma vez e passada adiante, sem cache implícito. `inference.date_column_shapes(df)` classifica as datas de todas as colunas de texto numa passada. `quality.analyze` calcula datas e CPF/CNPJ uma vez e os entrega aos três detectores que dependem deles (`detect_date_format_variance`, `detect_documents` e `detect_numeric_as_text`, que ganharam parâmetros opcionais para receber a classificação pronta). Resultados:
- num `info`, a classificação de CPF/CNPJ caiu de 2 para 1 execução, e a amostragem de datas de 2 para 1 por coluna de texto;
- no CSV de 200 mil linhas e 10 colunas, o tempo foi de ~0,58 s para ~0,48 s;
- a saída não mudou, conferida byte a byte em 72 comandos, e `TestColumnClassificationRunsOnce` conta as chamadas (falha na versão anterior).

No `clean`, cada operação ainda classifica o DataFrame que recebe. Isso é necessário, porque as operações anteriores mudam os valores (ex.: `--normalize-dates` antes de `--fix-types`).

### DT22 — `utils encode/decode`: ofuscação caseira
[utils.py](../src/datatool/utils.py) faz base64 com rotação de bytes, sem documentação de propósito. Não é criptografia; se a ideia é usar isso no licenciamento (spec 016), não protege nada. `encode("")` sai com exit 2. **Decidir:** remover, ou documentar e testar o caso de uso.

**Resolução:** decidido remover. Saíram `utils.py`, o grupo `datatool utils` e seus testes, e também o parâmetro `log_args` do `@logged`, que só existia para não logar o valor a codificar. Se o licenciamento (spec 016) precisar validar algo, deve usar assinatura criptográfica, não ofuscação.

### DT23 — Nomes confusos
- `profiler.py` (o comando) vs. `profiling.py` (o cálculo);
- `structures/` mistura enums, IO e SQLite, e o IO fica num genérico `functions.py`;
- `save_function` é um nome de função **e** de variável local dentro dela ([structures/functions.py:108-119](../src/datatool/structures/functions.py#L108-L119));
- `read_function[FileType.CSV]` nunca é usado, porque `read_file` trata CSV à parte;
- `utils_encode2`/`utils_decode2` em `main.py`.

**Resolução:**
- `profiling.py` virou `column_stats.py` (o cálculo das estatísticas); `profiler.py` continua sendo o comando, como a spec 003 decidiu para não colidir com o módulo `profile` da stdlib.
- `structures/` virou o pacote `files/`: `types.py` (`FileType`, extensões e inferência), `csv.py` (detecção de delimitador e encoding) e `sqlite.py`; `read_file`/`save_file` ficam no `__init__`, com um leitor e um gravador por formato (`_READERS`/`_WRITERS`). Com isso sumiram o `functions.py` genérico, o `save_function` sombreado e o `read_function[CSV]` morto.
- `OutputFormat` foi para `reporting.py`, e os enums usados só pelos comandos-esqueleto (`Language`, `EncodingType`, `OnErrorType`) para `main.py`.
- `utils_encode2`/`utils_decode2` saíram com o DT22.
- As specs com links para os caminhos antigos foram atualizadas, com nota do nome anterior.

### DT24 — Uso de API do polars que muda na 2.0
A leitura de xlsx emite um `FutureWarning` (`from_arrow ... will return a Series instead of a DataFrame in 2.0`, via [structures/functions.py:127](../src/datatool/structures/functions.py#L127)), visível na execução dos testes. Com `polars` sem versão máxima (DT18), vai quebrar no upgrade.

**Correção do diagnóstico:** o aviso não vem do nosso código. Quem chama `from_arrow()` é o próprio `pl.read_excel` (`_read_spreadsheet_calamine`, no polars 1.44 com fastexcel 0.21), então quem precisa se ajustar para a 2.0 é o polars, não o datatool. O problema real era o ruído, não uma quebra futura.

**Resolução:** `structures.functions.read_excel` envolve o `pl.read_excel` e silencia só esse aviso, só nessa chamada. Além disso, o pytest passou a tratar `FutureWarning` como erro (`filterwarnings` no `pyproject.toml`), para que um aviso novo desse tipo quebre a suíte em vez de passar despercebido.

### DT25 — Testes
- [test_cli.py](../tests/test_cli.py) tem 2.435 linhas num arquivo só. A sugestão é dividir por comando.
- O CI não mede cobertura (`pytest-cov`).
- Os testes dos comandos-esqueleto fixam um comportamento placeholder (DT06).
- Faltam testes de regressão para DT01, DT05, DT07 e DT15.

**Resolução:** os testes do DT06 e os de regressão de DT01, DT05, DT07 e DT15 já tinham entrado junto com esses itens. Agora:
- `test_cli.py` (2.779 linhas) virou 12 arquivos por comando/assunto (o maior tem 785 linhas), com os mesmos 234 testes. `conftest.py` tem o `runner` e o fixture de log; `helpers.py` tem `isolated_filesystem`, `load_json`, `read_log` e `write_bytes`, antes privados e duplicados em `test_mcp_server.py`.
- O CI mede cobertura (`pytest --cov`, hoje ~97%) e falha abaixo de 95% (`fail_under` no `pyproject.toml`).

### DT26 — Sem type hints/checker; ruff com poucas regras
Quase nenhuma função tem anotação de tipo, e o ruff seleciona só `E, F, I`. Ativar `B`, `UP` e `SIM` pega bugs comuns (ex.: `List[str] = None` em [main.py:266](../src/datatool/main.py#L266)). Considerar `pyright` em modo básico.

**Resolução:**
- O ruff passou a usar `E, F, I, B, UP, SIM` (alvo `py310`). As correções foram quase todas automáticas: `X | None`, `list[...]` e a remoção de `# -*- coding -*-` e de `typing_extensions`. À mão, só `zip(..., strict=True)` no dígito verificador e um `raise ... from None`.
- `pyright` em modo `basic` roda no CI com 0 erros. As correções foram reais:
  - anotações erradas nos comandos-esqueleto (`str = None`);
  - o tipo do `ContextVar` do log;
  - o import opcional do `mcp`, que deixava nomes possivelmente indefinidos. Por isso o entry point do `datatool-mcp` foi para `mcp_cli.py`, que importa `mcp_server` só depois de conferir que o `mcp` está instalado, e `mcp_server` importa o `mcp` normalmente.
- **Fora do escopo:** anotar todas as funções. O checker agora roda, e anotações podem entrar aos poucos, começando pelas APIs públicas (`loading`, `inference`, `documents`).

### DT27 — Arquivo solto versionado
`src/file.txt` (`A, B / 1, 2`) não era usado por nenhum código ou teste.

**Resolução:** removido.

---

## Segunda revisão (2026-09-30)

Revisão do código depois da resolução de DT01–DT27 (commit `b37d80a`). Estado de partida: 231 testes passando, cobertura de 97,7%, ruff e pyright limpos. Os itens abaixo foram encontrados lendo o código e exercitando casos de borda que a suíte não cobria.

| ID | Item | Área | Severidade | Esforço |
|----|------|------|------------|---------|
| DT28 ✅ | Valor fora do padrão depois das primeiras linhas: arquivo não abre (CSV/JSON/JSONL) ou vira nulo em silêncio (Excel) | IO | Alta | P |
| DT29 ✅ | `--normalize-documents --document-columns` em coluna não textual quebra com traceback | clean | Média | P |
| DT30 ✅ | Opções de parâmetro do `clean` ignoradas em silêncio | clean | Média | P |
| DT31 | SQLite perde tipos na ida e volta e não abre colunas com tipos mistos | IO | Média | M |
| DT32 | `--normalize-dates` lento em colunas com muitos valores distintos | Performance | Baixa | M |
| DT33 | Log do MCP registra "exit code 0" quando a ferramenta falha | Log/MCP | Baixa | P |
| DT34 | Código morto: `print_json` | Legibilidade | Baixa | P |
| DT35 | Lacunas de teste: `--version` e o `datatool-mcp` de verdade (stdio) | Testes | Baixa | P |
| DT36 | Site e índice das specs desatualizados | Docs | Baixa | P |

### DT28 — Valor fora do padrão depois das primeiras linhas **(reproduzido)**
[files/__init__.py](../src/datatool/files/__init__.py), [files/csv.py:89](../src/datatool/files/csv.py#L89)

O polars infere o tipo de cada coluna só pelas primeiras linhas (100 no CSV, no JSON e no JSONL; 1.000 no Excel, via fastexcel). Um "N/D" numa coluna numérica depois disso, justamente o tipo de sujeira que a ferramenta existe para achar, causa:
- **CSV, JSON, JSONL:** o arquivo não abre em nenhum comando (`info`, `profile`, `clean`, `convert`). Ex.: `idade` com 150 números e um "N/D" na linha 151 → `Não foi possível ler tardio.csv como csv: could not parse 'N/D' as dtype i64`.
- **Excel:** pior, sem erro. O valor vira **nulo em silêncio** (uma planilha de 1.500 linhas com "N/D" na linha 1.501 é lida como `idade = null`). Um `convert` de xlsx para csv perde o valor sem avisar, e o `info` o contaria como nulo, não como texto numa coluna numérica.

**Correção:** inferir os tipos com o arquivo inteiro. No CSV/JSON/JSONL, `infer_schema_length=None`; no Excel, a opção equivalente do fastexcel (`schema_sample_rows`/`infer_schema_length`). No CSV de 200 mil linhas, a leitura foi de 0,08 s para 0,12 s. A coluna passa a ser lida como texto, o `info` aponta "armazenada como texto mas parece numérica", e o `clean --fix-types` converte, exatamente o fluxo que a ferramenta propõe. Acrescentar testes com a anomalia depois da linha 100 (e da 1.000, no Excel) para cada formato.

**Resolução:**
- `read_csv`, `read_json`, `read_ndjson` e `read_excel` passam `infer_schema_length=None` (em `files/`).
- `tests/test_schema_inference.py` cobre os quatro formatos com a anomalia logo depois do limite de amostragem: o arquivo abre, o `info` aponta a coluna como número em texto, o `convert` preserva o `N/D` e o `clean --fix-types` converte e reporta o valor que não converteu. Os 12 testes falham com a leitura anterior e passam com a nova; a saída dos 72 comandos do snapshot não mudou.
- **Mínimo do polars subiu para 1.27.1** (era 1.0). O job de versões mínimas mostrou que, lendo o arquivo inteiro, o polars de 1.3 a 1.26 transforma em **nulo** os números de uma coluna JSONL que também tem texto, a mesma perda silenciosa que este item corrige; antes da 1.3, o `read_ndjson` nem aceita `infer_schema_length`. A suíte inteira passa com o polars 1.27.1 no Python 3.10.
- **Custo:** a leitura de um CSV de 200 mil linhas e 10 colunas foi de ~0,007 s para ~0,11 s, e o `info` nesse arquivo de ~0,48 s para ~0,59 s. O custo cresce linearmente com o tamanho. Se virar problema, dá para ler primeiro com a amostragem padrão e só reler por inteiro quando a leitura falhar. Isso vale para CSV/JSON/JSONL, que dão erro; o Excel, que zera em silêncio, precisa continuar lendo tudo.
- O SQLite tem o mesmo tipo de problema, na montagem do DataFrame, e continua no DT31.

### DT29 — `--document-columns` em coluna não textual **(reproduzido)**
[clean.py:104-121](../src/datatool/clean.py#L104-L121)

`--normalize-dates --date-columns` recusa colunas que não são texto, mas `--normalize-documents --document-columns` não faz essa checagem: numa coluna `Float64`, `document_shape` chama `value.strip()` num `float` e o comando termina com `AttributeError` e traceback.

**Correção:** aceitar só colunas de texto ou inteiras (o que `document_columns` já detecta) e recusar as demais com `CommandError` (exit 2), como em `--date-columns`.

**Resolução:** feito em `_apply_normalize_documents`: `Coluna(s) em --document-columns que não são de texto nem de inteiros: valor` (exit 2), sem traceback e sem gravar nada. O teste `TestDocumentColumnsType` falha na versão anterior.

### DT30 — Opções de parâmetro do `clean` ignoradas em silêncio **(reproduzido)**
[clean.py:35-63](../src/datatool/clean.py#L35-L63), [main.py](../src/datatool/main.py)

Opções que só configuram uma operação não fazem nada sem ela, e o comando não avisa:
- `--key` sem `--remove-duplicates`, `--drop-null-columns` sem `--drop-null`, `--document-columns` sem `--normalize-documents`, `--date-columns` sem `--normalize-dates`, `--decimal-separator` sem `--fix-types`;
- `--output` (e `--overwrite`) sem nenhuma operação: o comando faz só o diagnóstico e **não grava nada**, com exit 0. Ex.: `clean d.csv --date-columns data --output out.csv` imprime "Nenhum problema encontrado." e `out.csv` não existe. Quem esqueceu `--normalize-dates` acha que o arquivo foi gerado.

O servidor MCP já recusa `datatool_clean_apply` sem operação; o CLI não.

**Correção:** validar em `CleanOptions` (um método que lista parâmetros sem a operação correspondente) e falhar com exit 2 e mensagem clara ("--date-columns só tem efeito com --normalize-dates"). Para `--output` sem operação, o mesmo erro do MCP.

**Resolução:**
- `CleanOptions.validate()` reúne as regras de combinação: a exclusão mútua de `--lowercase`/`--uppercase`/`--normalize-case`, que já existia, e os parâmetros sem a operação (`_PARAMETER_OPERATIONS`, com os nomes das flags derivados dos campos). Todos os problemas saem numa mensagem só (ex.: `--key só tem efeito com --remove-duplicates; --date-columns só tem efeito com --normalize-dates.`), com exit 2, antes de ler o arquivo.
- A validação roda em `apply_operations`, o que vale para o CLI e para o `datatool_clean_apply`, e também no modo diagnóstico do CLI.
- No CLI, `--output`/`--overwrite` sem operação e `--overwrite` sem `--output` são erro. No `convert`, `--overwrite` sem `TO_FILENAME` também, porque era o mesmo tipo de opção ignorada em silêncio.
- 14 testes novos (CLI, JSON e MCP) falham na versão anterior; um caso positivo confirma que o parâmetro junto com a sua operação continua funcionando. A saída dos 72 comandos do snapshot não mudou.
- **Quebra de compatibilidade:** scripts que passavam uma dessas opções sem efeito passam a falhar com exit 2, e a mensagem diz o que falta.

### DT31 — SQLite: tipos perdidos e inferência pelas primeiras linhas **(reproduzido)**
[files/sqlite.py](../src/datatool/files/sqlite.py)

- **Ida e volta perde tipos:** `Boolean` vai como `INTEGER` e volta como `Int64`; `Date`/`Datetime` vão como texto ISO e voltam como `String`. Um `convert` parquet → db → parquet muda o schema.
- **Tipos mistos não abrem:** `read_sqlite` monta o DataFrame com `pl.DataFrame(rows, orient="row")`, que infere pelas primeiras 100 linhas; uma coluna com inteiros e um texto na linha 151 (o SQLite aceita, pela tipagem dinâmica) faz a leitura falhar.
- Carrega todas as linhas em tuplas Python (`fetchall`), o que é lento e pesado para tabelas grandes.

**Correção:** na gravação, declarar `BOOLEAN`, `DATE` e `TIMESTAMP` conforme o dtype. Na leitura, usar o tipo declarado (`PRAGMA table_info`) para converter de volta e `infer_schema_length=None` (ou ler colunas de tipo misto como texto). Avaliar `pl.read_database` com o cursor, para não passar por tuplas Python.

### DT32 — `--normalize-dates` lento em colunas com muitos valores distintos **(medido)**
[clean.py:152-192](../src/datatool/clean.py#L152-L192), [inference.py](../src/datatool/inference.py)

A normalização testa `strptime` em Python para cada valor distinto (e duas vezes em `date_formats_for`). Num CSV de 200 mil linhas com 70 mil datas distintas, `--normalize-dates` leva 2,8 s, contra 0,2–0,8 s das outras operações, e o custo cresce linearmente com os valores distintos.

**Correção:** vetorizar com o polars (`str.to_date(formato, strict=False)` por formato, combinados com `coalesce` na ordem de preferência), mantendo o pré-filtro, a preferência dd/mm e a exclusão de `yyyymmdd` (spec 009). Conferir o resultado contra a implementação atual antes de trocar.

### DT33 — Log do MCP registra "exit code 0" quando a ferramenta falha
[execution_log.py:130-163](../src/datatool/execution_log.py#L130-L163), [mcp_server.py:106-117](../src/datatool/mcp_server.py#L106-L117)

As ferramentas MCP devolvem erro como `CallToolResult(is_error=True)`, sem levantar exceção, então o `@logged` sempre registra `fim — exit code 0`. A spec 020 aceitou isso como limitação quando cada ferramenta montava o próprio resultado; hoje todas passam por `_run_tool`, que conhece o `exit_code` do `CommandError`. Além disso, `execution_log` depende de `typer.Exit` para saber o exit code, o que acopla o log ao framework do CLI.

**Correção:** o `logged` lê o exit code de um jeito que não dependa do typer (ex.: um `ContextVar`/atributo que `_run_tool` e `_fail` preenchem, ou uma exceção própria). O MCP passa a registrar o exit code real.

### DT34 — Código morto: `print_json`
[reporting.py:61](../src/datatool/reporting.py#L61)

`print_json` não é chamada por nenhum módulo desde o DT08, e a docstring de `build_document` ainda diz que ela é "usada pelo CLI". Remover a função e corrigir a docstring.

### DT35 — Lacunas de teste
- `datatool --version` (DT18) não tem teste.
- Nenhum teste sobe o `datatool-mcp` de verdade: todos chamam o servidor em processo (`server.call_tool`). Uma regressão no entry point (`mcp_cli`), no transporte stdio ou algo escrevendo no stdout do processo passaria pela suíte. Um teste de fumaça que inicie o processo, faça o `initialize` e chame uma ferramenta pelo stdio cobriria isso.

### DT36 — Site e índice das specs desatualizados
- [website/index.html](../website/index.html): o exemplo de `--format json` não tem `count_unit` (DT20), e a instalação indicada é `pip install -e .` (clonar o repositório), sem mencionar o `pip install datatool-cli` que o README já traz.
- [specs/README.md](README.md) não aponta este arquivo; a lista de débitos só é encontrada por quem já sabe que ela existe.

---

## Ordem sugerida

1. ~~**Rápidos e de alto impacto:** DT02, DT03, DT01, DT05, DT06, DT14, DT15, DT17, DT27.~~ Feito (DT14 em parte).
2. ~~**Refatoração base:** DT09 → DT10 → DT08 → DT11/DT13, e depois DT04 e DT19.~~ Feito.
3. ~~**Consistência do produto:** DT07 + DT12 (módulo único de inferência), DT20.~~ Feito.
4. ~~**Higiene contínua:** DT16, DT18, DT24, DT25, DT26.~~ Feito.
5. **Segunda revisão:** DT28 primeiro (um arquivo sujo não abrir, ou perder valores em silêncio, contradiz o propósito da ferramenta), depois DT29 e DT30 (rápidos, e evitam resultado enganoso), e então DT31, DT33, DT34, DT35, DT36 e DT32.
