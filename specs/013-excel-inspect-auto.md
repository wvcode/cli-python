# US-013: Inspeção e limpeza automática de Excel bagunçado

## User story
Como analista que recebe planilhas Excel desorganizadas, eu quero inspecionar o arquivo e aplicar uma limpeza automática com um único comando, para transformar uma planilha bagunçada em um dataset pronto para análise.

## Contexto
Nicho de posicionamento comercial descrito na ideia ("Excel → dados profissionais"), com o exemplo `relatorio_vendas_final_FINAL2.xlsx`. Feature **Pro** (ver [016-licenciamento-pro](016-licenciamento-pro.md)).

O que o código já faz com Excel, e onde falha:
- **Diagnóstico:** `info` e `clean` já leem `.xlsx`, com os mesmos diagnósticos de CSV ([002](002-info-diagnostico.md), [005](005-clean-detectar-problemas.md)).
- **Várias abas:** só a primeira é lida, sem aviso. Numa planilha com as abas "Resumo", "Vendas 2025" e "Clientes", `info` analisa só o resumo e responde "Nenhum problema encontrado". A spec [022](022-excel-selecao-de-aba.md) (`--sheet`) resolve isso, e esta spec a pressupõe.
- **Cabeçalho fora da primeira linha:** uma planilha com um título na linha 1 e o cabeçalho na linha 3 é lida com as colunas erradas (`Relatório de vendas 2025`, `__UNNAMED__1`). O leitor do polars/fastexcel já aceita a linha do cabeçalho (`read_options={"header_row": n}`); falta detectá-la.
- **Limpeza:** as correções existem uma a uma no `clean` (specs 006–011, 018). O `info` já escolhe quais delas sugerir a partir dos problemas encontrados (`_SUGGESTIONS` em [src/datatool/info.py](../src/datatool/info.py)).

Esta spec junta essas peças: uma visão da planilha inteira (`inspect`) e uma limpeza com as correções que o diagnóstico indicar (`--auto`).

## Interface proposta
```bash
datatool inspect relatorio_vendas_final_FINAL2.xlsx
datatool clean relatorio_vendas_final_FINAL2.xlsx --auto
datatool clean relatorio_vendas_final_FINAL2.xlsx --auto --sheet "Vendas 2025" --output vendas.parquet
```

## Comportamento — `inspect`
- **Por aba:** nome, linhas, colunas e a linha de cabeçalho detectada. Também mostra os problemas do `info` e do diagnóstico do `clean` (`info.diagnose` e `clean.diagnose`), sem cálculo novo.
- **Detecção do cabeçalho:** a primeira linha com a maioria das células preenchidas e com texto é o cabeçalho. As linhas acima dela (títulos, datas de emissão) são ignoradas e listadas no relatório. `--header-row N`, em `inspect`, `info`, `clean` e `convert`, fixa a linha quando a detecção erra.
- **Particularidades de Excel reportadas:**
  - linhas e colunas totalmente vazias;
  - linhas que parecem totais ou subtotais (primeira célula "Total" ou "Subtotal");
  - colunas sem nome.
- **Saída:** texto e `--format json`, no formato de [019](019-saida-json.md), com uma entrada por aba. Nada é gravado.

## Comportamento — `clean --auto`
- **O que aplica:** as correções que o diagnóstico sugerir para aquela aba, com as mesmas regras do `info`:
  - `--trim`, sempre;
  - `--fix-types`, que também trata moeda BR (`R$ 1.234,56`);
  - `--normalize-dates`;
  - `--remove-duplicates`.
- **O que só reporta:** nulos e CPF/CNPJ. Remover linhas com nulo (`--drop-null`) apaga dados, e mascarar documentos muda a representação; nenhum dos dois deve acontecer sem pedido explícito.
- **Particularidades de Excel:** remove as linhas e colunas totalmente vazias. As linhas de total **não** são removidas; só aparecem no relatório (ver questão 2).
- **Combinação com operações explícitas:** `--auto` junto com operações explícitas (`--auto --fill-null 0`) aplica a união das duas. Uma operação incompatível é recusada pelas regras de sempre (`--lowercase` com `--normalize-case`, exit 2).
- **Saída:**
  - Grava em `<nome>_clean.parquet`, ao lado do original, ou em `--output`.
  - Grava também o relatório de qualidade `<nome>_quality.html`, com a infraestrutura da [004](004-profile-relatorio-html.md).
  - Os dois seguem as regras de sobrescrita do CLI: nada existente é substituído sem `--overwrite`, e a checagem é feita antes de processar.
  - Cada gravação tem sua linha "Gravado …" no stderr.
