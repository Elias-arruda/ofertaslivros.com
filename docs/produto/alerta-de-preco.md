# Spec: alerta de preço ("me avise quando o livro X chegar a R$ Y")

Status: proposta, 2026-10-18. Autor: product-manager. Implementação: ver "Divisão por agent".

## 1. Problema e usuário

**Em uma frase:** o leitor que quer um livro específico, mas acha caro agora, pede para ser avisado no Telegram quando o preço cair até o valor que ele aceita pagar. Quando o aviso chega, ele clica no nosso link de afiliado no momento em que tem mais chance de comprar.

- **Usuário:** quem chegou pelo site (card de oferta ou lista de monitorados) e tem Telegram. Não precisa de cadastro, e-mail nem login.
- **Por que dá dinheiro:** o alerta dispara no momento de maior intenção de compra, e o clique sai com a nossa tag/`matt_word`. Também cria retenção: o usuário volta sem precisarmos de anúncio.
- **Interpretações do pedido:**
  1. Preço-alvo livre ("R$ 39,90"). **É o pedido literal.**
  2. "Me avise se baixar" em um clique (alvo = abaixo do preço atual).
  3. "Me avise quando voltar ao menor preço em 90 dias".

  **Recomendação:** a 2 é o botão do card (um clique) e a 1 é o comando do bot, para quem quer escolher o valor. A 3 fica para depois porque depende de histórico real, que ainda não existe.

## 2. O que existe hoje (conferido no repo)

| Item | Existe? | Onde |
|---|---|---|
| Site estático gerado de JSON | Sim | `build.py` (stdlib), saída em `dist/` (no `.gitignore`) |
| Validação forte de oferta, allowlist de host, link do ML preso ao `matt_word` | Sim | `build.py`: `validate_offer`, `check_url`, `ml_url`, `affiliate_url` |
| Link da Amazon montado no código (`/dp/<ASIN>?tag=`) | Sim | `build.py:affiliate_url`. **O humano não precisa gerar o link da Amazon, só lançar o preço.** |
| Redirect `/r/<id>` só para ofertas ativas | Sim | `build.py:build` gera `dist/_redirects` |
| Headers (CSP etc.) | Sim | `build.py:HEADERS` (CSP sem `script-src`, `form-action 'none'`) |
| Páginas por nicho | Sim | `GENRES` em `build.py` |
| Ofertas reais | **Não** | `data/offers.json` tem `"_exemplo": true`: ASIN/MLB fictícios, e o `lowest_90d_cents` é digitado à mão |
| Coletor (ML API, Creators API) | **Não** | Não há código de coleta no repo |
| Histórico de preço (`price_history`) | **Não** | Só o modelo em `.claude/agents/collector-engineer.md` |
| Catálogo de livros monitorados (separado das ofertas ativas) | **Não** | `offers.json` só tem ofertas ativas |
| GitHub Actions (cron, deploy) | **Não** | Não existe `.github/` |
| Deploy no Cloudflare Workers (static assets) | **Não** | Nenhuma config ou workflow, só o `dist/` local |
| Bot/canal do Telegram | **Não** | Só a descrição em `.claude/agents/alerts-engineer.md` |
| Página de privacidade | **Não** | — |

**Referência (ofertasdiscos.com, conferido em 2026-10-18):** vitrine curada (cerca de 45 ofertas ativas, filtro por gênero, ordenação, "Destaques"), canais de WhatsApp e Telegram só de leitura e sem cadastro, bot de lista de desejos no Telegram (`t.me/BisDoDiscoBot`, página `/bis/wishlist`), "Pedir um disco", guias, página `/privacidade` e só a Amazon como loja. A página pública não mostra se a wishlist aceita preço-alvo. O que parece é que ela avisa de "ofertas curadas" de um item, e não de um valor escolhido. **O nosso preço-alvo com histórico de 90 dias é diferencial, não cópia.**

## 3. Gaps em ordem de prioridade

