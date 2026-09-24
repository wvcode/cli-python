# US-012: Pipeline de limpeza via arquivo YAML

## User story
Como engenheiro de dados, eu quero declarar uma sequência de operações em um arquivo YAML e executá-la com um único comando, para reproduzir a mesma limpeza em múltiplos arquivos sem repetir flags manualmente.

## Contexto
Camada 4 da ideia ("Automação"), descrita como o que transforma a CLI em um "mini DataOps local". Feature **Pro** natural (ver [016-licenciamento-pro](016-licenciamento-pro.md)).

## Interface proposta
```yaml
input: clientes.csv

operations:
  - trim_strings
  - normalize_dates
  - remove_duplicates
  - validate_emails

output:
  format: parquet
  file: clientes_clean.parquet
```
```bash
datatool run pipeline.yaml
```

## Critérios de aceite
- [ ] Lê o YAML com o schema `input`, `operations` (lista ordenada) e `output.format`/`output.file`
- [ ] Cada item de `operations` mapeia para um operador já implementado nas specs 006-011 (`trim_strings`, `normalize_dates`, `remove_duplicates`, `fill_null`, `drop_null`, `convert_types`, `rename_columns`, `remove_columns`) mais `validate_emails` (reaproveita a detecção de [005-clean-detectar-problemas](005-clean-detectar-problemas.md))
- [ ] Executa as operações na ordem declarada no arquivo
- [ ] Valida o schema do YAML antes de executar; erro claro se houver operação desconhecida ou campo obrigatório ausente
- [ ] Grava a saída no formato/arquivo declarado em `output`, reaproveitando [001-convert](001-convert.md)

## Dependências
[006](006-clean-operadores-string.md), [007](007-clean-remover-duplicidades.md), [008](008-clean-tratar-nulos.md), [009](009-clean-normalizar-datas.md), [010](010-clean-corrigir-tipos.md), [011](011-clean-colunas.md)
