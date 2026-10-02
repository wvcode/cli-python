# US-012: Pipeline de limpeza via arquivo YAML

## User story
Como engenheiro de dados, eu quero declarar uma sequência de operações em um arquivo YAML e executá-la com um único comando, para reproduzir a mesma limpeza em múltiplos arquivos sem repetir flags manualmente.

## Contexto
Camada 4 da ideia ("Automação"), descrita como o que transforma a CLI em um "mini DataOps local". Feature **Pro** natural (ver [016-licenciamento-pro](016-licenciamento-pro.md)).

Todas as operações já existem no `clean` (specs 006–011 e [018](018-cpf-cnpj-validacao.md)). Elas são configuradas por `CleanOptions` e executadas por `clean.apply_operations`, em [src/datatool/clean.py](../src/datatool/clean.py). O pipeline é outra forma de preencher o mesmo `CleanOptions`: um arquivo no lugar das flags. Com isso, as operações, as validações de combinação (DT15, DT30), a gravação e o relatório são os mesmos do `clean`, sem uma segunda implementação.

**A ordem das operações é fixa.** O `clean` sempre aplica as operações nesta ordem, qualquer que seja a ordem das flags:
1. remover e renomear colunas;
2. `trim`, caixa (`lowercase`/`uppercase`/`normalize_case`);
3. documentos, datas, tipos;
4. `fill_null`, `drop_null`;
5. `remove_duplicates`.

A ordem foi pensada para que cada passo veja o resultado do anterior da forma certa: renomear antes das opções que citam colunas, `trim` antes de deduplicar. O pipeline usa a mesma ordem. O YAML **declara** o que fazer, não em que sequência.

## Interface proposta
```yaml
# pipeline.yaml
input:
  file: clientes.csv
  sep: ";"            # opcional, como --sep
  encoding: cp1252    # opcional, como --encoding

operations:
  remove_columns: [coluna_temp]
  rename_columns: {nome_cliente: nome}
  trim: true
  normalize_case: true
  normalize_documents:
    format: masked      # digits ou masked
    columns: [cpf]      # opcional, como --document-columns
  normalize_dates:
    columns: [data_nascimento]   # opcional, como --date-columns
  fix_types:
    decimal_separator: ","       # opcional
  fill_null: ["N/A", "idade:0"]
  drop_null:
    columns: [email]             # opcional, como --drop-null-columns
  remove_duplicates:
    key: [cpf]                   # opcional, como --key

output:
  file: clientes_limpo.parquet
  overwrite: false
```

```bash
datatool run pipeline.yaml
datatool run pipeline.yaml --input outro.csv --output outro_limpo.parquet
datatool run pipeline.yaml --format json
```

- **Nomes das operações:** os mesmos campos de `CleanOptions`, que são as flags do `clean` com `_` no lugar de `-`. Quem já usa o CLI não aprende nada novo.
- **Parâmetros junto da operação:** `key` fica dentro de `remove_duplicates`, `columns` dentro de `drop_null`, e assim por diante. Assim o YAML não permite, pela própria estrutura, um parâmetro sem a sua operação, o erro que o DT30 teve de detectar no CLI.
- **`--input`/`--output`:** reaproveitam o mesmo pipeline em outros arquivos, que é o que a user story pede. Processar vários arquivos de uma vez (glob) é o item F10 do backlog.

## Comportamento
- **Validação antes de executar:** chaves desconhecidas, tipos errados e combinações inválidas são erro com exit code 2, antes de ler o arquivo de dados. A mensagem aponta o caminho do campo (`operations.remove_duplicates.key: esperado uma lista de colunas`). Colunas inexistentes são detectadas como no `clean`, depois da leitura e antes de gravar.
- **Regras do `clean`:** `lowercase`, `uppercase` e `normalize_case` continuam mutuamente exclusivas. Pelo menos uma operação é obrigatória. `output.file` existente só é substituído com `overwrite: true` ou `--overwrite`.
- **Caminhos relativos** (`input.file`, `output.file`) são resolvidos em relação ao diretório do arquivo YAML, não ao diretório atual. Um pipeline versionado junto com os dados funciona de qualquer lugar. `--input`/`--output` na linha de comando continuam relativos ao diretório atual, como qualquer argumento.
- **Formato de saída:** inferido pela extensão de `output.file`, como no `clean` e no `convert`. `output.type` é opcional e equivale ao `--to-type`.
- **Relatório:** o mesmo do `clean --output` (texto, ou `--format json` com `command: "run"` e a mesma estrutura de `operations`), mais a linha "Gravado …" no stderr. `--redact-values` vale como no `clean`.
- **Leitura segura do YAML:** só `yaml.safe_load`. Um YAML com tags Python (`!!python/object`) é recusado, porque o arquivo pode vir de outra pessoa.
- **Log:** registra o caminho do pipeline e as operações, como o `clean`.

