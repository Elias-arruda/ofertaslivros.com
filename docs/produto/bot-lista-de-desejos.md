# Spec: bot de lista de desejos no Telegram ("me avise quando este livro entrar em oferta")

Status: spec, 2026-11-06. Autor: product-manager. Decidido pelo Elias em 2026-11-06 (seção 2).
Substitui, nos pontos marcados, a proposta antiga [`alerta-de-preco.md`](alerta-de-preco.md) (preço-alvo + `getUpdates` no Actions).
**Todos os PRs desta spec são sensíveis** pelo CLAUDE.md: dado de usuário (`chat_id`), Worker e `wrangler.jsonc`, `_redirects`/rota `/r/` e tag de afiliado, texto de privacidade. Merge só com "aprovado, pode seguir" do Elias na sessão.

## 1. Problema e usuário

**Em uma frase:** o leitor que quer um livro específico (ou tudo de um autor), mas não vai abrir o site todo dia, monta uma lista no Telegram e recebe uma mensagem só quando aquele livro entra em oferta. O aviso chega no momento de maior intenção de compra, com o nosso link de afiliado, e a lista traz a pessoa de volta sem anúncio.

- **Usuário:** quem chega pelo sino do card ("Me avise se baixar"), pelo capítulo do alerta no site, pelo canal @maviOfertaslivros ou direto pelo @ofertaslivros_bot. Sem cadastro, e-mail ou login.
- **Por que dá dinheiro:** o canal manda tudo para todo mundo (até 8 por dia). O bot manda só o que a pessoa pediu, então a taxa de clique por mensagem é bem maior. O clique sai por `/r/<id>/bot`, com tracking ID próprio da Amazon, o que ajuda nas cerca de 10 vendas que liberam a Creators API.
- **Diferença para o canal:** o canal é um para muitos e não guarda nada. O bot guarda o `chat_id` e a lista, então tem LGPD (seção 9).

## 2. Decisões já tomadas (não reabrir)

1. O webhook do Telegram chega **na hora** numa rota do Worker do site (`ofertaslivros`, o mesmo do `/pedido` e do `/painel`, plano Free). A lista fica no **Cloudflare D1**, fora do repo público. O Worker confere o header `X-Telegram-Bot-Api-Secret-Token`.
2. O modelo é o do BIS (@BisDoDiscoBot): "me avise quando este livro, ou este autor, entrar em oferta". **Oferta = a mesma regra do site e do canal:** `build.em_oferta` (campo `oferta` do `resolve`), preço no prazo e sem preço vencido (`velho`). Preço-alvo fica para depois.
3. Comandos inspirados no BIS: `/start`, `/lista`, `/pausar`, `/ajuda`. O bot já existe como "Mavi · Ofertas Livros" (@ofertaslivros_bot).
4. Fora do MVP: a Mini App (lista visual). Livro fora do catálogo vira **pedido de livro** para a curadoria (`pedido-de-livro.md`), e não um alerta.

## 3. O que existe hoje (conferido na origin/main, 4d17c2c)

| Item | Estado | Onde |
|---|---|---|
| Worker do site com rotas próprias | Sim: `/pedido` e `/painel*` em `run_worker_first`; o resto vem dos assets | `worker/index.js`, `wrangler.jsonc` |
| D1 | `ofertaslivros-analytics` (binding `ANALYTICS`), com as tabelas `daily_rollup` e `pedidos` (30 dias) | `wrangler.jsonc`, `cron/rollup.js` |
| Rate limit | `LIMITE`, 5 por minuto por IP, só para o `/pedido` | `wrangler.jsonc` |
| Cron Triggers | 3 no `ofertaslivros-cron` (`*/30`, `0 12`, `15 3`). O Free permite 5 por conta | `cron/wrangler.jsonc` |
| Regra de oferta e texto do post | `resolve` (campos `oferta`, `velho`), `ofertas`, `post_text` (aceita só `/r/<id>`, `/r/<id>/tg` e `/r/<id>/wa`) | `build.py` |
| `/r/<id>/tg` e `/wa` com tag por canal | Sim, `channel_tags()` com `AMAZON_TAG_TG`/`AMAZON_TAG_WA`. ML: mesmo `ml_url` | `build.py:redirects` |
| Botão do site | `tg_alert_url` gera `https://t.me/<bot>?start=<id>` quando `TELEGRAM_BOT_USERNAME` existe. **Hoje a var está desligada de propósito**: botões em "em breve" | `build.py`: `alert_link`, `banner_bot`, `bot_block`, `faq`, `canais`, `offer_json` |
| Canal | No ar desde 2026-11-06: `telegram_post.py`, chamado por `telegram.yml` depois de cada deploy. Usa `TELEGRAM_BOT_TOKEN` (Environment `telegram` no GitHub). Não usa `getUpdates`, então não conflita com o webhook | `telegram_post.py`, `.github/workflows/telegram.yml` |
| `/privacidade/` | Existe, mas descreve o modelo antigo (preço-alvo, 90 dias, `/remover`, "apagado quando dispara") | `build.py:privacy` |
| Textos do site sobre o alerta | Falam em "guarda o preço de hoje" e "apaga o alerta quando ele disparar", o que deixa de ser verdade | `banner_bot`, `bot_block`, `faq` |
| Busca sem acento | `build.fold` (Python) e `fold` no `static/app.js` (mesmo NFKD + sem marcas) | `build.py`, `static/app.js` |
| Catálogo | 168 livros no `offers.json` do `price-history`, id mais longo com 54 chars | branch `price-history` |

**Referência (ofertasdiscos.com, 2026-11-06):** `/bis/wishlist` só abre a Mini App ("Abrindo sua lista…"). A `/privacidade` deles não diz nada sobre o que o BIS guarda. A nossa política explícita é um diferencial, não cópia.

## 4. Escopo do MVP

