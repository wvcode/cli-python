# US-016: Licenciamento das funcionalidades Pro

## User story
Como responsável pelo produto, eu quero bloquear as funcionalidades Pro atrás de uma licença/assinatura, para monetizar sem impedir o uso gratuito das funcionalidades básicas (community).

## Contexto
Ver seção "Onde eu vejo potencial de monetização" da ideia: Community (conversão, estatísticas, profiling básico, limpeza básica, CLI) é grátis; Pro ($49/ano) inclui relatórios HTML avançados, pipelines, IA, entre outros.

## Interface proposta
```bash
datatool license activate <chave>
```

## Critérios de aceite
- [ ] `license activate` valida a chave e a armazena localmente (ex.: arquivo de config do usuário)
- [ ] Comandos Pro ([004-profile-relatorio-html](004-profile-relatorio-html.md), [012-pipeline-automacao](012-pipeline-automacao.md), [013-excel-inspect-auto](013-excel-inspect-auto.md), [014-ai-explain](014-ai-explain.md), [015-ai-ask](015-ai-ask.md)) verificam a licença antes de executar e retornam mensagem clara com link de compra caso não haja licença válida
- [ ] Comandos Community ([001-convert](001-convert.md), [002-info-diagnostico](002-info-diagnostico.md), [003-profile-estatistico](003-profile-estatistico.md), [005](005-clean-detectar-problemas.md)-[011](011-clean-colunas.md)) nunca são bloqueados
- [ ] A verificação de licença é local (sem chamada de rede a cada execução); revalidação periódica (ex.: a cada N dias) pode checar online

## Fora de escopo
- Backend de emissão/pagamento de licenças (fluxo de compra em si, ex.: Gumroad/GitHub Sponsors) — este spec cobre apenas o lado da CLI

## Dependências
Nenhuma tecnicamente, mas só faz sentido implementar depois que ao menos uma feature Pro existir (004, 012, 013, 014 ou 015).