| # | Gap | Por que essa prioridade | Bloqueia o alerta? | Agent |
|---|---|---|---|---|
| 1 | Coletor do ML + `price_history` append-only | Sem preço atual coletado sozinho, não há o que comparar com o alvo | **Sim** | collector-engineer |
| 2 | Workflow do GitHub Actions com cron | É o "servidor" do projeto: coleta, lê o bot e envia | **Sim** | collector-engineer (o alerts-engineer acrescenta o passo do bot) |
| 3 | Catálogo de monitorados com `id` estável, separado de `offers.json` | A oferta vence e sai da lista, mas o alerta precisa continuar apontando para o livro. O livro do pedido geralmente **não** está em oferta | **Sim** | collector-engineer |
| 4 | Entrada estruturada do preço manual da Amazon | Hoje o preço só entra editando `offers.json` à mão | Só o alerta da Amazon | collector-engineer |
| 5 | Bot do Telegram + armazenamento dos alertas fora do repo | É o alerta em si | **Sim** | alerts-engineer (Elias cria o bot e a conta de storage) |
| 6 | Página `/privacidade/`, botão "Me avise" no card, página `/monitorados/` | LGPD: a política precisa estar publicada antes de guardar `chat_id`. O botão é a porta de entrada | **Sim** (privacidade e botão) | frontend-developer |
| 7 | Deploy no Cloudflare Workers, static assets (workflow + DNS) | Sem site no ar, ninguém chega ao botão. O bot funciona sozinho, mas ninguém o encontra | Para o lançamento | collector-engineer (workflow) + security-auditor |
| 8 | Dados reais no lugar do exemplo | `offers.json` é fictício | Para o lançamento | Elias + collector-engineer |
| 9 | Canal público no Telegram (e depois no WhatsApp) | É a maior alavanca para chegar às cerca de 10 vendas na Amazon (ver seção 5). Reaproveita o bot e o pipeline | Não | alerts-engineer |
| 10 | Ordenação, "Destaques", "Pedir um livro", guias | Melhoram a vitrine, mas não mudam a receita no início | Não | frontend-developer |

## 4. Escopo do MVP

**Dentro:**
- Alerta individual pelo Telegram, para qualquer livro do **catálogo de monitorados**: a lista curada pelo Elias, que inclui as ofertas ativas e livros fora de oferta.
- Duas entradas:
  - Botão "Me avise se baixar" no card (`/`, nichos e `/monitorados/`). É um deep link `https://t.me/<bot>?start=<id>`, e o alvo fica abaixo do preço atual (`target_cents = preço_atual - 1`).
  - Comando `/alerta <id> <preço>` para escolher o alvo (por exemplo, `/alerta torto-arado 39,90`). A confirmação do botão já sugere esse comando com o `id` preenchido.
- Comandos `/meus_alertas`, `/remover <id>` e `/parar` (apaga tudo do chat).
- Disparo: uma mensagem por alerta, com o link de afiliado validado. Depois de enviado, o alerta é apagado.
- Expiração: 90 dias sem disparar e o alerta é apagado.
- Lojas: **ML automático** (API de itens) e **Amazon semi-automática** (preço lançado pelo humano). Ver seção 5 e a decisão 1.
- Página `/privacidade/` e menção a ela no rodapé.

**Fora (e quando vale fazer):**
- Alerta para livro fora do catálogo (o usuário cola um link qualquer). O link do ML vem do painel, à mão (regra 2), então um item arbitrário não teria link de afiliado: alerta sem receita e vetor de abuso. **Quando:** com a Creators API, só para Amazon, porque o link é montado no código.
- Alerta por ISBN valendo para as duas lojas ("o mais barato entre Amazon e ML"). **Quando:** o catálogo tiver ISBN preenchido nas duas lojas.
- "Avise quando voltar ao menor preço em 90 dias". **Quando:** o `price_history` tiver 90 dias reais.
- Busca no bot (`/buscar <título>`). **Quando:** o catálogo passar de uns 100 livros e a página `/monitorados/` ficar ruim de navegar.
- Webhook ou Cloudflare Worker para o bot responder na hora. **Quando:** a latência do cron (até cerca de 30 a 40 min) aparecer como queixa ou derrubar a conversão do `/start`.
- E-mail, WhatsApp individual e aviso de "seu alerta expirou". **Quando:** houver demanda.
- Formulário de preço no site. Exigiria JS ou mudar a CSP (`form-action 'none'`, sem `script-src`), e o comando no bot resolve.