**Dentro:**
- Webhook `POST /telegram` no Worker do site. Só chat privado e só os updates `message`, `callback_query` e `my_chat_member`.
- Comandos: `/start [id]`, `/lista`, `/pausar`, `/voltar`, `/parar`, `/ajuda`.
- Cadastro por texto (título, autor, ou "Título — Autor"), até 10 por mensagem, um por linha, casando com o catálogo publicado.
- Entrada pelo botão do site: `t.me/ofertaslivros_bot?start=<id>`.
- Item de lista de dois tipos: **livro** (id do catálogo) e **autor** (nome normalizado).
- Disparo a cada 30 min por um Cron Trigger **no próprio Worker do site**, lendo o `/bot.json` que o build publica (seção 7).
- Aviso com o texto do `post_text` e o link `/r/<id>/bot`, com tag da Amazon própria (`AMAZON_TAG_BOT`).
- Livro não encontrado: botão "Pedir este livro", que grava na tabela `pedidos` que já existe, sem `chat_id`.
- `/privacidade/` e os textos do site atualizados, e a var `TELEGRAM_BOT_USERNAME` ligada no fim.

**Fora (e quando vale fazer):**
- **Mini App** (lista visual). Quando: a lista por texto aparecer como atrito (muitos `/lista` seguidos de remoções) ou passar de uns 200 chats ativos.
- **Preço-alvo** ("me avise abaixo de R$ X"). Quando: alguém pedir. O modelo de dados já comporta uma coluna a mais em `desejos`.
- **Avisar quando um livro pedido entrar no catálogo.** Exige guardar o `chat_id` junto do pedido. É a "Pedir um livro v2", que fica para depois.
- **Foto no aviso** (`sendPhoto` com a foto do ML). Quando: o CTR do bot for medido. Hoje cada foto é uma subrequest a mais e o texto já resolve.
- **Contagens do bot no `/painel`** (chats, itens, avisos por dia). Quando: o bot estiver no ar há 2 semanas. Precisa só de `SELECT COUNT(*)`, sem nenhum `chat_id` na tela.
- **Grupos e canais** usando o bot. Ficam fora de propósito.

## 5. Fluxo do usuário

**A. Pelo site (o caminho principal)**
1. No card, no hero, no modal ou na página `/livro/<id>/`, o usuário toca no sino ("Me avise se baixar").
2. O Telegram abre `t.me/ofertaslivros_bot?start=<id>`, e ele toca em **Iniciar**. Chega `/start <id>`.
3. O bot adiciona o livro e responde na hora (textos na seção 6). Se o livro já está em oferta agora, manda também o aviso (e grava em `avisos`, para o cron não repetir).

**B. Direto no bot**
1. `/start` sem parâmetro: boas-vindas.
2. O usuário manda "torto arado" ou "Itamar Vieira Junior" ou várias linhas.
3. Com um único resultado, o bot adiciona e mostra um botão "Desfazer". Com vários, mostra até 5 botões para escolher. Sem nenhum, oferece o pedido de livro.

**C. Aviso**
1. A cada 30 min, o cron do Worker lê o `/bot.json` publicado e vê quais livros estão em oferta.
2. Para cada chat não pausado com aquele livro (ou autor) na lista que ainda não foi avisado nesta entrada em oferta, manda uma mensagem, das 08h às 22h BRT.
3. O usuário toca no link `/r/<id>/bot`, que leva à loja com a nossa tag.

**D. Sair**
- `/lista` e o botão "Tirar" removem um item. `/pausar` e `/voltar` controlam os avisos. `/parar` apaga tudo depois de um toque de confirmação. Bloquear o bot também apaga tudo (update `my_chat_member` com `kicked`, ou erro 403 no envio).

## 6. Comandos e textos exatos

Regras para todos os textos:
- Texto puro, **sem `parse_mode`**, e `link_preview_options.is_disabled = true` em toda mensagem (seção 10).
- Título e autor vêm do `bot.json` e entram literais.
- Nos botões, o rótulo é cortado em 60 chars com "…".
- `SITE` = `https://ofertaslivros.com.br`. `<lista>` = "Sua lista: /lista".
- Tom da Mavi: primeira pessoa, curto, sem exclamação em excesso nem emoji.

### 6.1 `/start` (sem parâmetro)
```
Oi, eu sou a Mavi, do Ofertas Livros.
Me diga um livro ou um autor e eu aviso aqui quando ele entrar em oferta no site.
É só mandar o título ou o nome do autor numa mensagem. Pode mandar vários, um por linha.
Ajuda: /ajuda
```
Botão (URL): `Ver as ofertas de hoje` → `SITE/ofertas/`.
Na **primeira** mensagem a um chat novo (quando a linha em `chats` é criada, por qualquer caminho), acrescentar:
```
Guardo só o número desta conversa e a sua lista. Para apagar tudo: /parar. Privacidade: https://ofertaslivros.com.br/privacidade/
```

### 6.2 `/start <id>` (botão do site)
- O id passa em `TG_START_RE` e existe no `bot.json`:
  ```
  Pronto: <Título>, de <Autor>, está na sua lista.
  Aviso aqui quando ele entrar em oferta.
  Sua lista: /lista
  ```
  - Se o livro está em oferta agora (`texto` não nulo e dentro do `valido_ate`), manda uma segunda mensagem com o aviso da seção 6.9, cabeçalho `Ele já está em oferta agora:`, e grava em `avisos`.
- Já estava na lista: `<Título> já está na sua lista. Sua lista: /lista`.
- Lista cheia: `Sua lista já tem 30 itens, o máximo. Tire algum em /lista e tente de novo.`
- O id é inválido ou não está no catálogo: `Não achei esse livro no catálogo agora. Mande o título que eu procuro.`

### 6.3 Texto livre (cadastro)
**Normalização:**
- `fold` igual ao do `app.js`/`build.fold` (minúsculas, NFKD, sem marcas), espaços colapsados e aspas e pontuação nas pontas removidas.
- Se a linha tiver ` — `, ` – ` ou ` - `, a parte da esquerda é o título e a da direita, o autor.
- A linha precisa ter de 3 a 120 chars.

**Casamento:**
- **Livro:** todas as palavras da consulta aparecem no campo `busca` do livro (`fold(título + " " + autor)`). Com "Título — Autor", as palavras do título aparecem no título e as do autor, no autor.
- **Autor:** a consulta normalizada é igual a um dos `autores` de algum livro.
- A ordem: título exato primeiro, depois o título que começa com a consulta, depois o resto, por título.

