# US-001: Converter arquivo entre formatos

## User story
Como analista/engenheiro de dados, eu quero converter um arquivo de um formato para outro, para poder usar o formato mais adequado em cada ferramenta ou pipeline.

## Contexto
Implementado em [src/convert.py](../src/convert.py) e [src/structures/functions.py](../src/structures/functions.py), usando polars para ler/gravar os formatos suportados. Além dos formatos pedidos na ideia (CSV, JSON, JSONL, Excel, Parquet, SQLite), a implementação também mantém Feather e Avro, que já existiam no código antes desta spec.

Leitura/gravação de SQLite usa o módulo `sqlite3` da stdlib (sem dependência extra): o nome da tabela é derivado do nome do arquivo (`vendas.sqlite` → tabela `vendas`); na leitura, se esse nome não existir mas o banco tiver exatamente uma tabela, essa tabela é usada. Excel usa `fastexcel`/`xlsxwriter` via polars (adicionados em `requirements.txt`/`setup.py`).

## Interface proposta
```bash
datatool convert vendas.csv vendas.parquet
datatool convert vendas.xlsx vendas.csv
```
`to_filename` é um argumento posicional opcional (se omitido, o resultado é impresso no stdout). O formato de entrada/saída é inferido pela extensão do arquivo; `--from-type`/`--to-type` continuam disponíveis como fallback para quando a extensão não é reconhecida ou precisa ser sobrescrita.

## Critérios de aceite
- [x] Converte corretamente entre CSV, JSON, JSONL, Excel (xlsx), Parquet e SQLite, sem perda de linhas/colunas
- [x] Formato pode ser inferido pela extensão do arquivo de entrada e saída
- [x] Arquivo inexistente, formato não suportado ou diretório sem permissão de escrita retornam mensagem clara e exit code != 0
- [x] `--show-stats` imprime (linhas, colunas) da origem e do destino

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestConvertCommand`), incluindo round-trip sem perda de dados para cada formato.

## Fora de escopo
- Transformação de dados durante a conversão (isso é responsabilidade das specs de `clean`)

## Dependências
Nenhuma — é a camada base sobre a qual as demais specs se apoiam.

## Nota de compatibilidade
Antes desta spec, a saída do `convert` era informada via `--output` (opção nomeada) e `--from-type`/`--to-type` tinham defaults obrigatórios (`csv`/`json`). Essa interface mudou para bater com a proposta acima: `--output` foi removido em favor do segundo argumento posicional, e os tipos passaram a ser opcionais (inferidos por extensão). Scripts que usavam `--output` precisam ser atualizados.
