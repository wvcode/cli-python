# datatool Python CLI

Command line tool para manipulação de datasets de maneira facilitada: converter entre formatos, diagnosticar problemas de qualidade, gerar profiling estatístico e limpar dados — tudo pela linha de comando.

O roadmap completo, com o status de cada funcionalidade, está em [specs/README.md](specs/README.md).

## Status

- **Implementado**: `convert`, `info`, `profile`, `clean` (diagnóstico + `--trim`/`--lowercase`/`--uppercase`/`--normalize-case`/`--remove-duplicates`/`--fill-null`/`--drop-null`)
- **Ainda não implementado**: `clean --fix-types`/`--normalize-dates`/`--rename-columns`/`--remove-columns`, `dataset`, `excel`, relatório HTML de profiling, pipelines YAML, IA opcional, licenciamento Pro — veja [specs/README.md](specs/README.md) para o detalhamento spec a spec

## Requisitos

- Python >= 3.10

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Isso registra o comando `datatool` no ambiente virtual (instalação editável: alterações em `src/` refletem sem reinstalar). Para apenas rodar via módulo, sem instalar:

```bash
python -m src.main <comando> ...
```

Para desenvolvimento (testes e lint):

```bash
pip install -r requirements-dev.txt
```

## Comandos disponíveis

### `convert` — converter arquivo entre formatos

```bash
datatool convert vendas.csv vendas.parquet
datatool convert vendas.xlsx vendas.csv
```

- Formatos suportados: **CSV, JSON, JSONL, Excel (xlsx), Parquet, SQLite**, além de Feather e Avro.
- O formato de entrada e saída é inferido pela extensão do arquivo. Use `--from-type`/`--to-type` para sobrescrever quando a extensão não é reconhecida ou é ambígua.
- Se `to_filename` for omitido, o resultado é impresso no stdout em vez de gravado em arquivo.
- `--show-stats` imprime (linhas, colunas) da origem e do destino.

```bash
datatool convert vendas.csv vendas.parquet --show-stats
```

Arquivos inexistentes, formatos não suportados ou diretórios sem permissão de escrita retornam uma mensagem clara e exit code diferente de zero.

### `info` — diagnóstico automático de um arquivo

```bash
datatool info clientes.csv
```

Mostra linhas, colunas e tamanho do arquivo, além de detectar automaticamente:

- valores nulos por coluna
- linhas duplicadas
- colunas com múltiplos formatos de data
- colunas numéricas armazenadas como texto

Para cada problema encontrado, sugere o comando `datatool clean` correspondente. Hoje `--remove-duplicates` e `--drop-null` já existem; `--fix-types` e `--normalize-dates` ainda não (veja [specs/README.md](specs/README.md)). Funciona para CSV, JSON, Excel e Parquet.

```text
Arquivo: clientes.csv
Linhas: 10
Colunas: 6
Tamanho: 711 bytes

Problemas encontrados:
  ⚠ 3 valores nulos em "email"
  ⚠ 1 linhas duplicadas
  ⚠ "data_nascimento" contém 5 formatos de data diferentes
  ⚠ "idade" está armazenada como texto mas parece numérica

Sugestões:
  1. Corrigir tipos → datatool clean clientes.csv --fix-types
  2. Remover duplicidades → datatool clean clientes.csv --remove-duplicates
  3. Normalizar datas → datatool clean clientes.csv --normalize-dates
  4. Tratar valores nulos → datatool clean clientes.csv --drop-null
```

Um arquivo de exemplo que dispara todos esses problemas está em [examples/clientes.csv](examples/clientes.csv).

### `profile` — profiling estatístico de um dataset

```bash
datatool profile vendas.csv
datatool profile vendas.csv --key cpf
```

Para cada coluna, mostra contagem e percentual de nulos, e:

- **colunas numéricas**: min, max, média, mediana, desvio padrão, percentis (25/50/75) e outliers (método IQR)
- **colunas categóricas/texto**: cardinalidade e top 5 valores mais frequentes (com percentual)

Também reporta a quantidade de linhas totalmente duplicadas e, com `--key coluna1,coluna2`, a quantidade de duplicidades considerando apenas essas colunas como chave.

```text
Arquivo: clientes.csv
Linhas: 10
Colunas: 6
Linhas duplicadas: 1
Linhas duplicadas (chave: cpf): 1

Coluna "cpf" (numérica)
  Nulos: 0 (0.00%)
  Min: 11122233344.00  Max: 99900011122.00  Média: 52222222221.70  Mediana: 50011122232.50  Desvio padrão: 30544672345.70
  Percentis: p25=22233344455.00  p50=55566677788.00  p75=77788899900.00
  Outliers (IQR): 0

Coluna "cidade" (categórica)
  Nulos: 0 (0.00%)
  Cardinalidade: 9
  Top 5 valores:
    Rio de Janeiro: 2 (20.00%)
    São Paulo: 1 (10.00%)
    ...
```

### `clean` — detectar e corrigir problemas de qualidade

