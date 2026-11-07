# Spec: evento de saída para a loja na Meta Conversions API

Status: spec do `product-manager`, escrita em 2026-11-07. Nada implementado. Base conferida na `origin/main` em baba58c (2026-11-07): `worker/index.js`, `wrangler.jsonc`, `build.py` (`redirects()`, `HEADERS`, `privacy()`), `static/app.js` e `docs/produto/analytics.md`.

Todo o trabalho desta spec é **PR sensível** pelo CLAUDE.md: mexe na rota `/r/`, no Worker, em dado de usuário e em texto de privacidade. O merge de cada PR só acontece com o "aprovado, pode seguir" do Elias na sessão.

## 1. Problema e usuário

**Em uma frase:** quem vê o anúncio "OL | Black Friday IG | nov-26" no Instagram ou no Facebook cai numa das 5 páginas de destino e clica numa oferta. Hoje a Meta só vê a visualização da página de destino, e o nosso rollup vê o clique em `/r/`, mas misturado com o tráfego orgânico. Ninguém sabe **qual anúncio e qual posicionamento levam a pessoa até a loja**, que é o sinal mais próximo da venda.

**O que a spec entrega:** um evento server-side `SaidaLoja`, enviado pelo Worker à Meta quando uma pessoa que veio de anúncio pago passa por `/r/<id>`. No Ads Manager, ele vira a conversão personalizada "Saída para a loja", com custo por saída por anúncio e por posicionamento.

**O que a spec não entrega:** a venda. A venda acontece na Amazon e no ML, e o sinal dela continua sendo só o relatório de cada programa, importado no `/painel`.

### Como está hoje (conferido na `origin/main`)

- `/r/<id>`, `/r/<id>/<loja>` e `/r/<id>/tg|wa|bot` são regras estáticas do `_redirects`, geradas por `redirects()` no `build.py`, com o curinga `/r/* / 302`. O Worker não roda no `/r/`: o `run_worker_first` do `wrangler.jsonc` só tem `/pedido`, `/painel`, `/painel/*` e `/telegram`.
- O `docs/produto/analytics.md` registra a decisão de manter o `/r/` estático "para que a cota do Free nunca derrube o clique de afiliado". **Esta spec muda essa decisão** (risco na seção 9).
- Todo link para o `/r/` sai com `rel="sponsored noopener noreferrer"`: no `build.py` (`card`, `hero`, botões da outra loja) e no `static/app.js` (modal, linha 227). Com `noreferrer`, o navegador não manda `Referer` nem para o nosso próprio `/r/`.
- `Referrer-Policy: strict-origin-when-cross-origin` no `_headers`. A CSP é `script-src 'self'` e não muda.
- O GraphQL da zona no Free não traz query string nem referrer (teste F0 do `analytics.md`), então o `fbclid` não aparece no painel.
- Não há tag `ads` na `main`. O clique de saída de quem veio do anúncio é indistinguível do orgânico no `daily_rollup`.
- A `/privacidade/` diz: "O site não tem cadastro, cookies nem ferramentas de análise." Esse texto vai mudar.
- O `docs/produto/anuncios-lancamento.md` (rascunho local, fora da `main`) previa `/vitrine/` e a tag `ads`, e deixava a CAPI para "spec própria". Esta é essa spec. As decisões novas do Elias trocam o destino pelas 5 páginas abaixo. **A frase que aquele rascunho propunha para a `/privacidade/` ("O site não envia nenhum dado seu para ela") fica proibida**, porque passaria a ser falsa.

## 2. Como saber que a pessoa veio do anúncio (sem JS e sem cookie)

O `fbclid` só existe na URL da página de destino (`/black-friday/?fbclid=...`). O `/r/<id>` é outra requisição. Três caminhos levam o `fbclid` até o `/r/`:

| Caminho | Como | Sem JS? | Prós | Contras |
|---|---|---|---|---|
| **A. `Referer` (recomendado)** | Tirar o `noreferrer` dos links para o `/r/`. O navegador manda a URL completa da página como `Referer` na navegação same-origin (política `strict-origin-when-cross-origin`). O Worker lê o `fbclid` do `Referer` | Sim | Nenhum cookie, nenhum Worker nas páginas de destino, nenhum dado guardado | Perde o evento se a pessoa navegar para outra página do site antes de clicar |
| B. Cookie `_fbc` primário | Worker nas 5 páginas de destino grava `_fbc` por 90 dias (é o que a Meta recomenda); o `/r/` lê o cookie | Sim | Pega o clique mesmo depois de navegar | Cria um cookie de publicidade num site que hoje não tem cookie. O guia de cookies da ANPD torna o legítimo interesse bem mais difícil de sustentar. Também põe o Worker no caminho das páginas mais visitadas |
| C. `app.js` copia o `fbclid` para os links | JS | **Não** | — | Quebra a regra de "site completo sem JS" para a medição |

