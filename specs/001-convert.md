# US-001: Converter arquivo entre formatos

## User story
Como analista/engenheiro de dados, eu quero converter um arquivo de um formato para outro, para poder usar o formato mais adequado em cada ferramenta ou pipeline.

## Contexto
Já existe uma implementação parcial em [src/convert.py](../src/convert.py) e [src/structures/functions.py](../src/structures/functions.py), usando pandas para ler/gravar CSV, JSON, Parquet, Feather, HDF, HTML, ORC, Pickle, SAS, SPSS e GBQ. Faltam formatos citados na ideia: **Excel (.xlsx)**, **JSONL** e **SQLite**.

## Interface proposta
```bash
datatool convert vendas.csv vendas.parquet
datatool convert vendas.xlsx vendas.csv
```
Formato de entrada/saída inferido pela extensão do arquivo (hoje o comando exige `--from-type`/`--to-type` explícitos — avaliar se mantém como fallback).

## Critérios de aceite
- [ ] Converte corretamente entre CSV, JSON, JSONL, Excel (xlsx), Parquet e SQLite, sem perda de linhas/colunas
- [ ] Formato pode ser inferido pela extensão do arquivo de entrada e saída
- [ ] Arquivo inexistente, formato não suportado ou diretório sem permissão de escrita retornam mensagem clara e exit code != 0
- [ ] `--show-stats` imprime (linhas, colunas) da origem e do destino

## Fora de escopo
- Transformação de dados durante a conversão (isso é responsabilidade das specs de `clean`)

## Dependências
Nenhuma — é a camada base sobre a qual as demais specs se apoiam.
