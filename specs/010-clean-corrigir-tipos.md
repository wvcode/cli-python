# US-010: Corrigir tipos de colunas

## User story
Como analista de dados, eu quero que colunas numéricas armazenadas como texto sejam convertidas para o tipo correto, incluindo valores monetários em formato brasileiro, para poder fazer cálculos sobre elas.

## Contexto
Exemplo citado na ideia: coluna "Valor" contendo `R$` e separadores brasileiros (`1.234,56`).

Implementado em [src/clean.py](../src/clean.py), como mais uma flag de operação do comando `clean` (junto das de [006](006-clean-operadores-string.md)–[009](009-clean-normalizar-datas.md)). É a correção sugerida pelo `info` ([002](002-info-diagnostico.md)) quando detecta colunas numéricas armazenadas como texto.

## Interface proposta
```bash
datatool clean relatorio.xlsx --fix-types
datatool clean relatorio.xlsx --fix-types --decimal-separator ,
```

## Critérios de aceite
- [x] Detecta colunas que são numéricas mas estão armazenadas como string
- [x] Remove símbolo de moeda (`R$`) e normaliza separador de milhar/decimal brasileiro (`1.234,56` → `1234.56`)
- [x] Converte a coluna para tipo numérico apropriado (`int`/`float`)
- [x] Reporta quais colunas foram convertidas e quantos valores falharam na conversão (sem interromper o processamento das demais)

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestCleanFixTypes`).

## Nota de implementação
- Detecção: colunas de texto (`Utf8`) em que ≥ 90% de uma amostra de até 2.000 valores não nulos é numérica — mesmos limiares usados pelo `info` para o diagnóstico "armazenada como texto mas parece numérica". Sem nenhuma coluna candidata, imprime `Nenhuma coluna numérica armazenada como texto encontrada` e segue.
- Antes da conversão, remove `R$` e qualquer espaço (inclusive o não separável, comum em exportações do Excel). Sinal negativo antes ou depois do `R$` é aceito (`-R$ 5,50`, `R$ -5,50`).
- Separadores: `--decimal-separator` (`,` ou `.`) define o separador decimal para todas as colunas convertidas; o separador de milhar é sempre o outro caractere e é opcional (`,` aceita `1.234,56`, `2.000`, `10,5`; `.` aceita `1,234.56`, `2,000`, `10.5`). Outro valor é erro claro, exit code != 0.
- Sem `--decimal-separator`, o separador é decidido por coluna: se algum valor tem vírgula ou `R$`, usa `,`; senão, `.`. Nesse modo automático, uma coluna só com valores como `1.500` (sem vírgula nem `R$`) vira `1.5` — é o caso em que o usuário deve informar `--decimal-separator ,`.
- Tipo resultante: `Int64` quando nenhum valor convertido tem parte decimal, senão `Float64`.
- Colunas com algum valor com zero à esquerda (`01001000`) são ignoradas na detecção: são códigos (CEP, CPF, conta) e a conversão perderia os zeros. Observação: em CSV, o `pl.read_csv` já infere colunas assim como inteiro na leitura (antes do `clean`), então esse cuidado vale para colunas que chegam como texto (JSON, Excel, CSV com outros valores não numéricos).
- Valores que falham na conversão viram nulo; por coluna, reporta no stdout o tipo resultante, quantos valores falharam e até 10 deles, sem interromper a conversão das demais colunas — mesmo quando o resultado é gravado via `--output`.
- Ordem de aplicação: `--remove-columns`/`--rename-columns` ([011](011-clean-colunas.md)) → operadores de texto ([006](006-clean-operadores-string.md)) → `--normalize-dates` ([009](009-clean-normalizar-datas.md)) → `--fix-types` → `--fill-null` → `--drop-null` → `--remove-duplicates`. Vir antes de `--fill-null`/`--drop-null` permite tratar os nulos gerados pelas falhas (ex.: `--fix-types --fill-null idade:0`).

## Dependências
[001-convert](001-convert.md), [006-clean-operadores-string](006-clean-operadores-string.md)
