# US-002: Diagnóstico automático ao abrir um arquivo

## User story
Como analista que recebeu um arquivo de terceiros, eu quero rodar um comando e ver um diagnóstico automático dos problemas do arquivo, para decidir rapidamente o que precisa ser corrigido antes de analisar os dados.

## Contexto
Este é o diferencial comercial citado na ideia: a ferramenta não só converte, ela **entende o arquivo e sugere operações**.

## Interface proposta
```bash
datatool info clientes.csv
```
Saída no formato do exemplo da ideia: linhas, colunas, tamanho, lista de problemas (⚠) e sugestões numeradas de comandos a executar.

## Critérios de aceite
- [ ] Mostra número de linhas, colunas e tamanho do arquivo
- [ ] Detecta e lista: valores nulos por coluna, duplicidades, colunas com múltiplos formatos de data, colunas numéricas armazenadas como texto
- [ ] Lista sugestões acionáveis (ex.: "Corrigir tipos", "Remover duplicidades") apontando o comando `datatool clean` correspondente
- [ ] Funciona para CSV, JSON, Excel e Parquet
- [ ] Executa em tempo aceitável para arquivos de até ~200 mil linhas

## Fora de escopo
- Corrigir os problemas (isso é `datatool clean`, specs 005-011)

## Dependências
[001-convert](001-convert.md) para a camada de leitura de arquivos. Reaproveita as heurísticas de detecção que também serão usadas em [005-clean-detectar-problemas](005-clean-detectar-problemas.md).