## 5. Como a Creators API ainda não liberada afeta o alerta

- **Sem API, não há preço automático da Amazon, e scraping é proibido** (regra 1). Nenhum passo deste MVP pode buscar `amazon.com.br`. Isso vale para requests, headless e "só pegar o preço": nada disso é permitido.
- **O que já dá para alertar automaticamente:** os itens do **Mercado Livre**, pela API de itens (`/items?ids=` em lotes). O preço é coletado a cada execução do cron, e o link é o do painel, já validado por `ml_url`.
- **Amazon no período semi-automático.** O motor de alerta não sabe de onde vem o preço: ele lê a última linha do `price_history`. Para a Amazon, essa linha vem do humano.
  - **Como entra:** o humano lança o preço em um arquivo de entrada, por exemplo `data/amazon_prices.csv` com `asin, price_cents, list_price_cents, checked_at`. O formato final é decisão do collector-engineer. O coletor faz append no `price_history` com `source='manual'`.
  - **Frequência:** uma vez por dia, na mesma rotina em que ele já confere as ofertas da Amazon. Para não virar trabalho infinito, o coletor gera uma lista de ASINs com alerta ativo, ordenada por número de alertas. O humano confere essa lista primeiro. A demanda dos alertas diz o que vale olhar.
  - **Frescor:** um alerta da Amazon só dispara com um preço de menos de 24 h. A mensagem diz "preço conferido manualmente em DD/MM às HHhMM; o preço final é o da loja".
  - **Consequência honesta:** o alerta da Amazon atrasa até 24 h e pode perder uma promoção relâmpago. O ML não tem esse atraso.
- **O ovo e a galinha.** A Creators API exige cerca de 10 vendas qualificadas em 30 dias com a tag. Um MVP só com ML não gera **nenhuma** venda na Amazon e adia a liberação. Por isso a recomendação é **incluir a Amazon semi-automática no MVP**. O custo de código é quase zero, porque o motor é o mesmo. O custo real é o tempo diário do humano. Mesmo assim, no início os alertas individuais geram pouco volume. Quem mais deve ajudar a bater as 10 vendas é a vitrine com o canal público do Telegram (gap 9), e não o alerta.
- **O que muda quando a API for liberada:**
  - O coletor da Amazon passa a gravar `price_history` com `source='creators_api'`, na frequência que a cota permitir. A cota provavelmente depende do volume de vendas: confirmar na documentação na hora.
  - Sai a entrada manual e a fila de ASINs. O limite de 24 h de frescor passa a ser o mesmo do ML.
  - O motor de alerta, o bot e o storage **não mudam**.
  - Vale então abrir o "alerta para qualquer ASIN" (seção 4, fora), porque o link da Amazon já é montado no código.

## 6. Fluxo do usuário

1. O usuário vê um livro no site (card de oferta ou `/monitorados/`) e clica em **"Me avise se baixar (Telegram)"**.
2. O Telegram abre `t.me/<bot>?start=<id>`, e o usuário toca em **Iniciar**. O Telegram envia `/start <id>`.
3. Na próxima execução do cron (até cerca de 30 min, mais o atraso do GitHub), o bot:
   - valida o `id` contra o catálogo, o limite por chat e se o chat é privado;
   - grava o alerta com alvo abaixo do preço atual;
   - responde: "Pronto: aviso quando *<título>* (<loja>) ficar abaixo de R$ X. Quer outro valor? Envie `/alerta <id> 39,90`. Seus alertas: /meus_alertas. Privacidade: <url>/privacidade/".