**Decisão recomendada: A.** O dado continua indo da página para o `/r/` sem nada guardado no navegador. A perda (quem navega antes de clicar) é aceitável para medir anúncio contra anúncio, porque ela afeta todos os anúncios por igual.

**Por que tirar o `noreferrer` não vaza nada para a loja:** o `noopener` continua lá. No 302 para a Amazon ou o ML, a política `strict-origin-when-cross-origin` é aplicada de novo a cada salto do redirecionamento, então a loja recebe só a origem (`https://ofertaslivros.com.br/`), sem caminho e sem `fbclid`. Hoje a loja não recebe nada. O `security-auditor` confere esse comportamento no teste manual (critério 9).

**Pago e orgânico:** o Instagram e o Facebook põem o `fbclid` em **qualquer** clique de saída, inclusive no link da bio e em posts orgânicos. Para mandar só o clique de anúncio pago, o anúncio leva o parâmetro de URL `utm_medium=paid`, configurado pelo Elias no campo "Parâmetros de URL" do anúncio. O Worker só envia o evento quando o `Referer` tem **os dois**: o `fbclid` e o `utm_medium=paid`.

## 3. O evento

### 3.1 Nome: `SaidaLoja` (evento personalizado)

- **Não usar `ViewContent`.** Esse evento padrão quer dizer "viu a página do produto", e quem passa pelo `/r/` está saindo para a loja. Se um dia houver outro sinal de `ViewContent`, os dois se misturariam.
- Também não usar `Lead`, `InitiateCheckout` nem `Purchase`: são eventos de outra coisa, e a otimização da Meta passaria a buscar um comportamento que não acontece no site.
- Um evento personalizado com nome próprio não se mistura com nada e vira conversão personalizada com uma regra só.

### 3.2 Quando dispara (todas as condições)

1. A requisição é `GET /r/...` e a resposta do `_redirects` é um 302 com `Location` em host da allowlist (`amazon.com.br`, `www.amazon.com.br`, `mercadolivre.com.br`, `www.mercadolivre.com.br`, `mercadolivre.com`, os mesmos de `ALLOWED_HOSTS`). O curinga `/r/* / 302`, que manda para a home, **não** dispara.
2. O `Referer` é da nossa origem (`https://ofertaslivros.com.br`).
3. O `Referer` tem `fbclid` que casa `^[A-Za-z0-9_-]{10,500}$`, sem mudar maiúsculas e minúsculas (a Meta avisa que o click ID diferencia caixa).
4. O `Referer` tem `utm_medium=paid`.
5. O navegador **não** manda `Sec-GPC: 1` e a requisição **não** traz o cookie de opt-out `sem_meta=1` (seção 5.4).
6. Os segredos `META_CAPI_TOKEN` e `META_DATASET_ID` existem. Sem eles, o Worker não faz nada além do redirecionamento. É o interruptor de desligar.

### 3.3 Corpo enviado

`POST https://graph.facebook.com/<versão>/<META_DATASET_ID>/events`, com o token no corpo ou no parâmetro `access_token` e a versão da Graph API fixada numa constante do Worker.

```json
{
  "data": [{
    "event_name": "SaidaLoja",
    "event_time": <agora, em segundos>,
    "event_id": "<crypto.randomUUID()>",
    "action_source": "website",
    "event_source_url": "https://ofertaslivros.com.br<caminho do Referer, sem query>",
    "user_data": {
      "fbc": "fb.1.<agora em ms>.<fbclid>",
      "client_user_agent": "<User-Agent da requisição>"
    }
  }],
  "test_event_code": "<META_TEST_CODE, só se o segredo existir>"
}
```

- `fbc`: formato `fb.1.<creationTime>.<fbclid>`. A Meta manda usar o índice `1` quando o servidor gera o valor sem gravar cookie, e usar como `creationTime` o momento em que o `fbclid` foi visto pela primeira vez. Aqui esse momento é o clique em `/r/`, porque nada é guardado. Não fazer hash.
- `client_user_agent`: a Meta exige esse campo em evento de site.
- `event_id`: não há pixel para deduplicar. Ele serve para a Meta descartar reenvio, se um dia houver retry.
- `event_source_url`: o caminho da página de destino sem a query string. É uma informação que a Meta já tem, porque é o destino do próprio anúncio.

### 3.4 O que **não** vai, e por quê

| Campo | Por que fica de fora |
|---|---|
| `client_ip_address` | A Meta recomenda, mas não exige. O `fbc` já identifica o clique exato do anúncio, e o IP só melhoraria a correspondência. Fica de fora por minimização (decisão 3). Se o teste mostrar evento recebido e não atribuído, a decisão volta para o Elias |
| E-mail, telefone, nome, `fbp`, `external_id` | Não temos, e não vamos coletar |
| Qual livro, autor, nicho ou loja (`content_ids`, `content_category`) | O livro clicado, ligado à identidade da pessoa na Meta, revela interesse de leitura. Com nichos como `politica`, isso pode virar inferência de opinião política ou convicção religiosa, que são dados sensíveis (LGPD, art. 5º, II). Para medir anúncio contra anúncio, o livro não é necessário |
| `value` e `currency` | A comissão não é conhecida no clique. Fora do MVP |

