# Changelog

As mudanças de cada versão do `datatool-cli`. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões seguem o [versionamento semântico](https://semver.org/lang/pt-BR/).

## [0.1.3] — não publicada

### Corrigido

- `--fix-types` apagava os valores que não conseguia converter: numa coluna de códigos (`1000`, `1001`, `A12`, `B7`), `A12` e `B7` viravam nulos no arquivo gravado, e o `info` sugeria a operação. Agora uma coluna com algum valor que não é número não é convertida: continua como texto, sem perder nada, e o relatório lista os valores (veja "Alterado").
- Gravar sobre a própria planilha de entrada (`clean relatorio.xlsx --sheet "Vendas 2025" --output relatorio.xlsx --overwrite`, ou o mesmo no `convert`) apagava as outras abas, com exit code 0. Agora, se a planilha tem mais de uma aba, a gravação é recusada antes de processar (exit code 2), mesmo com `--overwrite`. Ao gravar em outro `.xlsx`, a aba mantém o nome da aba lida, em vez de "Sheet1".
- Um banco SQLite com várias tabelas e nenhuma com o nome do arquivo não abria em nenhum comando. Agora o erro lista as tabelas e sugere `--table` (exit code 2, em vez de 1).
- Colunas com espaços nas pontas do nome (`" email "`, comum em exportações do Excel) não podiam ser referenciadas em `--key`, `--columns`, `--rename-columns` e nas demais opções de coluna. Agora são encontradas pelo nome sem os espaços; se duas colunas casarem, é erro (exit code 2).

### Adicionado

- `--table` em `convert`, `info`, `profile` e `clean` (e `table` nas ferramentas do servidor MCP) escolhe a tabela de um banco SQLite. O JSON traz `table` e `tables` no resumo do arquivo, e as sugestões do `info` incluem a tabela.
- O diagnóstico do `clean` aponta nomes de coluna com espaços nas pontas (categoria `column_name_whitespace`, com o novo `count_unit` `columns`) e mostra o `--rename-columns` que os tira.
- `drop_null_columns` no `datatool_clean_apply` do servidor MCP, com o mesmo nome da opção do CLI.
- `--null-values` no `clean` (e `null_values` no `datatool_clean_apply`) troca por nulo, nas colunas de texto, valores que querem dizer "sem dado": `datatool clean dados.csv --null-values "N/D,-" --fix-types` converte uma coluna de números com `N/D`, o que o `--fix-types` sozinho deixou de fazer. Quando uma coluna não é convertida, o relatório do `--fix-types` sugere a opção.

### Alterado

- `--fix-types` não converte mais colunas em que algum valor não é número (antes, esses valores viravam nulo). No texto, a coluna aparece como `"idade": não convertida, 1 valores não são números (a coluna continua como texto):`, seguida dos valores. No JSON, cada coluna da operação `fix_types` ganha `converted` (`true`/`false`), e `type` é `null` nas não convertidas. Uma coluna com `N/D` no lugar de números agora fica como texto; para convertê-la, use `--null-values "N/D" --fix-types`.
- O `info` aponta essas colunas como `mixed_types` (`"idade" parece numérica, mas 1 valores não são números`), sem sugerir `--fix-types`. A categoria `types`, que dispara a sugestão, fica só para colunas em que todos os valores são números.
- Sem nenhuma sugestão, o `info` não imprime mais o título "Sugestões:" vazio.
- No servidor MCP, os erros de sandbox (caminho fora da raiz, destino igual à entrada, destino existente sem `overwrite=true`) passam a ser registrados no log, como os demais erros.

### Obsoleto

- O parâmetro `columns` do `datatool_clean_apply` (servidor MCP) continua aceito, mas será removido numa versão futura: use `drop_null_columns`. Passar os dois é erro.

## [0.1.2] — 2026-10-02

A versão seguinte à 0.1.0: não houve 0.1.1 publicada.

### Adicionado

- `--sheet` em `convert`, `info`, `profile` e `clean` (e `sheet` nas ferramentas do servidor MCP) escolhe a aba de uma planilha Excel, pelo nome ou pela posição. O texto mostra a aba lida, o JSON lista todas as abas, e as sugestões do `info` incluem a aba.

### Corrigido

- Em planilhas Excel com várias abas, só a primeira era lida, sem aviso: o `info` podia analisar uma aba de resumo e responder "Nenhum problema encontrado". Agora é lida a primeira aba visível com dados, e um aviso no stderr diz qual foi lida e quais são as outras.
- Uma planilha cuja primeira aba está vazia (uma capa, por exemplo) não abria. Agora a aba vazia é pulada.
- Num CSV separado por `;` (o do Excel em português), `1.500` era lido como 1,5, sem aviso, em todos os comandos. Agora a vírgula é o separador decimal nesses arquivos: `10,5` é lido como número, e `1.500` chega como texto, para o `--fix-types` converter em 1500. Num CSV separado por vírgula, nada muda.
- CSV com a chave de acesso da NF-e, o código de barras de um boleto ou qualquer inteiro que não cabe em 64 bits não abria. Essas colunas agora são lidas como texto, sem perder dígitos, e o `info` não sugere mais convertê-las em número (o `--fix-types` quebrava ao tentar).
- CSV em UTF-16 com BOM ("Texto Unicode" do Excel e exportações de alguns sistemas) era lido como uma única coluna ilegível, com "Nenhum problema encontrado". Agora o encoding é detectado pelo BOM.

### Alterado

- No PyPI, o link *Homepage* aponta para o [site](https://wvcode.github.io/cli-python/), e o GitHub aparece como *Repository*.

## [0.1.0] — 2026-09-30

Primeira versão publicada.

### Comandos

- **`convert`**: converte entre CSV, JSON, JSONL, Excel (xlsx), Parquet, Feather, Avro e SQLite, com o formato inferido pela extensão (ou `--from-type`/`--to-type`). Sem arquivo de destino, imprime o CSV no stdout, pronto para pipe. Um destino existente só é substituído com `--overwrite`.
- **`info`**: diagnostica o arquivo e sugere o comando que corrige cada problema. Aponta valores nulos, linhas duplicadas, datas em formatos diferentes, números guardados como texto e CPF/CNPJ inválido.
- **`profile`**: estatísticas por coluna. Numéricas: mínimo, máximo, média, mediana, percentis e outliers. Categóricas: cardinalidade e valores mais frequentes. Também conta linhas duplicadas, no total e por chave (`--key`). `--columns` e `--max-columns` limitam o relatório em arquivos largos.
- **`clean`**: sem operação, diagnostica sem alterar nada (e-mail inválido, telefones em formatos diferentes, espaços extras, duplicidade por chave, capitalização, CPF/CNPJ). Com operações, corrige e grava em `--output`:
  - `--trim`, `--lowercase`, `--uppercase`, `--normalize-case`
  - `--remove-duplicates` (com `--key`)
  - `--fill-null`, `--drop-null`
  - `--normalize-dates`: datas em formatos variados para `aaaa-mm-dd`
  - `--fix-types`: números guardados como texto, em formato brasileiro (`1.234,56`, `R$`) ou americano (`1,234.56`)
  - `--normalize-documents`: CPF/CNPJ só com dígitos ou com máscara
  - `--rename-columns`, `--remove-columns`

### Feito para arquivos brasileiros

- CSV exportado pelo Excel em português: o delimitador (`;`) e o encoding (`cp1252`) são detectados sozinhos. `--sep` e `--encoding` forçam outro valor.
- CPF e CNPJ validados pelo dígito verificador, inclusive quando a coluna foi lida como número e perdeu os zeros à esquerda.
- Datas `dd/mm/aaaa` têm prioridade sobre `mm/dd/aaaa` quando o valor é ambíguo.

### Integração com scripts e agentes de IA

- `--format json` em `info`, `profile`, `clean` e `convert`: um documento versionado (`schema_version: 1`), para `jq`, notebooks e pipelines de CI.
- `--redact-values`: tira os valores de célula do relatório e mantém as contagens, para compartilhar a saída sem expor dados.
- Servidor MCP `datatool-mcp` (extra `[mcp]`): expõe os comandos como ferramentas para agentes de IA, com os arquivos restritos ao diretório de `--root` e valores de célula ocultos por padrão.
- Log de execução no diretório de logs do usuário, sem valores de célula. `DATATOOL_LOG_DIR` muda o diretório e `DATATOOL_NO_LOG=1` desliga o log.

### Requisitos

- Python 3.10 ou mais novo.

[0.1.2]: https://github.com/wvcode/cli-python/compare/v0.1.0...v0.1.2
[0.1.0]: https://github.com/wvcode/cli-python/releases/tag/v0.1.0