**Uma linha só:**

| Resultado | Resposta |
|---|---|
| 1 livro e nenhum autor | `Pronto: <Título>, de <Autor>, está na sua lista.` + `Aviso aqui quando ele entrar em oferta.` Botão `Desfazer` (remove o item) |
| Autor (com ou sem livros) | `Quer aviso de qual?` Botões: `Todos de <Autor> (<n> no catálogo)` e até 4 livros como `<Título> — <Autor>` |
| 2 a 5 livros | `Achei mais de um. Qual deles?` 1 botão por livro, mais `Nenhum desses` |
| Mais de 5 livros | `Achei <n>. Mostro os 5 primeiros; se não for nenhum, mande o título mais completo.` 5 botões, mais `Nenhum desses` |
| Nenhum | `Não achei “<linha>” no nosso catálogo. Quer que eu peça para a curadoria incluir?` Botões: `Pedir este livro` e `Não, obrigado` |

- Depois de escolher num botão, vale a mesma confirmação "Pronto: …". Para o autor: `Pronto: aviso quando sair oferta de livro de <Autor>.`
- O botão `Nenhum desses` leva à pergunta do pedido de livro.

**Pedido de livro:**
- `Pedir este livro` grava em `pedidos` (`titulo` = a linha original, até 150 chars, e `autor` = a parte do autor, se houver), no D1 `ANALYTICS`, com o mesmo `PEDIDOS_SCHEMA` e a mesma retenção de 30 dias do form. Não grava `chat_id` e não manda e-mail (o form manda; aqui não, para não virar canal de spam por e-mail).
- Resposta: `Pedido enviado para a curadoria. Se o livro entrar no catálogo, ele aparece no site e no canal. Eu não aviso sozinha: quando ele aparecer, é só me mandar o título de novo.`
- O texto do pedido não cabe no `callback_data` (64 bytes). Por isso a resposta do bot é enviada como reply da mensagem do usuário (`reply_parameters`), e o callback lê o texto em `callback_query.message.reply_to_message.text`. Nada fica guardado entre as duas mensagens.
- Limite: 1 pedido por chat por minuto (rate limit `BOT_PEDIDOS`, seção 10). Passou disso: `Calma, acabei de anotar um pedido seu. Tente de novo em um minuto.`

**Várias linhas** (2 a 10):
- Adiciona só os resultados únicos e responde com um resumo. Cada linha do resumo aparece só se tiver item:
  ```
  Adicionei: <Título 1>; <Título 2>.
  Achei mais de um para: <linha>. Mande sozinho para eu mostrar as opções.
  Não achei: <linha>. Mande sozinho para pedir à curadoria.
  Sua lista: /lista
  ```
- Mais de 10 linhas, ou linha com mais de 120 chars: `Mande até 10 nomes por mensagem, um por linha.`

**Outros casos:**
- Mensagem sem texto (foto, figurinha, áudio): `Por aqui eu só entendo texto: mande o título ou o nome do autor.`
- Comando desconhecido: `Não conheço esse comando. Veja /ajuda.`

### 6.4 `/lista`
- Vazia: `Sua lista está vazia. Mande o título ou o autor de um livro para começar.`
- Com itens (ordem de inclusão):
  ```
  Sua lista (<n> de 30):
  • <Título>, de <Autor> (em oferta agora)
  • <Título>, de <Autor>
  • Autor: <Autor> (<k> livros no catálogo)
  • <id> (fora do catálogo agora)
  Para tirar um item, toque nele abaixo.
  ```
  - "(em oferta agora)" só aparece com `texto` não nulo e dentro do `valido_ate`.
  - Se o chat estiver pausado, acrescentar `Avisos pausados. Para voltar: /voltar.`
  - Um botão por item: `Tirar: <Título>` / `Tirar: <Autor>`. O máximo é 30 botões, e o Telegram aceita 100.
- Tocar em `Tirar`: o callback responde `Tirei da lista.` (`answerCallbackQuery`) e a mensagem é editada (`editMessageText`) com a lista nova. Se a edição falhar, manda a lista nova numa mensagem nova.

### 6.5 `/pausar`
`Avisos pausados. Sua lista continua guardada. Para voltar: /voltar.`

### 6.6 `/voltar`
`Voltei a avisar. Sua lista: /lista`
- Livros que entraram em oferta durante a pausa e ainda estão em oferta são avisados no próximo cron, dentro dos limites da seção 7.4.

### 6.7 `/parar`
- `Isso apaga sua lista e tudo o que guardo sobre esta conversa. Quer mesmo?`, com os botões `Apagar tudo` e `Cancelar`.
- `Apagar tudo`: apaga as linhas do chat em `chats`, `desejos` e `avisos` e responde `Pronto, apaguei tudo. Se quiser voltar, é só mandar /start.`
- `Cancelar`: `Nada foi apagado.`

### 6.8 `/ajuda`
```
Como usar:
• Mande o título ou o nome do autor. Pode mandar vários, um por linha. Ex.: Torto Arado — Itamar Vieira Junior
• Eu aviso aqui quando o livro entrar em oferta no site, com o mesmo critério do site e do canal.
• Aviso uma vez por oferta, das 8h às 22h. Se o preço cair mais, aviso de novo.
• /lista mostra e tira itens · /pausar pausa os avisos · /voltar retoma · /parar apaga tudo
• O preço final é o da loja. Os links são de afiliado: ganhamos com compras qualificadas, sem custo para você.
Privacidade: https://ofertaslivros.com.br/privacidade/
```

### 6.9 Aviso (enviado pelo cron)
```
Entrou em oferta (está na sua lista):

<texto do bot.json, que é o build.post_text(o, SITE + "/r/<id>/bot")>

Tirar da lista: /lista
```
- Cabeçalho para item de autor: `Entrou em oferta, de <Autor> (autor na sua lista):`.
- Cabeçalho para queda adicional: `Baixou mais (está na sua lista):`.
- O `post_text` já traz o selo "Menor preço em 90 dias", o de/por, a loja, "preço verificado em DD/MM às HHhMM. O preço final é o da loja." e "Link de afiliado: …". O Worker **não formata preço**: só junta o cabeçalho e o rodapé ao texto pronto.

