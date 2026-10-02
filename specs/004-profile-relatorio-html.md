# US-004: Relatório de profiling em HTML

## User story
Como analista de dados, eu quero exportar o profiling como um relatório HTML, para compartilhar um resultado visual com outras pessoas do time.

## Contexto
Citado explicitamente na ideia como algo "muito mais útil do que simplesmente imprimir estatísticas no terminal". Candidato natural a feature **Pro** (ver [016-licenciamento-pro](016-licenciamento-pro.md)).

O `profile` ([003](003-profile-estatistico.md)) já calcula tudo e monta um documento com as métricas: é o que `--format json` imprime ([019](019-saida-json.md)), gerado por `profiler.to_document` em [src/datatool/profiler.py](../src/datatool/profiler.py). O relatório HTML é **outra forma de mostrar esse mesmo documento**, sem cálculo novo. Assim o HTML e o JSON nunca divergem, e `--columns`, `--max-columns`, `--key` e `--redact-values` valem para o HTML sem trabalho extra.

## Interface proposta
```bash
datatool profile vendas.csv --format html --output relatorio.html
datatool profile vendas.csv --format html --output relatorio.html --redact-values --max-columns 30
```

`html` passa a ser um valor de `--format`, ao lado de `text` e `json`. Como o relatório é um arquivo para compartilhar, `--format html` exige `--output`, do mesmo jeito que `clean --format json` exige `--output`.

## Comportamento
- **Conteúdo:** as mesmas seções do texto e do JSON: resumo do arquivo (caminho, formato, linhas, colunas, tamanho), duplicidade (total e por chave), e um bloco por coluna. Colunas numéricas mostram mínimo, máximo, média, mediana, percentis e outliers, com um histograma ou box plot. Colunas categóricas mostram cardinalidade e valores mais frequentes, com um gráfico de barras. Com colunas truncadas por `--max-columns`, o relatório lista as que ficaram de fora.
- **Autocontido:** CSS e gráficos (SVG) embutidos no próprio arquivo. Sem JavaScript, CDN, fontes externas ou imagens remotas: o relatório abre offline e não faz nenhuma requisição ao ser aberto.
- **Sem dependência nova:** o HTML é montado com a biblioteca padrão (`html.escape` e templates em string). Um motor de templates (Jinja2) só entra se o relatório crescer a ponto de justificar.
- **Segurança:** todo texto vindo do arquivo (nomes de coluna, valores frequentes, caminho) passa por `html.escape`. Uma coluna chamada `<script>alert(1)</script>` aparece como texto e não executa nada. É o mesmo cuidado de qualquer página que mostra dado de terceiros.
- **Privacidade:** os valores mais frequentes são valores de célula. Com `--redact-values`, eles saem do relatório e as contagens ficam, como no texto e no JSON. Vale lembrar que o relatório existe para ser compartilhado.
- **Gravação:** segue as regras do `clean --output` e do `convert`:
  - um destino existente só é substituído com `--overwrite`;
  - a checagem acontece antes de processar;
  - uma linha de confirmação vai para o stderr (`Gravado relatorio.html (html): 12 colunas`);
  - o log registra a gravação, sem valores de célula.
- **Tamanho:** o relatório depende do número de colunas, não do de linhas, porque mostra estatísticas agregadas. Em arquivos largos, `--max-columns` limita o tamanho.
- **Servidor MCP:** fora do escopo. Agentes consomem o JSON, que a ferramenta `datatool_profile` já devolve.

## Critérios de aceite
- [ ] `profile --format html --output arquivo.html` grava um HTML válido com as métricas do documento de `--format json` para o mesmo arquivo e as mesmas opções
- [ ] `--format html` sem `--output` é erro claro, exit code 2, sem processar nada
- [ ] O arquivo não referencia nenhum recurso externo (sem `<script src>`, `<link href>`, `<img src>` ou `url(...)` com http/https) e abre offline
- [ ] Nomes de coluna e valores com `<`, `>`, `&` e aspas aparecem escapados, e nenhum conteúdo do arquivo vira marcação
- [ ] `--redact-values` remove os valores mais frequentes do HTML e mantém as contagens
- [ ] `--columns`, `--max-columns` e `--key` têm no HTML o mesmo efeito que no JSON
- [ ] Destino existente sem `--overwrite` é recusado (exit code 2) antes do processamento, e a confirmação de gravação vai para o stderr
- [ ] Um arquivo de 200 mil linhas e 50 colunas gera um relatório que abre sem travar num navegador comum. O tamanho do HTML não cresce com o número de linhas.
- [ ] O `--format html` só é aceito no `profile`: nos outros comandos é recusado pelo próprio CLI

## Fora de escopo
- Customização de tema/branding do relatório
- Relatório HTML do `info` e do `clean` (o relatório de qualidade da [013](013-excel-inspect-auto.md) pode reaproveitar esta infraestrutura)
- Gráficos interativos (exigiriam JavaScript)

## Questões em aberto
1. **`--format html --output` ou uma opção própria (`--html relatorio.html`)?** A proposta segue o padrão do `clean --format json --output`. Uma opção própria permitiria gerar o HTML e imprimir o texto no mesmo comando.
2. **Plano Pro, e a primeira feature Pro.** Esta é a candidata mais simples a primeira feature Pro, mas o bloqueio por licença depende da [016](016-licenciamento-pro.md), que por sua vez tem uma questão de licença do código (GPLv3) a resolver antes. Até lá, a spec pode ser implementada sem bloqueio, ou esperar a 016.

## Revisão (2026-09-30)
Revisada contra o código da v0.1.0. O que mudou em relação à versão original:
- **Interface:** `profile --output report.html` virou `--format html --output`. `--output` sozinho não existe no `profile`, e no `clean` ele grava o dataset, não um relatório.
- **Fonte dos dados:** o HTML é gerado a partir do documento do `--format json` (`profiler.to_document`), que não existia quando a spec foi escrita. Isso garante os mesmos números e herda `--columns`/`--max-columns`/`--redact-values`.
- **Critérios novos:** escape de HTML, privacidade com `--redact-values`, regras de sobrescrita e confirmação iguais às do resto do CLI (DT04, v0.1).
- **Critério reescrito:** "até ~200 mil linhas sem travar o navegador" virou tamanho independente do número de linhas, porque o relatório só tem estatísticas agregadas.

## Dependências
[003-profile-estatistico](003-profile-estatistico.md), [019-saida-json](019-saida-json.md) (documento que o HTML renderiza), [016-licenciamento-pro](016-licenciamento-pro.md) (bloqueio Pro, ver questão 2)
