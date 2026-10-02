# US-023: Ver o efeito do `clean` sem gravar nada (`--dry-run`)

## User story
Como analista que vai limpar um arquivo grande, eu quero ver quantos valores e linhas cada operação mudaria antes de gravar, para conferir o efeito da limpeza sem gerar arquivo nem despejar o dataset inteiro no terminal.

## Contexto
Item [F07](backlog-novas-features.md#f07----dry-run-no-clean) do backlog. Hoje, para ver o efeito de `clean --trim --remove-duplicates` sem gravar, a única saída é rodar sem `--output`. O comando imprime o dataset inteiro em CSV no stdout, com o relatório no stderr. Num arquivo de 200 mil linhas, o relatório se perde no meio do CSV.

E o relatório não diz tudo. As operações de texto (`--trim`, `--lowercase`, `--uppercase`, `--normalize-case`) não informam nada, nem no texto nem no JSON (`{"operation": "trim"}`, sem contagem), em [src/datatool/clean.py](../src/datatool/clean.py) (`_string_operator`, `_text_nothing`). As demais já informam as contagens: linhas removidas, células preenchidas, datas normalizadas, valores que não converteram.

O `--dry-run` é especialmente útil antes do `--fix-types`: o relatório mostra quantos valores não converteriam e virariam vazios (ver o débito técnico DT49) antes que isso aconteça no arquivo gravado.

## Interface proposta
```bash
datatool clean clientes.csv --trim --remove-duplicates --dry-run
datatool clean clientes.csv --fix-types --normalize-dates --dry-run --format json
datatool clean clientes.csv --trim --output limpo.parquet --dry-run   # ensaio do comando completo
```

```
"nome": 87 valores alterados por --trim
"cidade": 12 valores alterados por --trim
23 linhas removidas
Resultado: 152.438 → 152.415 linhas, 6 colunas. Nada foi gravado.
```

## Comportamento
- **O que faz:** roda as operações pedidas exatamente como sem `--dry-run`, com as mesmas validações, a mesma ordem e o mesmo relatório. Só não grava e não imprime o dataset.
- **Contagem nas operações de texto:** `--trim`, `--lowercase`, `--uppercase` e `--normalize-case` passam a informar, por coluna de texto, quantos valores mudaram (comparação que trata nulos como iguais). Colunas sem mudança não aparecem. Isso vale **também sem `--dry-run`**: o relatório normal do `clean` ganha essas linhas, e o JSON ganha `columns: [{"column", "changed"}]` nessas operações. É um campo novo, então `schema_version` continua 1.
- **Resumo final:** uma linha com linhas e colunas antes e depois, e "Nada foi gravado." No JSON, `dry_run: true`, um `result` com `rows`/`columns` finais e nenhum `output`.
- **Saída:** em `--dry-run`, o relatório vai para o **stdout**, porque não há dataset para disputar o stdout. Não há linha "Gravado …".
- **Com `--output`:** o destino é validado como numa execução real (formato pela extensão; existente sem `--overwrite` é erro, exit 2), mas nada é gravado. O resumo diz qual seria o destino. Assim dá para ensaiar o comando completo e depois rodar o mesmo comando sem `--dry-run`.
- **`--format json` sem `--output`:** permitido com `--dry-run`. Sem ele, continua exigindo `--output`, porque o dataset não cabe no documento.
- **Sem operação:** `--dry-run` sem nenhuma operação é erro (exit 2), como `--output` sem operação (DT30). Sem operação, o `clean` já é só diagnóstico.
- **Log:** registra a execução como dry-run e as mesmas contagens. Nenhum "gravado".
- **Servidor MCP:** uma ferramenta nova, `datatool_clean_preview`, **somente leitura** (`read_only_hint`, sem `destructive_hint`). Ela recebe os mesmos parâmetros de operação de `datatool_clean_apply`, sem `output` e `overwrite`, e devolve o mesmo relatório, com `dry_run: true`. Um agente pode mostrar o efeito à pessoa antes de chamar `datatool_clean_apply`. Como a ferramenta não grava nada, o cliente MCP não precisa pedir confirmação. `datatool_clean_apply` não muda. A descrição das duas ferramentas cita a outra, para o agente saber que pode prever antes de gravar.

## Critérios de aceite
- [ ] `--dry-run` aplica as operações e imprime o relatório e o resumo, sem gravar arquivo e sem imprimir o dataset
- [ ] `--trim`, `--lowercase`, `--uppercase` e `--normalize-case` informam, por coluna, quantos valores mudaram, com e sem `--dry-run`, em texto e em JSON (decisão 1)
- [ ] O resumo mostra linhas e colunas antes e depois e termina com "Nada foi gravado."
- [ ] Com `--output`, o destino é validado (existente sem `--overwrite`: exit 2), mas o arquivo não é criado nem alterado
- [ ] `--format json --dry-run` funciona sem `--output` e traz `dry_run: true`, as operações e `result`
- [ ] `--dry-run` sem operação: exit 2, sem ler o arquivo
- [ ] O relatório de um `--dry-run` é igual ao da execução real com as mesmas opções (um teste compara os dois)
- [ ] `datatool_clean_preview` existe no servidor MCP, marcada como somente leitura, aceita as mesmas operações de `datatool_clean_apply` (sem `output`/`overwrite`), não grava nada e devolve o mesmo relatório que a ferramenta de gravação devolveria
- [ ] Sem nenhuma operação, `datatool_clean_preview` recusa a chamada, como `datatool_clean_apply`
- [ ] Os testes que conferem a lista de ferramentas do servidor (hoje 5, em `tests/test_mcp_server.py`, inclusive o que sobe o `datatool-mcp` pelo stdio) passam a esperar a nova, e o README e o site a listam
- [ ] O log registra a execução como dry-run

## Fora de escopo
- Mostrar exemplos dos valores antes/depois de cada operação (o `diff` da [024](024-diff-datasets.md) entre entrada e saída cobre isso depois da gravação)
- `--dry-run` no `convert`

## Decisões confirmadas
Confirmadas em 2026-10-02:
1. **As operações de texto informam quantos valores mudaram também sem `--dry-run`.** O relatório é um só, com e sem a opção, e o `--dry-run` só deixa de gravar. Isso muda a saída atual do `clean` com `--trim`, `--lowercase`, `--uppercase` e `--normalize-case`: o texto ganha uma linha por coluna alterada, e o JSON ganha `columns` nessas operações (campo novo, `schema_version` continua 1). A mudança entra no CHANGELOG da versão que trouxer esta spec.

2. **No servidor MCP, uma ferramenta separada e somente leitura: `datatool_clean_preview`.** Um parâmetro `dry_run` na `datatool_clean_apply` herdaria a marcação de ferramenta destrutiva, e o cliente MCP poderia pedir confirmação para algo que não grava nada. Com uma ferramenta própria, a marcação de cada uma diz a verdade, e a `datatool_clean_apply` continua como está. O custo é uma sexta ferramenta no servidor.

## Dependências
[005](005-clean-detectar-problemas.md)–[011](011-clean-colunas.md) (operações), [019](019-saida-json.md) (relatório em JSON), [020](020-mcp-server.md) (ferramenta `datatool_clean_apply`)
