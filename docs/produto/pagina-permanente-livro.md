# Spec: página permanente do livro (`/livro/<id>/` não some quando a oferta acaba)

Status: PR 1 (seções 2, 3, 6 e 7) implementado em 2026-11-07; o PR 2 (seção 5 e livro retirado) vem depois. Autor: product-manager. Pedido do Elias (2026-11-07): manter a página no ar com "sem oferta agora" e o histórico de preço, sem botão de compra ativo, e com a oferta de volta quando o preço cair.

## 1. Problema e usuário

**Em uma frase:** quem chega ao `/livro/<id>/` pelo Google, por um post antigo do canal ou por um link salvo quer saber se o livro está barato. Hoje, às vezes, ele recebe um 404. Com a página no ar, ele vê o histórico de preço e toca em "Me avise se baixar". O Google mantém a URL indexada, e o alerta vira clique de afiliado quando o preço cair.

### 1.1 Quando a página some hoje (conferido no código)

O pedido parte de "a oferta vence e a página some". Isso vale só em parte. O `build.render_pages` gera `/livro/<id>/` para todo livro que o `build.resolve` devolve, e o `resolve` já devolve:

- livro **em oferta**: a página normal;
- livro **sem oferta, com preço** (loja fresca, ou só a Amazon vencida, o `velho`): a página já fica no ar com "Sem oferta agora", o preço e o botão para a loja (`book_page`, `nov-nota`). Isso vem da decisão de 2026-10-21 e de `aba-curadoria.md`.

A página some, e o endereço dá 404, em três casos:

| Caso | Por quê | Hoje (price-history, 2026-11-07) |
|---|---|---|
| **A. Livro só do ML com preço fora do prazo** (mais de 2 h, `FRESH["mercadolivre"]`) | O `resolve` descarta: não há loja fresca nem Amazon para cair no `velho` (`build.py`, `if not el: continue`). Acontece quando o anúncio fica inativo ou quando o coletor do ML falha por mais de 2 h | 7 dos 168 livros são só do ML. 2 estão sem página agora: `como-morrem-os-nossos-escritores` e `pre-sal` |
| **B. Livro retirado do catálogo** | O `curator.retire` tira do `catalog.json` com 30 dias sem anúncio ativo (todos) ou sem oferta (só os automáticos, com `genre_source`). O coletor para de gerar o livro no `offers.json` | 0 retirados até agora. Nenhum livro tem `genre_source`, então só vale a regra "sem anúncio". A primeira retirada possível é em **2026-11-19** (o `publicado` mais antigo é 2026-10-20) |
| **C. Última leitura com mais de 5 meses** | O `collect.summarize` lê só 5 meses do `price_history` | Na prática, o caso B acontece antes |

O MVP resolve o caso A e deixa a decisão sobre o caso B para o Elias (decisão em aberto 1). O caso C se resolve junto com o B.

### 1.2 Referência

O ofertasdiscos.com tem uma página fixa por álbum (`/discos/cartola/1976`), separada das ofertas, que "saem daqui quando deixam de valer". Não mostra histórico. É o mesmo modelo: a página do produto fica, a oferta entra e sai dela.

## 2. Escopo do MVP

### 2.1 Quem ganha página permanente

**Todo livro que está no `offers.json`**, ou seja, todo livro do `catalog.json` com pelo menos uma leitura de preço nos últimos 5 meses. Isso já inclui o livro sem nenhuma loja fresca (caso A). O livro retirado (caso B) fica de fora do MVP (decisão em aberto 1).

Interpretações consideradas:
1. **Só os livros do catálogo (recomendada).** O build já tem todos os dados (título, autor, capa, nicho, nota, histórico). Mexe só no `build.py`. O livro continua sendo monitorado, então a promessa "volta a ter oferta quando o preço cair" vale de verdade.
2. Todos que já tiveram oferta, mesmo retirados. Precisaria guardar os metadados do livro depois da retirada, porque hoje `retirados` é só `{id: data}`. Também precisaria de uma página "congelada", que nunca volta a ter oferta, já que o livro deixa de ser coletado. Fica para a decisão 1.

### 2.2 Três estados da página

| Estado | Quando | O que muda |
|---|---|---|
| **Em oferta** | `oferta` | Nada |
| **Sem oferta, com preço** | Loja fresca ou Amazon `velho`, sem `oferta` | Nada. Continua com o preço e o botão para a loja, porque o livro está na `/curadoria/` e o clique rende comissão (`aba-curadoria.md`). Decisão 2 (Elias, 2026-11-07) |
| **Sem preço** (novo) | Nenhuma loja fresca e nenhuma leitura da Amazon (caso A) | A página fica no ar, conforme a seção 3 |

