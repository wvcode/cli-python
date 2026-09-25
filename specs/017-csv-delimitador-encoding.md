# US-017: Detectar delimitador e encoding de CSV, com log de execução

## User story
Como analista que recebe CSVs exportados pelo Excel em português, eu quero que o datatool leia arquivos separados por `;` e codificados em `cp1252` sem configuração, para não receber um diagnóstico errado (uma coluna só, ou erro de encoding) logo no primeiro uso.

Como usuário que roda o datatool em scripts e pipelines, eu quero um arquivo de log com o que cada execução fez (o que foi lido, detectado, alterado e gravado), para entender e auditar o resultado sem poluir a saída do terminal.

## Contexto
Origem: item [F01 do backlog](backlog-novas-features.md#f01--detecção-de-delimitador-e-encoding-em-csv).

Hoje `convert`, `info`, `profile` e `clean` leem CSV com `pl.read_csv` nos padrões do polars (`read_function[FileType.CSV]` em [src/structures/functions.py](../src/structures/functions.py)): separador `,` e UTF-8. O Excel em português exporta "CSV (separado por vírgulas)" com `;` e em `cp1252`. Resultado:

- arquivo com `;` → lido como **uma única coluna** (`nome;email;cidade`), e o `info` diagnostica problemas que não existem;
- arquivo em `cp1252` com acentos → falha com `Could not load file ... invalid utf-8 sequence`.

Como os quatro comandos leem pelo mesmo `read_function`, a correção em um único ponto de leitura de CSV beneficia todos.

A detecção automática precisa ser rastreável (o usuário tem que conseguir saber que o arquivo foi lido como `;`/`cp1252`), mas não pode ir para o terminal: `convert` sem arquivo de destino e `clean` sem `--output` imprimem o resultado no stdout, que pode estar sendo redirecionado. Por isso esta spec introduz um **log de execução em arquivo**, cobrindo tudo o que o CLI faz, e não só a detecção.

## Interface proposta
```bash
datatool info vendas.csv                                  # detecta ; e cp1252 sozinho
datatool info vendas.csv --sep ";" --encoding latin-1     # override explícito
datatool convert vendas.csv vendas.parquet --sep "\t"
datatool clean vendas.csv --encoding cp1252 --trim --output vendas_limpo.csv
```

`--sep` e `--encoding` passam a existir em `convert`, `info`, `profile` e `clean`, e se aplicam **só ao arquivo de entrada**.

A saída no terminal não muda: o que foi detectado automaticamente vai só para o log.

## Comportamento — leitura de CSV
**Encoding**
1. Tenta ler como UTF-8. BOM UTF-8 (gerado pelo Excel em "CSV UTF-8") é aceito e não aparece no nome da primeira coluna — o polars já faz isso hoje.
2. Se o arquivo não for UTF-8 válido, relê como `cp1252`. Escolhido em vez de `latin-1` porque é o que o Excel/Windows em português de fato gera e é superconjunto dos caracteres imprimíveis de `latin-1` (inclui `€`, aspas curvas `“ ”`, travessão `–`).
3. `--encoding` aceita qualquer codec conhecido pelo Python (`latin-1`, `utf-16`, `cp850`, ...) e desliga a detecção.

**Delimitador**
1. Detectado com `csv.Sniffer` da stdlib sobre uma amostra do início do arquivo (até 64 KB, já decodificada no encoding escolhido), restrito aos candidatos `,` `;` `\t` `|`.
2. Se o sniffer não conseguir decidir (ex.: arquivo de uma coluna só), usa `,`.
3. `--sep` aceita um único caractere; `"\t"` (escrito literalmente, com barra) é aceito como tab. Desliga a detecção.

## Comportamento — log de execução
**Local e formato**
- Grava em `logs/datatool.log`, relativo ao **diretório atual** onde o comando é executado. O diretório `logs/` é criado se não existir.
- Arquivo acumulativo (append), com rotação por tamanho: ao passar de 5 MB vira `datatool.log.1`, mantendo até 3 arquivos antigos (`logging.handlers.RotatingFileHandler` da stdlib).
- Uma linha por evento: data/hora, nível, identificador da execução, comando e mensagem. O identificador (curto, gerado por execução) permite separar execuções simultâneas ou seguidas:

```text
2026-09-25 14:03:12,345 INFO    [a1b2c3] info: início — args: filename=vendas.csv, output_format=text
2026-09-25 14:03:12,351 INFO    [a1b2c3] info: lendo vendas.csv (csv)
2026-09-25 14:03:12,352 INFO    [a1b2c3] info: encoding detectado: cp1252 (arquivo não é UTF-8 válido)
2026-09-25 14:03:12,352 INFO    [a1b2c3] info: delimitador detectado: ';'
2026-09-25 14:03:12,410 INFO    [a1b2c3] info: lido — 1204 linhas, 8 colunas
2026-09-25 14:03:12,411 INFO    [a1b2c3] info: diagnóstico — 2 problemas (nulls, types)
2026-09-25 14:03:12,498 INFO    [a1b2c3] info: fim — exit code 0, 0,15 s
```

**O que é registrado** — tudo o que o CLI faz, em todos os comandos (inclusive os ainda esqueleto, como `excel` e `dataset`, que registram ao menos início e fim):

| Evento | Nível | Conteúdo |
|--------|-------|----------|
| Início do comando | INFO | comando e argumentos/opções recebidos |
| Leitura de arquivo | INFO | caminho, formato, e para CSV: delimitador e encoding usados, dizendo se vieram de detecção ou de `--sep`/`--encoding` |
| Arquivo lido | INFO | linhas e colunas |
| Cada operação do `clean` | INFO | operação e o mesmo resumo que vai ao terminal (ex.: `--remove-duplicates: 12 linhas removidas`, `--fix-types: "valor" convertida para float`) |
| Valores não convertidos/reconhecidos (`--fix-types`, `--normalize-dates`) | WARNING | coluna e quantidade |
| Gravação de arquivo | INFO | caminho, formato, linhas e colunas gravadas |
| Erro | ERROR | a mesma mensagem mostrada ao usuário; exceções inesperadas com traceback |
| Fim do comando | INFO | exit code e duração |

**Privacidade** — o log registra metadados (caminhos, nomes de coluna, contagens, opções), **nunca valores das células**. Os valores não reconhecidos que o `clean` lista no terminal (ex.: `"N/D"`) não vão para o log. Isso evita que um CPF, e-mail ou nome de cliente acabe num arquivo de log esquecido na pasta de trabalho (LGPD).

**Falha ao gravar o log** — se `logs/` não puder ser criado ou o arquivo não puder ser gravado (diretório somente leitura, por exemplo), o comando roda normalmente, sem log e sem mensagem de erro: o log é auxiliar e nunca pode fazer um comando que funcionaria falhar.

## Critérios de aceite
**Leitura de CSV**
- [x] CSV separado por `;` é lido com as colunas corretas em `convert`, `info`, `profile` e `clean`, sem nenhuma opção
- [x] Os delimitadores `,`, `;`, tab e `|` são detectados automaticamente
- [x] CSV em `cp1252` com acentos (`São Paulo`, `João`) é lido sem erro e com os caracteres corretos, sem nenhuma opção
- [x] CSV UTF-8 com BOM continua sendo lido sem o BOM no nome da primeira coluna
- [x] `--sep` e `--encoding` sobrescrevem a detecção
- [x] Valor inválido — `--sep` com mais de um caractere, `--encoding` com codec desconhecido — gera erro claro e exit code 2, sem gravar nada
- [x] `--sep`/`--encoding` com arquivo de entrada que não é CSV gera erro claro e exit code 2 (em vez de ser ignorado em silêncio)
- [x] Arquivo que não decodifica no encoding informado em `--encoding` gera erro claro e exit code 1, como as demais falhas de leitura
- [x] A saída no terminal (stdout) não muda por causa da detecção: CSVs que já funcionam hoje (`,` e UTF-8) produzem exatamente o mesmo resultado, e os testes existentes continuam passando sem alteração

**Log**
- [x] Toda execução de qualquer comando grava em `./logs/datatool.log`, criando `logs/` se necessário
- [x] Cada execução registra início (com argumentos) e fim (com exit code e duração), identificadas pelo mesmo id de execução
- [x] Delimitador e encoding usados em cada leitura de CSV aparecem no log, indicando se foram detectados ou informados
- [x] Leituras, gravações, operações do `clean` (com as contagens) e erros aparecem no log, nos níveis da tabela acima
- [x] Nenhum valor de célula aparece no log
- [x] O arquivo é rotacionado ao passar de 5 MB, mantendo até 3 arquivos antigos
- [x] Se o log não puder ser gravado, o comando executa normalmente, com o mesmo resultado e exit code

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestCsvDetection`, `TestExecutionLog`). A saída em texto de `convert`, `info`, `profile` e `clean` foi comparada com a versão anterior à spec (16 cenários, incluindo erros) e é idêntica. Dois testes existentes precisaram de ajuste, porque conferiam que o diretório tinha só `dados.csv` depois do `clean` e agora também existe `logs/`: passaram a esperar `["dados.csv", "logs"]`, o que mantém a intenção (nenhum arquivo de dados gravado). Desempenho: `info` num CSV de 200 mil linhas (10 MB) continua em ~0,15 s; em `cp1252`, ~0,16 s.

## Nota de implementação
- **Leitura:** `read_csv` em [src/structures/functions.py](../src/structures/functions.py) faz a detecção e é a entrada `FileType.CSV` do `read_function`. `read_file`/`save_file` envolvem leitura e gravação de qualquer formato e registram `lendo`/`lido`/`gravado` no log; `csv_options_error` valida `--sep`/`--encoding`.
- **Validação de UTF-8:** feita com um decodificador incremental em blocos de 1 MB, sem carregar o arquivo inteiro na memória. Tentar ler com o polars e cair para `cp1252` em caso de erro foi descartado, porque qualquer outro erro de leitura (ex.: linhas com número de campos diferente) também dispararia o fallback.
- **Delimitador:** o `csv.Sniffer` já desempata a favor de `,` quando mais de um candidato é consistente. A amostra de 64 KB é cortada na última quebra de linha, para não sniffar uma linha pela metade.
- **Log:** [src/execution_log.py](../src/execution_log.py). O decorator `@logged(comando)`, aplicado a todos os comandos em [src/main.py](../src/main.py), abre o arquivo, registra início (só as opções com valor diferente do padrão), fim, exit code e duração, e fecha o arquivo ao terminar. Exceções inesperadas são registradas com traceback e relançadas.
- **Um handler por execução:** o arquivo é aberto no diretório atual a cada comando e fechado no fim. Isso importa nos testes, em que várias execuções rodam no mesmo processo, cada uma num diretório temporário.
- **Silêncio garantido:** o logger `datatool` tem `propagate=False` e um `NullHandler`, para o `logging` nunca imprimir no stderr ("last resort"), e o handler de arquivo ignora falhas de escrita (`handleError`).
- **Erros:** registrados em `fail()` de [src/reporting.py](../src/reporting.py), que o `convert` também passou a usar (antes ele fazia `print` + `return` direto); as mensagens no terminal não mudaram.
- **Operações do `clean`:** registradas em `_record`, a partir dos mesmos relatórios da [019](019-saida-json.md), mas sem os campos `unrecognized_examples`/`failed_examples`. Os valores não reconhecidos continuam aparecendo só no terminal.
- **`utils encode`/`decode`:** registram início e fim com `args: (omitidos)`, porque o argumento é o próprio valor a codificar.
- Números no log saem sem separador de milhar (`1204 linhas`), diferente do exemplo original desta spec.

## Fora de escopo
- **Gravar** CSV com `;` ou em `cp1252`: a saída continua `,` e UTF-8. É uma opção natural para depois (`--output-sep`/`--output-encoding`), para quem precisa devolver o arquivo ao Excel.
- Detectar outros encodings além de UTF-8 e `cp1252` (ex.: via `chardet`): o usuário informa com `--encoding`.
- Separador decimal `,` nos valores numéricos: já é tratado pelo `clean --fix-types --decimal-separator ,` de [010](010-clean-corrigir-tipos.md). Com esta spec, um CSV do Excel BR passa a chegar com as colunas certas e os números como texto (`1.234,56`), prontos para o `--fix-types`.
- Linhas de título/rodapé antes do cabeçalho (comuns em relatórios exportados), aspas ou caractere de escape customizados.
- Configurar o log (local, nível, desligar, `--verbose` para espelhar no terminal): o local e o formato são fixos nesta spec.
- Reconciliar o comando-esqueleto `dataset decode` (ver [backlog](backlog-novas-features.md#reconciliar-comandos-esqueleto)).

## Notas originais do desenho
- **Leitura:** ponto único de mudança — um wrapper de leitura de CSV em [src/structures/functions.py](../src/structures/functions.py) que recebe `sep`/`encoding` opcionais, faz a detecção e registra no log o que foi usado. `pl.read_csv` aceita `separator=` e `encoding=`; para encodings diferentes de UTF-8 o polars decodifica em Python, o que é aceitável para o volume-alvo (~200 mil linhas, ver [002](002-info-diagnostico.md)). O fallback para `cp1252` implica ler o arquivo duas vezes quando ele não é UTF-8; o custo do sniffer é limitado à amostra de 64 KB.
- **Log:** módulo `logging` da stdlib, configurado uma vez por execução (ex.: no callback do `typer.Typer` em [src/main.py](../src/main.py)), com um logger por módulo (`logging.getLogger(__name__)`). Nenhum handler de console: o terminal continua recebendo só os `print` que já existem. O id de execução pode ir num `logging.Filter` ou `LoggerAdapter`, para não precisar ser repassado a cada chamada.
- Os módulos de comando (`convert`, `info`, `profiler`, `clean`) passam a registrar os eventos da tabela nos mesmos pontos onde hoje fazem `print`; as mensagens do terminal continuam como estão.
- `convert --show-stats` relê o arquivo de destino para mostrar `(linhas, colunas)`; essa releitura também é registrada como leitura.
- `logs/` deve entrar no `.gitignore` do repositório, já que os testes e o uso local vão criá-lo.
- Nos testes, o `isolated_filesystem()` de [src/test_cli.py](../src/test_cli.py) já roda cada caso num diretório temporário, então o `logs/` criado ali não vaza para o repositório e pode ser lido para verificar os critérios do log.

## Dependências
[001-convert](001-convert.md) (camada de leitura). Afeta a leitura de [002](002-info-diagnostico.md), [003](003-profile-estatistico.md) e [005](005-clean-detectar-problemas.md)–[011](011-clean-colunas.md), sem mudar a interface delas além das duas opções novas, e passa a registrar no log as operações de todas elas.