### 6.10 Lista de comandos e descrição (BotFather / `setMyCommands`)
| Comando | Descrição |
|---|---|
| `lista` | Minha lista |
| `pausar` | Pausar avisos |
| `voltar` | Voltar a avisar |
| `ajuda` | Como usar |
| `parar` | Apagar meus dados |

- Descrição curta (`setMyShortDescription`): `Aviso no Telegram quando o livro que você quer entrar em oferta. ofertaslivros.com.br`.
- Descrição (`setMyDescription`): `Sou a Mavi, do Ofertas Livros. Me diga um livro ou um autor e eu aviso quando ele entrar em oferta, com o preço conferido na loja. Toque em Iniciar.`
- A descrição atual ("Em breve: …") sai **só no lançamento** (seção 12, etapa 5).

## 7. Disparo: onde roda e regras

### 7.1 Opções

| | (A) Cron Trigger no Worker do site lendo `/bot.json` | (A') Cron no `ofertaslivros-cron` | (B) `telegram.yml` lendo o D1 pela API |
|---|---|---|---|
| Onde está a regra de oferta | No `build.py`, que grava `oferta`, `texto` e `valido_ate` no `bot.json`. O Worker só compara estados | Igual à A | No Python, com `build` importado direto |
| Dado de usuário | Não sai da Cloudflare | Não sai da Cloudflare | Passa pelo runner do GitHub, num repo com **log público** |
| Credenciais novas | `TELEGRAM_BOT_TOKEN` como segredo do Worker do site (ele já precisa para responder ao webhook) | Token também no Worker de cron: dois Workers com o token | Token da Cloudflare com **D1 Edit** no GitHub. Se vazar, expõe todos os `chat_id` |
| Latência | Até 30 min depois do deploy | Igual | Logo depois do deploy, mas o GitHub atrasa no pico |
| Limites | Free: 10 ms de CPU por execução (I/O não conta) e 50 subrequests externas (envios ao Telegram). D1 conta no limite interno de 1.000 | Igual | Sem limite prático |
| Cron Triggers | +1 (4 de 5 no Free) | 0 (reaproveita o `*/30`) | 0 |
| Testes | `node --test`, como `worker/*.test.mjs` | Igual | pytest |
| Código duplicado | Nenhuma regra: o Worker não calcula oferta nem formata preço | Igual | Nenhum |

**Recomendação: (A).**
- O dado pessoal fica só na Cloudflare, e nenhum token de D1 vai para o GitHub.
- A regra continua num lugar só (`build.py`), porque o build exporta o resultado pronto.
- O Worker do site já tem o D1, o token e o binding `ASSETS` para ler o `bot.json` sem subrequest externa.
- A (A') obrigaria a pôr o token do bot em mais um Worker e a ler o arquivo por HTTP.
- A (B) só ganha na latência de minutos, o que não compensa expor `chat_id` a um runner com log público.

### 7.2 O `bot.json` (gerado pelo `build.py`, publicado em `dist/bot.json`)
- Só dado que já é público no site. Sem dado de usuário.
- Formato, uma entrada por livro do `resolve` (os mesmos que têm `/livro/<id>/`):
  ```json
  {"version": 1, "gerado_em": "2026-11-06T12:00:00+00:00",
   "livros": [{"id": "torto-arado", "titulo": "Torto Arado", "autor": "Itamar Vieira Junior",
               "busca": "torto arado itamar vieira junior", "autores": ["itamar vieira junior"],
               "preco_cents": 4290, "desconto": 42, "valido_ate": "2026-11-06T14:00:00+00:00",
               "texto": "Torto Arado, de Itamar ... Link de afiliado: https://ofertaslivros.com.br/r/torto-arado/bot"}]}
  ```
- **`texto`** só existe com `oferta and not velho`, e nos outros casos é `null`. Sai de `post_text(o, f"{SITE}/r/{o['id']}/bot")`.
- **`valido_ate`** = `checked_at + FRESH[store]` da loja que vence primeiro (o `texto` pode citar a outra loja, em "Também no..."). Assim o Worker não manda um preço que venceu entre o deploy e o cron, e não precisa conhecer o `FRESH`.
- **`autores`:** o `autor` dividido em `,`, `;`, `&` e ` e `, cada parte com `fold`. Ex.: "Neil Gaiman e Terry Pratchett" → `["neil gaiman", "terry pratchett"]`.
  - `ponytail`: a divisão ingênua erra autor com " e " no nome. Corrigir com um campo `authors` no contrato se aparecer caso real.
- `bot` entra em `RESERVED`.
- O `robots.txt` ganha `Disallow: /bot.json`.

### 7.3 Regra de "avisar uma vez por entrada em oferta" (idempotência)
O estado fica no D1 `BOT` (seção 9). Em cada execução, **sempre**, inclusive fora da janela:
1. Lê `env.ASSETS.fetch("/bot.json")` e valida `version == 1`. Se o arquivo for inválido, lança o erro (aparece no Workers Logs) e não manda nada.
2. `O` = livros com `texto` não nulo e `agora <= valido_ate`.
3. Atualiza `em_oferta(book_id, visto_em = agora)` para cada livro de `O`.
4. **Saída da oferta:** livro com `em_oferta.visto_em` mais velho que **6 h** saiu. Apaga a linha dele em `em_oferta` e todas as linhas de `avisos` com aquele `book_id`. A carência de 6 h absorve o pisca-pisca (a loja do ML perde o prazo de 2 h por uma coleta, e o livro some e volta). Sem ela, o mesmo livro avisaria duas vezes no mesmo dia.
5. Só **dentro da janela 08h–22h BRT**, calcula os candidatos: pares `(chat, livro)` em que
   - o chat não está pausado;
   - o livro está em `O` e está na lista do chat (como livro ou por um dos `autores`);
   - **e** não há linha em `avisos` para o par **ou** `preco_cents * 100 <= avisos.price_cents * 95`. Isso é "caiu mais": pelo menos 5% abaixo do último aviso.
   - O join pode usar `json_each(?1)` com `O` passado como parâmetro, sem tabela temporária.
   - O mesmo livro pela lista e pelo autor conta como **um** par.
6. Envia, com os limites da 7.4. Depois do `ok` do Telegram, faz upsert de `avisos(chat_id, book_id, price_cents, avisado_em)`.
   - Limite conhecido, como no canal: se a execução morrer entre o envio e o upsert, aquele aviso se repete uma vez.

### 7.4 Limites de envio
- No máximo **3 avisos por chat por execução** e **10 por chat por dia BRT**. O dia conta pelas linhas de `avisos` com `avisado_em` de hoje. O que passar fica para a próxima execução: o estado garante que nada se perde enquanto o livro estiver em oferta.
- No máximo **40 envios por execução**, abaixo das 50 subrequests externas do Free. A ordem: chats com menos avisos hoje primeiro, depois livros com selo de 90 dias e depois o maior desconto.
- Telegram **429**: para a execução e deixa o resto para a próxima.
- **403** (bot bloqueado ou chat apagado): apaga o chat e tudo dele.
- Outros erros: conta e segue.
- O log só leva contagens: `bot-cron: 12 em oferta, 5 enviados, 1 bloqueado, 0 erro`.
- Cron: `"triggers": {"crons": ["20,50 * * * *"]}` no `wrangler.jsonc`. Ele roda 20 min depois do dispatch da coleta, quando o deploy normalmente já terminou.

## 8. Medição: `/r/<id>/bot`

- O `build.py` passa a gerar `/r/<id>/bot` junto de `/tg` e `/wa`. `channel_tags()` ganha `"bot"`, com a var `AMAZON_TAG_BOT`, e `post_text` aceita o caminho `/r/<id>/bot`.
- Sem a var, vale a tag do site, como já acontece com `/tg` e `/wa`. No ML, o link é o mesmo `ml_url`, e os cliques ficam agregados no painel do ML.
- **Por que tracking ID próprio:** o relatório da Amazon por tracking ID separa as vendas do bot das do canal sem nenhum código de contagem, e o `daily_rollup` já conta os 302 por caminho.
  - O `/painel` e a query "Telegram × WhatsApp × site" da `analytics.md` ganham o caso `'%/bot' → 'bot'`.
  - O Elias cria o tracking ID no painel dos Associados (ex.: `<base>bot-20`) e o cadastra como var `AMAZON_TAG_BOT`, que não é segredo.
- **Regras do `_redirects`:** passam de 5 para 6 por livro (`/r/<id>`, as duas lojas, `/tg`, `/wa` e `/bot`), o que cabe cerca de 333 livros com duas lojas. Hoje são 168. A docstring de `redirects` e o `MAX_REDIRECTS` continuam valendo: o build falha se passar.

## 9. Dados, retenção e LGPD

**Banco:** um D1 novo, **`ofertaslivros-bot`** (binding `BOT`), separado do `ofertaslivros-analytics`. Assim, uma query do painel ou do rollup nunca toca `chat_id`, e o acesso a dado pessoal fica restrito a um binding só. O Free permite 10 bancos.

```sql
CREATE TABLE IF NOT EXISTS chats (
  chat_id INTEGER PRIMARY KEY,   -- id do chat privado (= id do usuário no Telegram)
  pausado INTEGER NOT NULL DEFAULT 0,
  criado_em TEXT NOT NULL,
  visto_em TEXT NOT NULL         -- última mensagem ou toque do usuário (para a retenção)
);
CREATE TABLE IF NOT EXISTS desejos (
  id INTEGER PRIMARY KEY,        -- usado no callback "Tirar"
  chat_id INTEGER NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('livro', 'autor')),
  chave TEXT NOT NULL,           -- id do livro (ID_RE) ou autor com fold, até 100 chars
  criado_em TEXT NOT NULL,
  UNIQUE (chat_id, tipo, chave)
);
CREATE TABLE IF NOT EXISTS avisos (
  chat_id INTEGER NOT NULL, book_id TEXT NOT NULL, price_cents INTEGER NOT NULL, avisado_em TEXT NOT NULL,
  PRIMARY KEY (chat_id, book_id)
);
CREATE TABLE IF NOT EXISTS em_oferta (book_id TEXT PRIMARY KEY, visto_em TEXT NOT NULL);  -- sem dado pessoal
```

- **O que guardamos:** `chat_id`, a lista (ids de livro e nomes de autor), se está pausado, as datas de criação e de último uso e, por livro, o preço e a data do último aviso.
- **O que não guardamos:** nome, `username`, telefone, idioma, o texto das mensagens (a consulta é usada na hora e descartada; só a escolha vira `desejos`) e o histórico de avisos depois que o livro sai da oferta.
- **Onde fica:** Cloudflare D1, sem acesso público. O operador é a Cloudflare. A mensagem passa pelo Telegram, que tem a política dele.
- **Por quanto tempo:**
  - a lista fica enquanto o chat estiver em uso. Um chat sem nenhuma mensagem ou toque por **12 meses** é apagado por inteiro, sem aviso (pelo cron diário do próprio Worker, na primeira execução depois das 03h BRT);
  - a linha de `avisos` some quando o livro sai da oferta (7.3, passo 4);
  - os pedidos feitos pelo bot seguem a regra do form: 30 dias, sem dado do usuário.
- **Como o usuário remove:** `Tirar` em `/lista` (um item), `/parar` (tudo) ou bloqueando o bot (tudo, por `my_chat_member` `kicked` ou pelo 403 no envio).
- **Base legal:** execução do serviço pedido pelo próprio usuário. Não há uso para outra finalidade, perfil nem compartilhamento.
- **Logs:** nunca `chat_id`, texto de mensagem, `callback_data`, token nem o header secreto. Só contagens e tipos de erro, como no `pedido.js`.

**Mudanças na `/privacidade/` (`build.py:privacy`):** a seção "No alerta de preço do Telegram" vira "Na lista de desejos do Telegram", com o conteúdo acima:
- o que guardamos e o que não guardamos;
- que é um D1 da Cloudflare;
- os 12 meses sem uso;
- como apagar (`/lista`, `/parar`, bloquear o bot).

Sai do texto atual: preço-alvo, "90 dias", "apagado quando a mensagem é enviada" e `/remover`. Acrescentar uma frase sobre o pedido pelo bot: "Se você pedir um livro pelo bot, o pedido vai para a curadoria sem nenhum dado seu."

Há também uma inconsistência que já existe e não é deste escopo: a seção "No pedido de livro" diz "O site não guarda o pedido", mas o `pedido.js` guarda por 30 dias no D1 desde a `analytics.md`. O Elias decidiu em 2026-11-05 não mudar esse texto. Ela fica registrada como decisão em aberto 3.

## 10. Segurança

- **Webhook:**
  - `POST /telegram` em `run_worker_first`. **A rota não é secreta,** porque o `wrangler.jsonc` é público. O controle real é o header `X-Telegram-Bot-Api-Secret-Token`, comparado em tempo constante (`crypto.subtle.timingSafeEqual`) com o segredo `TELEGRAM_WEBHOOK_SECRET` (aleatório, 32+ chars em `[A-Za-z0-9_-]`, como o Telegram exige).
  - Header ausente ou errado: `401` sem corpo útil e sem tocar no D1. Método diferente de POST: `405`.
  - `Content-Length` acima de 64 KB: `413`, conferido antes de ler o corpo, como no `pedido.js`.
  - Autenticado: responde sempre `200`, mesmo com erro interno (contado no log). Assim o Telegram não fica reenviando o mesmo update.
- **Escopo:**
  - `setWebhook` com `allowed_updates: ["message", "callback_query", "my_chat_member"]`.
  - Qualquer update com `chat.type != "private"` é ignorado em silêncio.
  - No BotFather: `/setjoingroups` desligado.
- **Rate limit:** binding novo `BOT_LIMITE`, com 20 updates por minuto por `chat_id`. Passou disso, o update é ignorado em silêncio. A chave não é guardada. Os pedidos de livro usam um segundo namespace, `BOT_PEDIDOS`, com 1 por minuto por `chat_id`. O binding só aceita período de 10 ou 60 s, então não existe limite diário sem guardar contador; com 20 updates por minuto no total e sem e-mail, o pior caso é lixo na tabela `pedidos`, que o Elias vê no `/painel` e o cron apaga em 30 dias.
- **Callbacks:** o `callback_data` é dado do cliente e não é confiável.
  - `add:<id>`: o id passa em `ID_RE` e existe no `bot.json`.
  - `au:<id>:<k>`: o autor `k` do livro `id`.
  - `rm:<n>`: `DELETE ... WHERE id = ? AND chat_id = ?`, preso ao chat de quem tocou (sem IDOR).
  - `pd`, `no` e `stop:sim`/`stop:nao`.
  - Tudo com até 64 bytes. Formato desconhecido: `answerCallbackQuery` vazio.
  - O build já barra id com mais de 64 chars quando o bot está ligado (`tg_alert_url`). O id mais longo hoje tem 54. Com o prefixo `add:`, o limite efetivo é de 60: o contrato do `offers.json` (`validate_offer`) passa a aceitar id de até 60 chars, com ou sem o bot ligado. Assim um id longo falha no `catalog-check`, e não só no deploy depois de ligar a var. Nenhum id real quebra: o coletor já limita a 57 (`collector/collect.py`, `ID_MAX`).
- **Saída:**
  - texto puro, **sem `parse_mode`** (um título com `<b>` ou `*` chega literal);
  - sem prévia de link, pelo mesmo motivo do canal: o servidor do Telegram seguiria o `/r/` e geraria clique de robô no link de afiliado;
  - o único link de loja é o `/r/<id>/bot` do nosso domínio, já validado pelo `post_text`. Nenhuma URL vinda do usuário é ecoada como link.
- **SQL:** só com `prepare().bind()`, nunca interpolando texto do usuário.
- **Front:** nada de `innerHTML` com dado do bot. O site não muda de JS: o botão é um `<a>` que o build gera.
- **Segredos:**
  - `TELEGRAM_BOT_TOKEN` e `TELEGRAM_WEBHOOK_SECRET` ficam como segredos do Worker `ofertaslivros` (`wrangler secret put` ou painel), fora do repo.
  - O token passa a existir em dois lugares (o Environment `telegram` do GitHub e o Worker). A rotação precisa atualizar os dois: registrar no `SETUP.md`.
- **Logs da Cloudflare:** o `wrangler.jsonc` não liga o `observability`. Se alguém ligar, o security-auditor confere se os headers da requisição (com o secret) não vão para os logs.

## 11. Critérios de aceite (testáveis)

Testes do Worker em `worker/bot.test.mjs` (`node --test`, como os que já existem), com o Telegram e o D1 falsos.

**Webhook e segurança**
1. Sem o header, ou com o header errado: `401`, nenhuma query no D1 e nenhuma chamada ao Telegram.
2. Com o header certo e corpo maior que 64 KB: `413` antes de ler o corpo.
3. Update de grupo, supergrupo ou canal: `200`, nada gravado e nada enviado.
4. O 21º update do mesmo `chat_id` no mesmo minuto não gera resposta.
5. Nenhum `console.log` do bot contém o `chat_id` sentinela, o texto sentinela da mensagem ou o token. O teste captura o console e procura os três.
6. Toda chamada `sendMessage`/`editMessageText` sai sem `parse_mode` e com `link_preview_options.is_disabled: true`. Um título `<b>x</b>` chega literal.
7. Um callback `rm:<n>` de outro chat não apaga nada. `add:` com id fora do catálogo ou fora de `ID_RE` não grava nada.

**Comandos**
8. `/start torto-arado` cria `chats` e `desejos(livro, torto-arado)` e responde o texto 6.2 com a nota de privacidade (primeira vez). Repetir não duplica e responde "já está na sua lista".
9. `/start <id>` de livro em oferta manda o aviso na hora e grava em `avisos`. O cron seguinte não reenvia.
10. `/start id-que-nao-existe`, `/start ../x` e `/start` com 65 chars respondem "Não achei esse livro…" e não gravam nada.
11. Texto "torto arado" com um único resultado adiciona e mostra `Desfazer`. "itamar vieira junior" mostra o botão `Todos de …`. Uma consulta com 7 resultados mostra 5 botões e o texto "Achei 7…". "xyzxyz" oferece o pedido.
12. "Torto Arado — Itamar Vieira Junior" e "torto arado - itamar" casam com o mesmo livro. A dobra de acento bate com o `fold` do `app.js` (vetores de teste compartilhados: "Ação" → "acao", "Mangá" → "manga").
13. Uma mensagem com 3 linhas (1 única, 1 ambígua, 1 sem resultado) adiciona 1 e responde o resumo da 6.3. Com 11 linhas, responde o erro de limite sem gravar nada.
14. O 31º item é recusado com o texto de lista cheia.
15. `Pedir este livro` grava uma linha em `pedidos` com o texto da mensagem original e sem nenhuma coluna de chat. Um segundo pedido do mesmo chat no mesmo minuto é recusado.
16. `/lista` mostra os itens na ordem, "(em oferta agora)" só nos que têm `texto` válido, e um botão `Tirar` por item. `Tirar` apaga só aquele item e edita a lista.
17. `/pausar` → o cron não envia nada para o chat. `/voltar` → o próximo cron envia.
18. `/parar` + `Apagar tudo` apaga todas as linhas do chat em `chats`, `desejos` e `avisos`. `Cancelar` não apaga nada.
19. Um update `my_chat_member` com `new_chat_member.status = "kicked"` apaga tudo do chat.

**Disparo (cron)**
20. Um livro em `O` e na lista de um chat ativo gera exatamente 1 envio. Rodar o cron duas vezes sobre o mesmo estado: 1 envio, não 2.
21. O livro some de `O` por menos de 6 h e volta: nenhum envio novo. Some por mais de 6 h e volta: 1 envio novo.
22. O preço cai para 95% ou menos do último aviso: 1 envio com o cabeçalho "Baixou mais". Cai só 3%: nenhum envio.
23. Livro com `agora > valido_ate` ou `texto: null`: nenhum envio.
24. Às 23h BRT: nenhum envio, mas o `em_oferta` é atualizado. Às 08h20, sem ter saído da oferta, o aviso pendente sai, e um livro que estava em oferta à noite não conta como "saiu e voltou".
25. Com 5 livros elegíveis para um chat, saem 3 na execução e 2 na seguinte. Com 60 pares elegíveis, saem 40.
26. Um chat com o livro na lista e o autor na lista recebe 1 aviso para aquele livro, não 2.
27. Um 403 do Telegram apaga o chat. Um 429 interrompe a execução sem gravar `avisos` dos não enviados.
28. Um `bot.json` com `version` diferente de 1, ou inválido: a execução lança erro e não manda nada.
29. Chat com `visto_em` de 12 meses e 1 dia atrás é apagado na limpeza diária. Chat com 11 meses fica.

**Build (pytest / `build.py --selftest`)**
30. O `dist/bot.json` tem uma entrada por livro do `resolve`. `texto` não é nulo só com `oferta and not velho`, e é igual a `post_text(o, SITE + "/r/<id>/bot")`. `valido_ate` = o menor `checked_at + FRESH[store]` entre as lojas do livro.
31. O `_redirects` tem `/r/<id>/bot` para cada livro, com a tag `AMAZON_TAG_BOT` na Amazon (ou a do site, sem a var) e o mesmo `ml_url` no ML.
32. O `post_text` aceita `/r/<id>/bot` e continua recusando qualquer outro caminho e host de loja.
33. O build falha com id de mais de 60 chars, com ou sem `TELEGRAM_BOT_USERNAME` (o deep link também recusa 61).
34. `bot` está em `RESERVED`, e o `robots.txt` tem `Disallow: /bot.json`.

**Site**
35. Com `TELEGRAM_BOT_USERNAME=ofertaslivros_bot`, todo sino e todo "Me avise se baixar" apontam para `https://t.me/ofertaslivros_bot?start=<id>`, com `rel="noopener noreferrer"`. A CSP não muda e o site continua sem JS.
36. `/privacidade/` descreve o que está na seção 9 e não menciona preço-alvo, 90 dias nem `/remover`. O FAQ, o `banner_bot` e o `bot_block` não dizem mais "guarda o preço de hoje" nem "apaga o alerta quando ele disparar". Passam a dizer "avisa quando entrar em oferta" e "para apagar, /parar".

## 12. Divisão por agent (ordem de execução)

0. **Elias (antes):**
   - criar o tracking ID do bot nos Associados e cadastrar a var `AMAZON_TAG_BOT`;
   - confirmar no BotFather que `/setjoingroups` está desligado;
   - responder às decisões da seção 14.
1. **frontend-developer + collector-engineer**, PR 1, sensível (`_redirects`, tag, rota `/r/`). No `build.py`:
   - `/r/<id>/bot` e `AMAZON_TAG_BOT` em `channel_tags`, e o `post_text` aceitando `/bot`;
   - o `dist/bot.json` e `bot` em `RESERVED`;
   - o `Disallow` no robots;
   - o limite de 60 chars para o id;
   - `AMAZON_TAG_BOT` no `env` do `deploy.yml` (workflow: sensível).
   - Critérios 30 a 34. Quem pega: o collector-engineer cuida do contrato do `bot.json`, e o frontend-developer cuida de `robots`/`RESERVED`. Pode ser um agent só, se o Elias preferir.
2. **infra-engineer**, PR 2, sensível (`wrangler.jsonc`, Cloudflare, segredos):
   - criar o D1 `ofertaslivros-bot` e o binding `BOT`;
   - os ratelimits `BOT_LIMITE` e `BOT_PEDIDOS`;
   - `/telegram` em `run_worker_first`;
   - `triggers.crons: ["20,50 * * * *"]` no `wrangler.jsonc` do site (confere o total de 4 de 5 Cron Triggers da conta);
   - os segredos `TELEGRAM_BOT_TOKEN` e `TELEGRAM_WEBHOOK_SECRET` no Worker;
   - `SETUP.md` com a rotação do token nos dois lugares.
   - Ainda **sem** `setWebhook`.
3. **alerts-engineer**, PR 3, sensível (dado de usuário):
   - `worker/bot.js` (webhook, comandos, busca, callbacks e pedidos) e `worker/bot-cron.js` (7.3 e 7.4, mais a limpeza de 12 meses);
   - em `worker/index.js`, a rota `/telegram` e o handler `scheduled`;
   - o schema criado com `CREATE TABLE IF NOT EXISTS`, como o `PEDIDOS_SCHEMA`;
   - `worker/bot.test.mjs` com os critérios 1 a 29;
   - o caso `'bot'` no canal do `painel.js` e na query da `analytics.md`.
4. **security-auditor:**
   - revisar os PRs 2 e 3: header secret em tempo constante, IDOR nos callbacks, logs, `allowed_updates`, rate limit, SQL com bind, segredos fora do repo e `observability`;
   - rodar `/threat-model` com o bot incluído e `/security-review` antes do deploy.
5. **infra-engineer**, lançamento, depois do merge e do deploy dos PRs 1 a 3:
   - `setWebhook` (`url` = `https://ofertaslivros.com.br/telegram`, `secret_token`, `allowed_updates`, `drop_pending_updates: true`);
   - `setMyCommands`, `setMyShortDescription` e `setMyDescription` com os textos da 6.10;
   - tudo por `curl` local com o token do `.env`, sem ecoar o token.
   - Teste de fumaça no chat do Elias: `/start`, adicionar, `/lista`, `Tirar` e `/parar`.
6. **frontend-developer**, PR 4, sensível (texto legal):
   - `/privacidade/`, FAQ, `banner_bot`, `bot_block` e a página `/canais/` com os textos novos (critério 36).
   - Merge **antes** de ligar a var, porque a política precisa estar publicada antes de guardar `chat_id`.
7. **Elias:** liga a var `TELEGRAM_BOT_USERNAME=ofertaslivros_bot` no GitHub (critério 35). O próximo deploy acende os botões.
8. **code-reviewer:** review em cada PR (no PR 4, com `web-design-guidelines`), além do review do Codex do fluxo de merge.

## 13. Riscos

- **Regra 1 (Amazon):** nada aqui faz request à Amazon. O preço vem do `offers.json` que já existe. Valem as mesmas ressalvas da exceção do navegador: o aviso usa o preço lido pelo Chrome do Elias, com "preço verificado em" e "o preço final é o da loja".
- **Política da Amazon para link em mensagem privada:** a dúvida de 2026-10-18 (`alerta-de-preco.md` §10) nunca foi respondida para mensagem **individual**. O Elias liberou o canal público em 2026-10-21, mas o bot é outro caso. Ver a decisão 1.
- **Transparência (regra 4):** todo aviso traz "Link de afiliado:" e "O preço final é o da loja." (pelo `post_text`), e o `/ajuda` traz o aviso de associado.
- **LGPD:** seção 9. O dado pessoal é o mínimo, a finalidade é o serviço pedido, há prazo e remoção por comando, e a política sai publicada antes da coleta (etapa 6 antes da 7). Se a chave da Cloudflare vazar, ficam expostos o `chat_id` e os livros de interesse. A mitigação é um banco separado e um token da Cloudflare sem D1 no GitHub (é por isso que a recomendação é a opção A).
- **Custo:** R$ 0.
  - Workers Free: 100 mil requests por dia. Cada mensagem é 1 request: o webhook não chega perto, salvo abuso, e o rate limit segura.
  - D1 Free: 5 milhões de linhas lidas e 100 mil escritas por dia. O `em_oferta` escreve cerca de 50 linhas por execução, ou umas 2.400 por dia.
  - Os 10 ms de CPU: a busca percorre cerca de 170 livros por mensagem. Se o catálogo passar de uns 1.000, medir.
  - Cron: 4 de 5 triggers.
- **Operação:**
  - Se o deploy parar, o `bot.json` envelhece, e o `valido_ate` impede aviso com preço vencido. O bot só fica mudo.
  - Se o Worker cair, o Telegram guarda os updates por até 24 h e reenvia.
- **Spam por avisos:** os limites da 7.4 e a regra de uma vez por entrada em oferta. O canal já posta até 8 por dia. Quem segue o canal e tem o livro na lista recebe o mesmo livro duas vezes, o que é aceitável: são produtos diferentes.

## 14. Decisões em aberto para o Elias (com default recomendado)

1. **Link da Amazon no aviso individual.** Os termos dos Associados restringem link em comunicação privada (e-mail, mensagem). O BIS faz isso no Telegram.
   - **Default:** seguir o modelo do BIS, com o link `/r/<id>/bot` e tracking ID próprio, aceitando o risco como no canal. Se a Amazon reclamar, o aviso da Amazon passa a apontar para `/livro/<id>/` e só o ML leva o link direto.
   - Confirmar ou mandar o agent conferir o Operating Agreement antes do lançamento.
2. **Limites.** Default: 30 itens por chat, 3 avisos por chat por execução, 10 por dia, janela das 08h às 22h, "caiu mais" = 5% abaixo do último aviso e carência de 6 h para a saída da oferta. Ficam como constantes no `worker/bot-cron.js`.
3. **Texto do pedido de livro na `/privacidade/`.** Ele diz que o site não guarda o pedido, mas o D1 guarda por 30 dias. Default: corrigir junto, no PR 4 ("guardamos o pedido, sem dado seu, por 30 dias"). O Elias tinha decidido não mexer em 2026-11-05: confirmar se mantém.
4. **Retenção por inatividade.** Default: 12 meses sem nenhuma mensagem ou toque apagam tudo, sem aviso prévio. A alternativa é avisar uma semana antes, o que exige mais um estado e mais um envio.
5. **Disparo:** confirmar a opção A (Cron Trigger no Worker do site lendo o `/bot.json`) em vez do `telegram.yml` lendo o D1.