O pedido de "sem botão de compra ativo" vale para o estado **sem preço**. Ali não há preço conferido que justifique mandar o leitor para a loja.

### 2.3 Fora do MVP

- **Livro retirado do catálogo** (caso B): decisão 1. Prazo para decidir: antes de 2026-11-19.
- **Livro sem preço na `/curadoria/`, nos nichos ou em alguma lista "fora de oferta".** A vitrine, os nichos, `/ofertas/`, as faixas, `/black-friday/` e os canais continuam só com ofertas ativas, e a `/curadoria/` continua só com livros que têm preço. A página sem preço é encontrada pelo sitemap, pelo Google e por links antigos. `aba-curadoria.md` §3 deixou isso para "quando a área piscar demais com o rodízio do coletor". O critério continua o mesmo.
- **`<lastmod>` no sitemap**: continua sem, como no #142.
- **Mudar a contagem de cliques do `/painel`** (ver Riscos).

## 3. O que a página sem preço mostra

Mesma URL, status 200, mesmo layout de `book_page`, sem `noindex`:

- breadcrumb, chip do nicho, título (`<h1>`), autor, capa, nota da curadoria (`blurb`), se houver;
- no lugar do bloco de preço (`hero-deal`): **"Sem oferta agora"**, sem preço em destaque, sem riscado, sem % e sem selo;
- uma frase com a última leitura, por exemplo: "Não conseguimos conferir o preço na loja desde 03/11. O último preço que vimos foi R$ 39,90 no Mercado Livre." Data e loja vêm do `checked_at` mais recente. A frase fala do passado, e o preço não aparece como preço atual. Hoje o caso A é só do ML. Se um dia a Amazon entrar neste estado, a frase não deve mostrar o preço da Amazon (regra de 24 h dos Associados, a mesma do `OFFER_MAX`): fica só a data;
- **o histórico** (gráfico `chart` e tabela, `#historico`) com os pontos que existirem. Pela regra do coletor, o histórico cobre os últimos 90 dias até hoje (`collect.price_points`). Sem pontos na janela, a página mostra "Sem leitura de preço nos últimos 90 dias" no lugar do gráfico;
- o botão **"Me avise se baixar"** (`alert_link`), quando o bot está configurado. É o único CTA da página;
- **nenhum link `/r/`**: sem `go()`, sem `store_list`, sem botão de loja ativo, nem desabilitado. "Sem botão de compra ativo" quer dizer que o botão não aparece. Um botão cinza sem ação só confunde;
- `<title>` pelo `book_title`, mas sem o trecho "por R$ ..." (não há preço conferido para pôr no título): "{título}, {autor} | Ofertas Livros". A `meta description` não tem preço: "{título}, de {autor}: histórico de preço e aviso quando entrar em oferta."

Quando o livro volta a ter loja fresca, a página volta ao estado "com preço" ou "em oferta" no build seguinte, sem ação manual.

## 4. Fluxo do usuário

1. O leitor busca o título no Google e cai em `/livro/<id>/`, ou toca num post antigo do canal (`/r/<id>/tg`).
2. Livro sem preço: vê "Sem oferta agora", a última leitura e o gráfico. Pelo post antigo, o `/r/` leva à página do livro, e não à home (seção 5).
3. Toca em "Me avise se baixar", vai ao bot e põe o livro na lista. O id está no `bot.json`, então o bot reconhece o livro.
4. Quando o ML volta a ter preço e o livro entra em oferta, o build seguinte põe o livro na vitrine, e o cron do bot manda o aviso com `/r/<id>/bot`. Aí sai o clique de afiliado.

## 5. `/r/<id>` de livro sem preço (PR sensível)

**Hoje:** o livro sem preço não tem regra no `_redirects`, então `/r/<id>` e as variantes caem no curinga `/r/* / 302` e vão para a home (`distribuicao-canais.md`, item 12).

**Comportamento esperado:**
- `/r/<id>`, `/r/<id>/tg`, `/r/<id>/wa`, `/r/<id>/bot` e `/r/<id>/<loja>` de um livro **sem preço** → **302 para `/livro/<id>/`**, que é um destino interno montado só com o `id` já validado por `ID_RE`. Nunca para a loja, porque não há preço conferido. O código é 302, e não 301, porque o endereço volta a apontar para a loja quando o preço voltar.
- Livro com preço (em oferta ou não): sem mudança.
- Id desconhecido ou retirado: sem mudança, continua no curinga para a home.
- O número de regras não cresce. O livro sem preço usa no máximo as 6 regras que já usava com preço (`MAX_REDIRECTS` continua igual).

**É PR sensível** (`_redirects`/rota `/r/`). Precisa do review do Codex e do "aprovado, pode seguir" do Elias. Por isso vai num PR separado do resto (seção 8).

