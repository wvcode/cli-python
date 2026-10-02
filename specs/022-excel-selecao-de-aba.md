# US-022: Escolher a aba de uma planilha Excel

## User story
Como analista que recebe planilhas Excel com várias abas, eu quero escolher qual aba o `datatool` lê e ser avisado quando há outras, para diagnosticar, limpar e converter os dados certos, não uma aba de capa ou de resumo.

## Contexto
Item [F04](backlog-novas-features.md#f04--seleção-de-aba-em-excel---sheet) do backlog, prioridade alta. Planilhas reais costumam ter várias abas (capa, dados, resumo, gráficos), e hoje o `datatool` lê sempre a primeira, sem opção e sem aviso. Dois problemas reproduzidos na v0.1.0:

**A primeira aba não tem os dados.** Com as abas "Resumo", "Vendas 2025" e "Clientes":
```
$ datatool info relatorio.xlsx
Linhas: 1
Colunas: 1
Nenhum problema encontrado.
```
O `info` analisou só o resumo (uma linha com um total) e respondeu que não há problemas. Os dados estavam em "Vendas 2025", com linhas duplicadas e um "N/D" num campo numérico. Para uma ferramenta de diagnóstico, é o pior resultado possível: uma resposta errada que parece certa.

**A primeira aba está vazia.** Com uma aba "Capa" vazia antes dos dados, o arquivo inteiro não abre:
```
$ datatool info relatorio.xlsx
Não foi possível ler relatorio.xlsx como xlsx: empty Excel sheet
If you want to read this as an empty DataFrame, set `raise_if_empty=False`.
```
A mensagem ainda sai em inglês e fala de um parâmetro interno do polars.

O suporte já existe nas bibliotecas: o fastexcel lista as abas (`sheet_names`) desde a versão mínima declarada (0.10), e o `pl.read_excel` lê uma aba por nome ou por posição. Quais abas estão ocultas é lido direto do `xl/workbook.xml` da planilha (ver a decisão 3).

Implementado em [src/datatool/files/excel.py](../src/datatool/files/excel.py) (lista de abas e leitura) e [src/datatool/loading.py](../src/datatool/loading.py) (escolha da aba, mensagens, aviso e resumo no JSON).

## Interface proposta
```bash
datatool info relatorio.xlsx                          # lê a primeira aba com dados e avisa das outras
datatool info relatorio.xlsx --sheet "Vendas 2025"
datatool clean relatorio.xlsx --sheet 2 --fix-types --output vendas.parquet
datatool convert relatorio.xlsx clientes.csv --sheet Clientes
datatool profile relatorio.xlsx --sheet "Vendas 2025" --format json
```

`--sheet` existe em `info`, `profile`, `clean` e `convert`, e vale para o arquivo de **entrada**.

## Comportamento — qual aba é lida
- **Com `--sheet`:** o valor é procurado primeiro como **nome** exato da aba. Se nenhuma aba tem esse nome e o valor é um número inteiro, ele é a **posição** da aba, começando em 1, como no Excel. Assim uma aba chamada "2025" é encontrada pelo nome, e `--sheet 2` numa planilha sem aba "2" lê a segunda.
- **Sem `--sheet`:** lê a **primeira aba visível que tem dados**. Abas vazias e ocultas são puladas. Em planilhas de uma aba só, nada muda.
- **Abas ocultas** só são lidas quando pedidas explicitamente com `--sheet`.
- **Aba não encontrada:** erro com exit code 2 listando as abas existentes, como o erro de coluna inexistente (`A aba "Vendas" não existe em relatorio.xlsx. Abas: Resumo, Vendas 2025, Clientes.`).
- **Aba vazia pedida com `--sheet`:** erro em português com exit code 1 (`A aba "Capa" de relatorio.xlsx está vazia.`).
- **Nenhuma aba com dados:** erro com exit code 1 (`Nenhuma aba de relatorio.xlsx tem dados.`).
- **Outros formatos:** `--sheet` num arquivo que não é Excel é erro com exit code 2, antes de ler, como `--sep` num arquivo que não é CSV (`--sheet só vale para arquivos Excel (xlsx).`).

## Comportamento — aviso e saída
- **Aviso:** quando a planilha tem mais de uma aba e `--sheet` não foi passado, uma linha vai para o **stderr**, para não misturar com o CSV do `convert` no stdout:
  ```
  Aviso: relatorio.xlsx tem 3 abas (Resumo, Vendas 2025, Clientes); lida: "Resumo". Use --sheet para escolher outra.
  ```
  Com `--sheet`, não há aviso: a escolha foi explícita.
- **Texto:** o cabeçalho do `info`, do `profile` e do diagnóstico do `clean` ganha uma linha `Aba: Vendas 2025 (2 de 3)` logo depois de "Arquivo:", só para arquivos Excel.
- **JSON (019):** o resumo do arquivo (`file` no `info`, `profile` e `clean`; `source` no `convert`) ganha dois campos, só para Excel:
  - `sheet`: o nome da aba lida;
  - `sheets`: todas as abas, na ordem, cada uma com `name`, e `hidden` quando oculta.

  São campos novos num objeto existente: `schema_version` continua 1, como no DT20.
- **Sugestões do `info`:** quando a planilha tem mais de uma aba, os comandos sugeridos incluem a aba lida (`datatool clean relatorio.xlsx --sheet "Vendas 2025" --fix-types`), com aspas quando o nome tem espaço. Sem isso, a sugestão corrigiria outra aba.
- **Log:** registra a aba lida e quantas abas a planilha tem. Nomes de aba são metadados, como nomes de coluna, e não valores de célula.

## Comportamento — servidor MCP
- As ferramentas `datatool_info`, `datatool_profile`, `datatool_clean_diagnose`, `datatool_clean_apply` e `datatool_convert` ganham o parâmetro opcional `sheet`, com as mesmas regras.
- O documento devolvido traz `file.sheets`. Um agente que recebe uma planilha com várias abas vê a lista e pode chamar de novo com a aba certa, ou perguntar à pessoa.
- O aviso do stderr não existe no MCP: o stdout e o stderr não fazem parte da resposta. A informação está em `file.sheet` e `file.sheets`.

## Critérios de aceite
**Seleção**
- [x] `--sheet NOME` lê a aba com esse nome, em `info`, `profile`, `clean` e `convert`
- [x] `--sheet N` lê a N-ésima aba (a partir de 1) quando não há aba com o nome `N`; uma aba chamada `"2025"` é encontrada pelo nome
- [x] Sem `--sheet`, é lida a primeira aba visível com dados: uma capa vazia e uma aba oculta antes dos dados são puladas
- [x] Aba inexistente: exit code 2 e mensagem com a lista de abas; aba vazia pedida explicitamente e planilha sem dados: exit code 1 e mensagem em português, sem o texto do polars
- [x] `--sheet` em arquivo que não é xlsx: exit code 2, sem ler o arquivo
- [x] Planilhas de uma aba só se comportam exatamente como hoje (a saída dos comandos do snapshot não muda, exceto pela linha "Aba:" nos arquivos Excel)

**Aviso e saída**
- [x] Planilha com várias abas e sem `--sheet`: aviso no stderr com as abas e a lida; com `--sheet`, nenhum aviso
- [x] O texto mostra `Aba: <nome> (<posição> de <total>)` para arquivos Excel
- [x] O JSON traz `sheet` e `sheets` (com `hidden` nas ocultas) no resumo do arquivo, só para Excel, e `schema_version` continua 1
- [x] As sugestões do `info` incluem `--sheet` quando a planilha tem mais de uma aba, com o nome entre aspas quando necessário, e o comando sugerido funciona se copiado
- [x] O log registra a aba lida

**MCP**
- [x] As cinco ferramentas aceitam `sheet` e devolvem `file.sheets`
- [x] Os testes cobrem: nome, posição, nome numérico, capa vazia, aba oculta, aba inexistente, planilha sem dados, `--sheet` em CSV, aviso, JSON e sugestões

**Dependências**
- [x] ~~O mínimo do fastexcel no `pyproject.toml` sobe para 0.12.0~~. Substituído na implementação (ver a decisão 3): o mínimo continua 0.10, e a suíte passa com ele no job de versões mínimas.

## Fora de escopo
- **Ler todas as abas de uma vez** (`--all-sheets`, um diagnóstico por aba): faz parte do `inspect` da [013](013-excel-inspect-auto.md)
- **Linha do cabeçalho fora da primeira linha** (`--header-row`): também na [013](013-excel-inspect-auto.md)
- **Nome da aba na gravação** (`convert dados.csv saida.xlsx` com a aba chamada "Dados", ou acrescentar uma aba a uma planilha existente)
- **Escolha de tabela no SQLite:** hoje a tabela vem do nome do arquivo, ou é a única do banco. É o mesmo tipo de problema e poderia ganhar uma opção `--table` no mesmo padrão, numa spec própria. *(Registrado como débito técnico DT53.)*
- `.xls` (Excel antigo) e `.ods`

## Decisões confirmadas
Confirmadas antes da implementação (2026-09-30); a 3 foi revista durante ela:
1. **Sem `--sheet`, a primeira aba visível com dados.** Resolve o caso da capa vazia, e o aviso diz qual aba foi lida. Planilhas de uma aba só não mudam.
2. **Várias abas sem `--sheet`: aviso, não erro.** Mantém funcionando quem hoje usa planilhas cuja primeira aba é a certa. Para quem automatiza, a lista de abas está no JSON e no MCP.
3. **Abas ocultas tratadas, lendo o `xl/workbook.xml`; o fastexcel mínimo continua 0.10.** *(Revista na implementação, em 2026-10-01.)*
   - **O plano era subir o fastexcel para 0.12.0**, a primeira versão que expõe a visibilidade da aba.
   - **Por que mudou:** a medição mostrou que o `load_sheet` do fastexcel carrega a aba inteira, mesmo com `n_rows=0`. Saber a visibilidade de todas as abas custaria tanto quanto ler todas elas. Numa planilha com 3 abas de 100 mil linhas, a leitura iria de 0,16 s para 0,52 s.
   - **Como ficou:** a lista de abas ocultas vem do `xl/workbook.xml` (parte do formato xlsx, atributo `state` de cada `<sheet>`), lido com `zipfile` e `xml` da biblioteca padrão em ~1 ms. Funciona com qualquer versão do fastexcel.
   - **Aba vazia:** detectada pelo `NoDataError` que o polars já levanta ao lê-la, sem custo extra quando a primeira aba tem dados.
   - **Se o `workbook.xml` não puder ser lido,** todas as abas contam como visíveis.
   - **Medido depois da implementação:** o `info` na planilha de teste levou 0,29 s, contra 0,28 s na v0.1.0.

## Dependências
[001-convert](001-convert.md) (leitura de Excel), [002-info-diagnostico](002-info-diagnostico.md) (sugestões), [019-saida-json](019-saida-json.md) (resumo do arquivo no JSON), [020-mcp-server](020-mcp-server.md) (parâmetro nas ferramentas). A [013](013-excel-inspect-auto.md) depende desta.
