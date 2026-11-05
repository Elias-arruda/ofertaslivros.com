# Spec: analytics e painel de monitoramento

Plano do agent-dados, aprovado pelo Elias na sessão de 2026-11-04. Nada daqui está implementado ainda; cada fase entra por PR próprio.

## Objetivo

Medir o site e mostrar ao Elias, num painel privado:
- acessos;
- cliques nos links de afiliado (`/r/`), por livro, loja, nicho e canal;
- termos buscados;
- Telegram × WhatsApp × site;
- vendas e comissões da Amazon e do ML.

## Restrições que não mudam

- CSP `script-src 'self'`, sem script de terceiros, site completo sem JS. Nada de Google Analytics nem Web Analytics da Cloudflare, cujo beacon vem de `cloudflareinsights.com`.
- Sem cookie, sem IP e sem user agent guardados. O país é o único dado de localização.
- O `/r/` continua sendo o `_redirects` estático gerado pelo `build.py`, sem Worker. A allowlist, o `affiliate_url`, o `ml_url` e o `check_url` não mudam.
- O repo é público. Dado de venda e de comissão nunca vai para o repo, issue, PR ou artifact do Actions.

## Coleta

| Fonte | O que mede | Como |
|---|---|---|
| GraphQL da zona (`httpRequestsAdaptiveGroups`) | views por página, cliques em `/r/` (302 por livro, loja e canal), país, bot | Leitura com token só de leitura. No Free, guarda **31 dias** e não traz referrer nem query string (teste da F0, 2026-11-04) |
| Beacon `/e` (`static/app.js`) | termos buscados | `navigator.sendBeacon`, para o mesmo domínio (o `connect-src` já é o `SITE`). Nada é enviado com `navigator.globalPrivacyControl` ligado |
| Painéis de afiliado | pedidos e comissões | CSV exportado pelo próprio painel, no Chrome do Elias (seção "Vendas") |

**Clique sem Worker.** O caminho já carrega o que importa:
- `/r/<id>` é a loja vencedora, e a loja vem do `offers.json` do mesmo dia;
- `/r/<id>/<loja>` é a outra loja;
- `/r/<id>/tg` e `/r/<id>/wa` são os canais.

Conta só `edgeResponseStatus = 302`, excluindo bots pelo `userAgentBrowser` (GoogleBot e afins). O `robots.txt` ganha `Disallow: /r/` (agent-front), porque o GoogleBot seguia os links de afiliado.

**Fica de fora por enquanto:** a página de origem e a posição do card (exigiriam um Worker no `/r/*`) e o referrer (o Free não traz). O Elias decidiu em 2026-11-04 que não precisa deles ainda.

## Esquema

**`daily_rollup` no D1.** Guarda o histórico além dos 31 dias do GraphQL. O Worker `ofertaslivros-cron` grava uma vez por dia o dia anterior:

```sql
CREATE TABLE daily_rollup (
  day TEXT NOT NULL,        -- AAAA-MM-DD (UTC)
  path TEXT NOT NULL,       -- /, /manga/, /livro/<id>/, /r/<id>[/loja|/tg|/wa]
  status INTEGER NOT NULL,  -- 200 ou 302
  country TEXT NOT NULL,
  requests INTEGER NOT NULL,
  PRIMARY KEY (day, path, status, country)
);
```

Entram só os caminhos de página (HTML) e de `/r/`, sem bots. Asset (`.css`, `.woff2`, `.svg`) fica de fora.

**`search_events`, dataset `ol_search` no Analytics Engine (F2).** Guarda o termo (`blob1`), os resultados (`double1`) e o país (`blob2`), por 92 dias. Na F0, a SQL API do AE devolveu 403. Antes da F2, é preciso habilitar o AE na conta; se não der, a busca vai para uma tabela no D1.

**Termo de busca.** É texto livre, então pode trazer dado pessoal.
- O termo passa pelo `fold()`, é cortado em 40 caracteres e é descartado se tiver `@` ou 5 dígitos ou mais.
- O evento sai uma vez por termo: depois de 1,5 s sem digitar, no Enter ou no blur.
- O painel só mostra termo com 3 ocorrências ou mais.

**Nicho.** O painel cruza o `<id>` do caminho com o `genre` do `offers.json`.

**Vendas** ficam no D1, sem prazo de retenção:

