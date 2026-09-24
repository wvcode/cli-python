# US-005: Detectar problemas de qualidade (modo diagnóstico do clean)

## User story
Como analista de dados, eu quero rodar `clean` sem nenhuma flag e ver um relatório dos problemas encontrados por coluna, para decidir quais operações de limpeza aplicar antes de alterar o arquivo.

## Contexto
Camada 3 da ideia ("Data cleaning"), primeiro passo antes de aplicar qualquer transformação destrutiva.

Implementado em [src/clean.py](../src/clean.py) (leitura + impressão, no mesmo padrão de [src/info.py](../src/info.py)) e nos detectores adicionados a [src/quality.py](../src/quality.py) (`detect_invalid_emails`, `detect_phone_format_variance`, `detect_leading_trailing_whitespace`, `detect_key_duplicates`, `detect_case_inconsistency`, orquestrados por `analyze_clean`).

## Interface proposta
```bash
datatool clean clientes.csv
```
Saída no formato do exemplo da ideia (problema por coluna: e-mails inválidos, variação de formato de telefone, espaços extras, duplicidade de CPF, inconsistência de capitalização em cidade etc.).

## Critérios de aceite
- [x] Sem flags de operação, o comando **não** grava nenhum arquivo — é somente leitura/diagnóstico
- [x] Lista por coluna: valores inválidos (ex.: formato de e-mail), variação de formatos (ex.: telefone), espaços extras nas bordas, duplicidade por chave, inconsistência de capitalização
- [x] Formato de saída consistente com [002-info-diagnostico](002-info-diagnostico.md) (mesmo cabeçalho `Arquivo`/`Linhas`/`Colunas`)

Coberto por testes em [src/test_cli.py](../src/test_cli.py) (`TestCleanCommand`). Testado manualmente com 200 mil linhas (~0,3s).

## Nota de implementação — heurísticas
Todas de conteúdo (não dependem do nome da coluna), consistente com as heurísticas de [002](002-info-diagnostico.md)/[003](003-profile-estatistico.md):
- **E-mail inválido**: coluna é considerada "parece e-mail" se ≥50% dos valores não nulos contêm `@`; dentro dela, valores que não casam com `^[^@\s]+@[^@\s]+\.[^@\s]+$` são contados como inválidos (checagem de formato simples, não RFC completa).
- **Variação de formato de telefone**: mesma técnica de amostragem/classificação de shape usada para datas em 002 — reconhece formatos comuns brasileiros (`(dd) ddddd-dddd`, `dd ddddd-dddd`, `dddddddddd`, `+dd dd ddddd-dddd`, etc.); reporta quando ≥2 formatos distintos aparecem na amostra.
- **Espaços extras**: contagem exata (vetorizada, não amostrada) de valores onde `valor != valor.strip()`.
- **Duplicidade por chave**: diferente da duplicidade de linha inteira usada em [002](002-info-diagnostico.md)/[003](003-profile-estatistico.md) — aqui cada coluna é avaliada isoladamente; uma coluna "parece chave" quando ≥95% dos seus valores não nulos são únicos (mínimo de 5 valores não nulos), e o que sobra da diferença `não-nulos - únicos` é reportado como duplicado.
- **Inconsistência de capitalização**: agrupa valores distintos (até 2.000, mesmo limite de amostragem do módulo) por forma normalizada (`casefold`); grupos com mais de uma variante são reportados, listando até 10 variantes por coluna.

## Fora de escopo
- Aplicar as correções (specs 006-011)

## Dependências
[001-convert](001-convert.md)