## Critérios de aceite
- [ ] `datatool run pipeline.yaml` aplica as operações declaradas e grava em `output.file`, com o mesmo resultado de `datatool clean` com as flags equivalentes (um teste compara os dois arquivos de saída)
- [ ] Todas as operações do `clean` são aceitas com os nomes de `CleanOptions`, com os parâmetros dentro da operação
- [ ] Chave desconhecida, tipo errado, operação ausente ou `lowercase`+`uppercase` juntos geram erro com o caminho do campo, exit code 2, sem ler os dados
- [ ] Caminhos relativos do YAML são resolvidos a partir do diretório do YAML
- [ ] `--input` e `--output` substituem `input.file` e `output.file`
- [ ] `output.file` existente é recusado sem `overwrite: true`/`--overwrite`
- [ ] `--format json` imprime o relatório com `command: "run"`, e `--redact-values` funciona como no `clean`
- [ ] Um YAML com tags Python é recusado sem executar nada
- [ ] A ordem das chaves em `operations` não muda o resultado (as operações seguem a ordem fixa do `clean`)

## Fora de escopo
- Ordem de execução definida pelo usuário, e a mesma operação mais de uma vez (ver questão 1)
- Validação de qualidade que faz o pipeline falhar (ex.: e-mails inválidos): é o item F05 do backlog (`datatool check`), que pode usar um arquivo no mesmo estilo
- Vários arquivos de entrada (glob): item F10 do backlog
- Ferramenta MCP para rodar pipelines

## Questões em aberto
1. **Ordem fixa ou ordem declarada?** A proposta mantém a ordem fixa do `clean`, e o pipeline vira só outro jeito de passar as mesmas opções. Permitir a ordem declarada, e repetir operações, exige refatorar `apply_operations` para receber uma lista ordenada, e mudar regras que hoje dependem da ordem (ex.: `--key` validado depois do renomear). É mais flexível, mas o `run` e o `clean` passariam a poder dar resultados diferentes.
2. **YAML (dependência nova, PyYAML) ou TOML?** YAML é o que a ideia e a user story citam, e o mais comum em pipelines. TOML dispensa dependência a partir do Python 3.11 (`tomllib`), mas o projeto suporta 3.10. A proposta é YAML, com o PyYAML no extra das features Pro, se a [016](016-licenciamento-pro.md) separar essas features num pacote próprio.
3. **Nome do comando:** `run` (proposta, como na versão original) ou `clean --pipeline pipeline.yaml`.

## Revisão (2026-09-30)
Revisada contra o código da v0.1.0. O que mudou em relação à versão original:
- **Nomes das operações** alinhados ao código: `trim_strings` virou `trim`, `convert_types` virou `fix_types`; entraram `lowercase`, `uppercase`, `normalize_case` e `normalize_documents`, que a versão original não previa. `validate_emails` saiu: não existe como operação (e-mail é só diagnosticado), e "falhar se houver e-mail inválido" é o quality gate do F05.
- **Parâmetros** (`key`, `columns`, `decimal_separator`, formato dos documentos) passaram a ter lugar no YAML. A lista original não tinha como passá-los.
- **"Executa na ordem declarada" foi substituído pela ordem fixa do `clean`**, com a alternativa registrada na questão 1. A versão original assumia uma ordem livre que o código não tem.
- **Novos comportamentos:** resolução de caminhos relativa ao YAML, `--input`/`--output` para reaproveitar o pipeline, `safe_load`, regras de sobrescrita, relatório e JSON iguais aos do `clean`.
- **`output.format` virou opcional** (`output.type`), porque o formato é inferido pela extensão, como no resto do CLI.

## Dependências
[006](006-clean-operadores-string.md), [007](007-clean-remover-duplicidades.md), [008](008-clean-tratar-nulos.md), [009](009-clean-normalizar-datas.md), [010](010-clean-corrigir-tipos.md), [011](011-clean-colunas.md), [018](018-cpf-cnpj-validacao.md), [019](019-saida-json.md) (relatório em JSON)
