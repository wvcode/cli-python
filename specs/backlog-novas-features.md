# Backlog — novas features para o datatool

Propostas que **não estão cobertas** pelas specs 001–016. Cada item vem de uma de três fontes:

- **Ideia**: citado em [ideia.md](ideia.md) (planos Pro/Team) mas sem spec correspondente
- **Código**: lacuna encontrada ao implementar as specs 001–008
- **Mercado BR**: oportunidade específica para o público brasileiro, que é o posicionamento natural do produto (mensagens em pt-BR, formato monetário BR já previsto em 010)

Os IDs usam o prefixo `F` para não colidir com a numeração das specs. Esforço: **P** (≤1 dia), **M** (2–4 dias), **G** (≥1 semana). A coluna **Spec** indica os itens que já viraram spec (ainda não implementada, salvo indicação no [README das specs](README.md)).

## Resumo priorizado

| ID | Feature | Fonte | Plano | Esforço | Prioridade | Spec |
|----|---------|-------|-------|---------|------------|------|
| F01 | Detecção de delimitador e encoding em CSV | Código, Mercado BR | Community | P | Alta | [017](017-csv-delimitador-encoding.md) |
| F02 | Validação de CPF/CNPJ com dígito verificador | Mercado BR | Community | P | Alta | [018](018-cpf-cnpj-validacao.md) |
| F03 | Saída estruturada (`--format json`) em `info`/`profile`/`clean` | Código | Community | P | Alta | [019](019-saida-json.md) |
| F04 | Seleção de aba em Excel (`--sheet`) | Código | Community | P | Alta | — |
| F05 | Quality gate para CI (`datatool check`) | Ideia | Pro | M | Alta | — |
| F06 | Mascaramento de dados pessoais (LGPD) | Mercado BR | Pro | M | Alta | — |
| F07 | `--dry-run` no `clean` | Código | Community | P | Média | — |
| F08 | Comparação entre dois datasets (`datatool diff`) | Novo | Community | M | Média | — |
| F09 | Validação de schema declarado | Ideia | Pro | M | Média | — |
| F10 | Processamento em lote (glob) | Ideia | Pro | M | Média | — |
| F11 | Amostragem e visualização (`head`/`sample`) | Novo | Community | P | Média | — |
| F12 | Arquivos grandes via modo lazy/streaming | Ideia | Pro | G | Média | — |
| F13 | Histórico de operações e reprodutibilidade | Ideia | Pro | M | Baixa | — |
| F14 | Conectores (PostgreSQL, S3) | Ideia | Team | G | Baixa | — |
| F15 | Unir arquivos (`concat`/`join`) | Novo | Community | M | Baixa | — |