### 3.5 Como usar na campanha

No Gerenciador de Eventos, o Elias cria a **conversão personalizada** "Saída para a loja":
- fonte: o conjunto de dados desta spec;
- evento: `SaidaLoja`;
- regra: URL contém `ofertaslivros.com.br`;
- categoria: a mais neutra que o Gerenciador oferecer, como "Outro".

No Ads Manager:
- no nível do anúncio, em "Rastreamento", marcar o conjunto de dados;
- em "Colunas > Personalizar", acrescentar "Saída para a loja" e "Custo por Saída para a loja";
- em "Detalhamento", usar "Por entrega > Posicionamento" e o nível de anúncio.

## 4. Fluxo do usuário

1. A pessoa vê o anúncio no Feed ou nos Reels do Instagram ou do Facebook.
2. Ela toca e abre `https://ofertaslivros.com.br/negocios/?utm_source=meta&utm_medium=paid&utm_campaign=bf-ig-nov26&fbclid=...`. A página é a mesma de sempre: estática, sem JS obrigatório, sem cookie.
3. Ela toca numa oferta (card, hero ou modal). O navegador pede `/r/<id>` com `Referer: https://ofertaslivros.com.br/negocios/?utm_source=...&fbclid=...`.
4. O Worker pega a resposta do `_redirects` (302 para a loja) e a devolve na hora.
5. Depois de responder, dentro do `ctx.waitUntil`, o Worker manda o `SaidaLoja` para a Meta, com timeout de 3 s. Se a chamada falhar, nada acontece para a pessoa.
6. Ela chega à Amazon ou ao ML com a tag de sempre. A loja recebe só a origem do site como `Referer`.
7. No Ads Manager, a saída aparece no anúncio e no posicionamento de origem, conforme a janela de atribuição da conta.

Quem chega sem anúncio pago (orgânico, Telegram, WhatsApp, busca, link da bio do Instagram) segue exatamente o fluxo de hoje, e nada é enviado.

## 5. Dados, LGPD e privacidade

### 5.1 Inventário

| Dado | De onde vem | Para onde vai | Onde fica no nosso lado | Por quanto tempo |
|---|---|---|---|---|
| `fbclid` | Query da página de destino, que a própria Meta acrescentou | Meta, dentro do `fbc` | Em lugar nenhum: só em memória durante a requisição | Zero |
| User agent | Header da requisição | Meta | Em lugar nenhum | Zero |
| Caminho da página de destino | `Referer` | Meta | Em lugar nenhum | Zero |
| Horário | Relógio do Worker | Meta | Em lugar nenhum | Zero |
| IP | — | **Não vai.** A Meta vê o IP da Cloudflare, não o da pessoa | — | — |

Regras para o Worker:
- não gravar nada em D1, KV ou cache;
- não fazer `console.log` do `fbclid`, do `Referer`, do user agent nem do corpo. No máximo o status HTTP da Meta;
- o `wrangler.jsonc` continua sem `observability` ligado.

**Como a pessoa remove os dados:** do nosso lado não há o que apagar, porque nada fica guardado. Na Meta, o dado vale pela política dela. A pessoa pode ver e desligar o uso desses dados em "Central de Contas > Sua atividade fora das tecnologias da Meta". Para não ser enviada daqui em diante, existe o opt-out da seção 5.4.

### 5.2 Base legal: legítimo interesse (art. 7º, IX), com teste de balanceamento

Consentimento seria a base mais segura. Mas, sem JS de terceiros, ele exige um banner com formulário e cookie em todas as páginas de destino. Isso derruba o volume, que já é pequeno, e põe um cookie num site que hoje não tem nenhum. Por isso a recomendação é **legítimo interesse**, com o teste abaixo seguindo as três fases do guia da ANPD (finalidade, necessidade, balanceamento e salvaguardas). Se o Elias não aceitar essa base (decisão 1), a recomendação é **não fazer a CAPI**, em vez de pôr banner.

**Finalidade (LGPD, art. 10, I: "apoio e promoção de atividades do controlador").** Saber quais anúncios pagos levam a pessoa até a loja e, se o volume permitir, deixar a Meta entregar o anúncio a quem tem mais chance de clicar. A finalidade é concreta, atual (há campanha no ar) e lícita.

**Necessidade.**
- Sem a CAPI, a campanha só mede a visualização da página de destino. O rollup não separa anúncio de orgânico, e o Free não guarda query.
- Não existe meio menos invasivo que dê o número por anúncio. Uma tag por anúncio exigiria uma página por anúncio e não diria qual posicionamento funcionou.
- O conjunto enviado é o mínimo que a Meta aceita para evento de site: `fbc` e user agent, mais horário e página. Fica de fora o IP, o livro e qualquer contato.

