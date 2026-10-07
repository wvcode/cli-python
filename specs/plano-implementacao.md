# Plano de implementação — débito técnico e specs prontas

Ordem de implementação dos itens abertos do [débito técnico](debito-tecnico.md) (DT37–DT62) e das specs prontas para implementar ([021](021-leitura-via-url.md), [023](023-clean-dry-run.md), [024](024-diff-datasets.md), [025](025-head-sample.md) e o `concat` da [026](026-concat-join.md)). Substitui a antiga seção "Ordem sugerida" do débito técnico. O débito técnico e as specs continuam sendo a fonte de cada item (o problema, o comportamento e os critérios de aceite); aqui fica só a ordem, o que muda em cada passo e como conferir.

Situação em 2026-10-02, depois da publicação da v0.1.2: DT01–DT36 e DT44–DT47 resolvidos e publicados; DT37–DT43 e DT48–DT62 abertos. Em 2026-10-07, a fase 1 (DT37, DT38, DT48, DT49, DT52 e DT53) foi implementada para a v0.1.3, ainda não publicada. Specs implementadas: 001–003, 005–011, 017–020 e 022.

**Specs prontas:** as que têm "Decisões confirmadas" e nenhuma questão em aberto. Ficam fora deste plano:
- [004](004-profile-relatorio-html.md) e [012](012-pipeline-automacao.md)–[016](016-licenciamento-pro.md), que ainda têm "Questões em aberto". Entram no plano quando essas questões forem decididas.
- O `join` da [026](026-concat-join.md), adiado até haver demanda (decisão 1 da spec).

## Ponto de partida

Já feito, na ordem em que foi planejado:

1. **Rápidos e de alto impacto:** DT01, DT02, DT03, DT05, DT06, DT14, DT15, DT17, DT27.
2. **Refatoração base:** DT09 → DT10 → DT08 → DT11/DT13, e depois DT04 e DT19.
3. **Consistência do produto:** DT07 + DT12 (módulo único de inferência), DT20.
4. **Higiene contínua:** DT16, DT18, DT24, DT25, DT26.
5. **Segunda revisão:** DT28, DT29, DT30, DT31, DT33, DT34, DT35, DT36 e DT32.
6. **Publicação da v0.1.0** (PyPI, 2026-09-30): descrições no `--help`, confirmação "Gravado …" no stderr, metadados do PyPI, README e site, CHANGELOG, checagem da versão contra a tag. Os comandos-esqueleto saíram, o que completou o DT06.
7. **Correções antes de divulgar** (v0.1.2, PyPI, 2026-10-02; não houve 0.1.1): DT46 (UTF-16), DT45 (números além de 64 bits), DT47 (seleção de aba, spec [022](022-excel-selecao-de-aba.md)) e DT44 (`1.500` lido como `1,5`).
8. **Fase 1 deste plano** (v0.1.3, não publicada): DT52, DT53, DT49 (decidido: não converter colunas mistas), DT37, DT38 e DT48. Junto, `clean --null-values` (extensão da spec [008](008-clean-tratar-nulos.md)), para converter colunas com `N/D` de forma explícita.

## Decisões pendentes

Itens que não dá para implementar sem uma escolha antes. Vale decidir no começo da fase em que o item está.

| Item | Decisão | Opções (detalhes no débito técnico) |
|------|---------|-------------------------------------|
| DT50 | Interface do CSV para o Excel em português | `--output-sep`/`--output-encoding` · atalho `--excel-br` · herdar separador e encoding da entrada |
| DT39 | Contagem de testes no site | Remover · gerar no workflow `deploy-pages` |
| DT59 | Garantia de redação no MCP | Só documentar · opção `datatool-mcp --force-redact` |
| 021 | URL nos comandos criados antes dela (`head`, `sample`, `diff`, `concat`) | A spec cita só `convert`, `info`, `profile` e `clean`, mas a mudança fica no `load_input`, que os comandos novos também usam: aceitar e testar em todos · recusar nos novos por enquanto |

## Fase 1 — Perda de dado e atritos de uso ✅

Implementada em 2026-10-07 para a v0.1.3. A resolução de cada item está no [débito técnico](debito-tecnico.md).

Primeiro o que apaga dado sem aviso, depois o que impede de usar a ferramenta, depois os atritos.

### 1.1 DT52 — Gravar sobre uma planilha de várias abas apaga as outras