4. Se o usuário enviar `/alerta <id> <preço>`, o bot troca o alvo daquele livro (um alerta por livro por chat). Se o alvo já for maior ou igual ao preço atual, o bot não grava nada e responde com o preço atual e o link.
5. Quando o preço coletado chega ao alvo (ML: coleta do mesmo run; Amazon: lançamento manual de menos de 24 h), o bot envia: "*<título>* está R$ Y na <loja> (alvo R$ X), verificado em DD/MM HHhMM. Preço final é o da loja. <link>". O alerta é apagado.
6. `/remover <id>` apaga um alerta e `/parar` apaga todos os dados do chat. Se o usuário bloquear o bot (o Telegram devolve 403), tudo do chat é apagado.

## 7. Dados

**Preço (público, sem dado de usuário).** Dono: collector-engineer.
- `books`/catálogo: `id` (slug, estável para sempre, até 57 chars, `ID_RE` do `build.py`), `store`, `asin` ou `ml_item_id`, `ml_url` (ML), `title`, `author`, `genre`.
  - Exportado para um JSON público (por exemplo `data/catalog.json`) para o build gerar `/monitorados/` e os botões.
  - O deep link do Telegram aceita `start` com até 64 chars em `[A-Za-z0-9_-]`. O limite de 57 deixa folga para um prefixo futuro.
- `price_history(book_id, store, price_cents, list_price_cents, checked_at, source)`, append-only, com `source ∈ {ml_api, manual, creators_api}`.
- Frequência: **ML a cada execução do cron (30 min)**, com multi-get em lotes de 20, timeout e backoff. **Amazon uma vez por dia, manual.**
- Antes de codar, o collector-engineer confere duas coisas:
  - se `/items` do ML ainda responde sem token ou exige token de app (`client_credentials`);
  - qual campo bate com o preço que o comprador vê (`price` x `sale_price`).

**Alertas (dado pessoal, nunca no repo).** Dono: alerts-engineer.
- `alerts(chat_id, book_id, target_cents, created_at, expires_at)`, com PK `(chat_id, book_id)`.
- `bot_state(key, value)` para o `offset` do `getUpdates`.
- **Onde fica:** um banco gerenciado fora do repo, Supabase (Postgres free) ou Cloudflare D1 via API (decisão 2). O acesso usa uma chave de serviço em GitHub Secret, sem acesso anônimo (RLS ligado, se for Supabase).
- **Quanto tempo fica:** até disparar (apagado no envio), até 90 dias ou até o usuário remover. Não fica histórico de alertas disparados.
- **Como o usuário remove:** `/remover <id>`, `/parar` ou bloqueando o bot.
- **O que não guardamos:** nome, username, telefone, texto livre das mensagens.

## 8. Critérios de aceite

Preço e catálogo:
1. Um item do ML do catálogo ganha uma linha nova em `price_history` a cada execução do cron. Nenhuma linha é alterada ou apagada (teste: contar as linhas antes e depois e comparar o hash das antigas).
2. `grep -ri amazon` no código do coletor só encontra a montagem do link e a leitura do arquivo manual. Nenhuma request HTTP vai para domínio da Amazon (teste: rodar o coletor com a rede mockada e afirmar que nenhum host `*.amazon.*` foi chamado).
3. Um lançamento manual da Amazon com `checked_at` sem fuso, preço não inteiro ou ASIN fora de `ASIN_RE` faz o job falhar sem gravar nada.
4. Um `id` do catálogo com mais de 57 chars ou fora de `ID_RE` faz o build falhar.

