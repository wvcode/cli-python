# US-024: Comparar dois datasets (`datatool diff`)

## User story
Como analista que recebe o mesmo arquivo todo mês, ou que acabou de limpar um arquivo, eu quero comparar duas versões e ver o que mudou no esquema e nas linhas, para saber se o arquivo novo bate com o anterior e se a limpeza fez só o que eu esperava.

## Contexto
Item [F08](backlog-novas-features.md#f08--comparação-entre-dois-datasets-datatool-diff) do backlog. Duas perguntas comuns hoje exigem carregar os arquivos em pandas:
- "o arquivo deste mês tem as mesmas colunas e o volume esperado em relação ao do mês passado?";
- "o que exatamente o `clean` mudou?".

A segunda fecha o ciclo do produto: `info` aponta, `clean` corrige, `diff` mostra o que foi corrigido.

A leitura reaproveita `load_input` ([src/datatool/loading.py](../src/datatool/loading.py)), então os dois arquivos podem estar em formatos diferentes (ex.: o CSV original e o Parquet limpo). A detecção de delimitador e encoding, a seleção de aba e as demais regras de leitura valem para cada um.

## Interface proposta
```bash
datatool diff vendas_jan.csv vendas_fev.csv
datatool diff clientes.csv clientes_limpo.parquet --key cpf
datatool diff clientes.csv clientes_limpo.parquet --key cpf --format json
```

```
Esquema
  + desconto (f64)
  - observacao (str)
  ~ valor: str → f64
Linhas: 10.234 → 11.012 (+778)

Por chave (cpf)
  23 removidas, 0 adicionadas, 87 alteradas, 10.124 iguais
  Colunas mais alteradas: nome (64), cidade (23)
```

## Comportamento — esquema
- **Colunas:** adicionadas (só em B), removidas (só em A) e com tipo alterado (mesmo nome, tipo diferente). A comparação é pelo nome; a ordem das colunas não conta como diferença, mas é informada quando muda.
- **Linhas:** total de A e de B, e a diferença.

## Comportamento — linhas
- **Com `--key col1,col2`:** as linhas são casadas pela chave e contadas em removidas (chave só em A), adicionadas (só em B), alteradas (mesma chave, algum valor diferente) e iguais. Para as alteradas, conta quantas linhas mudaram em cada coluna, e as colunas aparecem da mais alterada para a menos.
  - **Comparação de valores:** só nas colunas presentes nos dois arquivos **com o mesmo tipo**. Nulo é igual a nulo. Colunas com tipo alterado já aparecem no esquema e ficam fora da contagem por valor (decisão 2).
  - **Chave repetida** em qualquer um dos arquivos é erro com exit code 2, com quantas chaves se repetem e em qual arquivo, porque a correspondência ficaria ambígua. O `profile --key` já ajuda a achar as repetições.
  - **Chave inexistente** em algum dos arquivos: erro com exit code 2, como no `profile --key`.
- **Sem `--key`:** compara as linhas inteiras, como multiconjuntos, nas colunas comuns aos dois com o mesmo tipo. Informa quantas linhas só existem em A e quantas só existem em B. Sem chave não há "alterada": uma linha mudada aparece como uma removida e uma adicionada.
- **Exemplos:** até 5 chaves de cada grupo (removidas, adicionadas, alteradas) no texto e no JSON. Com `--redact-values`, os exemplos saem e as contagens ficam, porque chaves são valores de célula (CPF, e-mail).

## Comportamento — saída
- **Texto:** como no exemplo acima. Quando não há nenhuma diferença: "Nenhuma diferença encontrada."
- **JSON (019):** `command: "diff"`, `files` (resumo dos dois, como `file` nos outros comandos), `schema` (`added`, `removed`, `type_changed`, `order_changed`), `rows` (`a`, `b`) e `by_key` ou `by_row` com as contagens e os exemplos.
- **Exit code:** 0 quando a comparação roda, com ou sem diferenças (decisão 1). Erros seguem os códigos de sempre (2 para opção ou chave inválida, 1 para falha de leitura).
- **Opções de leitura:** `--sep`, `--encoding` e `--sheet` valem para os dois arquivos. É o caso comum de duas versões do mesmo arquivo.
- **Servidor MCP:** ferramenta nova `datatool_diff`, somente leitura, com os mesmos parâmetros e `redact_values` ligado por padrão, como nas demais.
- **Log:** registra os dois arquivos e as contagens, sem valores de célula.

## Critérios de aceite
- [ ] O esquema mostra colunas adicionadas, removidas e com tipo alterado, e a mudança de ordem
- [ ] Com `--key`, as contagens de removidas, adicionadas, alteradas e iguais estão certas, e as colunas alteradas aparecem com as contagens, da mais para a menos alterada
- [ ] Sem `--key`, informa as linhas que só existem em A e só em B, comparando linhas inteiras com repetições
- [ ] Nulo é igual a nulo; colunas com tipo alterado ficam fora da comparação de valores e aparecem no esquema
- [ ] Com ou sem diferenças, a comparação sai com exit code 0
- [ ] Chave repetida ou inexistente em qualquer arquivo: exit code 2 com mensagem que diz o arquivo e o problema
- [ ] Funciona entre formatos diferentes (ex.: CSV e Parquet)
- [ ] `diff` de um arquivo com ele mesmo: "Nenhuma diferença encontrada."
- [ ] `diff` entre a entrada e a saída de um `clean --trim --remove-duplicates` reflete exatamente o relatório do `clean`
- [ ] `--redact-values` remove os exemplos e mantém as contagens; `--format json` segue o envelope de 019
- [ ] `datatool_diff` no servidor MCP, somente leitura, com `redact_values` ligado por padrão
- [ ] Um par de arquivos de 200 mil linhas compara em poucos segundos

## Fora de escopo
- Tolerância numérica (ex.: considerar `10.000001` igual a `10`)
- Mostrar as linhas alteradas lado a lado, célula por célula
- Opções de leitura diferentes para cada arquivo (ex.: `--sep` só para A)
- Comparar mais de dois arquivos

## Decisões confirmadas
Confirmadas em 2026-10-02:
1. **Exit code 0 sempre que a comparação roda, com ou sem diferenças.** No datatool, o 1 já significa falha de leitura, e um código próprio para "há diferenças" dividiria esse papel com outro comando. Fazer o pipeline falhar quando os dados não batem é o papel do quality gate do item F05 (`datatool check`). Quem automatiza com o `diff` usa o `--format json` e as contagens.
2. **Colunas com tipo alterado ficam fora da comparação de valores.** Elas aparecem no esquema (`~ valor: str → f64`), e o relatório por valor cobre só as colunas comuns com o mesmo tipo. Assim um `diff` entre a entrada e a saída de um `--fix-types` não marca a coluna inteira como alterada por causa da representação (`"10,50"` contra `10.5`).

## Dependências
[001](001-convert.md) (leitura dos formatos), [003](003-profile-estatistico.md) (validação de `--key`), [019](019-saida-json.md), [020](020-mcp-server.md), [022](022-excel-selecao-de-aba.md) (`--sheet`)