- **Mudança:** em `loading.py` (ao lado de `check_output`), quando o destino é o próprio arquivo de entrada, o formato é xlsx e a planilha tem mais de uma aba, recusar com exit 2 antes de processar. Vale para `clean --output` e `convert`. Ao gravar xlsx a partir de uma aba, usar o nome da aba lida em vez de "Sheet1".
- **Conferir:** teste em `tests/test_excel_sheets.py` com uma planilha de três abas: `--overwrite` sobre a entrada sai com exit 2 e o arquivo continua com as três abas; gravar em outro arquivo funciona e a aba sai com o nome original.

### 1.2 DT53 — SQLite com várias tabelas não abre

- **Mudança:** opção `--table` no padrão do `--sheet` em `convert`, `info`, `profile` e `clean`, e parâmetro `table` no servidor MCP. Sem `--table` e com várias tabelas: exit 2, lista em texto (`Tabelas: clientes, pedidos.`) e a sugestão de `--table`. O JSON traz `table`/`tables` no resumo do arquivo.
- **Conferir:** testes em `tests/test_sqlite.py` para tabela escolhida, tabela inexistente (exit 2 com a lista) e várias tabelas sem `--table`; teste da ferramenta MCP com `table`.

### 1.3 DT49 — `--fix-types` apaga os valores que não converte

- **Antes:** decidir entre as opções da tabela de decisões.
- **Mudança:** em `clean.py`, o comportamento escolhido; em qualquer opção, o `info` só sugere `--fix-types` para colunas em que todos os valores da amostra são números.
- **Conferir:** a coluna de códigos do item (`1000`, `1001`, `A12`, `B7`) não perde `A12` nem `B7` no arquivo gravado, e o `info` deixa de sugerir `--fix-types` para ela.

### 1.4 DT37 — Erro de sandbox do MCP não diz o motivo no log

- **Mudança:** `_sandbox_error_result` passa pelo `error_document` com um `CommandError(mensagem, 2)`.
- **Conferir:** a linha `ERROR` aparece no log para os três casos (caminho fora da raiz, destino igual à entrada, destino existente sem `overwrite=true`).

### 1.5 DT38 — Parâmetro `columns` do `datatool_clean_apply`

- **Mudança:** aceitar `drop_null_columns`, manter `columns` como alias obsoleto (dito na descrição da ferramenta) e recusar os dois juntos. Anotar no CHANGELOG a remoção futura do alias.
- **Conferir:** testes no `tests/test_mcp_server.py` para o nome novo, o alias e os dois juntos (erro).

### 1.6 DT48 — Coluna com espaço nas pontas do nome

- **Mudança:** em `resolve_columns`, quando o nome exato não existe, aceitar a coluna cujo nome sem espaços nas pontas é igual ao pedido, se só uma casar. O diagnóstico do `clean` aponta nomes com espaços extras e sugere o renomear.
- **Conferir:** `--key " email "` e `--key email` funcionam num CSV com cabeçalho `" email "`; dois cabeçalhos que casam (`"email"` e `" email "`) dão erro de ambiguidade.

**Fase pronta quando:** os seis itens estão resolvidos, a suíte e o CI passam, e o CHANGELOG registra as mudanças de comportamento (recusa no xlsx, `--table`, `--fix-types`, alias do MCP). É um bom ponto para publicar uma versão, porque o DT52 e o DT49 evitam perda de dado.

## Fase 2 — Confiança e acabamento

### 2.1 DT56 — Workflows sem `permissions:` explícito

- **Mudança:** `permissions: contents: read` no topo do `ci.yml` e do `publish-pypi.yml`; o job `publish` continua pedindo `id-token: write`.
- **Conferir:** o CI passa num PR, e a próxima publicação (ou um teste no TestPyPI) continua autenticando por OIDC.

### 2.2 DT62 — Teste de regressão para fuga do sandbox por link simbólico

- **Mudança:** só testes, em `tests/test_mcp_server.py`: link para diretório fora da raiz, link para arquivo fora da raiz e destino novo dentro de um link, na leitura e na gravação.
- **Conferir:** os testes passam hoje e falham se `_resolve` trocar `resolve()` por `absolute()`.

### 2.3 DT57 — Actions fixadas por SHA

- **Mudança:** fixar as actions por SHA completo, com a versão num comentário, ao menos no `publish-pypi.yml`; adicionar o Dependabot para `github-actions`.
- **Conferir:** o CI passa e o Dependabot abre o primeiro PR de atualização.

### 2.4 DT40 — CI também em Windows e macOS

- **Mudança:** `windows-latest` e `macos-latest` na matriz de um job de testes, sem multiplicar pelas versões de Python.
- **Conferir:** a suíte passa nos três sistemas, incluindo o teste do `datatool-mcp` via stdio (DT35). Falhas de caminho, `\r\n` ou pasta de log viram correções neste mesmo passo.

