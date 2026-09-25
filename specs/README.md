# Specs

Uma spec por user story, derivadas de [ideia.md](ideia.md), na ordem sugerida de implementação.

| # | Spec | Camada | Status atual | Depende de |
|---|------|--------|---------------|------------|
| 001 | [Converter arquivo entre formatos](001-convert.md) | Conversão | Implementado | — |
| 002 | [Diagnóstico automático ao abrir um arquivo](002-info-diagnostico.md) | Diagnóstico | Implementado | 001 |
| 003 | [Profiling estatístico de um dataset](003-profile-estatistico.md) | Profiling | Implementado | 001 |
| 004 | [Relatório de profiling em HTML](004-profile-relatorio-html.md) | Profiling (Pro) | Não implementado | 003 |
| 005 | [Detectar problemas de qualidade](005-clean-detectar-problemas.md) | Cleaning | Implementado | 001 |
| 006 | [Operadores de limpeza de texto](006-clean-operadores-string.md) | Cleaning | Implementado | 001, 005 |
| 007 | [Remover duplicidades](007-clean-remover-duplicidades.md) | Cleaning | Implementado | 001, 006 |
| 008 | [Tratar valores nulos](008-clean-tratar-nulos.md) | Cleaning | Implementado | 001, 006, 007 |
| 009 | [Normalizar formatos de data](009-clean-normalizar-datas.md) | Cleaning | Implementado | 001, 006 |
| 010 | [Corrigir tipos de colunas](010-clean-corrigir-tipos.md) | Cleaning | Implementado | 001, 006 |
| 011 | [Renomear e remover colunas](011-clean-colunas.md) | Cleaning | Implementado | 001, 006 |
| 012 | [Pipeline via arquivo YAML](012-pipeline-automacao.md) | Automação (Pro) | Não implementado | 006-011 |
| 013 | [Inspeção e limpeza automática de Excel](013-excel-inspect-auto.md) | Nicho Excel (Pro) | Não implementado | 002, 004, 005-011 |
| 014 | [Explicação em linguagem natural](014-ai-explain.md) | IA opcional (Pro) | Não implementado | 003, 005 |
| 015 | [Perguntas em linguagem natural](015-ai-ask.md) | IA opcional (Pro) | Não implementado | 014 |
| 016 | [Licenciamento das funcionalidades Pro](016-licenciamento-pro.md) | Monetização | Não implementado | pelo menos uma feature Pro |
| 017 | [Detectar delimitador e encoding de CSV, com log de execução](017-csv-delimitador-encoding.md) | Conversão + infra | Implementado | 001 |
| 018 | [Validar e normalizar CPF/CNPJ](018-cpf-cnpj-validacao.md) | Cleaning | Não implementado | 005, 010 |
| 019 | [Saída estruturada em JSON](019-saida-json.md) | Diagnóstico/Profiling | Implementado | 002, 003, 005 |

## MVP v0.1

Segundo a ideia, o menor produto funcional cobre: **001, 002, 003, 005, 006, 007, 008, 009, 010, 011** (comandos `info`, `profile`, `convert`, `clean` com os ~10 operadores básicos). As demais specs (004, 012-016) são evoluções pós-MVP e concentram o potencial de monetização Pro.

**Progresso do MVP: 10/10** — implementadas 001, 002, 003, 005, 006, 007, 008, 009, 010, 011.

## Além das specs

Propostas de features ainda sem spec (lacunas encontradas no código, itens da ideia sem spec e oportunidades para o mercado BR) estão em [backlog-novas-features.md](backlog-novas-features.md).

## Template usado em cada spec
- User story (Como / eu quero / para que)
- Contexto (por que importa, referência à ideia)
- Interface proposta (comando de exemplo)
- Critérios de aceite (checklist verificável)
- Fora de escopo (quando relevante)
- Dependências
