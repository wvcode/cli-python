# Changelog

As mudanças de cada versão do `datatool-cli`. O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e as versões seguem o [versionamento semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

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

[0.1.0]: https://github.com/wvcode/cli-python/releases/tag/v0.1.0
