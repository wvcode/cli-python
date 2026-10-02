# US-025: Ver as primeiras linhas e tirar amostras (`head`/`sample`)

## User story
Como analista que recebe um arquivo novo, eu quero ver as primeiras linhas, ou uma amostra aleatória, em qualquer formato, para entender o conteúdo antes de diagnosticar, e para compartilhar um recorte pequeno de um arquivo grande.

## Contexto
Item [F11](backlog-novas-features.md#f11--amostragem-e-visualização-headsample) do backlog. Para "dar uma olhada" num Parquet, num SQLite ou numa planilha, hoje o caminho é `datatool convert arquivo.parquet` sem destino. Ele imprime **o arquivo inteiro** em CSV no stdout (DT19), o que num arquivo grande é inútil, e não permite escolher linhas nem colunas. Para CSV, `head -n 20` do shell funciona; para os outros formatos, não há alternativa sem código.

## Interface proposta
```bash
datatool head vendas.parquet                     # 10 primeiras linhas, em tabela
datatool head vendas.parquet -n 20 --columns nome,valor
datatool head vendas.db --format csv | less      # CSV no stdout, para pipe
datatool sample vendas.csv -n 1000 --seed 42 --output amostra.csv
```

## Comportamento — `head`
- **Linhas:** as `-n` primeiras, 10 por padrão. Com menos linhas no arquivo, mostra todas.
- **Colunas:** `--columns col1,col2` mostra só essas, na ordem pedida. Coluna inexistente é erro (exit 2), como no `profile --columns`.
- **Saída em texto:** uma tabela alinhada com os nomes e os tipos das colunas, sem truncar colunas nem valores além de um limite de largura por célula, e com o total de linhas e colunas do arquivo no rodapé (`10 de 152.438 linhas, 6 colunas`).
- **`--format csv`:** as linhas em CSV no stdout, para pipe.
- **`--format json`:** o envelope de 019, com `file` e `rows` (lista de objetos).

  Como `csv` não vale para `info`, `profile` e `clean`, esses dois comandos usam uma opção de formato própria, em vez da `--format` compartilhada.
- **`--output arquivo`:** grava as linhas em qualquer formato suportado, com as regras de gravação de sempre (`--overwrite`, confirmação "Gravado …" no stderr).
- **Leitura:** as opções de entrada de sempre (`--sep`, `--encoding`, `--sheet`). O arquivo é lido inteiro, para os tipos serem os mesmos dos outros comandos (DT28). Ler só o começo de arquivos grandes é o item F12.

## Comportamento — `sample`
- **Amostra:** `-n` linhas sorteadas sem repetição, 10 por padrão, **na ordem original do arquivo**, o que facilita comparar com o arquivo.
- **`--seed N`:** repete a mesma amostra na mesma instalação (ver a decisão 2 sobre versões). Sem `--seed`, cada execução sorteia outra amostra, e a semente usada vai para o log e para o JSON, para ser possível repetir depois.
- **`-n` maior que o arquivo:** devolve todas as linhas, com um aviso no stderr, em vez do erro do polars (`ShapeError`).
- **Saída:** as mesmas opções do `head` (`--columns`, texto/CSV/JSON, `--output`).

## Comportamento — privacidade
- Os dois comandos existem para mostrar valores de célula. Por isso não têm `--redact-values`, e os valores não vão para o log: só o arquivo, o número de linhas e a semente.
- **Reprodutibilidade:** a mesma `--seed` repete a amostra na mesma instalação (mesma versão do polars). Entre versões diferentes, a amostra pode mudar (decisão 2). O README e a ajuda do `--seed` dizem isso.

## Comportamento — servidor MCP
As demais ferramentas ocultam valores de célula por padrão (`redact_values`). Uma ferramenta cujo propósito é devolver linhas contraria isso, então ela só existe quando quem configura o servidor a liga explicitamente (decisão 1), como o `--allow-urls` da [021](021-leitura-via-url.md).
- **`datatool-mcp --allow-rows`** registra duas ferramentas, `datatool_head` e `datatool_sample`, somente leitura (`read_only_hint`). Elas têm os mesmos parâmetros dos comandos (`filename`, `n`, `columns`, `seed`, e `sep`/`encoding`/`sheet`), sem `output`, e devolvem o JSON do `--format json`.
- **Sem `--allow-rows`**, as ferramentas não são registradas: não aparecem na lista do servidor, e o agente não tem como chamá-las. Isso evita que uma instrução maliciosa lida pelo agente o leve a extrair dados do arquivo.
- **Limite de linhas:** `n` vai até 100 por chamada nas ferramentas, para uma chamada não encher o contexto do modelo. Acima disso, a ferramenta recusa a chamada com uma mensagem que cita o limite. No CLI não há limite.
- **Descrição das ferramentas:** diz que elas devolvem valores reais das células, para o agente e para quem aprova a chamada saberem o que vai ao modelo.
- **Sandbox e log:** o caminho fica restrito a `--root`, como nas demais. O log registra a chamada sem os valores.

## Critérios de aceite
- [ ] `head` mostra as `-n` primeiras linhas (10 por padrão) de qualquer formato suportado, com nomes e tipos das colunas e o total do arquivo no rodapé
- [ ] `--columns` filtra e ordena as colunas; coluna inexistente é exit 2
- [ ] `--format csv` e `--format json` funcionam nos dois comandos; `--format csv` não aparece em `info`, `profile` e `clean`
- [ ] `--output` grava as linhas em qualquer formato, com as regras de sobrescrita e a confirmação no stderr
- [ ] `sample -n N --seed S` dá sempre as mesmas linhas, na ordem original, na mesma instalação
- [ ] `sample` sem `--seed` registra a semente usada no log e no JSON
- [ ] `sample -n` maior que o arquivo devolve todas as linhas com aviso no stderr, sem erro
- [ ] Os valores de célula não aparecem no log
- [ ] A ajuda do `--seed` e o README dizem que a amostra se repete na mesma versão do polars, não entre versões

**MCP**
- [ ] Sem `--allow-rows`, o servidor não registra `datatool_head` nem `datatool_sample` (não aparecem na lista de ferramentas)
- [ ] Com `--allow-rows`, as duas ferramentas aparecem, marcadas como somente leitura, com descrição que avisa que devolvem valores reais, e respeitam o sandbox de `--root`
- [ ] `n` acima de 100 numa ferramenta é recusado com mensagem que cita o limite; no CLI não há limite
- [ ] Os testes que conferem a lista de ferramentas cobrem as duas configurações, com e sem `--allow-rows`

## Fora de escopo
- `tail` (últimas linhas): registrado como débito técnico DT54
- Ler só o começo de arquivos grandes, sem carregar o arquivo inteiro (item F12)
- Amostra estratificada ou por fração (`--fraction 0.1`)
- Anonimizar a amostra (item F06)

## Decisões confirmadas
Confirmadas em 2026-10-02:
1. **Ferramentas MCP, só quando ligadas explicitamente.** `datatool_head` e `datatool_sample` existem apenas com `datatool-mcp --allow-rows`. Um agente às vezes precisa ver algumas linhas para entender um arquivo, mas mandar dados ao modelo tem de ser escolha de quem configura o servidor, não o padrão. O mesmo raciocínio do `--allow-urls` da [021](021-leitura-via-url.md).
2. **A semente repete a amostra na mesma instalação, não entre versões.** O sorteio é o do polars, que muda entre versões: com `seed=1`, o polars 1.44.2 sorteia as linhas 0, 5, 7 e 9 de 10, e o 1.27.1, as linhas 0, 1, 3 e 9. Um gerador próprio, de algoritmo fixo, daria repetição entre versões, mas custaria mais código e testes de estabilidade para um caso (auditoria entre máquinas) que ninguém pediu. A limitação fica documentada.

## Dependências
[001](001-convert.md) (leitura e gravação), [019](019-saida-json.md), [020](020-mcp-server.md) (servidor MCP e sandbox), [022](022-excel-selecao-de-aba.md) (`--sheet`)