**Balanceamento.**
- *Expectativa:* quem toca num anúncio da Meta já sabe que a Meta mede o anúncio. O `fbclid` foi a própria Meta que pôs na URL. Contar a ela que esse clique virou uma ida à loja está dentro do que a pessoa espera de um anúncio.
- *Natureza do dado:* identificador pseudônimo da Meta e dados técnicos do navegador. Nenhum dado sensível, porque o livro não vai justamente para não permitir inferência sobre opinião política ou religiosa.
- *Quem é afetado:* só quem chegou por anúncio pago (`utm_medium=paid`). A campanha é 18+, e o site não é dirigido a crianças.
- *Impacto:* a Meta passa a saber que essa conta tocou num anúncio nosso e foi para uma loja. Ela já sabe do toque.

**Salvaguardas.**
- Transparência na `/privacidade/` (texto abaixo).
- Opt-out simples e respeito ao Global Privacy Control.
- Nada guardado do nosso lado, nem em log.
- Envio só durante campanha paga: sem `utm_medium=paid`, nada sai.
- Interruptor: apagar o segredo `META_CAPI_TOKEN` desliga o envio sem deploy.
- Revisão: quando não houver campanha no ar por 30 dias, o Elias apaga o segredo.

**Transferência internacional:** a Meta processa fora do Brasil (LGPD, art. 33). A transferência se apoia nos Termos de Ferramentas de Negócios da Meta, que o Elias aceita ao criar o conjunto de dados. O texto da privacidade avisa.

