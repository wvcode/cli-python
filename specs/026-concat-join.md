# US-026: Unir arquivos (`concat` e `join`)

## User story
Como analista que recebe dados em vários arquivos (um por mês, um por filial) ou em tabelas separadas (clientes e pedidos), eu quero empilhar arquivos com as mesmas colunas e juntar tabelas por uma chave, para montar a base de análise sem escrever código.

## Contexto
Item [F15](backlog-novas-features.md#f15--unir-arquivos-concatjoin) do backlog, prioridade baixa. O próprio backlog aponta o risco: o `join` é o ponto em que a ferramenta começa a competir com SQL e DuckDB, em vez de complementá-los. A ideia do projeto sugere o DuckDB como motor, e um `datatool sql "SELECT ..." arquivo.csv` resolveria o `join` e muito mais, com menos código próprio.

Por isso esta spec trata os dois de forma diferente:
- **`concat`** resolve um problema comum e pouco servido: juntar "vendas_jan.csv … vendas_dez.csv". Cada arquivo pode vir com delimitador ou encoding próprios, que a leitura do datatool já detecta. É o que a spec detalha.
- **`join`** fica desenhado com um escopo mínimo, mas adiado até haver demanda. A escolha entre ele e um comando `sql` será refeita nesse momento (decisão 1).

## Interface proposta
```bash
datatool concat vendas_jan.csv vendas_fev.csv vendas_mar.csv --output vendas_t1.parquet
datatool concat "vendas_*.csv" --output vendas_2025.parquet --source-column arquivo
datatool join clientes.csv pedidos.csv --on cpf --output base.parquet
datatool join clientes.csv pedidos.csv --on cpf --how left --output base.parquet
```

## Comportamento — `concat`
- **Entradas:** dois ou mais arquivos, em qualquer formato suportado e misturando formatos. Padrões com `*` e `?` são expandidos pelo próprio datatool, em ordem alfabética, porque o shell do Windows não os expande. Um padrão que não casa com nenhum arquivo é erro (exit 2).
- **Leitura:** cada arquivo pelo `load_input`, com a detecção de delimitador, encoding e convenção decimal **por arquivo**. Um mês exportado com `;` e outro com `,` funcionam juntos. `--sheet` vale para todas as planilhas.
- **Colunas:** casadas pelo nome.
  - **Padrão:** todos os arquivos precisam ter as mesmas colunas. Senão é erro (exit 2), dizendo quais colunas faltam ou sobram em qual arquivo.
  - **`--allow-missing`:** junta mesmo assim, deixando nulo onde a coluna não existe.
- **Tipos:** quando a mesma coluna vem com tipos diferentes, usa o tipo comum mais largo (inteiro e decimal viram decimal; número e texto viram texto), como o `how="diagonal_relaxed"` do polars. A mudança aparece no relatório (`valor: i64 + f64 → f64`), para não passar despercebida.
- **`--source-column NOME`:** acrescenta uma coluna com o nome do arquivo de origem de cada linha.
- **Saída:**
  - com `--output`: grava em qualquer formato, com as regras de sempre;
  - sem `--output`: CSV no stdout, como o `convert`;
  - relatório: linhas por arquivo e o total, mais as mudanças de tipo;
  - `--format json`: o envelope de 019, com `sources` e `target`.

## Comportamento — `join` (adiado)
*Desenho para quando houver demanda (decisão 1); não faz parte da implementação inicial desta spec.*

- **Forma:** `join ESQUERDA DIREITA --on col1,col2`. As colunas da chave precisam existir nos dois arquivos, com o mesmo tipo. Senão é erro (exit 2), com a sugestão de `--fix-types` quando a diferença é texto contra número.
- **`--how`:** `inner` (padrão), `left`, `right` ou `outer`.
- **Nomes repetidos:** colunas que existem nos dois arquivos e não são chave ganham o sufixo `_direita` na tabela da direita. `--suffix` muda o sufixo.
- **Chave repetida na direita:** cada linha da esquerda se multiplica. O relatório avisa: "312 chaves de cpf se repetem em pedidos.csv: o resultado tem mais linhas que clientes.csv". Não é erro, porque é o comportamento esperado de juntar clientes com pedidos.
- **Relatório:** linhas de cada lado, linhas do resultado, chaves sem correspondência em cada lado (com exemplos, omitidos por `--redact-values`).
- **Saída e opções de leitura:** como no `concat`.

## Critérios de aceite
**`concat`**
- [ ] Empilha arquivos de formatos, delimitadores e encodings diferentes, cada um detectado por si
- [ ] Padrões com `*`/`?` são expandidos pelo datatool, em ordem alfabética; padrão sem arquivos é exit 2
- [ ] Colunas diferentes sem `--allow-missing`: exit 2 com as colunas e os arquivos; com a opção, nulos onde falta
- [ ] Tipos diferentes viram o tipo comum, e a mudança aparece no relatório
- [ ] `--source-column` acrescenta o nome do arquivo de cada linha
- [ ] Grava com as regras de sempre; sem `--output`, CSV no stdout; `--format json` com `sources` e `target`

**`join`** (adiado, ver a decisão 1; valem quando ele for implementado)
- [ ] `inner`, `left`, `right` e `outer` dão o resultado certo, com chave simples e composta
- [ ] Chave inexistente ou com tipos diferentes: exit 2, com sugestão de `--fix-types` no caso texto/número
- [ ] Colunas repetidas ganham o sufixo, configurável com `--suffix`
- [ ] Chave repetida na direita gera aviso no relatório com a contagem, sem erro
- [ ] O relatório traz as chaves sem correspondência de cada lado, e `--redact-values` remove os exemplos

## Fora de escopo
- Ferramentas MCP para `concat` e `join` (gravam arquivos; podem vir depois, no padrão de `datatool_convert`)
- Empilhar as abas de uma mesma planilha (`concat relatorio.xlsx --all-sheets`): registrado como débito técnico DT55
- Juntar mais de dois arquivos num só `join`, ou chaves com nomes diferentes de cada lado (`--left-on`/`--right-on`)
- Deduplicar o resultado do `concat` (já existe no `clean --remove-duplicates`)

## Decisões confirmadas
Confirmadas em 2026-10-02:
1. **`concat` agora; `join` adiado até haver demanda.** O `concat` resolve um problema comum que nenhuma outra ferramenta resolve bem: arquivos de cada mês com delimitador, encoding e convenção decimal diferentes, que a leitura do datatool já detecta. O `join` fica desenhado nesta spec, mas só é implementado se usuários pedirem. Nesse momento, a escolha entre ele e um comando `sql` com DuckDB é refeita, com o uso real em mãos. O DuckDB é uma dependência grande e leria os arquivos sem a detecção do datatool.
2. **Sufixo padrão `_direita`** para as colunas repetidas no `join`, em português como o resto da saída, e configurável com `--suffix`. Vale quando o `join` for implementado.

## Dependências
[001](001-convert.md) (leitura e gravação), [017](017-csv-delimitador-encoding.md) (detecção por arquivo), [019](019-saida-json.md), [022](022-excel-selecao-de-aba.md) (`--sheet`)
