# US-005: Detectar problemas de qualidade (modo diagnóstico do clean)

## User story
Como analista de dados, eu quero rodar `clean` sem nenhuma flag e ver um relatório dos problemas encontrados por coluna, para decidir quais operações de limpeza aplicar antes de alterar o arquivo.

## Contexto
Camada 3 da ideia ("Data cleaning"), primeiro passo antes de aplicar qualquer transformação destrutiva.

## Interface proposta
```bash
datatool clean clientes.csv
```
Saída no formato do exemplo da ideia (problema por coluna: e-mails inválidos, variação de formato de telefone, espaços extras, duplicidade de CPF, inconsistência de capitalização em cidade etc.).

## Critérios de aceite
- [ ] Sem flags de operação, o comando **não** grava nenhum arquivo — é somente leitura/diagnóstico
- [ ] Lista por coluna: valores inválidos (ex.: formato de e-mail), variação de formatos (ex.: telefone), espaços extras nas bordas, duplicidade por chave, inconsistência de capitalização
- [ ] Formato de saída consistente com [002-info-diagnostico](002-info-diagnostico.md)

## Fora de escopo
- Aplicar as correções (specs 006-011)

## Dependências
[001-convert](001-convert.md)