```sql
CREATE TABLE sales (
  store TEXT NOT NULL,            -- amazon | mercadolivre
  order_date TEXT NOT NULL,       -- AAAA-MM-DD
  tracking TEXT,                  -- tag da Amazon (site/tg/wa) ou etiqueta do ML
  item_id TEXT,                   -- ASIN ou MLB
  title TEXT,
  qty INTEGER NOT NULL,
  revenue_cents INTEGER,
  commission_cents INTEGER,
  status TEXT,                    -- pendente | confirmado | devolvido
  source_file TEXT NOT NULL,
  imported_at TEXT NOT NULL,
  UNIQUE (store, order_date, item_id, tracking, source_file)
);
```

## Queries das KPIs

GraphQL da zona, no período `$s`–`$e`:

```graphql
# Cliques em /r/ por caminho, sem bots (o painel separa livro, loja e canal pelo caminho)
httpRequestsAdaptiveGroups(limit: 1000, orderBy: [count_DESC], filter: {
  datetime_geq: $s, datetime_lt: $e, clientRequestPath_like: "/r/%",
  edgeResponseStatus: 302, userAgentBrowser_notin: $bots }) {
  count dimensions { clientRequestPath }
}

# Views por página (HTML), sem bots
httpRequestsAdaptiveGroups(limit: 1000, orderBy: [count_DESC], filter: {
  datetime_geq: $s, datetime_lt: $e, edgeResponseStatus: 200,
  edgeResponseContentTypeName: "html", userAgentBrowser_notin: $bots }) {
  count dimensions { clientRequestPath }
}

# Visitas por dia (page views e únicos; conta bot)
httpRequests1dGroups(limit: 31, filter: { date_geq: $d }) {
  dimensions { date } sum { pageViews requests } uniq { uniques }
}
```

Os filtros foram testados no Free na F0. `$bots` é a lista de navegadores de robô (GoogleBot, BingBot e afins).

SQL, para mais de 31 dias, sobre o `daily_rollup` do D1:

```sql
-- Cliques e views por dia
SELECT day,
       SUM(CASE WHEN path LIKE '/r/%' THEN requests END) AS cliques,
       SUM(CASE WHEN path NOT LIKE '/r/%' THEN requests END) AS views
FROM daily_rollup GROUP BY day ORDER BY day;

-- CTR por livro: cliques em /r/<id>* ÷ views de /livro/<id>/
WITH c AS (
  SELECT substr(path, 4, instr(substr(path, 4) || '/', '/') - 1) AS book_id, SUM(requests) AS cliques
  FROM daily_rollup WHERE path LIKE '/r/%' AND day >= date('now', '-7 days') GROUP BY book_id
), v AS (
  SELECT substr(path, 8, length(path) - 8) AS book_id, SUM(requests) AS views
  FROM daily_rollup WHERE path LIKE '/livro/%/' AND day >= date('now', '-7 days') GROUP BY book_id
)
SELECT c.book_id, c.cliques, v.views, 1.0 * c.cliques / v.views AS ctr
FROM c LEFT JOIN v USING (book_id) ORDER BY c.cliques DESC LIMIT 20;

-- Telegram × WhatsApp × site
SELECT CASE WHEN path LIKE '%/tg' THEN 'tg' WHEN path LIKE '%/wa' THEN 'wa' ELSE 'site' END AS canal,
       SUM(requests) AS cliques
FROM daily_rollup WHERE path LIKE '/r/%' AND day >= date('now', '-7 days') GROUP BY canal;
```

Termos buscados, na SQL API do AE (F2):

```sql
SELECT blob1 AS termo, SUM(_sample_interval) AS buscas,
       SUM(IF(double1 = 0, _sample_interval, 0)) AS sem_resultado
FROM ol_search WHERE timestamp > NOW() - INTERVAL '7' DAY
GROUP BY termo HAVING buscas >= 3 ORDER BY sem_resultado DESC, buscas DESC LIMIT 30;
```

D1:

```sql
-- Progresso para liberar a Creators API (~10 vendas qualificadas em 30 dias)
SELECT COUNT(*) FROM sales
WHERE store = 'amazon' AND status != 'devolvido' AND order_date >= date('now', '-30 days');

-- Comissão por semana, loja e canal
SELECT strftime('%Y-W%W', order_date) AS semana, store, tracking,
       SUM(qty) AS itens, SUM(commission_cents) AS comissao_cents  -- em centavos; o painel formata com brl()
FROM sales GROUP BY semana, store, tracking ORDER BY semana DESC;
```