### 2.5 DT39 — Números do site escritos à mão

- **Antes:** decidir entre remover a contagem de testes ou gerá-la no `deploy-pages`.
- **Mudança:** em `website/index.html` e, se for gerar, no workflow `deploy-pages.yml` (`pytest --collect-only -q`).
- **Conferir:** o site publicado não tem mais número de testes digitado à mão.

### 2.6 DT50 — CSV que abre no Excel em português

- **Antes:** decidir a interface (tabela de decisões).
- **Mudança:** na gravação de CSV (`files/__init__.py` e `files/csv.py`), separador `;`, vírgula decimal e UTF-8 com BOM conforme a opção escolhida, em `convert` e `clean`.
- **Conferir:** teste que lê o CSV gravado como bytes (BOM, `;`, `1.234,56`); abrir no Excel em português com duplo clique e ver colunas e acentos certos.

**Fase pronta quando:** o CI roda nos três sistemas com permissões mínimas e actions fixadas, e o CSV de saída tem um caminho documentado para o Excel em português.

## Fase 3 — Comandos novos

As specs menores primeiro. Cada uma acrescenta comando, JSON de 019 e, quase todas, ferramenta MCP. Por isso vêm depois da fase 2: o CI em três sistemas e o teste de symlink (DT62) já protegem o que elas tocam. Para cada spec, a conferência são os critérios de aceite dela; abaixo, só o que muda e os pontos de atenção.

### 3.1 Spec 023 — `clean --dry-run`

- **Depois de:** DT38, porque a `datatool_clean_preview` recebe os mesmos parâmetros da `datatool_clean_apply` e já nasce com `drop_null_columns`; e DT49, cujo comportamento novo do `--fix-types` é o que o `--dry-run` vai mostrar.
- **Mudança:**
  - em `clean.py`, contagem de valores alterados por coluna nas operações de texto (`_string_operator`), com e sem `--dry-run`;
  - a opção `--dry-run` em `main.py`, com o relatório no stdout e o resumo "Nada foi gravado.";
  - a ferramenta `datatool_clean_preview`, somente leitura, em `mcp_server.py`.
- **Atenção:** a saída do `clean` muda mesmo sem `--dry-run` (linhas novas no texto e `columns` no JSON). Precisa entrar no CHANGELOG (decisão 1 da spec). A lista de ferramentas do servidor passa de 5 para 6 nos testes, no README e no site.

### 3.2 Spec 025 — `head` e `sample`

- **Mudança:**
  - comandos `head` e `sample` em `main.py`, com opção de formato própria (texto, `csv`, `json`), porque `csv` não vale nos outros comandos;
  - `datatool-mcp --allow-rows` em `mcp_cli.py`, que registra `datatool_head` e `datatool_sample`, com limite de 100 linhas por chamada.
- **Atenção:**
  - são os primeiros comandos que mostram valores de célula de propósito: nada de valores no log, e as ferramentas MCP só existem com `--allow-rows`;
  - a ajuda do `--seed` e o README dizem que a amostra só se repete na mesma versão do polars (decisão 2 da spec).
- **Junto, se decidir fazer:** DT54 (`tail`), com as mesmas opções e saídas do `head`.

### 3.3 Spec 024 — `diff`

- **Depois de:** DT48, porque `--key` usa a mesma resolução de colunas; e da 023, porque um critério de aceite compara o `diff` entre entrada e saída do `clean` com o relatório do `clean`, que a 023 completa nas operações de texto.
- **Mudança:** módulo novo para a comparação (esquema, por chave e por linha inteira), comando `diff` em `main.py` e ferramenta `datatool_diff`, somente leitura, com `redact_values` ligado por padrão.
- **Atenção:**
  - exit code 0 com ou sem diferenças (decisão 1 da spec);
  - colunas com tipo alterado ficam fora da comparação de valores (decisão 2);
  - critério de desempenho: 200 mil linhas em poucos segundos. Vale medir antes de dar como pronto.

### 3.4 Spec 026 — `concat`

- **Depois de:** DT40, porque a expansão de `*`/`?` pelo próprio datatool existe por causa do Windows e só é conferida com o CI lá.
- **Mudança:** comando `concat` em `main.py`, com leitura de cada arquivo pelo `load_input` e as opções `--allow-missing` e `--source-column`. Sem ferramenta MCP (fora de escopo na spec).
- **Atenção:**
  - tipos diferentes viram o tipo comum (`how="diagonal_relaxed"`), e a mudança aparece no relatório;
  - o `join` não entra.