- **Relatório:** o mesmo do `clean` com operações, incluindo a lista das operações que o `--auto` escolheu, para que o resultado seja reproduzível com flags explícitas.
- **Outros formatos:** `--auto` funciona em qualquer formato de entrada, não só Excel. Só a remoção de linhas e colunas vazias e a detecção de cabeçalho são específicas de Excel.

## Critérios de aceite
- [ ] `inspect` lista todas as abas com linhas, colunas, cabeçalho detectado e os problemas de cada uma, em texto e em JSON
- [ ] Uma aba com título nas primeiras linhas tem o cabeçalho detectado e é lida com os nomes de coluna certos; `--header-row N` substitui a detecção
- [ ] `inspect` aponta linhas e colunas vazias, linhas de total e colunas sem nome
- [ ] `clean --auto` aplica `--trim` e as correções sugeridas pelo diagnóstico, e nunca aplica `--drop-null` ou `--normalize-documents` sem pedido explícito
- [ ] O relatório do `--auto` lista as operações escolhidas, e rodar o `clean` com essas flags explícitas dá o mesmo arquivo
- [ ] `--auto` grava `<nome>_clean.parquet` e `<nome>_quality.html` (ou `--output`), sem sobrescrever arquivos existentes sem `--overwrite`
- [ ] Com várias abas e sem `--sheet`, o `clean --auto` segue as regras da [022](022-excel-selecao-de-aba.md): lê a primeira aba com dados e avisa das outras

## Fora de escopo
- Células mescladas, fórmulas e formatação (cores, fontes)
- Remoção automática de linhas de total (ver questão 2)
- `.xls` (Excel antigo) e `.ods`
- Limpeza de várias abas de uma vez, gerando um arquivo por aba

## Questões em aberto
1. **Comando `inspect` ou `info --all-sheets`?** Se um `--all-sheets` for criado no `info` (a [022](022-excel-selecao-de-aba.md) deixou isso fora do escopo), o `inspect` fica com pouca coisa própria: o cabeçalho detectado e as particularidades de Excel. Uma opção é o `inspect` ser o nome Pro para "`info` de todas as abas + particularidades".
2. **Remover as linhas de total no `--auto`?** Elas distorcem somas e contagens, mas a detecção por "Total" na primeira célula pode errar, e apagar uma linha de dado real é pior que manter um total. A proposta é só reportar.
3. **Plano Pro:** o `--sheet` da [022](022-excel-selecao-de-aba.md) fica no Community. Nesta spec, o que é Pro é o `inspect` e o `--auto`.

## Revisão (2026-09-30)
Revisada contra o código da v0.1.0. O que mudou em relação à versão original:
- **Contexto:** registra o que o código já faz com Excel e as duas falhas reproduzidas: abas ignoradas em silêncio e título antes do cabeçalho.
- **Dependência nova da [022](022-excel-selecao-de-aba.md)** (`--sheet`, item F04 do backlog). A versão original tratava várias abas como parte desta spec Pro. Como é um problema de correção que afeta qualquer usuário, a leitura de abas vai para o Community (F04).
- **`--auto` definido com precisão:** as correções que o `info` já sugere, menos `--drop-null` e `--normalize-documents`, que são destrutivas ou mudam a representação. A versão original listava "tratar nulos", o que seria remover dados sem pedido.
- **Novos comportamentos:** `--header-row`, particularidades de Excel reportadas, regras de sobrescrita e confirmação para os dois arquivos gravados, e o relatório do `--auto` listando as operações escolhidas para reprodução.

## Dependências
[002](002-info-diagnostico.md), [005](005-clean-detectar-problemas.md), [006](006-clean-operadores-string.md)–[011](011-clean-colunas.md), [018](018-cpf-cnpj-validacao.md), [004](004-profile-relatorio-html.md) (relatório HTML), [022](022-excel-selecao-de-aba.md) (seleção de aba)