```bash
datatool clean clientes.csv
```

Sem nenhuma flag, é somente leitura/diagnóstico — **não grava nenhum arquivo**. Detecta, por coluna:

- valores inválidos (ex.: e-mail fora do formato)
- variação de formato (ex.: telefone em formatos diferentes)
- espaços extras nas bordas dos valores
- duplicidade por chave (coluna majoritariamente única com alguns valores repetidos, ex.: CPF)
- inconsistência de capitalização (ex.: "Porto Alegre" / "PORTO ALEGRE" / "porto alegre")

```text
Arquivo: clientes_sujos.csv
Linhas: 20
Colunas: 5

nome
  1 registros com espaços extras

email
  1 valores inválidos

telefone
  3 formatos diferentes

cpf
  1 valores duplicados

cidade
  "PORTO ALEGRE"
  "Porto Alegre"
  "porto alegre"
```

Um arquivo de exemplo que dispara todos esses problemas está em [examples/clientes_sujos.csv](examples/clientes_sujos.csv).

Com pelo menos uma flag de operação, o comando passa a transformar os dados (só em colunas de texto — colunas numéricas, por exemplo, não são alteradas) e mostra o resultado: grava em `--output arquivo` (formato inferido pela extensão, igual ao `convert`) ou, se omitido, imprime o DataFrame no stdout. Nada é gravado por padrão.

```bash
datatool clean clientes.csv --trim --normalize-case --output clientes_limpo.csv
datatool clean clientes.csv --lowercase --output clientes_limpo.csv
datatool clean clientes.csv --uppercase --output clientes_limpo.csv
```

- `--trim` remove espaços extras nas bordas
- `--lowercase` / `--uppercase` convertem a caixa de todo o texto da coluna
- `--normalize-case` unifica variações de capitalização em title case (`"PORTO ALEGRE"`/`"porto alegre"` → `"Porto Alegre"`)
- As flags são combináveis; quando combinadas, são aplicadas na ordem `--trim` → `--lowercase` → `--uppercase` → `--normalize-case`

```text
nome,email,telefone,cpf,cidade
Pessoa 1,Pessoa1@Example.Com,(11) 91234-5678,10000000001,Porto Alegre
Pessoa 2,Pessoa2@Example.Com,11 91234-5678,10000000002,Porto Alegre
Pessoa 3,Invalido-Sem-Arroba,11912345678,10000000003,Porto Alegre
```

`--remove-duplicates` remove linhas duplicadas, mantendo a primeira ocorrência, e reporta quantas foram removidas:

```bash
datatool clean clientes.csv --remove-duplicates
datatool clean clientes.csv --remove-duplicates --key cpf --output clientes_limpo.csv
```

- Por padrão considera a linha inteira (todas as colunas iguais); `--key coluna1,coluna2` deduplica por um subconjunto de colunas
- A quantidade de linhas removidas é sempre impressa, mesmo gravando em arquivo via `--output`
- Combinável com as flags de texto acima — quando combinadas, `--trim`/`--lowercase`/`--uppercase`/`--normalize-case` rodam **antes** da remoção de duplicidades, então linhas que só diferiam por espaço ou capitalização também são deduplicadas

`--fill-null`/`--drop-null` tratam valores nulos e reportam quantas células/linhas foram afetadas:

```bash
datatool clean clientes.csv --fill-null "N/A"
datatool clean clientes.csv --fill-null "idade:0" --output clientes_limpo.csv
datatool clean clientes.csv --drop-null
datatool clean clientes.csv --drop-null --columns email --output clientes_limpo.csv
```

- `--fill-null valor` (sem `:`) preenche nulos só nas colunas de texto — evita converter uma coluna numérica inteira para texto ao preencher com um valor não numérico
- `--fill-null coluna:valor` preenche só essa coluna, convertendo o valor para o tipo da coluna quando ela é numérica; é repetível (`--fill-null "N/A" --fill-null "idade:0"`)
- `--drop-null` remove linhas com nulos em qualquer coluna por padrão, ou só nas colunas de `--columns coluna1,coluna2`

As demais operações de correção (`--fix-types`, `--normalize-dates`, `--rename-columns`/`--remove-columns`) ainda não existem — acompanhe o status em [specs/README.md](specs/README.md).

### Em desenvolvimento

Os comandos abaixo já existem no CLI como esqueleto, mas ainda não implementam a lógica final — acompanhe o status em [specs/README.md](specs/README.md):

- `datatool dataset translate|explain|transform|decode`
- `datatool excel` — inspeção/limpeza de planilhas Excel

## Desenvolvimento

Rodar os testes:

```bash
python -m pytest src/ -v
```

Rodar o lint:

```bash
python -m ruff check src/
```

## Estrutura do projeto

```text
src/            código-fonte do CLI (comandos, leitura/gravação, heurísticas)
specs/          uma spec por user story, com critérios de aceite e status
examples/       arquivos de exemplo para testar os comandos manualmente
```