Bot e alertas (pytest):
5. `/start <id>` com `id` do catálogo, em chat privado, cria o alerta com `target_cents = preço_atual - 1` e responde com a confirmação.
6. `/start <id>` com id desconhecido ou malformado, ou em grupo/canal, não grava nada. O grupo é ignorado em silêncio, e o chat privado recebe "livro não encontrado".
7. O parser de `/alerta` aceita `39,90`, `39.90`, `R$ 39,90` e `40`, e converte para centavos com `Decimal`. Rejeita `0`, negativo, `abc`, `1e3`, valor acima de R$ 10.000 e mais de 2 casas decimais.
8. O 11º alerta ativo do mesmo chat é recusado com uma mensagem explicando o limite de 10.
9. Disparo: com preço ≤ alvo e preço fresco (ML até 2 h, Amazon até 24 h), sai exatamente 1 mensagem e o alerta é apagado. Rodar o motor duas vezes sobre o mesmo estado resulta em 1 envio, não 2.
10. Preço velho (fora da janela do item 9) não dispara.
11. O envio ao Telegram usa texto puro, sem `parse_mode`. Um título com `<a href=...>` ou `*bold*` chega literal.
12. O link na mensagem sai de `affiliate_url`/`check_url` do `build.py`, ou de uma função equivalente compartilhada. Uma URL fora da allowlist faz o envio falhar com erro, em vez de mandar a URL.
13. Uma resposta 403 do Telegram (bot bloqueado) apaga todos os alertas daquele `chat_id`.
14. `/parar` apaga todos os registros daquele `chat_id`. `/meus_alertas` lista título, alvo e data de expiração.
15. Um alerta com `expires_at` vencido é apagado na execução seguinte, sem envio.
16. O `offset` do `getUpdates` é persistido, e reprocessar o mesmo lote não duplica alertas nem respostas.
17. No máximo 500 updates processados por execução, para limitar o custo.

Privacidade e logs:
18. Os logs do workflow não contêm `chat_id`, texto de mensagem nem token. Teste: rodar com um `chat_id` sentinela e procurá-lo no log capturado. O log só mostra contagens ("3 alertas criados, 1 enviado").
19. Nenhum arquivo versionado nem JSON público contém `chat_id`. Teste: um passo no CI procura o sentinela em `data/` e `dist/`.
20. `/privacidade/` existe, está linkada no rodapé e diz o que guardamos, onde, por quanto tempo e como apagar.

Site:
21. Cada card tem o link `https://t.me/<bot>?start=<id>` com `rel="noopener noreferrer"` e texto acessível. O botão não usa JS, e a CSP atual continua igual.
22. `/monitorados/` lista título, autor e loja de cada livro do catálogo, com o botão, **sem preço**. Assim não exibimos preço da Amazon que pode estar velho.

## 9. Divisão por agent (ordem de execução)

0. **Elias (pré-requisito):**
   - criar o bot no @BotFather, com username, `/setprivacy` ligado e sem entrada em grupo (`/setjoingroups` desligado);
   - criar o banco de alertas (decisão 2);
   - cadastrar os GitHub Secrets: `TELEGRAM_BOT_TOKEN`, `ALERTS_DB_URL`/chave e, se o ML exigir, `ML_CLIENT_ID`/`ML_CLIENT_SECRET`;
   - definir a lista inicial do catálogo.
1. **collector-engineer:**
   - catálogo com id estável e export `data/catalog.json`;
   - coletor do ML e `price_history`;
   - entrada manual da Amazon e fila de ASINs com alerta;
   - workflow `.github/workflows/pipeline.yml` (cron `*/30`, actions por SHA, `permissions` mínimas, `concurrency` para não rodar duas vezes);
   - validação com schema e pytest do cálculo de preço. **Critérios 1 a 4.**
2. **alerts-engineer:**
   - passo do bot no mesmo workflow (`getUpdates`, comandos, motor de disparo, envio);
   - cliente do storage e pytest do parser e da regra;
   - reaproveitar `affiliate_url`/`check_url` do `build.py`, sem copiar. **Critérios 5 a 19.**
3. **frontend-developer:**
   - botão no card, `/monitorados/`, `/privacidade/` e o link no rodapé, tudo gerado pelo `build.py`;
   - a sessão que hoje mexe no `build.py`, `data/` e `static/` precisa terminar antes. **Critérios 20 a 22.**
4. **security-auditor:**
   - revisar workflow (secrets, SHA, `permissions`, sem `pull_request_target`), log, storage (acesso anônimo fechado), parser e allowlist;
   - rodar `/threat-model` incluindo o bot;
   - antes do deploy, `/security-review`.
5. **code-reviewer:** um PR por etapa. Na etapa 3, com `web-design-guidelines`.

## 10. Riscos