Há também uma pendência de **higiene** (não é feature, mas afeta o produto): ver [Reconciliar comandos-esqueleto](#reconciliar-comandos-esqueleto).

---

## Alta prioridade

### F01 — Detecção de delimitador e encoding em CSV

> Detalhada na spec [017-csv-delimitador-encoding](017-csv-delimitador-encoding.md).

**Problema.** Hoje `convert`, `info`, `profile` e `clean` leem CSV com `pl.read_csv` usando os padrões do polars: separador `,` e UTF-8. O Excel em português exporta CSV com `;` e, frequentemente, em `cp1252`/`latin-1`. Nesses casos o arquivo é lido como **uma única coluna** ou falha por encoding, e o usuário recebe um diagnóstico errado sem entender por quê. Para o público-alvo, esse é provavelmente o primeiro atrito.

**Proposta.**

```bash
datatool info vendas.csv                    # detecta ; e cp1252 automaticamente
datatool info vendas.csv --sep ";" --encoding latin-1   # override explícito
```

- Detectar o delimitador pela primeira linha (`csv.Sniffer` da stdlib cobre `,`, `;`, `\t`, `|`)
- Tentar UTF-8; se falhar, cair para `cp1252`
- Informar o que foi detectado quando diferir do padrão (`Delimitador detectado: ";"`)

**Onde mexe.** Um wrapper de leitura de CSV em [src/structures/functions.py](../src/structures/functions.py) — todos os comandos se beneficiam sem mudar individualmente.

**Relação com o que existe.** O comando-esqueleto `dataset decode` (com `EncodingType`) parece ter sido pensado para isso; ver [reconciliação](#reconciliar-comandos-esqueleto).

---

### F02 — Validação de CPF/CNPJ com dígito verificador

> Detalhada na spec [018-cpf-cnpj-validacao](018-cpf-cnpj-validacao.md).

**Problema.** A spec 005 detecta duplicidade de CPF, mas não valida se o CPF é **válido**. CPF/CNPJ com dígito verificador errado é um dos problemas de qualidade mais comuns em cadastros brasileiros, e nenhuma ferramenta genérica (pandas-profiling, great_expectations) faz isso nativamente.

**Proposta.** Um novo detector no diagnóstico do `clean` (e no `info`), no mesmo padrão dos detectores de e-mail/telefone de [005](005-clean-detectar-problemas.md):

```text
cpf
  23 CPFs com dígito verificador inválido
  4 CPFs com todos os dígitos iguais (ex.: 111.111.111-11)
```

E um operador de normalização:

```bash
datatool clean clientes.csv --normalize-cpf     # 123.456.789-09 → 12345678909 (ou o inverso)
```

**Detalhes.** Aceitar CPF com e sem máscara; identificar a coluna por conteúdo (≥X% dos valores com 11 dígitos) como os demais detectores, sem depender do nome. Tratar CPF lido como inteiro (o polars já infere `cpf` como `i64` em [examples/clientes.csv](../examples/clientes.csv), o que **perde zeros à esquerda** — CPFs começando com 0 viram 10 dígitos). Esse último ponto vale até como item isolado: sugerir no `info` quando uma coluna de identificador foi lida como número.

---

### F03 — Saída estruturada (`--format json`)

> Detalhada na spec [019-saida-json](019-saida-json.md).

**Problema.** `info`, `profile` e `clean` imprimem texto para humanos. Para usar o datatool em scripts, notebooks ou CI, é preciso parsear esse texto, o que é frágil. Além disso, as specs de IA ([014](014-ai-explain.md), [015](015-ai-ask.md)) exigem "a saída estruturada do profiling" como entrada — isso ainda não existe como formato público.

**Proposta.**

```bash
datatool profile vendas.csv --format json > perfil.json
datatool info vendas.csv --format json | jq '.problems[] | select(.category == "nulls")'
```

**Onde mexe.** O trabalho pesado já está feito: [src/profiling.py](../src/profiling.py) retorna um dicionário e [src/quality.py](../src/quality.py) retorna `Finding`s. É basicamente serializar o que já existe, em vez de passar pelo `print`. Também desbloqueia o relatório HTML ([004](004-profile-relatorio-html.md)) e as specs de IA.

---

### F04 — Seleção de aba em Excel (`--sheet`)

**Problema.** `pl.read_excel` lê só a **primeira aba** por padrão, e hoje não há como escolher outra. Planilhas reais têm várias abas (dados, resumo, gráficos), e o usuário não é avisado de que as demais foram ignoradas.

**Proposta.**

```bash
datatool info relatorio.xlsx                  # avisa: "Arquivo tem 3 abas; lendo 'Vendas'. Use --sheet."
datatool convert relatorio.xlsx vendas.csv --sheet "Vendas 2025"
datatool info relatorio.xlsx --all-sheets     # diagnóstico de cada aba
```

**Relação com o que existe.** A spec [013](013-excel-inspect-auto.md) prevê "múltiplas abas" para o `inspect` Pro; este item é a versão básica (Community) que o `013` reaproveitaria. O comando-esqueleto `excel --workbooks` também aponta nessa direção.

---

### F05 — Quality gate para CI (`datatool check`)

**Problema.** A ideia cita "data quality checks" e "regras de qualidade" (planos Pro/Team), mas nenhuma spec cobre o caso de **falhar um pipeline** quando os dados não atendem a critérios. Hoje `info`/`clean` sempre retornam exit code 0 mesmo encontrando problemas.

**Proposta.** Um arquivo de regras e um comando que retorna exit code != 0 se alguma regra falhar:

```yaml
# regras.yaml
rules:
  - column: email
    max_null_percent: 5
  - column: cpf
    unique: true
    valid_cpf: true
  - no_duplicate_rows: true
  - min_rows: 1000
```

```bash
datatool check vendas.csv --rules regras.yaml
# ✗ email: 8,2% nulos (limite: 5%)
# ✓ cpf: único
# exit code 1
```

**Por que Pro.** É exatamente o tipo de feature que empresas pagam para rodar em CI (é o nicho do Great Expectations, que é pesado para configurar). Reaproveita os detectores de [quality.py](../src/quality.py) e o parsing YAML que a spec [012](012-pipeline-automacao.md) já vai introduzir.

---

### F06 — Mascaramento de dados pessoais (LGPD)

**Problema.** Analistas frequentemente precisam compartilhar um dataset (com fornecedor, em ambiente de teste, em um ticket) sem expor dados pessoais. Fazer isso manualmente em Excel é lento e propenso a vazamento. Nenhuma spec cobre isso, e é um argumento de venda forte no Brasil por causa da LGPD.

**Proposta.**

```bash
datatool info clientes.csv                      # novo aviso: "⚠ Dados pessoais detectados: cpf, email, telefone"
datatool clean clientes.csv --mask-pii --output clientes_anon.csv
datatool clean clientes.csv --mask-columns cpf,email --output clientes_anon.csv
```

- Detecção de colunas com dados pessoais reaproveitando os detectores de e-mail/telefone (005) e CPF (F02)
- Estratégias: mascarar parcialmente (`***.456.789-**`), hash determinístico (mantém joins possíveis entre arquivos) ou remover
- Hash com salt configurável, para não ser revertível por dicionário de CPFs

---

## Média prioridade

### F07 — `--dry-run` no `clean`

**Problema.** Hoje, para saber o efeito de `--remove-duplicates --fill-null ...` sem gerar arquivo, o usuário roda sem `--output` e recebe o DataFrame inteiro no stdout, que em arquivos grandes é ruído. Não há um jeito de ver só "o que mudaria".

**Proposta.**

```bash
datatool clean clientes.csv --trim --remove-duplicates --dry-run
# --trim: 87 valores alterados em 2 colunas (nome, cidade)
# --remove-duplicates: 23 linhas seriam removidas
# Resultado: 152.438 → 152.415 linhas. Nada foi gravado.
```

**Onde mexe.** [src/clean.py](../src/clean.py): cada operador já reporta contagem (007/008); falta os operadores de texto (006) também reportarem e um modo que pule `_write_or_print`.

---

### F08 — Comparação entre dois datasets (`datatool diff`)

**Problema.** Um caso muito comum: "o arquivo deste mês bate com o do mês passado?" ou "a limpeza alterou o que eu esperava?". Hoje isso exige carregar os dois arquivos em pandas.

**Proposta.**

```bash
datatool diff vendas_jan.csv vendas_fev.csv
# Schema: +1 coluna (desconto), -0 colunas, 1 tipo alterado (valor: str → f64)
# Linhas: 10.234 → 11.012 (+778)

datatool diff clientes.csv clientes_limpo.csv --key cpf
# 23 linhas removidas, 87 linhas alteradas, 0 adicionadas
# Colunas mais alteradas: nome (64), cidade (23)
```

Útil também para validar o próprio `clean`: rodar `diff` entre entrada e saída mostra exatamente o que a limpeza fez.

---

### F09 — Validação de schema declarado

**Problema.** Citado na ideia ("validação de schema") e na estrutura sugerida (`cli/validate.py`), mas sem spec. Diferente do F05 (regras de qualidade sobre valores), aqui a pergunta é estrutural: o arquivo tem as colunas e tipos que o pipeline espera?

**Proposta.**

```bash
datatool schema vendas.csv > schema.yaml        # infere e exporta o schema atual
datatool validate novo_arquivo.csv --schema schema.yaml
# ✗ coluna "valor": esperado f64, encontrado str
# ✗ coluna "desconto" ausente
```

Pode ser implementado como um tipo de regra do F05 (`schema: schema.yaml`) em vez de um comando separado — vale decidir junto.

---

### F10 — Processamento em lote (glob)

**Problema.** Todos os comandos recebem um arquivo. Converter ou limpar 30 arquivos mensais exige um loop em shell.

**Proposta.**

```bash
datatool convert "dados/*.csv" --to parquet --output-dir dados_parquet/
datatool clean "exports/*.xlsx" --trim --remove-duplicates --output-dir limpos/
datatool info "dados/*.csv" --summary          # tabela resumida: arquivo, linhas, nº de problemas
```

A ideia cita "execução paralela" como Pro; faz sentido o lote sequencial ser Community e o paralelo (`--jobs 4`) ser Pro.

---

### F11 — Amostragem e visualização (`head`/`sample`)

**Problema.** Para "dar uma olhada" em um Parquet ou SQLite, hoje o caminho é `datatool convert arquivo.parquet` sem saída, que imprime o DataFrame truncado do polars — funciona, mas não é óbvio e não permite escolher linhas/colunas.

**Proposta.**

```bash
datatool head vendas.parquet -n 20
datatool sample vendas.csv -n 1000 --seed 42 --output amostra.csv
datatool head vendas.csv --columns nome,valor
```

`sample` também ajuda a compartilhar um recorte pequeno de um arquivo grande (combinado com F06 para anonimizar).

---

### F12 — Arquivos grandes via modo lazy/streaming

**Problema.** Todos os comandos carregam o arquivo inteiro em memória com `read_*`. Os critérios de aceite validaram ~200 mil linhas (~0,3s), mas arquivos de dezenas de GB vão estourar memória. A ideia cita "processamento de arquivos grandes" como Pro.

**Proposta.** Usar `pl.scan_csv`/`pl.scan_parquet` (LazyFrame) e o engine de streaming do polars quando o arquivo passar de um limiar de tamanho, ou via flag `--streaming`. `convert` e `profile` são os candidatos naturais; `clean` exige revisar operadores que hoje assumem DataFrame (ex.: amostragem em `quality.py`).

**Esforço G** porque exige revisar os módulos de leitura e todos os operadores; vale medir antes (qual o limite real hoje?) com um benchmark reproduzível.

---

## Baixa prioridade

### F13 — Histórico de operações e reprodutibilidade

A ideia cita "histórico de operações" e "auditoria". Proposta: o `clean` gravar, ao lado do arquivo de saída, um `.datatool.json` com as flags usadas, hash da entrada, versão do datatool e contagens de cada operação. Um `datatool replay clientes_limpo.datatool.json novo_arquivo.csv` reaplicaria a mesma limpeza. Tem sobreposição com os pipelines YAML ([012](012-pipeline-automacao.md)) — pode ser a forma de **gerar** um pipeline YAML a partir de uma sessão de `clean` feita na mão, o que é um bom caminho de onboarding para o Pro.

### F14 — Conectores (PostgreSQL, S3)

Citados no plano Team da ideia. `convert` já tem a abstração certa (`read_function`/`save_function` por `FileType`); um conector seria mais um tipo, identificado por URI em vez de extensão (`postgresql://...`, `s3://bucket/arquivo.parquet`). Polars já suporta S3 nativamente em `scan_parquet`, e `pl.read_database_uri` cobre bancos. Baixa prioridade porque o posicionamento atual é "arquivos locais bagunçados", e conectores mudam o público-alvo.

### F15 — Unir arquivos (`concat`/`join`)

```bash
datatool concat "vendas_*.csv" --output vendas_2025.parquet     # empilha arquivos com o mesmo schema
datatool join clientes.csv pedidos.csv --on cpf --output base.parquet
```

Útil, mas é o ponto em que a ferramenta começa a competir com SQL/DuckDB em vez de complementá-los. A ideia sugere DuckDB como engine; um `datatool sql "SELECT ..." arquivo.csv` talvez resolva `join` e muito mais com menos código próprio.

---

## Reconciliar comandos-esqueleto

O [src/main.py](../src/main.py) tem comandos que só imprimem os argumentos recebidos e **não correspondem a nenhuma spec**:

| Comando | Sobreposição com o roadmap |
|---------|---------------------------|
| `dataset transform` (`--uppercase`, `--lowercase`, `--fillna`, `--replace`...) | Quase tudo já existe em `clean` (006, 008) |
| `dataset decode` (`EncodingType`, `--onerror`) | F01 (encoding) |
| `excel` (`--workbooks`, `--split`) | F04 (abas) e spec 013 |
| `dataset explain` | Spec 014 (`datatool explain`) |
| `dataset translate` (tradução de cabeçalho/conteúdo) | Nenhuma — seria uma feature nova |
| `utils encode`/`decode` (base64 embaralhado) | Nenhuma; talvez relacionado ao licenciamento (016)? |

Hoje eles aparecem no `--help` e sucedem com exit code 0 sem fazer nada, o que confunde quem testa a ferramenta. Sugestão: decidir, para cada um, entre **remover**, **esconder** (`hidden=True` no Typer até ser implementado) ou **virar spec**. `dataset transform` em particular deveria ser removido em favor do `clean`, para não haver duas formas de fazer a mesma coisa.

---

## Sugestão de sequência

1. **Terminar o MVP** (009, 010, 011) antes de qualquer item daqui — várias propostas (F05, F09, F13) dependem dos operadores completos.
2. **F01, F04 e a reconciliação dos esqueletos** logo em seguida: são pequenos e removem atritos que um usuário novo encontraria no primeiro uso.
3. **F02 e F03** a seguir: F02 é o diferencial "feito para o Brasil" mais barato; F03 desbloqueia 004, 014 e 015.
4. **F05 e F06** como primeiros candidatos a Pro, antes ou junto do 012 — têm argumento de venda claro (CI e LGPD) e reaproveitam os detectores existentes.
