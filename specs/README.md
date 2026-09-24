# Specs

Uma spec por user story, derivadas de [ideia.md](ideia.md), na ordem sugerida de implementação.

| # | Spec | Camada | Status atual | Depende de |
|---|------|--------|---------------|------------|
| 001 | [Converter arquivo entre formatos](001-convert.md) | Conversão | Implementado | — |
| 002 | [Diagnóstico automático ao abrir um arquivo](002-info-diagnostico.md) | Diagnóstico | Implementado | 001 |
| 003 | [Profiling estatístico de um dataset](003-profile-estatistico.md) | Profiling | Não implementado | 001 |
| 004 | [Relatório de profiling em HTML](004-profile-relatorio-html.md) | Profiling (Pro) | Não implementado | 003 |
| 005 | [Detectar problemas de qualidade](005-clean-detectar-problemas.md) | Cleaning | Não implementado | 001 |
| 006 | [Operadores de limpeza de texto](006-clean-operadores-string.md) | Cleaning | Não implementado | 001 |
| 007 | [Remover duplicidades](007-clean-remover-duplicidades.md) | Cleaning | Não implementado | 001 |
| 008 | [Tratar valores nulos](008-clean-tratar-nulos.md) | Cleaning | Não implementado | 001 |
| 009 | [Normalizar formatos de data](009-clean-normalizar-datas.md) | Cleaning | Não implementado | 001 |
| 010 | [Corrigir tipos de colunas](010-clean-corrigir-tipos.md) | Cleaning | Não implementado | 001 |
| 011 | [Renomear e remover colunas](011-clean-colunas.md) | Cleaning | Não implementado | 001 |
| 012 | [Pipeline via arquivo YAML](012-pipeline-automacao.md) | Automação (Pro) | Não implementado | 006-011 |
| 013 | [Inspeção e limpeza automática de Excel](013-excel-inspect-auto.md) | Nicho Excel (Pro) | Não implementado | 002, 004, 005-011 |
| 014 | [Explicação em linguagem natural](014-ai-explain.md) | IA opcional (Pro) | Não implementado | 003, 005 |
| 015 | [Perguntas em linguagem natural](015-ai-ask.md) | IA opcional (Pro) | Não implementado | 014 |
| 016 | [Licenciamento das funcionalidades Pro](016-licenciamento-pro.md) | Monetização | Não implementado | pelo menos uma feature Pro |

## MVP v0.1

Segundo a ideia, o menor produto funcional cobre: **001, 002, 003, 005, 006, 007, 008, 009, 010, 011** (comandos `info`, `profile`, `convert`, `clean` com os ~10 operadores básicos). As demais specs (004, 012-016) são evoluções pós-MVP e concentram o potencial de monetização Pro.

## Template usado em cada spec
- User story (Como / eu quero / para que)
- Contexto (por que importa, referência à ideia)
- Interface proposta (comando de exemplo)
- Critérios de aceite (checklist verificável)
- Fora de escopo (quando relevante)
- Dependências