Fontes:
- [Guia Orientativo das Hipóteses Legais de Tratamento: Legítimo Interesse](https://www.gov.br/anpd/pt-br) (ANPD, publicado em 2024-02-02, modelo de teste em três fases; cópia em [tce.pb.gov.br](https://tce.pb.gov.br/wp-content/uploads/2025/03/guia_legitimo_interesse.pdf)). Lido por resumo de [Mattos Filho](https://www.mattosfilho.com.br/unico/anpd-legitimo-interesse-lgpd/) em 2026-11-07. O PDF integral não foi lido.
- [Guia Orientativo Cookies e Proteção de Dados Pessoais](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-orientativo-cookies-e-protecao-de-dados-pessoais.pdf) (ANPD, 2022-10-18), lido por resumo de [Mattos Filho](https://www.mattosfilho.com.br/unico/anpd-guia-cookies-protecao-dados/) em 2026-11-07. Esse guia é o motivo da escolha do caminho A, sem cookie.
- LGPD (Lei 13.709/2018), arts. 5º II, 7º IX, 10, 18 §2º e 33.
- Meta, [Customer Information Parameters](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/customer-information-parameters) e [fbp e fbc](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/fbp-and-fbc), lidos em 2026-11-07, sem data na página: `client_user_agent` obrigatório em evento de site, IP recomendado e não obrigatório, `fbc` sem hash, índice 1 quando gerado no servidor.
- Meta, [Server Event Parameters](https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/server-event), lido em 2026-11-07: `event_time` até 7 dias, `action_source=website`.

**A conferir:** não li o PDF integral dos dois guias da ANPD. Se o Elias tiver acesso a um advogado de dados, vale uma leitura de 15 minutos desta seção antes do merge.

### 5.3 Texto para a `/privacidade/`

**Troca** na seção "No site". De:
> O site não tem cadastro, cookies nem ferramentas de análise.

Para:
> O site não tem cadastro nem ferramentas de análise no navegador, e só grava um cookie se você pedir para não ser medido nos anúncios (veja "Se você chegou por um anúncio").

**Nova seção**, depois de "No pedido de livro":

> **Se você chegou por um anúncio**
>
> Quando você chega ao site por um anúncio pago nosso no Instagram ou no Facebook e clica numa oferta, o site avisa à Meta que aquele toque no anúncio levou a uma ida à loja. Isso serve para sabermos quais anúncios funcionam e para a Meta mostrar o anúncio a quem tem mais chance de se interessar.
>
> Enviamos à Meta só: o código do clique que a própria Meta põe no endereço da página (fbclid), os dados técnicos do navegador (user agent), o horário e a página do site em que você estava. Não enviamos qual livro você clicou, nem o seu endereço IP, nome, e-mail ou telefone. O site não guarda nenhum desses dados.
>
> A base legal é o legítimo interesse (LGPD, art. 7º, IX). A Meta trata esses dados conforme a política de privacidade dela, inclusive fora do Brasil. Lá você pode ver e desligar esse uso em "Central de Contas > Sua atividade fora das tecnologias da Meta".
>
> Quem chega ao site sem ser por anúncio pago não tem nada enviado. O site também respeita o sinal Global Privacy Control (GPC) do navegador. Para não ser medido, use o botão abaixo. Ele grava no seu navegador um cookie só com essa escolha, por 12 meses.
>
> [Não enviar meus cliques à Meta]

O resto da página não muda. O aviso de associado no rodapé também não muda.

### 5.4 Opt-out

- **Botão:** um `<form method="post" action="/privacidade/sem-meta">` com um `<button>`, sem JS. Ele cabe na CSP atual (`form-action` do SITE).
- **Worker em `POST /privacidade/sem-meta`:**
  - responde 303 para `/privacidade/#sem-meta-ok`;
  - grava `Set-Cookie: sem_meta=1; Max-Age=31536000; Path=/r/; Secure; HttpOnly; SameSite=Lax`. Com `Path=/r/`, o cookie só viaja para o `/r/`;
  - qualquer outro método recebe 405.
- A âncora `#sem-meta-ok` mostra "Pronto: seus cliques não serão enviados à Meta neste navegador", via `:target` em CSS, sem JS.
- `Sec-GPC: 1` tem o mesmo efeito, sem botão.

**Banner ou aviso de entrada:** não, porque a base é legítimo interesse e não consentimento. A transparência fica na `/privacidade/`, que é linkada no rodapé de todas as páginas.

## 6. Segredos

| Nome | Tipo | Onde | Quem cria |
|---|---|---|---|
| `META_CAPI_TOKEN` | **Secret** do Worker `ofertaslivros` | Cloudflare > Workers > ofertaslivros > Settings > Variables and Secrets, tipo "Secret" (nunca "Text") | Elias |
| `META_DATASET_ID` | Secret do Worker | idem | Elias |
| `META_TEST_CODE` | Secret do Worker, temporário | idem. Apagar depois da validação | Elias |

- Nada vai para o `wrangler.jsonc`, o `deploy.yml`, o GitHub Secrets ou o código. O deploy (`wrangler deploy`) mantém os secrets do Worker, como já acontece com `TELEGRAM_BOT_TOKEN`.
- O `wrangler.jsonc` ganha só um comentário com o nome dos segredos, como os que já existem.

**O que o Elias cria no Gerenciador de Eventos** (business.facebook.com > Gerenciador de Eventos, no portfólio empresarial da conta de anúncio):
1. **Conjunto de dados:** "Conectar fontes de dados > Web", com o nome "ofertaslivros.com.br". Não instalar o pixel nem usar parceiro. Aceitar os Termos de Ferramentas de Negócios. Anotar o **ID do conjunto de dados**.
2. **Vincular** o conjunto de dados à conta de anúncio da campanha (Configurações do conjunto > Ativos conectados).
3. **Token:** no conjunto de dados, "Configurações > API de Conversões > Configurar manualmente > Gerar token de acesso". O link só aparece para quem tem permissão de desenvolvedor no portfólio. Copiar uma vez, direto para o secret do Worker, sem colar em chat, arquivo ou PR.
4. **Código de teste:** na aba "Testar eventos", copiar o código e gravar em `META_TEST_CODE` durante a validação.
5. Depois da validação: criar a conversão personalizada (seção 3.5) e marcar o conjunto de dados nos anúncios.
6. **Integração automática de dados ("Core Setup" ou parecida):** se o Gerenciador oferecer, deixar desligada. A spec não manda nada além do listado aqui.

**Se o token vazar:** gerar outro no mesmo lugar (o antigo deixa de valer), trocar o secret e avisar o `security-auditor`.

## 7. Falhas

- **O redirecionamento nunca espera a Meta.** O Worker devolve a resposta do `_redirects` e só depois, em `ctx.waitUntil(...)`, chama a Meta. O `fetch()` do `index.js` passa a receber `(request, env, ctx)`.
- **Timeout:** `AbortSignal.timeout(3000)` no `fetch` para a Meta.
- **Falha silenciosa:** `try/catch` em volta de toda a parte da Meta (parse do `Referer`, montagem, envio). Erro, timeout ou status diferente de 2xx não muda a resposta e não tem retry. Log só do status, sem dado.
- **Allowlist intacta:**
  - o destino continua vindo **só** do `_redirects` gerado pelo `build.py`;
  - o Worker não monta, não reescreve e não lê URL de destino da query nem do `Referer`;
  - o `affiliate_url`, o `ml_url`, o `check_url` e o `ALLOWED_HOSTS` não mudam.
  - O Worker só **lê** o `Location` da resposta para decidir se dispara o evento (condição 1 da seção 3.2).
- **Teste F0 antes de tudo (bloqueante):** a doc da Cloudflare diz que "Redirects defined in the `_redirects` file are not applied to requests served by your Worker code" ([Static Assets > Redirects](https://developers.cloudflare.com/workers/static-assets/redirects/), atualizada em 2026-08-25). Ela não deixa claro se o `env.ASSETS.fetch(request)` aplica o `_redirects`.
  - O `infra-engineer` testa isso num Worker de preview (`wrangler versions upload` ou `wrangler dev` com o `dist/` real) antes de abrir o PR. Critério: `GET /r/<id>` devolve o mesmo 302 com o mesmo `Location`, e `/r/inexistente` cai na home.
  - **Se não aplicar:** o PR **não** segue. O plano B (o Worker emite o 302 a partir de um mapa gerado pelo `build.py`, com a allowlist conferida de novo no Worker) faz do Worker a fonte do redirecionamento e volta para o PM e para o Elias como nova decisão.
- **Cota do Workers Free (100 mil requisições por dia):** com `/r/*` no `run_worker_first`, todo clique de afiliado passa a contar. O volume de hoje está ordens de grandeza abaixo disso, mas se a cota estourar, o `/r/` passa a dar erro. Ver o risco na seção 9.
- **Analytics:** a contagem de `/r/` no `daily_rollup` vem do GraphQL da zona, com `edgeResponseStatus = 302`. O `infra-engineer` confere no dia seguinte ao deploy que as linhas de `/r/` continuam aparecendo (critério 10).

## 8. Uso na campanha e critério para trocar a otimização

**Recomendação:** manter a campanha de Tráfego com otimização por visualização da página de destino, e usar o `SaidaLoja` **só para medir**: custo por saída por anúncio e por posicionamento. É com ele que se pausa criativo e posicionamento ruim.

**Por que não otimizar por conversão agora:**
- R$ 350 até 30/11 dão cerca de R$ 17 por dia.
- Com a estimativa do `anuncios-lancamento.md` (R$ 1,60 por clique de saída), isso dá cerca de 220 saídas no mês, ou 70 por semana. Desse total, só uma parte é capturada (caminho A) e atribuída pela Meta.
- A Meta precisa de cerca de 50 eventos de otimização por conjunto em 7 dias para sair da fase de aprendizado. Esse número vem de fontes secundárias que citam a Central de Ajuda, porque a página oficial não abriu para leitura automática ([exemplo](https://lebesgue.io/blog/facebook-ads-learning-phase/), lido em 2026-11-07).
- A campanha de Tráfego não aceita conversão como meta de desempenho. Trocar exige **campanha nova**, com objetivo que aceite conversão no site (Engajamento, Leads ou Vendas, conforme o Ads Manager oferecer para conversão personalizada), e a fase de aprendizado recomeça do zero.

**Critério para trocar** (todas as condições):
1. **≥ 50** "Saída para a loja" atribuídas no Ads Manager, num conjunto, em 7 dias corridos;
2. custo por saída **≤ R$ 1,20**, o limite de escala do `anuncios-lancamento.md`;
3. pelo menos **10 dias** de campanha e verba restantes depois da troca.

Com R$ 350 e fim em 30/11, a condição 3 dificilmente vale em novembro. O resultado esperado é que o critério sirva para decidir a **próxima** campanha, de dezembro em diante. Se o Elias aumentar a verba, a conta muda.

**Leitura diária** (pelo Elias, no Ads Manager): gasto, cliques no link, visualizações da página de destino, "Saída para a loja" e "Custo por Saída para a loja", por anúncio e por posicionamento. Sinal de alerta: menos de 1 saída a cada 10 visualizações da página de destino num anúncio com R$ 30 ou mais gastos. Nesse caso, pausar o anúncio.

## 9. Riscos

- **Regra 1 (scraping da Amazon):** não é afetada. Nada aqui lê página da Amazon.
- **Programas de afiliado:** o link de afiliado, a tag e o destino não mudam. A loja passa a receber o `Referer` só com a origem. Os termos da Amazon lidos no `anuncios-lancamento.md` não tratam disso, e não há motivo para problema.
- **Cota do Worker no caminho do clique de afiliado** (muda decisão do `analytics.md`): se a cota do Free estourar, o `/r/` quebra. Mitigação: o volume atual está muito abaixo; o `infra-engineer` inclui no PR quantas requisições de Worker por dia os últimos 7 dias tiveram; o Elias pode tirar `/r/*` do `run_worker_first` (PR de uma linha) e voltar ao estático na hora. Alternativa paga: Workers Paid, cerca de US$ 5 por mês, se o volume chegar perto.
- **LGPD:** legítimo interesse para dado compartilhado com plataforma de anúncio é defensável com as salvaguardas da seção 5.2, mas não é a leitura mais conservadora. Se houver questionamento, o interruptor (apagar o secret) para o envio na hora.
- **Poluição do dataset:** alguém pode forjar `Referer` e `fbclid` e mandar `/r/` em massa. Um `fbclid` falso não casa com nenhum clique, então o efeito é ruído no Gerenciador de Eventos. Sem rate limit no MVP. Se aparecer, o `infra-engineer` usa um binding `ratelimits`, como o `LIMITE` do pedido.
- **Navegador do app do Instagram:** o envio do `Referer` same-origin com `target="_blank"` no WebView precisa ser conferido em Android e iOS (critério 9). Se o WebView não mandar `Referer`, o caminho A não funciona ali e a spec volta para decidir o caminho B.
- **Netlify (`ofertaslivros.com`):** o anúncio aponta direto para `.com.br`, para não depender de o redirecionamento preservar a query.
- **Custo:** a Meta CAPI é gratuita, e o Worker continua no plano Free. Não há custo novo, salvo o Workers Paid, se um dia for preciso.
- **Testes do Worker fora do CI:** os `worker/*.test.mjs` não rodam no `catalog-check` (só `build.py --selftest` e `pytest`). O teste novo roda local e o resultado vai na descrição do PR. Pôr no CI é um PR sensível à parte (workflow), fora daqui.

## 10. Critérios de aceite

1. **F0:** relatório do `infra-engineer` no PR mostrando que `env.ASSETS.fetch` aplica o `_redirects` (302 igual para um `/r/<id>`, um `/r/<id>/tg` e um `/r/inexistente`). Sem isso, nada é mergeado.
2. `wrangler.jsonc`: `run_worker_first` ganha `/r/*` e `/privacidade/sem-meta`. Nada mais muda além de comentários.
3. `worker/index.js` encaminha `/r/*` para um módulo novo (ex.: `worker/saida.js`). Para qualquer `/r/...`, a resposta é **byte a byte** a do `env.ASSETS.fetch(request)`: status, `Location` e headers.
4. Teste `worker/saida.test.mjs` (`node --test`), com `fetch` da Meta falso, cobrindo:
   - com `Referer` da origem com `fbclid` válido e `utm_medium=paid`, e 302 para host da allowlist → 1 chamada, com exatamente os campos da seção 3.3 e nenhum outro (sem IP, sem livro);
   - sem `fbclid`, sem `utm_medium=paid`, `Referer` de outra origem, `Sec-GPC: 1`, cookie `sem_meta=1`, 302 para `/` (curinga) ou secrets ausentes → 0 chamadas e a mesma resposta;
   - `fbclid` com caractere fora de `[A-Za-z0-9_-]` ou com mais de 500 caracteres → 0 chamadas;
   - Meta lenta (promessa que não resolve), Meta com 500 ou `fetch` que lança erro → a resposta ao usuário sai igual e sem atraso, e o envio fica dentro do `ctx.waitUntil`;
   - o `fbc` preserva maiúsculas e minúsculas do `fbclid` e tem o formato `fb.1.<13 dígitos>.<fbclid>`;
   - `event_source_url` sem query string.
5. Nenhum `console.log` com `fbclid`, `Referer`, user agent ou corpo, conferido por grep no PR.
6. `POST /privacidade/sem-meta` → 303 para `/privacidade/#sem-meta-ok` com o `Set-Cookie` exato da seção 5.4. `GET` → 405.
7. `build.py`: os links para `/r/` passam a usar `rel="sponsored noopener"` (sem `noreferrer`) em todos os lugares, e o `static/app.js` faz o mesmo no modal. Os links para `t.me` e outros externos continuam com `noreferrer`. O `selftest()` confere isso.
8. `/privacidade/` com o texto exato da seção 5.3 e o botão funcionando sem JS. `:target` mostra a confirmação. Contraste AA e área de toque ≥ 44 px no botão. O `_headers` (CSP e o resto) **não muda**.
9. **Teste manual em produção**, com `META_TEST_CODE` ligado:
   - abrir `https://ofertaslivros.com.br/negocios/?utm_medium=paid&fbclid=TesteManual_123abc` no Chrome do celular e, se possível, pelo navegador do app do Instagram (link enviado por DM para si mesmo);
   - tocar numa oferta e ver o 302 normal para a loja;
   - o evento `SaidaLoja` aparece em "Testar eventos" com `fbc` e user agent, sem IP;
   - nas ferramentas de rede do desktop: o pedido ao `/r/` leva o `Referer` completo, e o pedido à loja leva só `https://ofertaslivros.com.br/`.
10. No dia seguinte ao deploy, o `daily_rollup` tem as linhas de `/r/` com 302 em volume compatível com a semana anterior.
11. Sem os secrets, o `/r/` funciona igual e nenhuma chamada sai (verificado antes de o Elias criar os secrets).
12. O `docs/produto/analytics.md` tem a linha "O `/r/` continua sendo o `_redirects` estático... sem Worker" atualizada, apontando para esta spec.

## 11. Divisão por agent, em ordem

| # | Quem | Entrega | Sensível? |
|---|---|---|---|
| 0 | Elias | Decisões 1 a 4. Sem a decisão 1, nada começa | — |
| 1 | `infra-engineer` | Teste F0 (critério 1). Se passar: PR com `worker/saida.js`, rota no `index.js`, opt-out `POST /privacidade/sem-meta`, `run_worker_first`, comentário dos secrets no `wrangler.jsonc`, `worker/saida.test.mjs` e a linha do `analytics.md` (critérios 2 a 6, 11 e 12). O PR entra **inerte**: sem secrets, não envia nada | **Sim** (Worker, `wrangler.jsonc`, rota `/r/`, dado de usuário) |
| 2 | `frontend-developer` | PR com o `rel` dos links para `/r/` no `build.py` e no `app.js`, o texto da `/privacidade/`, o botão e a confirmação via `:target`, e o `selftest()` (critérios 7 e 8). Mergear junto do PR 1 ou logo depois, nunca antes: a página não pode descrever um envio sem opt-out funcionando | **Sim** (texto de privacidade, links do `/r/`) |
| 3 | `security-auditor` | Revisa os PRs 1 e 2: allowlist e destino intocados, sem open redirect, sem dado em log, CSP igual, cookie com `Path=/r/` e flags, `Referer` para a loja só com a origem, segredo sem rastro no repo | — |
| 4 | `code-reviewer` e review do Codex | Fluxo normal de PR, com `web-design-guidelines` no PR 2 | — |
| 5 | Elias | Seção 6: dataset, token e secrets com `META_TEST_CODE`. Depois o teste manual (critério 9) com o `infra-engineer`, a remoção do `META_TEST_CODE`, a conversão personalizada e o dataset marcado nos anúncios | — |

O `collector-engineer`, o `alerts-engineer` e o `catalog-curator` não entram.

**Prazo:** a campanha começa em 10/11. Os eventos só contam a partir do deploy e não há retroativo. Meta realista: tudo no ar até 12/11, se o Elias aprovar as decisões em 08/11 ou 09/11.

## 12. Fora do MVP, e quando vale

- **Cookie `_fbc` (caminho B):** se o critério 9 mostrar que o WebView do Instagram não manda `Referer`, ou se a perda de quem navega antes de clicar ficar grande (saídas da Meta muito abaixo das saídas de `/r/` no dia). Exige base legal revista.
- **IP no evento:** se o teste mostrar eventos recebidos e mal atribuídos (decisão 3).
- **Valor estimado (`value`):** quando houver comissão média confiável por loja no `/painel`.
- **Conversões offline com a venda real:** o relatório da Amazon não traz o clique, então não há como casar a venda com o `fbc`. Não vale.
- **Google (enhanced e offline conversions):** fora, pelos motivos do `anuncios-lancamento.md`.
- **Rate limit no envio:** se aparecer ruído no Gerenciador de Eventos.

## 13. Decisões do Elias

**2026-11-07:** o Elias aceitou as recomendações ("ok, recomendações capi"): 1 legítimo interesse + opt-out + GPC, sem banner; 2 caminho A (`Referer`, sem cookie); 3 sem IP; 4 Worker no `/r/` aceito; 5 `SaidaLoja`; 6 critério da seção 8. A decisão 7 (leitura jurídica) não tinha recomendação e continua em aberto.

Texto original das opções:

1. **Base legal:** legítimo interesse com o teste da seção 5.2, opt-out e GPC, sem banner (recomendado). A alternativa é não fazer a CAPI. Consentimento com banner não é recomendado.
2. **Caminho para levar o `fbclid` ao `/r/`:** A, o `Referer` sem cookie (recomendado), ou B, o cookie `_fbc` primário.
3. **IP no evento:** sem IP (recomendado, minimização) ou com IP (melhora a correspondência).
4. **Aceitar o Worker no caminho do clique de afiliado,** revertendo a decisão de 2026-11-04 do `analytics.md`, com o risco de cota da seção 9.
5. **Nome do evento:** `SaidaLoja` personalizado (recomendado) ou um evento padrão.
6. **Critério para trocar a otimização** (seção 8): ≥ 50 saídas atribuídas em 7 dias, custo por saída ≤ R$ 1,20 e ≥ 10 dias restantes.
7. **Leitura jurídica:** pedir ou não uma revisão rápida da seção 5 a um advogado de dados antes do merge do PR 2.

## 14. Ações que só o Elias pode fazer

1. Responder às decisões 1 a 7.
2. No Gerenciador de Eventos: criar o conjunto de dados, aceitar os Termos de Ferramentas de Negócios, vincular à conta de anúncio e gerar o token (seção 6).
3. Gravar `META_CAPI_TOKEN`, `META_DATASET_ID` e `META_TEST_CODE` como **Secret** no Worker `ofertaslivros`, e apagar o `META_TEST_CODE` depois do teste.
4. Nos anúncios: pôr os parâmetros de URL `utm_source=meta&utm_medium=paid&utm_campaign=bf-ig-nov26`, usar só URLs `https://ofertaslivros.com.br/...` e marcar o conjunto de dados em "Rastreamento".
5. Criar a conversão personalizada "Saída para a loja" e as colunas do Ads Manager.
6. Escrever "aprovado, pode seguir" na sessão para cada PR (1 e 2).
7. Fazer o teste manual no celular (critério 9), inclusive pelo navegador do app do Instagram.
8. Apagar o `META_CAPI_TOKEN` quando não houver campanha no ar por 30 dias.
