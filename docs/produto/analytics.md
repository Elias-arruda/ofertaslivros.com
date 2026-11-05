# Spec: analytics e painel de monitoramento

Plano do agent-dados, aprovado pelo Elias na sessão de 2026-11-04. Nada daqui está implementado ainda; cada fase entra por PR próprio.

## Objetivo

Medir o site e mostrar ao Elias, num painel privado:
- acessos;
- cliques nos links de afiliado (`/r/`), por livro, loja, nicho, posição e canal;
- termos buscados;
- origem do tráfego;
- Telegram × WhatsApp × site;
- vendas e comissões da Amazon e do ML.

## Restrições que não mudam

- CSP `script-src 'self'`, sem script de terceiros, site completo sem JS. Nada de Google Analytics nem Web Analytics da Cloudflare, cujo beacon vem de `cloudflareinsights.com`.
- Sem cookie, sem IP e sem user agent guardados. O país (`request.cf.country`) é o único dado de localização.
- O destino do `/r/` continua vindo do `_redirects` gerado pelo `build.py`. A allowlist, o `affiliate_url`, o `ml_url` e o `check_url` não mudam.
- O repo é público. Dado de venda e de comissão nunca vai para o repo, issue, PR ou artifact do Actions.

## Coleta

| Fonte | O que mede | Como |
|---|---|---|
| Worker em `/r/*` | cliques | Grava o evento no Workers Analytics Engine (AE) e chama `env.ASSETS.fetch()` com a URL **sem query**. Quem decide o destino continua sendo o `_redirects` |
| Beacon `/e` (`static/app.js`) | views de página e de modal, referrer, UTM, termos buscados | `navigator.sendBeacon`, para o mesmo domínio (o `connect-src` já é o `SITE`). Nada é enviado com `navigator.globalPrivacyControl` ligado |
| GraphQL da zona | volume bruto de requisições e países | Só para conferência, porque conta bot junto |
| Painéis de afiliado | pedidos e comissões | CSV exportado pelo próprio painel, no Chrome do Elias (seção "Vendas") |

Os links para `/r/` têm `rel="noreferrer"`. Por isso, o `build.py` passa a pôr a origem na URL: `/r/<id>?de=<página>&pos=<n>`. O Worker só grava esses valores se baterem com uma regex fechada, e eles nunca chegam ao destino, porque a query é removida antes do `ASSETS.fetch()`. Isso mantém o motivo da regra "caminho, não query" de `distribuicao-canais.md`.

## Esquema: dataset `ol_events` no AE

A retenção do AE é fixa em 92 dias. A contagem é sempre `SUM(_sample_interval)`.

| Coluna | Campo | view | click | search |
|---|---|---|---|---|
| `index1`, `blob1` | event | `view` | `click` | `search` |
| `blob2` | página normalizada (`/`, `/manga/`, `/livro/<id>/`), regex fechada, até 80 caracteres | vista | de origem (`?de=`) | da busca |
| `blob3` | book_id (regex de id do `build.py`) | modal ou página de livro | sim | — |
| `blob4` | loja, pelo host do `Location` que o `_redirects` devolve | — | sim | — |
| `blob5` | canal `site`/`tg`/`wa`, pelo sufixo do caminho | — | sim | — |
| `blob6` | só o host do `document.referrer`, ou `direto` | sim | — | — |
| `blob7` | `utm_source` de uma lista fechada, senão `outro` | sim | — | — |
| `blob8` | país | sim | sim | sim |
| `blob9` | termo buscado | — | — | sim |
| `double1` | posição do card | — | sim | — |
| `double2` | resultados da busca | — | — | sim |
| `double3` | `is_bot` 0/1, por regex de UA; o UA não é guardado | — | sim | — |

**Termo de busca.** É texto livre, então pode trazer dado pessoal.
- O termo passa pelo `fold()`, é cortado em 40 caracteres e é descartado se tiver `@` ou 5 dígitos ou mais.
- O evento sai uma vez por termo: depois de 1,5 s sem digitar, no Enter ou no blur.
- O painel só mostra termo com 3 ocorrências ou mais.

**Nicho.** Não é gravado no evento. O painel cruza o `book_id` com o `genre` do `offers.json`.

**Histórico além de 92 dias.** A tabela `daily_rollup(day, event, page, book_id, store, channel, n)` fica no D1 e é preenchida uma vez por dia pelo Worker `ofertaslivros-cron`.

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

SQL API do AE:

```sql
-- Visitas e cliques por dia
SELECT toStartOfDay(timestamp) AS dia,
       SUM(IF(blob1 = 'view',  _sample_interval, 0)) AS views,
       SUM(IF(blob1 = 'click' AND double3 = 0, _sample_interval, 0)) AS cliques
FROM ol_events WHERE timestamp > NOW() - INTERVAL '30' DAY
GROUP BY dia ORDER BY dia;

-- CTR por página
SELECT blob2 AS pagina,
       SUM(IF(blob1 = 'view',  _sample_interval, 0)) AS views,
       SUM(IF(blob1 = 'click', _sample_interval, 0)) AS cliques
FROM ol_events WHERE timestamp > NOW() - INTERVAL '7' DAY AND double3 = 0
GROUP BY pagina HAVING views >= 20 ORDER BY cliques DESC;

-- Top livros, loja vencedora e Telegram × site
SELECT blob3 AS book_id, blob4 AS loja, blob5 AS canal, SUM(_sample_interval) AS cliques
FROM ol_events
WHERE blob1 = 'click' AND double3 = 0 AND timestamp > NOW() - INTERVAL '7' DAY
GROUP BY book_id, loja, canal ORDER BY cliques DESC LIMIT 20;

-- Cliques por posição (sem impressão por card não há CTR; a distribuição dos cliques basta para comparar posições)
SELECT blob2 AS pagina, double1 AS pos, SUM(_sample_interval) AS cliques
FROM ol_events
WHERE blob1 = 'click' AND double3 = 0 AND timestamp > NOW() - INTERVAL '7' DAY
GROUP BY pagina, pos ORDER BY pagina, pos;

-- Origem do tráfego
SELECT blob6 AS origem, blob7 AS utm, SUM(_sample_interval) AS views
FROM ol_events WHERE blob1 = 'view' AND timestamp > NOW() - INTERVAL '7' DAY
GROUP BY origem, utm ORDER BY views DESC LIMIT 20;

-- Termos buscados (os sem resultado viram pauta da curadoria)
SELECT blob9 AS termo, SUM(_sample_interval) AS buscas,
       SUM(IF(double2 = 0, _sample_interval, 0)) AS sem_resultado
FROM ol_events WHERE blob1 = 'search' AND timestamp > NOW() - INTERVAL '7' DAY
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

O R$ por clique cruza o D1 com o AE por semana e loja. Esse cruzamento é feito no código do painel.

## Latência

| KPI | Latência real |
|---|---|
| Cliques, views, origem e busca (AE) | cerca de 1 min |
| Volume da zona (GraphQL) | alguns minutos |
| Pedidos e comissões | **Não é tempo real.** Os painéis atualizam com horas a 1 dia de atraso, e a comissão só fecha no mês. No painel, o dado chega com a rodada diária do navegador: D+1 no melhor caso |

Cada bloco do painel mostra "dados até HH:MM", e as vendas mostram "vendas até DD/MM".

## Painel `/painel`

- É uma página no Worker do site (`run_worker_first` com `/painel*`), protegida pelo **Cloudflare Access** só com o e-mail do Elias.
- O Worker **também confere o JWT do Access**: sem um JWT válido, a resposta é 403, mesmo se a regra do Access sumir.
- É HTML montado no servidor, sem JS, com `<meta http-equiv="refresh" content="60">`.
- O token só de leitura do AE e o binding do D1 ficam no Worker (segredo e binding, nunca no repo).
- Mostra também o uso diário de requisições do Worker.

**Risco do plano Free:** com o `/r/*` passando pelo Worker, se a cota de 100 mil requisições por dia acabar, o clique de afiliado quebra. Se o uso passar de 50%, a saída é o plano de US$ 5 ou amostrar o beacon.

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
| F0 | Teste só de leitura: o que o GraphQL do Free devolve e se o `ASSETS.fetch` respeita o `_redirects` e descarta a query | agent-dados, com o token só de leitura |
| F1 | Worker no `/r/*` gravando no AE e `?de=&pos=` nos links do `build.py` | agent-dados escreve; agent-backend revisa o Worker; agent-front, os links. PR sensível |
| F1b | `/painel` com Access e conferência do JWT | agent-dados e agent-backend. PR sensível |
| F2 | Beacon `/e`: views, origem e busca. Atualização da página de privacidade | agent-front e agent-dados. PR sensível (LGPD) |
| F3 | Vendas pelo navegador, importação no D1, progresso da Creators API, R$ por clique e `daily_rollup` | agent-dados |

## O que o Elias faz

- Criar o token da Cloudflare só de leitura: Account Analytics Read e Zone Analytics Read na zona `ofertaslivros.com.br`. Ele vira segredo do Worker e, se a F0 precisar, Secret no GitHub.
- Criar a aplicação do Access para `ofertaslivros.com.br/painel*` com o e-mail dele.
- Dar o "aprovado, pode seguir" em cada PR sensível.
