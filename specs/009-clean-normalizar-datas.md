# US-009: Normalizar formatos de data

## User story
Como analista de dados, eu quero normalizar colunas de data que estão em formatos diferentes, para um único formato consistente.

## Contexto
Exemplo citado na ideia: `data_nascimento` com 18 formatos diferentes.

Implementado em [src/clean.py](../src/clean.py), como mais uma flag de operação do comando `clean` (junto das de [006](006-clean-operadores-string.md)/[007](007-clean-remover-duplicidades.md)/[008](008-clean-tratar-nulos.md)). É a correção sugerida pelo `info` ([002](002-info-diagnostico.md)) quando detecta colunas com múltiplos formatos de data.

## Interface proposta
```bash
datatool clean clientes.csv --normalize-dates
datatool clean clientes.csv --normalize-dates --date-columns data_nascimento,data_cadastro
```

## Critérios de aceite
- [x] Detecta automaticamente colunas candidatas a data quando `--date-columns` não é informado
- [x] Reconhece ao menos os formatos comuns: `dd/mm/yyyy`, `mm/dd/yyyy`, `yyyy-mm-dd`, `dd-mm-yy`
- [x] Converte todos os valores reconhecidos para ISO 8601 (`yyyy-mm-dd`)
- [x] Valores não reconhecíveis são reportados na saída, não descartados silenciosamente

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestCleanNormalizeDates`).

## Nota de implementação
- Formatos reconhecidos (via `datetime.strptime`, que também aceita dia/mês com 1 dígito): `yyyy-mm-dd`, `yyyy/mm/dd`, `yyyy.mm.dd`, `yyyy-mm-ddThh:mm:ss`/`yyyy-mm-dd hh:mm:ss` (a hora é descartada), `dd/mm/yyyy`, `dd-mm-yyyy`, `dd.mm.yyyy`, `dd/mm/yy`, `dd-mm-yy` e as variantes `mm/dd` dos cinco últimos. `yyyymmdd` **não** é reconhecido de propósito: é indistinguível de códigos numéricos de 8 dígitos e o `strptime` aceita valores de 7 dígitos de forma ambígua.
- Ambiguidade `dd/mm` × `mm/dd`: decidida por coluna. A coluna só é tratada como `mm/dd` quando tem valores que só fazem sentido assim (ex.: `12/31/1990`) e nenhum que só faça sentido como `dd/mm` (ex.: `31/12/1990`); nos demais casos `dd/mm` tem prioridade (padrão BR). Valores inequívocos são sempre lidos corretamente, independentemente da preferência da coluna.
- Anos com 2 dígitos seguem o pivô do Python (`%y`): `00`–`68` → 2000–2068, `69`–`99` → 1969–1999.
- Detecção automática: colunas de texto (`Utf8`) em que ≥ 60% de uma amostra de até 2.000 valores não nulos é reconhecida como data — mesmos limiares usados pelo `info` para o diagnóstico de datas. Sem nenhuma coluna candidata, imprime `Nenhuma coluna de data encontrada` e segue.
- `--date-columns` com coluna inexistente ou que não é texto (ex.: numérica) é erro claro, exit code != 0, nada é gravado.
- A coluna continua sendo texto (não é convertida para o tipo `Date`): assim os valores não reconhecidos podem ser mantidos como estão em vez de virarem nulo. Conversão de tipo fica para [010-clean-corrigir-tipos](010-clean-corrigir-tipos.md).
- Por coluna, reporta no stdout quantas datas foram normalizadas e quantos valores não foram reconhecidos, listando até 10 valores distintos — mesmo quando o resultado é gravado em arquivo via `--output`.
- Ordem de aplicação: `--remove-columns`/`--rename-columns` ([011](011-clean-colunas.md)) → operadores de texto ([006](006-clean-operadores-string.md)) → `--normalize-dates` → `--fix-types` ([010](010-clean-corrigir-tipos.md)) → `--fill-null` → `--drop-null` → `--remove-duplicates`. Assim linhas que só diferiam no formato da data são deduplicadas depois de normalizadas. Espaços nas bordas de uma data são removidos na normalização mesmo sem `--trim`.

## Dependências
[001-convert](001-convert.md), [006-clean-operadores-string](006-clean-operadores-string.md)
