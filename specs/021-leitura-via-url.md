# US-021: Ler o arquivo de entrada a partir de uma URL

## User story
Como analista que recebe dados publicados na web (portal de dados abertos, planilha exportada do Google Sheets, arquivo num bucket público, anexo num sistema interno), eu quero passar a URL direto para o datatool, para diagnosticar, perfilar, limpar ou converter o arquivo sem precisar baixá-lo antes com outra ferramenta.

## Contexto
Ideia originada fora de [ideia.md](ideia.md) e do [backlog](backlog-novas-features.md). Ver [F17](backlog-novas-features.md#f17--ler-o-arquivo-de-entrada-a-partir-de-uma-url), adicionada junto com esta spec.

Hoje os quatro comandos só aceitam caminhos locais. A primeira verificação de [src/datatool/loading.py](../src/datatool/loading.py) (`os.path.exists`) recusa a URL:

```text
$ datatool info https://exemplo.gov.br/dados/vendas.csv
O arquivo https://exemplo.gov.br/dados/vendas.csv não existe.
```

O contorno é baixar antes (`curl -sL URL -o vendas.csv && datatool info vendas.csv`), o que funciona, mas é um passo a mais, deixa um arquivo solto e não está disponível para quem usa o datatool pelo servidor MCP de [020](020-mcp-server.md).

**Por que baixar para um arquivo temporário, e não passar a URL ao polars.** O polars lê CSV, Parquet e JSON direto de HTTP, mas isso deixaria de fora metade do que o datatool faz na leitura:
- a detecção de delimitador e encoding de [017](017-csv-delimitador-encoding.md) abre o arquivo local para examinar os bytes (`;`, `cp1252`), e é o que faz o CSV exportado pelo Excel em português funcionar sem opções;
- o SQLite precisa de um arquivo no disco, e escolhe a tabela pelo nome do arquivo;
- o resumo do arquivo no JSON de [019](019-saida-json.md) traz o tamanho em bytes.

Baixar para um arquivo temporário e seguir o fluxo normal mantém tudo isso funcionando para todos os formatos, com uma mudança concentrada num único ponto (`load_input`).

## Interface proposta
```bash
datatool info https://dados.exemplo.gov.br/vendas.csv
datatool profile "https://docs.google.com/spreadsheets/d/<id>/export?format=csv"
datatool clean https://exemplo.com/clientes.xlsx --fix-types --output clientes.parquet
datatool convert https://exemplo.com/eventos.jsonl eventos.parquet
```

Onde hoje se passa o caminho do arquivo de **entrada** (`FILENAME` de `convert`, `info`, `profile` e `clean`), passa a ser aceita também uma URL `http://` ou `https://`. Nenhuma opção nova é necessária para o caso comum. `--from-type` passa a existir também em `info`, `profile` e `clean` (hoje só o `convert` tem), para URLs cujo formato não dá para descobrir (ver abaixo).

## Comportamento — download
1. **Quando.** O argumento de entrada é tratado como URL se começar com `http://` ou `https://`. Qualquer outro valor continua sendo um caminho local, exatamente como hoje.
2. **Para onde.** O arquivo é baixado para um diretório temporário próprio da execução, **mantendo o nome do arquivo da URL** (`.../dados/vendas.db` → `<tmp>/vendas.db`), porque o leitor de SQLite escolhe a tabela pelo nome do arquivo. O diretório é apagado ao fim do comando, com sucesso ou com erro.
3. **Como.** Com a biblioteca padrão (`urllib.request`), sem dependência nova:
   - redirecionamentos são seguidos, até 5;
   - o certificado TLS é sempre verificado;
   - variáveis de proxy do ambiente (`HTTPS_PROXY`, `HTTP_PROXY`, `NO_PROXY`) são respeitadas, como no `pip` e no `curl`;
   - `User-Agent: datatool/<versão>`;
   - o corpo é gravado em blocos, sem passar inteiro pela memória.
4. **Limites.**
   - **Tamanho:** no máximo **500 MB** baixados por padrão, configurável por `DATATOOL_URL_MAX_MB`. O limite é conferido no `Content-Length`, quando o servidor informa, e também durante o download, porque o cabeçalho pode faltar ou mentir. Passou do limite, o download é interrompido e o arquivo parcial é apagado.
   - **Tempo:** **30 s** sem receber dados (conexão ou leitura), configurável por `DATATOOL_URL_TIMEOUT`. Não há limite de tempo total: um arquivo grande numa conexão lenta pode demorar, desde que continue chegando.
5. **Sem cache.** Cada execução baixa de novo. Quem vai rodar vários comandos sobre o mesmo arquivo deve baixá-lo uma vez, por exemplo com `convert URL local.parquet`.

## Comportamento — formato do arquivo
O formato continua vindo da extensão, agora a do **caminho da URL**, ignorando query string e fragmento (`.../vendas.csv?token=abc#x` → `csv`), depois de decodificar `%xx`. Quando o caminho não tem extensão conhecida (ex.: `.../export?format=csv` do Google Sheets), vale, nesta ordem:
1. `--from-type`, se informado;
2. o `Content-Type` da resposta (`text/csv` → csv; `application/json` → json; `application/x-ndjson` e `application/jsonl` → jsonl; `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` → xlsx; `application/vnd.apache.parquet` e `application/x-parquet` → parquet; `application/vnd.sqlite3` e `application/x-sqlite3` → sqlite), ignorando parâmetros como `; charset=utf-8`;
3. senão, erro dizendo que o formato não pôde ser inferido e sugerindo `--from-type`, nos moldes da mensagem que já existe para caminhos locais.

Um `Content-Type` genérico (`application/octet-stream`, `text/plain`) não decide o formato. Se a extensão da URL e o `Content-Type` discordarem, vale a extensão, que é o que a pessoa vê e o comportamento que ela já conhece dos arquivos locais.

Sem extensão no caminho, o arquivo temporário recebe um nome derivado do formato (`download.csv`, `download.db` etc.).

## Comportamento — saída, log e privacidade
- **Onde a URL aparece.** A URL aparece como a pessoa a passou em "Arquivo:" no texto, em `file.path` no JSON e nos comandos sugeridos pelo `info` (`datatool clean https://... --fix-types`, que continua funcionando). Há uma exceção: credenciais embutidas (`https://usuario:senha@host/...`) são removidas, porque vão para o stdout, que pode ir para um log de CI.
- **`file.size_bytes`** é o tamanho baixado.
- **Log de execução** ([017](017-csv-delimitador-encoding.md)): registra o download (host e caminho, tamanho, `Content-Type`, duração), mas **nunca a query string nem as credenciais**. URLs assinadas (S3 pré-assinada, links com `?token=`) carregam o segredo na query, e o log fica no disco muito depois da execução. O argumento `filename` no início do log passa pela mesma limpeza.
- **Destinos continuam locais.** `--output` do `clean` e `TO_FILENAME` do `convert` não aceitam URL (ver "Fora de escopo"); passar uma URL ali é erro claro, com exit code 2.

## Comportamento — erros

| Situação | Exit code | Mensagem (exemplo) |
|----------|-----------|--------------------|
| Esquema não suportado (`ftp://`, `s3://`, `file://`) | 2 | `Esquema de URL não suportado: s3. Use http:// ou https://.` |
| HTTP 404 ou 410 | 2 | `O arquivo https://.../vendas.csv não existe (HTTP 404).` (o mesmo código de um arquivo local inexistente) |
| Outro status HTTP de erro (401, 403, 500, ...) | 1 | `Não foi possível baixar https://.../vendas.csv: HTTP 403 Forbidden.` |
| Falha de rede, DNS, TLS ou tempo esgotado | 1 | `Não foi possível baixar https://.../vendas.csv: tempo esgotado (30 s sem receber dados).` |
| Arquivo maior que o limite | 1 | `https://.../vendas.csv passa do limite de 500 MB. Aumente com DATATOOL_URL_MAX_MB ou baixe o arquivo antes.` |
| Formato não inferível | 2 | `Não foi possível inferir o formato de https://.../export. Use --from-type para informar o formato.` |

Todas essas mensagens passam pela mesma limpeza da URL (sem credenciais e sem query) e saem em texto ou em JSON, conforme `--format`, como os demais erros de [019](019-saida-json.md).

## Comportamento — servidor MCP
URLs ficam **desligadas por padrão** no `datatool-mcp` ([020](020-mcp-server.md)). Hoje o servidor só enxerga arquivos dentro de `--root`. Aceitar URLs deixaria o agente fazer o computador de quem o roda buscar qualquer endereço de rede, inclusive serviços internos que não estão expostos à internet (SSRF). Uma instrução maliciosa dentro de um documento lido pelo agente bastaria para isso.

- `datatool-mcp --allow-urls` liga URLs em `filename`. Destinos (`output`, `to_filename`) continuam presos a `--root`.
- Mesmo com `--allow-urls`, o servidor recusa URLs cujo host resolva para endereço de loopback, rede privada, link-local ou reservado (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16` (inclui o `169.254.169.254` de metadados de nuvem), `::1`, `fc00::/7`, `fe80::/10`). A checagem vale também para o destino de cada redirecionamento.
- Sem `--allow-urls`, uma URL em `filename` volta como erro de ferramenta com `isError: true` e mensagem dizendo como ligar, sem tentar a conexão.

O CLI não tem essa restrição: quem digita a URL no terminal é quem decidiu acessá-la, o mesmo raciocínio de [020](020-mcp-server.md) para os guardrails que ficam só na camada MCP.

## Critérios de aceite
**Leitura**
- [ ] `info`, `profile`, `clean` e `convert` aceitam uma URL `http://`/`https://` no lugar do arquivo de entrada, para todos os formatos suportados (CSV, JSON, JSONL, Excel, Parquet, Feather, Avro, SQLite)
- [ ] O resultado para uma URL é idêntico ao do mesmo arquivo lido localmente (texto e JSON), exceto pelo caminho, que mostra a URL
- [ ] CSV com `;` e `cp1252` baixado por URL é lido sem opções, como o local ([017](017-csv-delimitador-encoding.md)); `--sep`/`--encoding` continuam funcionando
- [ ] SQLite por URL escolhe a tabela pelo nome do arquivo na URL, como o local
- [ ] O diretório temporário é apagado ao fim do comando, com sucesso, com erro (inclusive erro de leitura depois do download) e com exceção inesperada
- [ ] Caminhos locais funcionam exatamente como antes: a suíte existente passa sem alteração, e a saída do CLI para arquivos locais não muda

**Formato**
- [ ] A extensão vem do caminho da URL, ignorando query string e fragmento
- [ ] Sem extensão conhecida, `--from-type` e depois o `Content-Type` decidem o formato, nessa ordem; sem nenhum dos dois, erro com exit code 2 sugerindo `--from-type`
- [ ] `--from-type` existe em `info`, `profile` e `clean`, e também funciona com arquivos locais

**Limites e erros**
- [ ] Download acima de `DATATOOL_URL_MAX_MB` (padrão 500) é interrompido, com erro, exit code 1 e o arquivo parcial apagado, tanto com `Content-Length` quanto sem
- [ ] Servidor sem enviar dados por `DATATOOL_URL_TIMEOUT` segundos (padrão 30) gera erro com exit code 1
- [ ] Os erros da tabela acima têm as mensagens e os exit codes indicados, em texto e em JSON
- [ ] `--output`/`TO_FILENAME` com URL é recusado com exit code 2, sem baixar nada

**Privacidade**
- [ ] Nenhuma query string ou credencial de URL aparece no log de execução, nem no `filename` do início, nem nas mensagens de erro
- [ ] Credenciais embutidas (`usuario:senha@`) não aparecem no stdout (texto e JSON)

**MCP**
- [ ] Sem `--allow-urls`, URL em `filename` é recusada sem nenhuma conexão
- [ ] Com `--allow-urls`, URLs públicas funcionam, e hosts que resolvem para endereço privado, loopback ou link-local são recusados, inclusive quando só o destino de um redirecionamento é privado
- [ ] `output`/`to_filename` continuam presos a `--root`, com ou sem `--allow-urls`

**Testes**
- [ ] Os testes usam um servidor HTTP local (`http.server` numa thread), sem acesso à internet, e cobrem: cada formato, redirecionamento, 404, 403, tempo esgotado, limite de tamanho (com e sem `Content-Length`), formato pelo `Content-Type` e limpeza do diretório temporário

## Fora de escopo
- **Gravar em URL** (`--output https://...`, upload). É outro problema: autenticação, método HTTP e semântica de sobrescrita. Se houver demanda, é uma spec própria.
- **Autenticação.** Cabeçalhos (`Authorization`), tokens e cookies não são enviados. URLs pré-assinadas e com token na query já funcionam, porque a credencial está na própria URL. Para o resto, baixa-se antes.
- **Outros esquemas.** `s3://`, `gs://`, `az://` e bancos de dados são o item [F14](backlog-novas-features.md#f14--conectores-postgresql-s3) (conectores, plano Team); `ftp://` e `file://` não estão previstos.
- **Cache de downloads** e **leitura em streaming** sem baixar o arquivo inteiro. O arquivo continua carregado inteiro na memória, como os locais (ver [F12](backlog-novas-features.md#f12--arquivos-grandes-via-modo-lazystreaming)).
- **Barra de progresso.** O stdout pode estar redirecionado (CSV do `convert` sem destino), e o stderr leva o relatório do `clean`. Uma barra de progresso fica para quando houver uma opção de verbosidade.

## Questões em aberto
Decisões desta spec que merecem confirmação antes da implementação:
1. **Limite padrão de 500 MB.** Escolhido porque o arquivo inteiro vai para a memória depois do download. Um limite menor (100 MB) protege máquinas modestas; um maior evita que a pessoa precise da variável de ambiente para arquivos legítimos.
2. **HTTP 404 com exit code 2.** Escolhido para bater com "arquivo local não existe" (2), de modo que scripts tratem os dois casos igual. A alternativa é tratar toda falha de download como 1 (falha de leitura).
3. **`--from-type` nos quatro comandos.** Necessário para URLs sem extensão e sem `Content-Type` útil, e útil também para arquivos locais com extensão errada. Estende a interface de `info`, `profile` e `clean`.

## Dependências
[001-convert](001-convert.md) (leitura e inferência por extensão), [017-csv-delimitador-encoding](017-csv-delimitador-encoding.md) (detecção de CSV e log), [019-saida-json](019-saida-json.md) (resumo do arquivo e erros em JSON), [020-mcp-server](020-mcp-server.md) (sandbox e guardrails do servidor MCP).