- **Junto, se decidir fazer:** DT55 (`--all-sheets`), que reaproveita a listagem de abas da spec 022.

**Fase pronta quando:** os critérios de aceite das quatro specs estão marcados, o README e o site listam os comandos e ferramentas novos, e o CHANGELOG registra a mudança na saída do `clean`.

## Fase 4 — Leitura via URL (spec 021)

Fica por último entre as specs porque muda o `load_input`, por onde passam todos os comandos, inclusive os da fase 3, e porque é a primeira vez que a ferramenta acessa a rede. Antes de começar, decidir se a URL vale também para `head`, `sample`, `diff` e `concat` (tabela de decisões).

- **Depois de:**
  - DT53, porque o SQLite por URL escolhe a tabela pelo nome do arquivo, e o `--table` dá a alternativa;
  - DT37, porque a nova recusa de URL no MCP sem `--allow-urls` é um erro de sandbox e deve aparecer no log;
  - DT56 e DT62 (fase 2).
- **Mudança, em partes que podem virar commits separados:**
  1. `--from-type` em `info`, `profile` e `clean`. Útil também para arquivos locais.
  2. Download para um diretório temporário em `load_input`: `urllib.request`, até 5 redirecionamentos, TLS verificado, proxies do ambiente, gravação em blocos, limites de `DATATOOL_URL_MAX_MB` (500) e `DATATOOL_URL_TIMEOUT` (30 s), e apagar o temporário em qualquer saída.
  3. Formato pela extensão do caminho da URL, depois `--from-type`, depois `Content-Type`.
  4. Limpeza da URL (sem credenciais no stdout; sem query nem credenciais no log e nas mensagens de erro).
  5. MCP: `datatool-mcp --allow-urls`, recusando hosts que resolvem para loopback, rede privada, link-local ou reservado, inclusive no destino de cada redirecionamento.
- **Atenção:**
  - a checagem de endereço privado precisa olhar o IP que a conexão vai de fato usar, não só o resolvido antes: senão um DNS que responde diferente na segunda consulta passa pela checagem;
  - os testes usam um servidor HTTP local numa thread, sem internet, como a spec pede;
  - a suíte existente tem de passar sem alteração (caminhos locais não mudam).
- **Fase pronta quando:** os critérios de aceite da 021 estão marcados e o README explica `--allow-urls` e os limites.

## Fase 5 — Quando houver demanda

Sem ordem fixa: cada item entra quando aparecer um caso real que o justifique.

| Item | Gatilho | Resumo da mudança |
|------|---------|-------------------|
| DT41 | Bancos SQLite grandes, ou ida e volta parquet → db → parquet | Gravar e ler data-hora com o `time_unit` certo; `fetchmany` ou leitor opcional via connectorx/ADBC; fuso documentado ou guardado em metadados |
| DT42 | Reclamação de lentidão em arquivos grandes | Ler por amostragem e reler por inteiro quando falhar ou quando uma coluna vier só com nulos na amostra; conferir contra a leitura completa, como no DT32 |
| DT43 | Usuários tropeçando nas mensagens em inglês | Catálogo pt-BR para o `gettext` do click; frase em pt-BR antes do texto do polars nos casos comuns (CSV vazio, linhas de tamanhos diferentes) |
| DT51 | Planilhas financeiras com `(1.234,56)` | Parênteses como sinal negativo em `parse_number`, com testes para `(1.234,56)`, `(R$ 10,00)` e `(1,234.56)` |
| DT58 | Servidor MCP usado com arquivos grandes | Teto de tamanho em `_validate_input` (`--max-file-size`), recusado como erro de sandbox |
| DT59 | Uso do MCP com dados pessoais | Documentar o alcance do `redact_values` no README e na spec 020; se preciso, `--force-redact`; conferir se os erros do polars trazem valores |
| DT60 | `clean` apresentado como "sanitizar" | Documentar; se houver demanda, diagnóstico de células que começam com `=`, `+`, `-` ou `@` e operação opcional que as neutraliza |
| DT61 | Servidor MCP rodando num ambiente compartilhado | Abrir arquivos com `O_NOFOLLOW`/descritores relativos à raiz, ou reconferir o caminho depois de abrir |
| DT54 | Não feito junto com a spec 025 (passo 3.2) | `datatool tail arquivo -n N`, com as opções e saídas do `head` |
| DT55 | Não feito junto com a spec 026 (passo 3.4) | `concat relatorio.xlsx --all-sheets`, com o nome da aba na `--source-column` |
| `join` (026) | Usuários pedindo para juntar tabelas | Refazer a escolha entre `join` e um comando `sql` com DuckDB (decisão 1 da spec) |
