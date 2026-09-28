# US-018: Validar e normalizar CPF/CNPJ

## User story
Como analista que trabalha com cadastros brasileiros, eu quero que o datatool aponte CPFs e CNPJs inválidos (dígito verificador errado, todos os dígitos iguais, tamanho errado) e padronize o formato deles, para confiar que a coluna de documento identifica de fato cada cliente ou empresa.

## Contexto
Origem: item [F02 do backlog](backlog-novas-features.md#f02--validação-de-cpfcnpj-com-dígito-verificador).

O diagnóstico de [005](005-clean-detectar-problemas.md) já aponta duplicidade na coluna `cpf`, mas não diz se os valores são **válidos**. CPF/CNPJ com dígito verificador errado é um dos problemas de qualidade mais comuns em cadastros brasileiros, e ferramentas genéricas (pandas-profiling, great_expectations) não validam isso nativamente. É o diferencial "feito para o Brasil" mais barato do backlog.

Três problemas concretos do código atual entram nesta spec:

- **CPF lido como número.** O `pl.read_csv` infere `cpf` como `Int64` (é o que acontece em [examples/clientes.csv](../examples/clientes.csv) e [examples/clientes_sujos.csv](../examples/clientes_sujos.csv)). CPFs que começam com `0` perdem os zeros à esquerda e passam a ter 10 dígitos ou menos.
- **`--fix-types` pode estragar a coluna.** O `clean --fix-types` de [010](010-clean-corrigir-tipos.md) converte para `Int64` uma coluna de CPF sem máscara armazenada como texto, desde que nenhum valor da amostra comece com `0`. O `info` também sugere `--fix-types` para ela.
- **CNPJ alfanumérico.** Pela IN RFB nº 2.229/2024, desde julho de 2026 a Receita emite CNPJs com letras nas 12 primeiras posições (ex.: `12.ABC.345/01DE-35`). Um validador só numérico passaria a acusar CNPJs novos e legítimos como inválidos.

## Interface proposta
```bash
datatool clean clientes.csv                                   # diagnóstico passa a incluir CPF/CNPJ
datatool info clientes.csv                                    # idem, no resumo de problemas
datatool clean clientes.csv --normalize-documents digits      # 123.456.789-09 → 12345678909
datatool clean clientes.csv --normalize-documents masked      # 12345678909 → 123.456.789-09
datatool clean clientes.csv --normalize-documents masked --document-columns cpf,cnpj_empresa
```

Diagnóstico do `clean`, no mesmo formato por coluna de [005](005-clean-detectar-problemas.md):

```text
cpf
  23 CPFs com dígito verificador inválido
  4 CPFs com todos os dígitos iguais
  2 valores fora do formato de CPF/CNPJ
  2 formatos diferentes (com e sem máscara)
  coluna lida como número: 12 CPFs tinham zeros à esquerda perdidos
```

No `info`, cada problema vira uma linha `⚠` (ex.: `⚠ 23 CPFs inválidos em "cpf"`), e a sugestão `--normalize-documents` aparece quando há formatos misturados ou a coluna foi lida como número.

## Comportamento — validação
**Formatos aceitos** (com ou sem máscara, espaços nas bordas ignorados):

| Documento | Com máscara | Sem máscara |
|-----------|-------------|-------------|
| CPF | `123.456.789-09` | `12345678909` |
| CNPJ numérico | `12.345.678/0001-95` | `12345678000195` |
| CNPJ alfanumérico | `12.ABC.345/01DE-35` | `12ABC34501DE35` |

Máscara parcial (ex.: `123456789-09`) também é aceita. Letras do CNPJ alfanumérico são aceitas em maiúsculas ou minúsculas.

**Regras de validade**
- **CPF:** 11 dígitos; os dois dígitos verificadores seguem o cálculo módulo 11 da Receita (pesos 10→2 e 11→2).
- **CNPJ:** 14 posições. As 12 primeiras são dígitos ou letras (`A`–`Z`); as 2 últimas (dígitos verificadores) são sempre numéricas. Cálculo módulo 11 com pesos `5,4,3,2,9,8,7,6,5,4,3,2` e `6,5,4,3,2,9,8,7,6,5,4,3,2`, em que o valor de cada caractere é o código ASCII menos 48 (`0`–`9` → 0–9, `A` → 17, ..., `Z` → 42). Para CNPJs só numéricos o resultado é idêntico ao cálculo tradicional.
- **Todos os dígitos iguais** (`111.111.111-11`, `00.000.000/0000-00`): inválidos, contados à parte. Alguns passam no cálculo do dígito verificador, mas a Receita não os emite.
- **Coluna com CPF e CNPJ misturados** (ex.: `cpf_cnpj`, `documento`): cada valor é validado pelo seu tamanho, e as mensagens separam CPFs de CNPJs.

**Coluna lida como número** (`Int64`, como nos exemplos): o valor é convertido para texto e completado com zeros à esquerda até 11 posições (CPF) quando tem até 11 dígitos, ou até 14 (CNPJ) quando tem 12 a 14. Limitação: um CNPJ que comece com `000` (ex.: `00.000.000/0001-91`) cabe em 11 dígitos e é tratado como CPF. Na prática isso só acontece com colunas numéricas, e ler a coluna como texto resolve.

## Comportamento — detecção da coluna
Uma coluna é tratada como coluna de documento quando as duas condições valem:

1. **Formato:** pelo menos 80% de uma amostra de até 2.000 valores não nulos tem formato de CPF ou CNPJ (tabela acima). Para colunas numéricas: inteiros com até 14 dígitos.
2. **Evidência de que é documento**, e não telefone ou ID sequencial, que também têm 10 a 14 dígitos. Vale pelo menos uma destas:
   - a maioria dos valores com formato tem dígito verificador válido (um número aleatório passa em cerca de 1% dos casos, então telefones e IDs não passam);
   - os valores usam máscara de CPF/CNPJ (pontos, `/` e `-` nas posições do documento);
   - o nome da coluna contém `cpf`, `cnpj` ou `documento`, sem diferenciar maiúsculas.

O critério pelo nome é uma exceção deliberada à regra de [005](005-clean-detectar-problemas.md) de detectar só por conteúdo. Sem ele, uma coluna chamada `cpf` com a maioria dos valores inválidos não seria diagnosticada, e esse é justamente o caso mais importante de reportar. É o que acontece com os dois arquivos de exemplo: nenhum dos 10 CPFs de `clientes.csv` e só 1 dos 20 de `clientes_sujos.csv` são válidos.

As contagens do diagnóstico são **exatas**, sobre todos os valores distintos da coluna. Só a detecção usa amostra, como nos demais detectores.

## Comportamento — `--normalize-documents`
- `--normalize-documents digits` remove a máscara (`123.456.789-09` → `12345678909`); `--normalize-documents masked` aplica a máscara (`12345678909` → `123.456.789-09`, `12ABC34501DE35` → `12.ABC.345/01DE-35`). Qualquer outro valor é erro claro, exit code 2.
- Letras de CNPJ alfanumérico são convertidas para maiúsculas.
- Sem `--document-columns`, aplica às colunas detectadas como acima. Com `--document-columns a,b`, aplica só a essas; coluna inexistente é erro claro, exit code 2, nada gravado.
- A coluna resultante é sempre **texto**. Colunas lidas como número voltam a ter os zeros à esquerda.
- **Normalizar não é validar:** valores com dígito verificador inválido ou com todos os dígitos iguais também são formatados, porque têm o formato certo e o conteúdo é mantido. Valores fora do formato (tamanho errado, caracteres inválidos) são mantidos como estão.
- Reporta por coluna, no mesmo estilo de [009](009-clean-normalizar-datas.md)/[010](010-clean-corrigir-tipos.md):

```text
"cpf": 1.180 documentos normalizados
"cpf": 23 com dígito verificador inválido (formatados, mas continuam inválidos)
"cpf": 2 valores fora do formato de CPF/CNPJ, mantidos sem alteração
```

- **Ordem de aplicação:** `--remove-columns`/`--rename-columns` → operadores de texto → `--normalize-documents` → `--normalize-dates` → `--fix-types` → `--fill-null` → `--drop-null` → `--remove-duplicates`. Assim o `--trim` limpa espaços antes, e a deduplicação (por exemplo `--key cpf`) já compara documentos no mesmo formato.

## Critérios de aceite
**Diagnóstico (`clean` sem flags e `info`)**
- [x] Detecta colunas de CPF, de CNPJ e mistas por conteúdo, com ou sem máscara, e também pelo nome da coluna conforme as regras de detecção
- [x] Não confunde com documento colunas de telefone (ex.: `11912345678`) ou de ID numérico sequencial sem `cpf`/`cnpj`/`documento` no nome
- [x] Reporta, por coluna: documentos com dígito verificador inválido, documentos com todos os dígitos iguais, valores fora do formato, mistura de formatos (com e sem máscara) e, para colunas numéricas, quantos tinham zeros à esquerda perdidos
- [x] Valida CNPJ alfanumérico conforme a IN RFB nº 2.229/2024; um CNPJ alfanumérico válido não é reportado como inválido
- [x] Os dois arquivos de [examples/](../examples/) passam a mostrar os CPFs inválidos da coluna `cpf`
- [x] O `info` mostra os problemas de documento e sugere `--normalize-documents` quando há formatos misturados ou coluna lida como número
- [x] Contagens exatas; tempo aceitável para ~200 mil linhas, como em [002](002-info-diagnostico.md)/[005](005-clean-detectar-problemas.md)

**Operador `--normalize-documents`**
- [x] `digits` e `masked` produzem o formato pedido para CPF, CNPJ numérico e CNPJ alfanumérico
- [x] Colunas numéricas voltam a ter os zeros à esquerda e passam a ser texto
- [x] `--document-columns` restringe as colunas; coluna inexistente ou valor inválido de `--normalize-documents` gera erro claro, exit code 2, sem gravar nada
- [x] Valores fora do formato são mantidos como estão e reportados; documentos inválidos são formatados e reportados

**Interação com o que existe**
- [x] `clean --fix-types` ignora colunas detectadas como documento, e o `info` deixa de sugerir `--fix-types` para elas
- [x] O log de [017](017-csv-delimitador-encoding.md) registra só contagens; nenhum CPF/CNPJ aparece no log

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestCleanNormalizeDocuments`, 24 testes). A saída em texto dos comandos e caminhos que não mudam (`profile`, `convert`, `clean` com outros operadores, erros de arquivo) foi comparada com a versão anterior à spec e é idêntica; as únicas diferenças são os novos diagnósticos de documento em `info`/`clean` sem flags. Testado manualmente com 200 mil CPFs distintos: ~0,9s para o diagnóstico (`info`), ~1,7s para `--normalize-documents` com gravação — mais lento que os detectores de [002](002-info-diagnostico.md)/[003](003-profile-estatistico.md) (que não fazem conta de dígito verificador por valor), mas dentro do aceitável para uma CLI.

## Fora de escopo
- Remover ou anular documentos inválidos (ex.: `--drop-invalid-documents`). Pode virar um operador próprio depois.
- Listar no terminal os valores inválidos. Diferente de [009](009-clean-normalizar-datas.md)/[010](010-clean-corrigir-tipos.md), aqui os valores são dados pessoais, então o diagnóstico mostra só contagens. Exportar as linhas problemáticas é um candidato natural para a F03 (`--format json`).
- Consultar a situação cadastral na Receita (CPF/CNPJ existente, ativo, suspenso): a validação é só matemática.
- Outros documentos brasileiros (PIS, título de eleitor, CNH, RG) e CEP.
- Mascaramento para LGPD (`123.***.***-09`): é a F06.
- Mudar a leitura para trazer a coluna `cpf` como texto desde o início. A spec [017](017-csv-delimitador-encoding.md) mexe na leitura de CSV e pode ganhar isso depois; aqui os zeros são recuperados completando com `0`.
- Trocar os CPFs fictícios dos arquivos de exemplo por válidos.

## Formato JSON (spec [019](019-saida-json.md))
As categorias de `Finding` novas seguem a tabela de `count` de [019](019-saida-json.md): `document_invalid`, `document_all_same`, `document_out_of_format`, `document_format_variance`, `document_numeric_column` (essa última só em colunas numéricas). Todas têm `column` preenchida.

A operação `normalize_documents` (modo com flags do `clean`) aparece em `operations` assim:

```json
{"operation": "normalize_documents", "columns": [
  {"column": "cpf", "normalized": 1180, "still_invalid_count": 23,
   "unrecognized_count": 2, "unrecognized_distinct": 2,
   "unrecognized_examples": ["a-combinar", "sem-documento"]}
]}
```

`still_invalid_count` é a soma de dígito-verificador-inválido e todos-iguais (o relatório de operação não separa os dois como o diagnóstico separa); `unrecognized_*` segue o nome já usado por `normalize_dates` (valores fora do formato, mantidos como estão).

## Nota de implementação
- Validação e detecção em [src/quality.py](../src/quality.py): `detect_document_columns(df)` decide, por coluna, se é documento (amostra + evidência, como descrito acima); `detect_documents(df)` gera os `Finding`s a partir de `_document_summary` (contagem exata via `value_counts()` sobre a coluna inteira, não a amostra). Chamados por `analyze_clean` (diagnóstico do `clean`) e por `analyze` (`info`); `analyze` calcula `detect_document_columns` separadamente do `detect_documents` porque uma coluna pode ser detectada como documento sem gerar nenhum `Finding` (ex.: todos os CPFs válidos e no mesmo formato) — nesse caso ela ainda precisa entrar no `skip_columns` de `detect_numeric_as_text`.
- CPF/CNPJ reconhecidos por três padrões cada (sem máscara, com máscara completa, com máscara parcial só do dígito verificador — ex. `123456789-09`), em `_document_shape`; para colunas numéricas, `_document_shape_numeric` não usa regex — qualquer inteiro com até 14 dígitos "parece" documento (a validação é quem filtra depois), e o valor é completado com `zfill` para 11 (CPF) ou 14 (CNPJ) posições.
- Dígito verificador: `_check_digit(chars, weights)` genérico (usado por CPF e CNPJ), com valor de caractere `ord(c) - 48` (dígitos `0`-`9` → 0-9, letras `A`-`Z` → 17-42, conforme a tabela da Receita). Verificado contra CPFs/CNPJs de teste publicamente conhecidos (`52998224725`, `11222333000181`, `11444777000161`) antes de implementar, além do exemplo alfanumérico desta spec (`12ABC34501DE35`).
- "Todos os dígitos iguais" é checado **antes** do dígito verificador em `_validate_document`, porque alguns desses valores (ex.: `11111111111`) passam matematicamente na conta.
- **Evidência de que é documento** (`detect_document_columns`): testada por simulação antes de fixar o limiar — uma coluna de 5.000 números de 11 dígitos aleatórios passa no dígito verificador de CPF em ~1,4% dos casos (perto do ~1% citado na spec), bem abaixo do limiar de maioria (>50%) usado aqui; uma coluna de IDs sequenciais 1-1000 fica em ~0,9%. Confirma que o critério é robusto sem precisar de regra adicional para colunas pequenas.
- A lista de colunas de documento é reaproveitada por `_detect_numeric_text_columns` em [src/clean.py](../src/clean.py) (ignoradas por `--fix-types`) e pela própria `_apply_normalize_documents`.
- `_apply_normalize_documents`: para coluna numérica, faz `pl.col(column).cast(pl.Utf8)` primeiro e opera inteiramente em texto dali em diante — assim a mesma função de shape/validação serve para colunas Utf8 e para as que eram Int64. Contagens (`is_in`) são calculadas **antes** do `replace`, no mesmo padrão de `_apply_normalize_dates`/`_apply_fix_types`.
- Validar por valor distinto (`unique()`/`value_counts()`) e mapear de volta, como os demais operadores. Testado com 200 mil CPFs distintos (arquivo sintético, sem repetição): ~0,9s para o diagnóstico, ~1,7s para `--normalize-documents` gravando o resultado.
- Sugestão `--normalize-documents` no `info`: como ela precisa dispar por **duas** categorias (`document_format_variance` OU `document_numeric_column`), mas o campo `category` da sugestão no JSON deve continuar sendo uma string só (não uma lista, para não quebrar o formato de [019](019-saida-json.md)), `_SUGGESTIONS` ganhou uma categoria própria `"documents"` e um dicionário `_SUGGESTION_TRIGGERS` que mapeia essa categoria às duas categorias de `Finding` que a disparam. As demais sugestões (`types`, `duplicates`, `dates`, `nulls`) continuam mapeando 1:1, sem precisar do dicionário.
- Os detectores atuais de [005](005-clean-detectar-problemas.md) continuam valendo. A duplicidade por chave pode acabar comparando `123.456.789-09` com `12345678909` como valores diferentes; o `--normalize-documents` antes do `--remove-duplicates --key cpf` resolve, e a ordem de aplicação acima garante isso.
- Referência do CNPJ alfanumérico: Instrução Normativa RFB nº 2.229, de 15 de outubro de 2024, e a documentação técnica de cálculo do dígito verificador publicada pela Receita.

## Dependências
[005-clean-detectar-problemas](005-clean-detectar-problemas.md) (padrão do diagnóstico), [010-clean-corrigir-tipos](010-clean-corrigir-tipos.md) (interação com `--fix-types`). Relacionada a [017](017-csv-delimitador-encoding.md) (log, sem valores de células) e à F06 do backlog (mascaramento LGPD).
