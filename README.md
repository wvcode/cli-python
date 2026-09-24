# datatool Python CLI

Command line tool para manipulação de datasets de maneira facilitada: converter entre formatos, diagnosticar problemas de qualidade e (em breve) limpar dados — tudo pela linha de comando.

O roadmap completo, com o status de cada funcionalidade, está em [specs/README.md](specs/README.md).

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

Para cada problema encontrado, sugere o comando `datatool clean` correspondente (a implementar — veja [specs/README.md](specs/README.md)). Funciona para CSV, JSON, Excel e Parquet.

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

### Em desenvolvimento

Os comandos abaixo já existem no CLI como esqueleto, mas ainda não implementam a lógica final — acompanhe o status em [specs/README.md](specs/README.md):

- `datatool clean` — limpeza de dados (duplicidades, nulos, tipos, datas, colunas)
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
