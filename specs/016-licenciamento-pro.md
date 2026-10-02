# US-016: Licenciamento das funcionalidades Pro

## User story
Como responsável pelo produto, eu quero bloquear as funcionalidades Pro atrás de uma licença/assinatura, para monetizar sem impedir o uso gratuito das funcionalidades básicas (community).

## Contexto
Ver a seção "Onde eu vejo potencial de monetização" da ideia. Community (conversão, estatísticas, profiling básico, limpeza básica, CLI) é grátis. Pro ($49/ano) inclui relatórios HTML avançados, pipelines, IA, entre outros.

**Restrição que a versão original não considerava: o `datatool-cli` é GPLv3** (`LICENSE`, `license = "GPL-3.0-only"` no `pyproject.toml`, decidido no DT03). Qualquer pessoa pode legalmente modificar e redistribuir o código. Uma checagem de licença dentro do próprio pacote GPL pode ser removida por quem quiser, e a versão sem checagem pode ser redistribuída. Para o bloqueio ter efeito, o código Pro precisa estar **fora** do pacote GPL. É o modelo *open core*:
- **`datatool-cli` (GPLv3, PyPI):** as features Community, como hoje, sem nenhuma checagem de licença.
- **`datatool-pro` (licença proprietária, distribuído a quem compra):** as features Pro, que se registram no CLI como plugins e fazem elas mesmas a checagem de licença.

A troca de licença do projeto inteiro também resolveria o problema, mas só vale para versões futuras (a v0.1.0 já foi publicada como GPLv3) e exige que todo o código seja de autoria do dono do projeto. Ver a questão 1.

## Interface proposta
```bash
pip install datatool-pro --index-url <índice privado>   # instala o pacote Pro
datatool license activate <chave>
datatool license status
datatool license remove
DATATOOL_LICENSE=<chave> datatool run pipeline.yaml    # em CI, sem gravar arquivo
```

## Comportamento
- **Plugins:** o `datatool-cli` procura pacotes que declaram o grupo de entry points `datatool.plugins` e registra os comandos deles no `app` do typer. Esse é o único código novo no pacote GPL, e ele é genérico: não sabe o que é Pro nem o que é licença. Sem o `datatool-pro` instalado, os comandos Pro não aparecem no `--help`.
- **Chave de licença:** um documento assinado (e-mail, plano, validade) com uma assinatura Ed25519. O `datatool-pro` traz embutida a chave pública e verifica a assinatura **offline**, sem chamada de rede a cada execução. É a assinatura criptográfica que o DT22 recomendou no lugar da ofuscação caseira que existia antes.
- **Onde a licença fica:**
  - `license activate` valida a chave e a grava em `license.json`, no diretório de configuração do usuário (`platformdirs.user_config_dir("datatool")`, a mesma biblioteca que já decide o diretório de log).
  - `DATATOOL_LICENSE` tem prioridade sobre o arquivo, para CI e contêineres.
- **Validade:** licença vencida continua funcionando por um período de carência (ex.: 14 dias), com aviso no stderr. Depois disso, os comandos Pro são recusados. Revalidação online é opcional e fica fora desta spec.
- **Comando Pro sem licença válida:** mensagem clara com o link de compra, com um exit code próprio (ver questão 2), em texto e em JSON (019). Nenhum processamento acontece antes da checagem.
- **Community nunca é bloqueado:** convert, info, profile, clean, a saída JSON, o servidor MCP e a leitura por URL (001–003, 005–011, 017–021). A licença não é consultada nesses comandos.
- **Servidor MCP:** o `datatool-pro` pode registrar ferramentas Pro no servidor do [020](020-mcp-server.md) pelo mesmo mecanismo de plugins. Elas só aparecem com licença válida.
- **Log e privacidade:** o log registra só "licença válida/inválida/vencida" e o plano, nunca a chave.

## Critérios de aceite
- [ ] Sem nenhum plugin instalado, o `datatool-cli` funciona exatamente como hoje (a suíte atual continua passando) e não contém código de licença
- [ ] Um pacote de teste com entry point `datatool.plugins` tem seus comandos registrados e visíveis no `--help`
- [ ] `license activate` aceita uma chave com assinatura válida e recusa chave adulterada, com assinatura inválida ou vencida além da carência, com mensagem clara
- [ ] A verificação funciona offline (os testes rodam sem rede)
- [ ] `DATATOOL_LICENSE` tem prioridade sobre o arquivo gravado
- [ ] Comando Pro sem licença sai com o exit code definido e o link de compra, sem processar nada, em texto e em JSON
- [ ] A chave nunca aparece no log nem no stdout (`license status` mostra plano, e-mail e validade)
- [ ] Os comandos Community nunca consultam a licença

## Fora de escopo
- Backend de emissão e pagamento de licenças (fluxo de compra, ex.: Gumroad, Lemon Squeezy, GitHub Sponsors). Esta spec cobre só o lado da CLI.
- Revalidação online e revogação de chaves
- Distribuição do `datatool-pro` (índice privado, download após a compra)

## Questões em aberto
1. **Open core com pacote separado, ou mudar a licença do projeto?**
   - A proposta é manter o `datatool-cli` GPLv3 e criar o `datatool-pro` proprietário, que conversa com o CLI só pela interface de plugins. Plugins que se integram ao CLI dessa forma podem levantar dúvida sobre "obra derivada" na GPL; vale uma consulta jurídica antes de vender.
   - A alternativa é relicenciar as próximas versões (ex.: para MIT ou Apache-2.0, e o Pro no mesmo repositório com checagem), o que só é possível se todo o código for do dono do projeto.
   - Uma terceira opção é não bloquear nada e monetizar por suporte ou por um serviço hospedado.
2. **Exit code para "sem licença":** 2 (erro de uso, como os demais erros de configuração) ou um código novo, 4, para que scripts de CI distingam "falta licença" de "opção errada". A proposta é 4.
3. **Ordem de implementação:** esta spec só faz sentido quando existir a primeira feature Pro. A sugestão é implementar primeiro a interface de plugins (pequena, genérica e útil por si só), depois a primeira feature Pro já dentro do `datatool-pro`, e a checagem de licença junto com ela.

## Revisão (2026-09-30)
Revisada contra o código da v0.1.0. O que mudou em relação à versão original:
- **Restrição da GPLv3 (DT03):** um bloqueio dentro do pacote GPL pode ser removido e redistribuído legalmente. A proposta passou de "comandos Pro checam a licença" para *open core*, com um pacote Pro separado que se registra por plugins. É a questão 1, uma decisão de produto e jurídica.
- **Formato da chave definido:** assinatura Ed25519 verificada offline, como recomendado no DT22.
- **Armazenamento definido:** `platformdirs`, que já é dependência, e `DATATOOL_LICENSE` para CI.
- **Novos comportamentos:** carência para licença vencida, comportamento no servidor MCP e no JSON, e a regra de a chave nunca aparecer no log.
- **Lista Community atualizada** com as specs implementadas desde a versão original (017–020) e a 021.

## Dependências
Nenhuma tecnicamente, mas só faz sentido implementar depois que ao menos uma feature Pro existir ([004](004-profile-relatorio-html.md), [012](012-pipeline-automacao.md), [013](013-excel-inspect-auto.md), [014](014-ai-explain.md) ou [015](015-ai-ask.md)). Ver a questão 3.