O R$ por clique junta, no D1, as tabelas `sales` e `daily_rollup` por semana e loja.

## Latência

| KPI | Latência real |
|---|---|
| Cliques e views (GraphQL) | alguns minutos |
| Termos buscados (AE) | cerca de 1 min |
| Pedidos e comissões | **Não é tempo real.** Os painéis atualizam com horas a 1 dia de atraso, e a comissão só fecha no mês. No painel, o dado chega com a rodada diária do navegador: D+1 no melhor caso |

Cada bloco do painel mostra "dados até HH:MM", e as vendas mostram "vendas até DD/MM".

## Painel `/painel`

- É uma página no Worker do site (`run_worker_first` com `/painel*`), protegida pelo **Cloudflare Access** só com o e-mail do Elias.
- O Worker **também confere o JWT do Access**: sem um JWT válido, a resposta é 403, mesmo se a regra do Access sumir.
- É HTML montado no servidor, sem JS, com `<meta http-equiv="refresh" content="60">`.
- O token só de leitura (Account Analytics e Zone Analytics) e o binding do D1 ficam no Worker (segredo e binding, nunca no repo).
- Só o `/painel*` e o `/e` passam pelo Worker. O `/r/` continua estático, então a cota do Free nunca derruba o clique de afiliado.

## Vendas pelo navegador

Esta seção depende da exceção nas regras 1 e 2 do CLAUDE.md (risco aceito pelo Elias em 2026-11-04). Sem ela na `main`, nada desta seção roda.

1. **Onde:** só no Chrome do Elias (Claude in Chrome), já logado. As páginas são a de relatórios dos Associados da Amazon e a de relatórios do portal de afiliados do ML. O navegador embutido do Orca não serve: lá, qualquer agent alcança a aba e consegue ler o cookie da sessão.
2. **Ritmo:** uma página por vez, cerca de 20 s entre ações, no máximo 1 rodada por dia em cada painel.
3. **Como:** o agent usa o botão de exportar do próprio painel (CSV de pedidos e ganhos) e não lê a tabela da tela linha por linha. O CSV vai para a pasta local `~/ofertaslivros-vendas/<loja>/`, fora do repo.
4. **Importação:** um script local lê o CSV e grava na tabela `sales` do D1 com `wrangler d1 execute`. A chave `UNIQUE` evita duplicar linhas quando a mesma semana é reimportada.
5. **Proibido:**
   - guardar cookie, token ou sessão;
   - chamar API interna dos painéis;
   - fazer request em código à Amazon, ao ML ou aos painéis;
   - rodar no GitHub Actions ou em navegador fora da máquina do Elias.
6. **Parada:** em captcha, verificação, 2FA ou logout, o agent para na hora, não resolve, não faz login e avisa o Elias.
7. **ML:** antes de usar o navegador, conferir se o portal tem API ou exportação oficial de relatório. Se tiver, ela vem primeiro.

A rodada só acontece com uma sessão aberta na máquina do Elias, que pode ser agendada localmente. Se a rodada falhar, o "vendas até" do painel fica parado e mostra isso.

## Fases

| Fase | Entra | Quem |
|---|---|---|
| F0 ✅ | Teste só de leitura, feito em 2026-11-04. O GraphQL do Free traz caminho, status, navegador e país, por 31 dias; referrer e query não. A SQL API do AE deu 403 | agent-dados |
| F1 | `Disallow: /r/` no `robots.txt`, `daily_rollup` no D1 e rollup diário no `ofertaslivros-cron` | agent-front (robots); agent-dados e agent-backend (cron e D1). PR sensível (Worker) |
| F1b | `/painel` com Access e conferência do JWT, lendo o GraphQL e o D1 | agent-dados e agent-backend. PR sensível |
| F2 | Beacon `/e` para os termos buscados e atualização da página de privacidade | agent-front e agent-dados. PR sensível (LGPD) |
| F3 | Vendas pelo navegador, importação no D1, progresso da Creators API e R$ por clique | agent-dados |

## O que o Elias faz

- Token da Cloudflare só de leitura: criado em 2026-11-04 (`ofertaslivros-analytics-readonly`) e guardado no `.env` local. Na F1b, vira segredo do Worker.
- Criar a aplicação do Access para `ofertaslivros.com.br/painel*` com o e-mail dele.
- Dar o "aprovado, pode seguir" em cada PR sensível.