**Regras inegociáveis**
- *Scraping da Amazon:* o critério 2 trava isso no CI. Também não pode haver tentação de "só pegar o preço da página" para acelerar o alerta da Amazon.
- *Credenciais:* token do bot e chave do banco só em GitHub Secrets e `os.environ`, nunca ecoados. Um repo público deixa o log do Actions **público**: daí o critério 18.
- *Link do ML:* só o link completo do painel, conferido por `ml_url`. É por isso que o alerta fica restrito ao catálogo.
- *Transparência:* a mensagem do alerta diz que o preço final é o da loja e mostra o horário da verificação.

**Dado de usuário e LGPD**
- O `chat_id` é dado pessoal (identifica uma conta). Guardamos o mínimo: a finalidade é o próprio serviço pedido pelo usuário, há prazo de 90 dias, a remoção é por comando e a política está publicada.
- Operador do dado: Supabase ou Cloudflare. Registrar isso em `/privacidade/`.
- Um vazamento da chave do banco expõe `chat_id` + livros de interesse. A mitigação é chave só no Secret, acesso anônimo fechado e nada de dado pessoal fora do banco.

**Abuso e spam**
- O bot só responde a quem escreveu e nunca envia para terceiros.
- Limites: 10 alertas por chat, 1 alerta por livro por chat, 1 mensagem por disparo, 500 updates por execução, e grupos ignorados.
- O texto do catálogo vai em texto puro, sem formatação injetável (critério 11).

**Política dos programas (verificar antes de lançar)**
- Os Associados da Amazon restringem o uso de links de afiliado em e-mail e em comunicação "offline/privada". Uma mensagem individual de bot pode cair nessa regra. **Confirmar no Operating Agreement da Amazon.com.br antes de mandar link da Amazon no alerta** (decisão 1).
- Pela mesma lógica, confirmar o que a Amazon permite sobre exibir preço que não veio da API. Por isso `/monitorados/` não mostra preço.

**Operação e custo**
- Cron do GitHub: atrasa minutos em horário de pico e desliga o agendamento após 60 dias sem atividade no repo. O commit do `offers.json` pelo pipeline mantém o repo ativo.
- Repo público tem minutos ilimitados. Repo privado tem 2.000 min/mês: um run a cada 30 min, de cerca de 1 min, dá umas 1.440 min/mês, apertado mas cabe.
- O `getUpdates` guarda os updates por 24 h. Se o pipeline ficar mais de 24 h parado, comandos se perdem. Aceitável no MVP.
- Supabase free pausa após 7 dias sem uso. O cron de 30 min evita isso. Cloudflare D1 free não pausa.
- Latência: o usuário toca em "Iniciar" e espera até cerca de 30 a 40 min pela confirmação. Isso pode derrubar a conversão. Medir pela contagem de `/start` x alertas criados e, se ficar ruim, partir para o webhook (seção 4, fora).
- Custo monetário: R$ 0 nos free tiers. O custo real é o tempo diário do humano com o preço da Amazon.

## 11. Decisões do Elias (2026-10-18)

1. **Amazon no MVP:** sim, semi-automática. Antes de lançar, ainda é preciso confirmar no Operating Agreement se a Amazon aceita link de afiliado em mensagem individual de bot (seção 10).
2. **Banco dos alertas:** Cloudflare D1.
3. **Repo:** público. Os minutos do Actions passam a ser ilimitados, e os logs ficam públicos (critério 18).
4. **Cron:** a cada 30 min.
5. **`/monitorados/`:** entra no MVP, sem preço.
6. **Catálogo inicial e curadoria:** 20 livros na Amazon (~10 min/dia) e 40 itens no ML, em 2–3 nichos. Nas primeiras 4 semanas, a curadoria é do Elias. Depois da etapa 1 entra o `curator`: um script semanal no Actions que abre um PR com sugestões (busca do ML + Google Books/Open Library). Ele não descobre livros na Amazon até a Creators API ser liberada, e o link do ML e a aprovação continuam manuais.
7. **Limites:** confirmados: 10 alertas por chat e 90 dias de validade.