## 6. JSON-LD sem Offer

**Fato** ([Google, product snippets](https://developers.google.com/search/docs/appearance/structured-data/product-snippet)): o `Product` precisa de `offers`, `review` ou `aggregateRating`. Sem nenhum deles, o Search Console marca erro. O `book_ld` de hoje já gera `Product` sem `offers` quando o preço tem mais de 24 h (`OFFER_MAX`), por exemplo na Amazon `velho`.

**Regra:**
- com Offer (preço conferido há menos de 24 h): `"@type": ["Product", "Book"]` com `offers`, como hoje;
- sem Offer, em qualquer estado (sem preço, ou preço com mais de 24 h): `"@type": "Book"`, com `name`, `author`, `url`, `image` e `isbn` quando houver, **sem `offers`**. Nada de `Offer` com `availability: OutOfStock` nem preço antigo, porque não conferimos estoque;
- `BreadcrumbList` igual em todos os estados.

## 7. Sitemap

**Entra.** Toda página permanente `/livro/<id>/` (os três estados) entra no `sitemap.xml`. Com o livro sem preço dentro de `render_pages`, o `sitemap(pages)` já faz isso sozinho. Continua sem `<lastmod>`. Livro retirado sai do sitemap, como hoje.

## 8. Critérios de aceite

Todos viram assert no `build.py --selftest`, salvo onde está indicado.

**PR 1: página, JSON-LD, sitemap e `bot.json` (não sensível, se cumprir o item 9)**
1. Um livro só do ML com `checked_at` mais de 2 h antes do `now` gera `livro/<id>/index.html` com status de build ok, e o `render_pages` inclui a chave.
2. Essa página contém "Sem oferta agora" e a frase da última leitura com data e loja. Não contém `href="/r/`, nem `class="go"`, nem `class="price"` com o preço atual, nem riscado ou %.
3. Com `price_points` na janela, a página tem o gráfico (`class="hc"`). Sem pontos, tem "Sem leitura de preço nos últimos 90 dias" e nenhum gráfico.
4. Com bot configurado, a página tem o `alert_link` do livro. Sem bot, não tem nenhum CTA.
5. O livro sem preço não aparece na home, nos nichos, em `/ofertas/`, nas faixas, em `/black-friday/`, na `/curadoria/`, no `data_script` do modal nem nas contagens do menu. As listas e contagens são as mesmas do build sem ele.
6. `sitemap.xml` contém `/livro/<id>/` do livro sem preço.
7. JSON-LD do livro sem preço: `@type == "Book"`, sem a chave `offers`. JSON-LD de um livro `velho` (preço com mais de 24 h): também `Book` sem `offers`. Livro com preço de menos de 24 h: `["Product", "Book"]` com `offers`, igual ao #142.
8. `bot.json` contém o livro sem preço com `texto: null` e `desconto: 0`. O teste do Worker (`worker/bot.test.mjs`) não muda, porque `texto: null` já significa que não há envio.
9. O `_redirects` é **idêntico** ao do build atual para o mesmo `offers.json`: o livro sem preço não ganha regra e continua no curinga. A função `redirects()` não é alterada neste PR.
10. Quando o mesmo livro volta a ter `checked_at` fresco, a página volta ao estado com preço ou em oferta, com `go()`.
11. O texto do FAQ "quando o preço fica velho, sai do site" (`faq()`) passa a dizer que a página do livro continua no ar, com o histórico.
12. (Manual) Rich Results Test numa página sem preço publicada: sem erro de `Product`.

**PR 2: `/r/` do livro sem preço (sensível)**
13. Para o livro sem preço, o `_redirects` tem `/r/<id> /livro/<id>/ 302` e a mesma linha para `/tg`, `/wa`, `/bot` e cada loja que o livro tem no `offers.json`. Nenhuma dessas linhas aponta para domínio externo.
14. Livro com preço: as linhas são idênticas às de hoje. A última linha continua sendo `/r/* / 302`.
15. O total de linhas nunca passa de `MAX_REDIRECTS`, e o livro sem preço tem no máximo tantas linhas quanto teria com preço.
16. (Manual, depois do deploy) `curl -sI https://ofertaslivros.com.br/r/<id>/tg` de um livro sem preço devolve 302 com `Location: /livro/<id>/`.

## 9. Divisão por agent, na ordem

1. **frontend-developer**: PR 1. No `build.py`, o estado "sem preço" é uma lista separada da lista `offers` que alimenta a vitrine e o `redirects()`. Por exemplo, o `resolve` devolve os livros sem preço à parte, e o `render_pages` e o `bot_json` recebem essa lista. A forma fica com quem implementa. A condição é que o `redirects()` e o `affiliate_url` não mudem, para o PR não virar sensível. Inclui o `book_page` sem preço, o `book_ld` só com `Book` quando não há Offer, a frase do FAQ e os asserts de 1 a 11. Usar as skills frontend-design e web-design-guidelines no bloco "Sem oferta agora" (contraste, sem botão fantasma).
2. **collector-engineer**: nada no MVP. O `offers.json` já traz o livro sem loja fresca. Só entra se o Elias escolher (b) ou (c) na decisão 1.
3. **alerts-engineer**: nada no código. Só conferir que o Worker trata bem o livro com `texto: null` e `valido_ate` no passado, no `add:<id>` e no `/start`. Pela leitura de `worker/bot.js` (`emOferta`), já trata. O canal não muda, porque só posta oferta.
4. **frontend-developer**: PR 2, o `/r/` da seção 5, depois do merge do PR 1.
5. **security-auditor**: revisa o PR 2 antes do merge: destino só interno, `id` pelo `ID_RE`, nenhuma linha com URL de loja para livro sem preço, curinga no fim, sem injeção de linha no `_redirects`.
6. **code-reviewer**: revisa os dois PRs, com web-design-guidelines no PR 1.

## 10. Riscos

- **Regra 1 (Amazon):** nada novo é lido da Amazon. A página usa o que já está no `offers.json`. A frase da última leitura não mostra preço da Amazon com mais de 24 h.
- **Regra 4 (transparência):** o rodapé não muda. A página sem preço não tem link de afiliado, então não há o que avisar ali além do rodapé.
- **Open redirect (`/r/`):** o PR 2 só acrescenta destinos internos montados com o `id` validado. É sensível e tem auditoria (seção 9, item 5).
- **XSS:** título, autor e nota continuam passando por `e()`. Não há campo novo vindo de dado coletado.
- **SEO, soft 404:** uma página sem preço e quase vazia pode ser lida pelo Google como soft 404. O histórico, a nota e o alerta dão conteúdo próprio. Se o Search Console marcar soft 404 nessas páginas, é sinal de que ficaram finas demais (rever a frase e o histórico).
- **`/painel`:** o painel conta todo `/r/%` como clique de afiliado (`worker/painel.js`). Com o PR 2, o `/r/` de livro sem preço que leva à página do livro também conta. Hoje isso afeta 2 livros e links antigos, então o impacto é pequeno. Se crescer, o painel precisa separar esses cliques. Ver decisão 3.
- **LGPD:** nenhum dado de usuário novo. O `bot.json` não tem dado de usuário. A lista de desejos continua como em `bot-lista-de-desejos.md`.
- **Custo:** zero. São poucas páginas estáticas a mais (hoje 2), nenhuma regra nova de `_redirects` em termos líquidos e nenhum job novo.
- **Valor limitado no MVP:** o livro do caso A costuma ser anúncio inativo. Se continuar sem anúncio por 30 dias, o curator retira o livro, e a página cai no caso B. O ganho garantido do MVP é não perder a página em queda do coletor do ML e em anúncio que volta em menos de 30 dias. Para manter a página por mais tempo, é a decisão 1.

## 11. Decisões em aberto para o Elias

1. **Livro retirado do catálogo** (primeira retirada possível em 2026-11-19):
   (a) **continua dando 404, como hoje (recomendado no MVP)**: a retirada só acontece depois de 30 dias sem anúncio em nenhuma loja, então o livro dificilmente volta;
   (b) 301 para a página do nicho: preserva parte do link para o Google, mas exige guardar o `genre` em `retirados`. Mexe no `_redirects` e no `catalog.json`, então é sensível;
   (c) página "arquivada" congelada, com o histórico até a retirada e sem alerta: exige guardar os metadados e o histórico do retirado (collector-engineer). É o maior custo.
2. **Decidido (Elias, 2026-11-07): o botão some só no livro sem preço.** O livro com preço, mesmo sem desconto, continua com o botão para a loja. Implementado no PR 1.
   Contexto original: **Botão de loja no estado "sem oferta, com preço".** O pedido diz "sem botão de compra ativo". A recomendação é aplicar isso só ao estado sem preço e manter o botão nos livros com preço sem desconto, que estão na `/curadoria/` e rendem clique (`aba-curadoria.md`). Se a intenção era tirar o botão de todo livro fora de oferta, isso muda a decisão da Curadoria e reduz cliques.
3. **`/r/` do livro sem preço:** (a) **302 para `/livro/<id>/` (recomendado)**, aceitando a pequena inflação nos cliques do `/painel`; (b) deixar no curinga para a home, como hoje. Com (b), não existe PR 2 e nada do MVP é sensível, mas quem vem de um post antigo perde o livro de vista.
