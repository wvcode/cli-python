# US-002: Diagnóstico automático ao abrir um arquivo

## User story
Como analista que recebeu um arquivo de terceiros, eu quero rodar um comando e ver um diagnóstico automático dos problemas do arquivo, para decidir rapidamente o que precisa ser corrigido antes de analisar os dados.

## Contexto
Este é o diferencial comercial citado na ideia: a ferramenta não só converte, ela **entende o arquivo e sugere operações**.

Implementado em [src/info.py](../src/info.py) (orquestração: leitura, impressão) e [src/quality.py](../src/quality.py) (heurísticas de detecção, reutilizáveis pela futura spec 005). A leitura reaproveita `infer_file_type`/`read_function` de [001-convert](001-convert.md).

## Interface proposta
```bash
datatool info clientes.csv
```
Saída no formato do exemplo da ideia: linhas, colunas, tamanho, lista de problemas (⚠) e sugestões numeradas de comandos a executar.

## Critérios de aceite
- [x] Mostra número de linhas, colunas e tamanho do arquivo
- [x] Detecta e lista: valores nulos por coluna, duplicidades, colunas com múltiplos formatos de data, colunas numéricas armazenadas como texto
- [x] Lista sugestões acionáveis (ex.: "Corrigir tipos", "Remover duplicidades") apontando o comando `datatool clean` correspondente
- [x] Funciona para CSV, JSON, Excel e Parquet
- [x] Executa em tempo aceitável para arquivos de até ~200 mil linhas (~0,3s em teste manual com 200 mil linhas)

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestInfoCommand`).

## Heurísticas de detecção (nota de implementação)
- **Nulos**: contagem por coluna (`df.null_count()`), reportada apenas para colunas com contagem > 0.
- **Duplicidades**: linhas totalmente duplicadas (`df.height - df.unique().height`) — não tenta identificar uma coluna-chave (ex.: CPF) automaticamente, por ser um heurística mais ambígua e fora do escopo desta spec.
- **Formatos de data**: amostra até 2.000 valores não nulos de cada coluna texto; se ≥60% da amostra casar com algum padrão de data conhecido (`yyyy-mm-dd`, `dd/mm/yyyy`, `dd-mm-yyyy`, etc.) e houver ≥2 formatos distintos, a coluna é reportada.
- **Numérico como texto**: mesma amostragem; se ≥90% dos valores de uma coluna texto (que não foi classificada como data) parecerem numéricos (inteiro/decimal, incluindo separador de milhar `.`/decimal `,` do padrão BR), a coluna é reportada.
- Amostragem (2.000 valores) existe para manter o tempo de execução aceitável em arquivos grandes sem percorrer a coluna inteira.

## Fora de escopo
- Corrigir os problemas (isso é `datatool clean`, specs 005-011)
- Detectar duplicidade por coluna-chave específica (ex.: "127 CPFs duplicados") — a implementação atual reporta duplicidade de linha inteira

## Dependências
[001-convert](001-convert.md) para a camada de leitura de arquivos. Reaproveita as heurísticas de detecção que também serão usadas em [005-clean-detectar-problemas](005-clean-detectar-problemas.md).
