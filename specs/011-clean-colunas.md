# US-011: Renomear e remover colunas

## User story
Como analista de dados, eu quero renomear ou remover colunas de um dataset, para padronizar o schema antes de usá-lo em outra ferramenta.

## Interface proposta
```bash
datatool clean vendas.csv --rename-columns old_name:new_name,foo:bar
datatool clean vendas.csv --remove-columns coluna_interna,coluna_temp
```

## Critérios de aceite
- [ ] `--rename-columns` renomeia as colunas especificadas preservando os dados
- [ ] `--remove-columns` remove as colunas especificadas
- [ ] Erro claro (sem alterar o arquivo) se uma coluna referenciada não existir no dataset

## Dependências
[001-convert](001-convert.md)
