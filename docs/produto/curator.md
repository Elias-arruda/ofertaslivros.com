# Spec: curadoria automática do catálogo (`curator`)

Status: **conciliada com `curadoria-automatica.md` §10 em 2026-10-19** (decisões das rodadas de 2026-10-19, commits 9d30860 e 6248281). Autor: product-manager. A primeira versão desta spec (PR #4, aprovada em 2026-10-19 de manhã) previa um job semanal que abria PR com até 10 candidatos. Esse desenho foi substituído pela publicação automática com gates e modo sombra. Onde esta spec e o §10 divergirem, **vale o §10**.

O nome difere de `curadoria-automatica.md` porque a main já tinha outro texto nesse caminho. As duas convivem: o §10 de lá tem a pontuação, os gates e os fluxos de link; esta aqui diz como o `collector/curator.py` se encaixa e o que muda no código.

## 0. O que mudou em relação à versão do PR #4

| Tema | Antes (PR #4) | Agora (vigente) | Fonte |
|---|---|---|---|
| Publicação | PR semanal com entradas `"pendente": true`; o Elias faz o merge livro a livro | Publicação automática quando passam todos os gates e o limiar. Antes disso, modo sombra: nada muda no site | §10.6, decisão 1; §10.3 |
| Volume | 10 por semana, até 4 por nicho, `CATALOG_MAX` = 150 | **Pelo menos 50 livros novos por dia, até 10 por gênero.** É meta: se menos de 50 passarem, entram menos, e o limiar **não** baixa para completar. Tag não conta para o teto de gênero | §10.3, gate 8; §10.6, decisão 12 |
| Nichos | 5 gêneros mapeados; `autoajuda` fora | **10 gêneros**, com `estudo` (técnicos e didáticos juntos) e `autoajuda` **dentro**. Mais a tag `lgbtqia`, por cima dos gêneros | §10.1 e §10.1.1; decisões 2 e 3 |
| Escolha | Ordem do `/highlights`, desempate pelo desconto sobre `original_price` | Pontuação 35/25/15/25 (preço, demanda, avaliações, tendência), `score ≥ 70` e `confiança ≥ 0,5`; retirada com `score < 60` por 2 execuções | §10.3; decisão 5 |
| Avaliações | Fora (Google Books no "Fora") | Google Books com chave própria `GOOGLE_BOOKS_API_KEY`, em GitHub Secrets | §10.6, decisão 9 |
| Link do ML | Elias cola no PR | Fila por linha em `collector/ml_links.tsv` (`links-todo`/`links-apply`). O `affiliate-linker` pode fazer GET no link para conferir o livro | §10.4 |
| Amazon | "ASIN provável" no PR, `asin` à mão | Fila manual em `collector/amazon_links.tsv` (`amazon-todo`/`amazon-apply`), com link do SiteStripe e `isbn_confirmado` | §10.5; decisão 14 |
| Identidade | ISBN opcional; casamento com a Amazon "para depois" | Gate 7: identidade por loja (`ml_product_id` no ML; `asin` + `isbn_confirmado` na Amazon), uma loja não bloqueia a outra | §10.3, gate 7 |
| Log | `curator_seen.json` | Continua, mais `curation/AAAA-MM.jsonl` no branch `price-history`, 24 meses | §10.6, decisão 11 |

## 1. Problema e usuário

**Em uma frase:** hoje o Elias acha cada livro, gera o link no painel do ML e escreve a entrada do `collector/catalog.json` à mão. Ele quer que uma máquina encontre os livros que valem a pena, pontue e publique sozinha, sobrando para ele só o par livro ↔ link de afiliado. Mais livros bons monitorados dão mais ofertas reais na vitrine e nos canais, e portanto mais cliques de afiliado.

**Interpretações do pedido** (a 3 foi revista):
1. **Webscraper que busca "todos os livros"** nas lojas. Esbarra na regra 1 (Amazon) e nos termos do ML (seção 3.3). Também vai contra "curadoria, não despejo". **Descartada.**
2. **Agente com LLM que escolhe os livros e gera os links sozinho.** Não existe caminho oficial para gerar o link do ML (seção 3.4), e um LLM não é necessário para escolher. **Descartada no MVP.**
3. **Um job diário que descobre candidatos pela API oficial do ML, pontua com regras objetivas e publica sozinho o que passa nos gates**, depois de um período de sombra. Ao Elias sobram o par livro ↔ link do ML e a conferência da Amazon manual. **Vigente** (§10.6, decisão 1). A versão "PR semanal com merge humano" foi a primeira implementação e fica só como transição (seção 5.5).

## 2. O que existe hoje (conferido no repo em 2026-10-19)

| Item | Existe? | Onde |
|---|---|---|
| Catálogo de livros monitorados | Sim, 10 livros | `collector/catalog.json` |
| Validação do catálogo: `id` (`ID_RE`), `genre` em `GENRES`, ISBN-13, `ml_product_id` e `ml_url` juntos, `ml_url` preso ao `matt_word`, `pendente` | Sim | `collector/collect.py:load_catalog`, `build.py:ml_url` |
| Cliente da API do ML: token de app, backoff, um host só | Sim | `collect.py:ml_token`, `ml_request` |
| `curator.py probe` e `curator.py suggest` (PR semanal, até 10, até 4 por nicho) | Sim, desenho antigo | `collector/curator.py` (`WEEK_MAX = 10`, `GENRE_MAX = 4`, `CATALOG_MAX = 150`) |
| `GENRE_MAP` do curador | Sim, 6 ids para 4 slugs, sem `autoajuda` | `collector/curator.py:GENRE_MAP` |
| `GENRES` com 10 slugs e `TAGS` | **Não**: `GENRES` tem 5, `TAGS` não existe | `build.py:GENRES` (diff proposto em §10.1 e §10.1.1) |
| Pontuação, confiança, modo sombra, `curation/*.jsonl` | **Não** | — |
| `links-todo`/`links-apply`, `amazon-todo`/`amazon-apply` | **Não** | — |
| Google Books | **Não** (sem chave cadastrada) | — |
| Corte por desconto no site | **Não**. Todo livro do catálogo com preço fresco aparece | `build.py:resolve` |
| `_redirects` | 4 a 5 regras por livro e falha acima de 2.000 | `build.py:redirects`, `MAX_REDIRECTS` |
| Workflows | `curator.yml` (só `workflow_dispatch`, abre PR), `catalog-check.yml` (PR, sem secrets) | `.github/workflows/` |
| Coletor do ML | Lê os livros em rodízio, em série, com prazo de 40 s por execução | `collect.py:collect_ml`, `ML_DEADLINE_S = 40` |

## 3. O que as fontes dizem (fato x inferência)

O detalhe de cada sinal (preço, demanda, avaliações, tendência) está em `curadoria-automatica.md` §10.2. Aqui ficam só os fatos que definem o desenho do `curator`.

### 3.1 Amazon
- **Fato (regra 1 do CLAUDE.md):** scraping da Amazon é proibido. Isso inclui request, headless e "só a busca".
- **Fato:** a Creators API oferece `SearchItems` (busca por palavra-chave e browse node), `GetItems`, `GetVariations` e `GetBrowseNodes`. O acesso exige "at least 10 qualifying sales within the past 30 days" ([Creators API, Introduction](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction), página sem data, consultada em 2026-10-19). A página não lista os marketplaces nem os limites de taxa.
- **Fato:** a documentação da PA-API 5 manda migrar para a Creators API e informa a descontinuação em 30/04/2026 ([PA-API 5, Operations](https://webservices.amazon.ca/paapi5/documentation/quick-start/operations-and-resources.html), consultada em 2026-10-19).
- **Consequência:** **sem a Creators API, não há descoberta automática na Amazon.** O `curator` do MVP não faz nenhuma request para domínio da Amazon.
- **Inferência, a conferir pelo humano:** para livro físico, o ASIN costuma ser o ISBN-10. O `curator` pode calcular o ISBN-10 a partir do ISBN-13 (só para o prefixo 978) e mostrar esse valor no PR como "ASIN provável", sem request nenhuma. Quem confirma é o Elias, ao abrir a página no navegador dele, e só então põe o `asin` no catálogo. Isso não entra no catálogo de forma automática, porque cada `asin` soma uma linha à conferência manual diária da Amazon.
- **O que muda quando a API for liberada:**
  - `SearchItems` com browse node de livros passa a ser uma fonte de candidatos da Amazon, e `GetItems` pelo ISBN preenche o `asin` dos candidatos do ML;
  - o link da Amazon já é montado no código (`build.py:affiliate_url`, `/dp/<ASIN>?tag=`), então os livros da Amazon **não precisam de humano para o link**;
  - o preço e a foto passam a vir da API, e a conferência manual some;
  - o acesso depende de manter as vendas qualificadas. **Inferência:** a API pode ser cortada se as vendas caírem. Por isso o `curator` precisa continuar funcionando só com o ML.

### 3.2 Mercado Livre: endpoints para achar livros

Categoria: `MLB1196` ("Livros, Revistas e Comics") **não é folha**. A folha de livro físico é `MLB437616` ("Livros Físicos", domínio `MLB-BOOKS`, sem subcategorias). Conferi via `GET /categories/MLB1196` e `/categories/MLB437616`, públicos, em 2026-10-19.

A coluna "Token de app" abaixo é a da primeira redação. O resultado do passo 0 vem logo depois da tabela e prevalece.

| Endpoint | Para quê | Doc (data) | Sem token (testado 2026-10-19) | Token de app |
|---|---|---|---|---|
| `GET /highlights/MLB/category/MLB437616` | Top 20 mais vendidos da categoria. Cada item vem como `PRODUCT`, `USER_PRODUCT` (MLBU) ou `ITEM` | [Mais vendidos](https://developers.mercadolivre.com.br/pt_br/mais-vendidos-no-mercado-livre) (22/06/2026). A doc diz que a categoria tem de ser folha, ou devolve 404 | 401 | **A verificar** (passo 0) |
| `GET /highlights/MLB/category/MLB437616?attribute=BOOK_GENRE&attributeValue=<id>` | Top 20 por nicho | Mesma doc: "filtrar por qualquer atributo suportado". O exemplo usa `BRAND` | — | **A verificar**: se o `BOOK_GENRE` é aceito é **inferência** |
| `GET /trends/MLB/MLB437616` | 50 termos de busca em alta, com atualização semanal | [Tendências](https://developers.mercadolivre.com.br/pt_br/tendencias) (27/05/2025) | 403 | A verificar. Devolve só `keyword` e uma URL de `lista.mercadolivre.com.br`, que é HTML e **não pode ser seguida** |
| `GET /products/search?site_id=MLB&status=active&product_identifier=<ISBN>` (ou `q=`) | Achar o produto de catálogo pelo ISBN ou pelo título | [Buscador de produtos](https://developers.mercadolivre.com.br/pt_br/buscador-de-produtos) (29/12/2025). É voltado a vendedor | 403 | A verificar |
| `GET /sites/MLB/search` | Busca de anúncios | [Busca de itens](https://developers.mercadolivre.com.br/pt_br/itens-e-buscas) (31/08/2026). Só mostra uso por `seller_id`/`nickname` | 403 (produção e teste de hoje) | Não usar |
| `GET /products/{id}`, `/products/{id}/items` | Ficha (título, autor, GTIN, `BOOK_GENRE`, idioma, foto) e preço | Buscador de produtos (29/12/2025) | 401 | **Funciona** (produção) |
| `GET /items/{id}/sale_price` | Preço promocional | — | — | **403** (produção, run 39178554200) |
| `GET /categories/MLB437616/attributes` | Ids do `BOOK_GENRE`, `LANGUAGE` etc. | — | **200** | — |

**Passo 0, resultado (2026-10-19, token de app):** probe 39258219518.
- `/highlights` geral: 200, 20 itens (16 `PRODUCT`, 4 `USER_PRODUCT`).
- `/highlights?attribute=BOOK_GENRE`: **400**. Não é usado; o nicho sai só do `BOOK_GENRE` da ficha (`/products/{id}`).
- `/trends`: 200, 50 termos. Vira segunda fonte: os 5 primeiros termos são resolvidos por `/products/search?q=&domain_id=MLB-BOOKS` (até 10 produtos cada), com posição a partir de 101, depois de todo o `/highlights`.
- `/products/search?product_identifier=`: 200.
- suggest 39258304023: 16 de 16 descartados por ISBN. O `product_gtins` só lia `value_name` do atributo `GTIN` com `\d{8,14}`: hífen, ISBN-10, `values[].name` e ids `ISBN`/`EAN` ficavam de fora. Corrigido (normaliza, converte ISBN-10 para 13, valida checksum), e o log separa `isbn_ausente`, `isbn_ausente_pai`, `isbn_invalido` e `isbn_multiplo`.

**Probe 39259800320 (2026-10-19, token de app):**
- **Fato:** o `/products/{id}` não traz nenhum atributo `GTIN`, `ISBN` ou `EAN`. Vêm `AUTHOR`, `BOOK_TITLE`, `BOOK_GENRE`, `BOOK_PUBLISHER`, `BOOK_EDITION`, `LANGUAGE`, `PAGES_NUMBER`, `BISAC`, `SYNOPSIS` etc. A correção acima não tinha o que ler: o filtro de ISBN obrigatório descartaria todo candidato.
- **Fato:** dos 3 primeiros `PRODUCT` do `/highlights` de `MLB437616`, o #3 não é livro. Os atributos são `BRAND`, `COLOR`, `PAPER_TYPE`, `GRAMMAGE` etc., ou seja, papelaria na categoria de livros.
- **Fato:** `/products/search?product_identifier=<ISBN>` funciona (200).

**Decisão do Elias (2026-10-19, opção 1):**
- **ISBN opcional.** Se a ficha trouxer ISBN (nos formatos aceitos acima), ele é validado e gravado. Se não trouxer, o candidato entra sem `isbn`. ISBN presente e inválido continua sendo descarte (`isbn_invalido`), e dois ISBNs distintos também (`isbn_multiplo`). Os motivos `isbn_ausente` e `isbn_ausente_pai` saem.
- **Identidade = `ml_product_id`.** Já é a chave de duplicado no catálogo e no `curator_seen.json`. O ISBN, quando existe, continua sendo checado como duplicado.
- **Prova de que é livro = `BOOK_TITLE` e `AUTHOR` não vazios na ficha.** Sem eles, o descarte é `nao_livro` (pega a papelaria). Título e autor do candidato vêm desses atributos (escapados no resumo do PR).
- **Casamento com a Amazon:** substituído pelo gate 7 de `curadoria-automatica.md` §10.3 (identidade por loja) e pelo fluxo manual de §10.5. Ver a seção 5.4 abaixo.

Ids do `BOOK_GENRE`: os 25 valores e o slug de cada um estão na tabela de `curadoria-automatica.md` §10.1, que é a vigente. O ML não tem "Literatura brasileira": esse nicho só entra à mão (§10.1).

**Fato da doc (31/08/2026):** `/items?ids=` será descontinuado até 25/10/2026, e o substituto é `/items/bulk?ids=`. O coletor atual não usa essa rota (conferido no `grep`), e o `curator` também não deve usar.

### 3.3 Scraping do HTML do ML
- **Fato:** os [Termos e Condições do Programa de Desenvolvedores do ML](https://developers.mercadolivre.com.br/pt_br/termos-e-condicoes) (sem data na página, consultados em 2026-10-19) proíbem, no item 7.6, "utilizar robôs, harvesters, spiders, scraping ou outra tecnologia para acessar o Conteúdo do Mercado Livre ou o Site ou os serviços prestados pelo Mercado Livre, ou utilizá-los para obter qualquer informação que não lhes seja fornecida pelo Mercado Livre no âmbito do Programa de Desenvolvedores". O item 7.5 proíbe "efetuar engenharia reversa" e "contornar limitações técnicas".
- **Fato, dos mesmos termos:** o item 5.3 manda atualizar o conteúdo do ML a cada 24 h, ou a cada 6 h quando for listagem de artigos. O pipeline de 30 min já cumpre isso.
- **Consequência:** **nada de raspar HTML do ML.** Ao usar a API, o Elias aceitou esses termos. O 403 em `/sites/MLB/search` não autoriza buscar o mesmo dado na página.

### 3.4 Link de afiliado do ML
- **Fato:** não achei, na documentação de desenvolvedores do ML, nenhum endpoint para gerar link de afiliado. Fontes de terceiros dizem o mesmo:
  - "O Mercado Livre não tem API pública para afiliados" ([grupozap.online](https://grupozap.online/afiliados/mercado-livre), conferido pelo autor em 08/10/2026);
  - "o Mercado Livre não oferece API pública" ([TabNews](https://www.tabnews.com.br/marcuth/criei-uma-cli-para-gerar-links-de-afiliados-de-marketplaces)). A CLI desse autor usa cookie de sessão, o que é exatamente o que não queremos.
- **Não verificado:** as páginas oficiais do programa ([afiliados-home](https://www.mercadolivre.com.br/l/afiliados-home) e [ajuda 39155](https://www.mercadolivre.com.br/ajuda/programa-afiliados-criadores_39155)) e os Termos do programa devolveram 403 para mim. Conheço os termos só por terceiros:
  - proibição de "editar, mascarar, encurtar links" e de usar automação para gerar cliques ([escoladoafiliado.com.br](https://escoladoafiliado.com.br/blog/mercado-livre-afiliados-pagamento-e-regras/), 10/07/2026);
  - um "item 1.8" sobre encurtar ou editar o link;
  - a exigência de divulgar só em canais informados no cadastro.
- **Montar o link à mão (URL do produto + `matt_word` + `matt_tool`, sem `ref`) atribui a comissão?** **Não é documentado.** Dizer que funciona é inferência a partir de links observados, e o próprio grupozap diz que "o Mercado Livre não documenta o formato" do `matt_tool`. Por terceiros, os termos proíbem editar o link gerado. **Recomendação: não montar.** O `build.py:ml_url` já rejeita esse formato, porque exige o caminho `/social/<aff>`. Fica assim.
- **GET no link do painel para conferir o livro:** decidido na rodada 3 (`curadoria-automatica.md` §10.4, item 5). O agent `affiliate-linker` pode fazer GET em cada link do ML e ler só o `og:title`, com 1 s de intervalo. Riscos aceitos e anotados lá: item 7.6 dos termos de dev, clique contado na nossa conta e casamento por título. Isso substitui o "nunca fazer GET no `ml_url`" de `curadoria-e-links.md` B.4. O código do `curator` e do build continua sem fazer GET em link de afiliado: a conferência é do agent, não do pipeline.
- **Automatizar o painel com navegador (Playwright) viola os termos?** **Inferência forte: sim.** O item 7.6 cobre "outra tecnologia para acessar [...] os serviços prestados pelo Mercado Livre", e o painel é um serviço. Também exigiria guardar sessão ou senha da conta do Elias num runner, e um ban derruba toda a receita do ML. **Recomendação: não fazer.**
- **Menor atrito possível:** segundo terceiros, o Gerador de links do painel aceita "1 ou mais URLs" e só funciona no computador (grupozap, 08/10/2026). Se isso se confirmar, o PR traz um bloco com todas as URLs de produto dos candidatos, pronto para colar de uma vez. O Elias confere na decisão 5.

## 4. Opções

| Opção | Prós | Contras |
|---|---|---|
| A. Raspar o HTML do ML e da Amazon | Acha tudo | Viola a regra 1 e o item 7.6 do ML. Risco de ban nos dois programas. É despejo. **Fora.** |
| B. API do ML para descobrir + Playwright no painel para o link | Zero trabalho manual | Item 7.6 (inferência forte), credencial de sessão no CI, risco de ban do afiliado. **Fora.** |
| C. API do ML para descobrir, regras fixas, PR semanal, merge humano | Oficial, R$ 0, auditável | Foi a primeira versão. Não chega a 50 por dia, porque cada livro passa por um merge. **Substituída** |
| **D. API do ML (+ Google Books) para descobrir e pontuar, modo sombra, depois publicação automática com gates; humano só faz o par livro ↔ link** | Oficial, R$ 0, auditável no log `curation/*.jsonl`, escala para 50 por dia | O par livro ↔ link continua manual (~50 links do ML por dia). Volume de fonte não confirmado (`/highlights` dá 20 itens) |
| E. D + LLM para escolher ou escrever blurb | Texto mais rico | Custo, prompt injection, alucinação de autor ou ISBN. Não melhora a escolha. **Fora do MVP** |

## 5. Recomendação e desenho vigente

**Opção D**, sem LLM. O `curator` continua sendo um script stdlib (`collector/curator.py`) que reaproveita o cliente do ML do `collect.py`, agora com um job **diário**.

### 5.1 Volume (gate 8)
- **Meta:** pelo menos 50 livros novos por dia. **Teto:** 10 por gênero por dia. Configurável (`DAY_TARGET = 50`, `GENRE_MAX = 10`).
- É meta, não cota: entra quem passa em todos os gates com `score ≥ 70` e `confiança ≥ 0,5`. Se forem 12, entram 12. **O limiar nunca baixa para completar 50.**
- Tag (`lgbtqia`) não conta para o teto de gênero: o livro conta só no seu `genre`.
- Se a fonte rende 50 por dia depois da primeira semana é **não confirmado** (o `/highlights` dá 20 itens e muda devagar; o `/trends`, até 50 termos por semana). A sombra mede e o resumo de segunda mostra.

### 5.2 Nichos e tags
- Os 10 gêneros de `curadoria-automatica.md` §10.1, com o mapa `BOOK_GENRE → slug` de lá: `literatura-brasileira` (só manual), `ficcao`, `nao-ficcao`, `negocios`, `manga`, `autoajuda`, `infantojuvenil`, `religiao`, `estudo`, `estilo-de-vida`. **Autoajuda entra.**
- `BOOK_GENRE` = LGBTQ+ (76624760) → `genre: "ficcao"`, `tags: ["lgbtqia"]`, `genre_source: "padrao_lgbtqia"` (§10.1.1). O Elias corrige o gênero à mão quando for não ficção.
- Livro já publicado mantém o gênero manual (decisão 4). Bíblia, Vade Mecum e apostila de concurso ficam fora do automático (decisão B5 de `curadoria-e-links.md`).

### 5.3 Pontuação e modo sombra
- Componentes, pesos e fórmulas de `curadoria-automatica.md` §10.3: preço 35, demanda 25, avaliações `15·min(1; v/50)`, tendência 25. Componente ausente não conta como zero.
- Publica com `score ≥ 70` **e** `confiança ≥ 0,5`. Retira com `score < 60` em 2 execuções seguidas.
- Avaliações pelo Google Books, com a chave `GOOGLE_BOOKS_API_KEY` (GitHub Secrets; nunca no repo nem no log). Enquanto o Elias não cadastrar a chave, o componente fica ausente.
- Tendência fica ausente até sair o acesso à Trends API alpha. Nunca `pytrends`.
- **Modo sombra primeiro:** o score é calculado e gravado em `curation/AAAA-MM.jsonl` (branch `price-history`, 24 meses), e nada muda no site. A publicação só liga com o critério de saída de §10.3, item 6. Na prática, nada publica antes de 30 dias de histórico de preço no ML.

### 5.4 Links e identidade
- **ML:** fila por linha em `collector/ml_links.tsv` (§10.4). O `curator` monta só a `product_url` `https://www.mercadolivre.com.br/p/<MLB>`; o Elias cola o link do painel na mesma linha; `links-apply` valida com `affiliate_url`/`check_url`. O `affiliate-linker` pode fazer GET no link para conferir o `og:title` (aceito na rodada 3, riscos em §10.4, item 5).
- **Amazon, manual até a Creators API** (§10.5): `amazon-todo` monta a URL da Amazon como texto (`/dp/<ASIN provável>` ou busca), **o código nunca a chama**; o Elias confere a edição, gera o link no SiteStripe e preenche o `isbn_confirmado`; `amazon-apply` guarda só o ASIN. O preço da Amazon continua digitado em `amazon_prices.csv`.
- **Gate 7, identidade por loja:** no ML, `ml_product_id`, e o livro só no ML não precisa de ISBN; na Amazon, `asin` + `isbn_confirmado`. Casamento entre lojas pelo ISBN-13 quando os dois lados têm. ISBN da ficha do ML diferente do `isbn_confirmado`: a linha da Amazon é recusada e o livro segue só com o ML. Nenhuma confirmação pelo `/products/search` (rejeitada na rodada 3). Uma loja não bloqueia a outra (gate 10, regra simétrica).
- Candidato aprovado e sem link nenhum entra no `catalog.json` como `"pendente": true` (mecanismo que já existe: não é coletado nem exportado) e sai da fila em 14 dias se não ganhar link.

### 5.5 Transição do desenho antigo
O `suggest` atual (PR semanal) pode continuar rodando por `workflow_dispatch` até a entrega 2 estar pronta, porque não publica nada sem merge. Quando o job diário de sombra entrar, o passo de PR do `curator.yml` sai e o cron passa a ser diário.

### 5.6 Teto da vitrine ativa e o limite do `_redirects` (proposta, decisão 1 da seção 14)

**O problema.** O `build.py:redirects` gera, por livro, `/r/<id>`, `/r/<id>/<loja>` para cada loja no prazo, `/r/<id>/tg` e `/r/<id>/wa`: 4 regras com uma loja, 5 com duas. Mais o curinga `/r/* / 302`. O build falha acima de `MAX_REDIRECTS = 2000`, que é o limite de regras estáticas. **Fato** ([Cloudflare, Redirects em static assets](https://developers.cloudflare.com/workers/static-assets/redirects/), consultada em 2026-10-19): "2,000 static redirects and 100 dynamic redirects", 1.000 caracteres por regra. Placeholder (`:id`) e splat (`*`) contam como dinâmicos.

**Por que placeholder sozinho não resolve.** Uma regra `/r/:id <destino>` só funciona se o destino puder ser montado a partir do `:id`. Não pode: o link do ML é opaco (`ref` cifrado) e o ASIN não é o `id`. Usar o ASIN ou o MLB como `id` quebraria os deep links que já existem e colocaria dado da requisição no destino externo, que é exatamente o open redirect que a allowlist evita.

**Onde ele resolve.** Em quase todo livro, `/r/<id>/tg` e `/r/<id>/wa` têm **o mesmo destino** de `/r/<id>`:
- quando a vencedora é o ML, o `ml_url` é o mesmo nos três (é o que o código faz hoje: "ML: mesmo ml_url");
- quando a vencedora é a Amazon, eles só diferem se `AMAZON_TAG_TG`/`AMAZON_TAG_WA` estiverem definidas.

| Opção | Regras por livro | Livros que cabem | Prós | Contras |
|---|---|---|---|---|
| R0. Teto de 380 livros, sem mudar o build | 4 a 5 | ~400 | Zero código | Satura em ~8 dias a 50 por dia; a aba de curadoria disputa o mesmo teto |
| **R1. Só gerar `/tg` e `/wa` estáticos quando o destino difere de `/r/<id>`; para os demais, 2 regras dinâmicas internas** | 1 + lojas no prazo (+2 se a Amazon vence e há tag por canal) | ~990 só ML; ~665 com duas lojas | Muda ~5 linhas em `redirects()`. Nenhum dado da requisição vai para destino externo | Depende de a regra estática vir antes da dinâmica no arquivo (já é o caso do curinga hoje) |
| R2. R1 + não gerar a rota da loja vencedora (`/r/<id>/<loja>` só para a loja da seta) | 1 a 2 (+2) | ~1.000 a 1.990 | Mais folga | Link de loja que virou vencedora entre um build e outro precisa de mais uma regra dinâmica `/r/:id/<loja> → /r/:id`, que leva à outra loja. Pouco ganho enquanto o coletor for o gargalo |
| R3. Worker em `/r/*` (`run_worker_first: ["/r/*"]`) resolvendo o `id` num mapa gerado pelo build | 0 regras | sem limite prático | Sem teto do `_redirects` | Vira código de servidor: precisa revalidar a allowlist no runtime, conta no limite de 100 mil requisições por dia do plano Free (**fato**, [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/); asset estático é grátis e ilimitado), e o comportamento ao estourar o limite não está documentado na página (**não confirmado**) |
| R4. Bulk Redirects da conta | 0 no arquivo | — | — | Exige token de API da conta no CI (credencial nova) e configuração fora do repo. **Fora** |

As regras dinâmicas de R1, no fim do arquivo, logo antes do curinga:
```
/r/:id/tg /r/:id 302
/r/:id/wa /r/:id 302
/r/* / 302
```
O destino é sempre um caminho interno que começa com `/r/`, então não vira `//host` nem URL externa. A segunda volta cai numa regra estática de `/r/<id>` (destino validado por `check_url`) ou no curinga, que vai para a home. A allowlist anti open-redirect fica igual: destino externo só sai de `affiliate_url` + `check_url`, com `id` de `offers.json`. Custo: 1 salto a mais nos links de canal de livro do ML.

**Fato a conferir antes de implementar:** a doc da Cloudflare diz que "static redirects should appear before dynamic redirects" e que, com a mesma origem, vale a de cima. Ela **não diz** explicitamente que uma regra estática vence uma dinâmica que vem depois em qualquer caso. O build atual já depende disso (o curinga `/r/*` está no fim). Critério de aceite: conferir no `wrangler dev` que `/r/<id>/tg` com regra estática usa a estática.

**O teto de 380 não é a resposta.** Com R1, o `_redirects` deixa de ser o limite que aperta primeiro. O limite real passa a ser o **coletor**:
- o `collect_ml` lê os livros em série, em rodízio, com `ML_DEADLINE_S = 40` por execução de 30 min;
- cada livro do ML precisa ser lido pelo menos a cada 2 h (`FRESH`), ou seja, a cada 4 execuções;
- com 1 a 2 requests por livro, a 0,3 a 0,5 s cada (**inferência**, não medido), cabem uns 40 a 80 livros por execução, o que dá **160 a 320 livros frescos**.

**Recomendação:**
1. Implementar R1 agora (frontend-developer, em `build.py:redirects`), com o `MAX_REDIRECTS` continuando a falhar o build.
2. Teto configurável `ACTIVE_MAX` de livros no catálogo (ativos + pendentes + aba de curadoria), **valor inicial 300**. Acima dele, o novo só entra no lugar do de menor score, e só se o superar por pelo menos 5 pontos (para não virar churn). Isso substitui o `CATALOG_MAX = 150`.
3. O collector-engineer mede, na sombra, o tempo por livro e sobe o `ML_DEADLINE_S` (o job tem 10 min de `timeout-minutes`). O `ACTIVE_MAX` sobe junto, até o limite de regras de R1 com 10% de folga (~1.800 regras).
4. R3 (Worker) só quando o `ACTIVE_MAX` medido passar de ~600. Não antes.

**Efeito na meta de 50 por dia:** com 300 de teto, o catálogo enche em ~6 dias. Depois disso, "50 novos por dia" vira "até 50 trocas por dia", limitadas pela margem de 5 pontos e pelo critério de churn da sombra (< 10% entram e saem em menos de 7 dias). O Elias precisa aceitar essa leitura (decisão 1).

### 5.7 Fila diária da Amazon manual e cobertura de 80% (proposta, decisões 2 e 3 da seção 14)

**O custo real não é a fila, é a conferência diária.** Cada linha nova da `amazon_links.tsv` custa ao Elias uns 2 min (abrir, conferir a edição, SiteStripe, ISBN). Mas cada livro aceito passa a exigir **uma conferência de preço por dia, para sempre** (frescor de 12 h), e isso cresce com o catálogo. A 50 por dia, em 30 dias seriam até 1.500 livros para conferir à mão.

**Proposta:**
- `AMAZON_QUEUE_DAY = 5`: a `amazon-todo` traz no máximo 5 linhas novas por dia, as de maior score (no empate, maior demanda, porque o objetivo da Amazon agora é chegar às 10 vendas que liberam a Creators API).
- `AMAZON_ACTIVE_MAX = 30`: no máximo 30 livros com a Amazon em conferência manual de preço. A `amazon_queue.csv`, que já existe, lista só esses 30, por score. A uns 30 s por livro, dá ~15 min por dia, acima dos ~10 min previstos em `distribuicao-canais.md`; com 20, fica em ~10 min.
- Acima do teto, um livro novo só entra na Amazon no lugar do de menor score. O que sai mantém o `asin` no catálogo (não precisa refazer o SiteStripe se voltar), só sai da conferência diária, e o livro segue pelo ML quando a Amazon perde o frescor.
- Quando a Creators API sair, os dois tetos somem: `GetItems` traz preço, ASIN e ISBN.

**Cobertura de 80% para o selo de 90 dias da Amazon.** Com amostras manuais esparsas, o mínimo que guardamos é maior ou igual ao mínimo real. O selo "menor preço em 90 dias" é afirmação ao consumidor (CDC, `distribuicao-canais.md` §12.3).
- **Regra:** a série da Amazon de um livro só conta para o selo e para o componente Preço se tiver amostra em **pelo menos 80% dos dias BRT da janela de 90 dias** (≥ 72 dias distintos com linha `source=manual`), além dos 90 dias de `history_since`.
- **Abaixo de 80%:**
  - se a vencedora é a Amazon, **sem selo** ("90d" e "since"), porque o "desde DD/MM" tem o mesmo problema;
  - se a vencedora é o ML, o selo considera só a série do ML e o texto passa a ser "Menor preço em 90 dias no Mercado Livre", para não afirmar nada sobre a Amazon;
  - no score, a Amazon cai para o tratamento de histórico curto (`desconto_rótulo`, `confidence = 0,5`).
- **Consequência prática:** 80% exige conferência em ~6 de cada 7 dias, fim de semana incluído. Se o Elias não confere no fim de semana (5/7 = 71%), nenhum livro da Amazon terá selo. É honesto, e é o motivo para a decisão 3 ser dele.
- **Dado novo:** `coverage_90d` (fração de 0 a 1) por loja no `offers.json`, calculado pelo coletor a partir do `price_history`. Campo opcional no contrato v2 de `comparacao-lojas.md`; o `seal_of` do build passa a usá-lo.

## 6. Escopo da entrega 2

**Dentro** (detalhe em §10 de `curadoria-automatica.md`):
- Primeira tarefa: o resto do passo 0 (§10.2): `/highlights/MLB/product/{id}`, `/reviews/item/{id}` num livro popular, `sold_quantity` ausente em `/items/{id}`, `PUBLICATION_YEAR` preenchido.
- `curator.py shadow`: descoberta (`/highlights` geral + `/trends`), ficha, gênero e tags, gates, componentes, score e confiança; grava uma linha por candidato em `curation/AAAA-MM.jsonl`; resumo semanal no log.
- Google Books por ISBN conhecido, com `GOOGLE_BOOKS_API_KEY`.
- `links-todo`/`links-apply` e `amazon-todo`/`amazon-apply` (§10.4 e §10.5).
- `GENRES` com 10 slugs, `TAGS`, `tags` no `load_catalog` e no build (§10.1, §10.1.1).
- R1 no `_redirects` e o `ACTIVE_MAX` (5.6). Os tetos da Amazon e o `coverage_90d` (5.7).
- `curator.yml` diário, escrevendo no branch `price-history`.

**Fora (e quando vale fazer):**
- **`curator.py publish`** (escrever no `catalog.json` sem humano). **Quando:** o critério de saída da sombra for atingido e o Elias registrar o "aprovado".
- **Descoberta na Amazon.** **Quando:** a Creators API for liberada.
- **`USER_PRODUCT`/`ITEM` (MLBU).** O coletor só lê `/products`. **Quando:** um nicho ficar sem candidatos por falta de produto de catálogo.
- **LLM.** **Quando:** o site passar a mostrar texto próprio por livro.
- **Worker no `/r/*` (R3).** **Quando:** o `ACTIVE_MAX` medido passar de ~600.
- **Busqy.** Descartado por enquanto (decisão 14). **Quando:** ~50 links do ML por dia pesarem demais.

## 7. Fluxo

1. **Todo dia, 09h BRT:** o `curator.yml` roda o `shadow`. Lê `/highlights` e `/trends`, a ficha dos produtos novos (`LOOKUP_MAX` por execução), o preço e, para quem passou nos gates, o Google Books. Grava `curation/AAAA-MM.jsonl` no branch `price-history`.
2. **Na sombra,** nada mais acontece. Segunda-feira sai o resumo no log. O Elias rotula a amostra cega (§10.3, item 4).
3. **Depois da saída da sombra:** o `publish` escreve no `catalog.json` os aprovados do dia (até 10 por gênero, dentro do `ACTIVE_MAX`), como `"pendente": true`, e roda `links-todo` e `amazon-todo` (até 5 linhas da Amazon).
4. **Elias, todo dia:** gera os links do ML no painel e cola na `ml_links.tsv` (ou passa a lista para o `affiliate-linker`); confere as até 5 linhas da Amazon e lança os preços da Amazon do dia.
5. `links-apply` e `amazon-apply` validam linha a linha e gravam `ml_url`/`asin`. O `pendente` sai quando o livro ganha a primeira loja.
6. Na próxima execução do `pipeline.yml`, o livro entra na coleta e aparece na vitrine com preço fresco. Score < 60 em 2 execuções ou 6 h sem nenhuma loja fresca: sai da vitrine.

## 8. Critérios de seleção

Os critérios por livro que bloqueiam ou só pontuam estão em `curadoria-e-links.md` A.2 (aprovados, B4) e nos gates de `curadoria-automatica.md` §4 e §10.3. Continuam valendo, desta spec, os filtros abaixo:

| Regra | Valor | Por quê |
|---|---|---|
| Fonte | `/highlights` geral de `MLB437616` e, em segundo, os termos do `/trends` via `/products/search?q=` | O filtro por `BOOK_GENRE` dá 400 |
| Tipo | Só `PRODUCT`, `status=active` | Compatível com o coletor (`ml_product_id`) |
| Prova de livro | `BOOK_TITLE` e `AUTHOR` não vazios; senão, `nao_livro` | A categoria tem papelaria |
| ISBN | Opcional. Presente: validado (978/979, checksum, um só); senão `isbn_invalido`/`isbn_multiplo` | A ficha com token de app não traz GTIN |
| Condição e moeda | Novo, BRL | Regra do coletor e do programa do ML |
| Preço | R$ 15 a R$ 400 | Decisão 3 do PR #4, não revista |
| Idioma | Português; ausente é descarte | Decisão 3 do PR #4, não revista |
| Nicho | `BOOK_GENRE` mapeado para um dos 10 gêneros (§10.1); sem mapeamento, descarte (gate 6) | `GENRES` é fechado |
| Duplicado | `ml_product_id` ou ISBN já no catálogo, ou no `curator_seen.json` há menos de 180 dias | Não insistir no recusado |
| **Ordem** | **Score (§10.3)**, desempate pela confiança e depois pelo `ml_product_id` | Substitui a posição no ranking |
| **Volume** | **Meta de 50 por dia, até 10 por gênero, dentro do `ACTIVE_MAX`** (5.1 e 5.6) | Decisão 12 |

**LLM:** continua sem uso, pelas mesmas razões (campos estruturados da API, sem blurb no site, risco de alucinar). Se um dia entrar: chave em Secret, sem ferramentas no contexto, saída só em enum ou texto validado por `_text`, e nunca decide sozinho o que vai ao ar.

## 9. Dados

- **`collector/catalog.json`:** ganha `tags` (lista de `TAGS`, até 3) e, no automático, `genre_source`. `pendente` continua, agora para o aprovado sem link. Pendente com `ml_url` ou `asin` continua `Invalid`.
- **`collector/curator_seen.json`:** igual (`ml_product_id` → data, poda de 180 dias, público).
- **`curation/AAAA-MM.jsonl`** (branch `price-history`, 24 meses): uma linha por candidato com componentes, score, confiança, gates e `would_publish` (§10.3). **Sem dado de usuário.**
- **`collector/ml_links.tsv` e `collector/amazon_links.tsv`:** locais, no `.gitignore`, transitórios.
- **`id`:** slug ASCII do título, estável para sempre, nunca reaproveitado (gate 9).
- **Dado de usuário:** nenhum. Não há LGPD envolvida.

## 10. Onde roda e permissões

**`curator.yml`** (passa a ser diário):
- `permissions: {}` no topo. No job de sombra, `contents: write` só para o push no branch `price-history`, com o mesmo padrão de `extraheader` do `pipeline.yml`. O passo de PR (`pull-requests: write`) sai quando a sombra entrar.
- Secrets só no `env` do passo que usa: `ML_CLIENT_ID`/`ML_CLIENT_SECRET` e `GOOGLE_BOOKS_API_KEY`. A chave do Google vai na query (`key=`), então **nenhuma URL do Google Books pode ir para o log**.
- `concurrency` compartilhado com o `pipeline.yml` no push do `price-history`, para os dois não brigarem pelo branch. `timeout-minutes` sobe para caber o `LOOKUP_MAX` maior (medir).
- Actions fixadas por SHA, `persist-credentials: false`.

**`catalog-check.yml`:** igual (`pull_request`, `contents: read`, sem secrets).

## 11. Critérios de aceite

1. **Hosts permitidos:** um teste troca o `urlopen` e confirma que toda URL chamada pelo `curator` tem host `api.mercadolibre.com` ou `www.googleapis.com` (só `/books/v1/volumes`). `grep -n "amazon\." collector/curator.py` só acha texto montado para TSV, nunca passado ao `urlopen`.
2. **Nenhum scraping de HTML:** resposta não JSON aborta; nada de `html.parser`, BeautifulSoup ou Playwright; nenhuma URL de `lista.mercadolivre.com.br` ou `www.mercadolivre.com.br` é chamada pelo código; `requirements-dev.txt` não muda.
3. **O `curator` nunca escreve `ml_url` nem `asin` sozinho:** só `links-apply`/`amazon-apply`, a partir de linha preenchida pelo humano e validada.
4. **Sombra não toca o site:** com o `shadow`, `catalog.json` e `offers.json` ficam byte a byte iguais; só o `jsonl` muda.
5. **Volume:** com 200 candidatos simulados acima do limiar, entram no máximo 10 por gênero e nunca acima do `ACTIVE_MAX`. Com 12 acima do limiar, entram 12 (o limiar não baixa). Tag não conta no teto de gênero.
6. **Nichos:** cada um dos 25 `BOOK_GENRE` vai para o slug da tabela de §10.1; Autoajuda (7538148) → `autoajuda`; LGBTQ+ (76624760) → `ficcao` + `tags: ["lgbtqia"]` + `genre_source: "padrao_lgbtqia"`. Livro já publicado não é reclassificado.
7. **Score:** componente ausente não entra no numerador nem no denominador do score, e conta como 0 no denominador 100 da confiança. Os exemplos de §10.3 (0,325 e 0,50) e de §10.6, item 9 (67, 73, 78) saem iguais no teste.
8. **Gate 7:** ISBN do ML diferente do `isbn_confirmado` recusa a linha da Amazon e mantém o ML; sem ISBN no ML, o `isbn_confirmado` vira o ISBN do livro com `amazon_match: "manual"`.
9. **Segredos:** token do ML, secret e `GOOGLE_BOOKS_API_KEY` nunca aparecem no stdout (teste que captura o log com a chave definida).
10. **`_redirects` (R1):** livro só no ML gera 2 regras; com duas lojas e ML vencendo, 3; Amazon vencendo com `AMAZON_TAG_TG`/`_WA` diferentes da tag do site, 5. As regras dinâmicas são exatamente `/r/:id/tg /r/:id 302`, `/r/:id/wa /r/:id 302` e o curinga, nessa ordem e depois de todas as estáticas. No `wrangler dev`, `/r/<id>/tg` de um livro com regra estática usa a estática.
11. **Amazon manual:** a `amazon-todo` nunca escreve mais de `AMAZON_QUEUE_DAY` linhas novas por dia; a `amazon_queue.csv` nunca lista mais de `AMAZON_ACTIVE_MAX` livros.
12. **Cobertura:** uma série da Amazon com 71 dias distintos de amostra em 90 não dá selo "90d" nem "since" quando a Amazon vence; com o ML vencendo, o selo sai como "no Mercado Livre". Com 72 dias, conta normalmente.
13. `python3 build.py --selftest` e `pytest` verdes.

## 12. Divisão por agent (ordem de execução)

1. **collector-engineer, passo 0 restante** (§10.2) e registro do resultado em `curadoria-automatica.md` §10.2.
2. **frontend-developer:** `GENRES` com 10 slugs, `TAGS`, `RESERVED`, `in_niche`, páginas de tag (diff de §10.1.1); R1 em `redirects()` e o teste no `wrangler dev`; `seal_of` com `coverage_90d` e o texto "no Mercado Livre".
3. **collector-engineer:** `tags` e `genre_source` no `load_catalog`/`BOOK_FIELDS`; `coverage_90d` no `offers.json`; tetos da Amazon em `write_queue`; as mudanças do `curator.py` da seção 15; `curator.yml` diário; medição do tempo por livro no coletor e proposta de `ML_DEADLINE_S`.
4. **catalog-curator:** conferir o mapa dos 25 `BOOK_GENRE` no código contra §10.1 e definir como excluir Bíblia, Vade Mecum e apostila (B5) sem casar por título.
5. **security-auditor:** escopo da `GOOGLE_BOOKS_API_KEY` (só no passo, nunca em URL logada); push no `price-history`; R1 (as regras dinâmicas não viram open redirect); `.gitignore` dos dois TSV. Rodar `/security-review`.
6. **code-reviewer:** um PR para o build (2), um para o coletor e o curador (3 e 4). No PR do build, com `web-design-guidelines`.
- **alerts-engineer:** nada aqui. Os links de canal (`/r/<id>/tg`, `/wa`) continuam iguais para quem posta.
- **Elias:** cadastrar `GOOGLE_BOOKS_API_KEY`; ajustar o `.claude/agents/affiliate-linker.md` para trabalhar sobre a `ml_links.tsv` em vez do PR do curator (o arquivo de agent é dele aprovar).

## 13. Riscos

**Regras inegociáveis**
- *Regra 1 (Amazon):* o código não toca nenhum domínio da Amazon (critério 1). A fila da Amazon só monta texto; quem abre é o Elias.
- *Regra 2 (link do ML):* o link vem do painel, gerado por humano, validado pelo `matt_word`. Nada de link montado nem de Playwright. O GET do `affiliate-linker` é conferência pontual, aceita com riscos (§10.4).
- *Regra 3 (credenciais):* entra uma credencial nova, `GOOGLE_BOOKS_API_KEY`, só em Secrets e restrita à Books API no Google Cloud.
- *Regra 4 (transparência):* não muda. O selo "no Mercado Livre" (5.7) evita afirmar sobre a Amazon o que não sabemos.

**Termos**
- ML 5.4: a posição do `/highlights` entra só na pontuação e nunca aparece no site (B1).
- ML 7.6: o GET do `affiliate-linker` é o ponto mais exposto; ele roda no computador do Elias, não no CI, a 1 s de intervalo.
- Amazon 2(h): histórico da Amazon guardado com risco aceito (decisão 7), pergunta por escrito em paralelo.

**Operação e custo**
- **Coletor é o gargalo** (5.6): sem subir o `ML_DEADLINE_S`, livros novos ficam sem preço fresco e somem da vitrine sozinhos. Medir na sombra.
- **Tempo do Elias:** ~50 links do ML por dia e até 5 linhas da Amazon, mais a conferência de até 30 preços da Amazon. Se pesar, é o gatilho para reabrir o Busqy.
- **Fonte curta:** o `/highlights` dá 20 itens. Pode não haver 50 por dia; a sombra mostra.
- Custo em dinheiro: R$ 0 (Actions em repo público, Google Books com cota gratuita, Cloudflare Free).

## 14. Decisões

**Já decididas** (registradas em `curadoria-automatica.md` §10.6; não reabrir): publicação automática com gates e sombra; 10 gêneros com `estudo` e a tag `lgbtqia`; pesos 35/25/15/25, `score ≥ 70`, `confiança ≥ 0,5`; Google Books com chave; Amazon manual até a Creators API; gate 7 por loja; GET do `affiliate-linker` aceito; volume de 50 por dia e 10 por gênero. As 5 decisões da versão do PR #4 (cron, volume, preço e idioma, mapeamento, conferência do painel) ficam: 1 e 2 substituídas, 3 mantida, 4 substituída por §10.1, 5 continua pendente com o Elias.

**Em aberto, para o Elias:**
1. **Teto da vitrine e `_redirects`** (5.6): (a) R0, teto de 380 sem mudar o build; (b) **R1 + `ACTIVE_MAX` = 300 inicial, subindo com a medição do coletor (recomendado)**; (c) R3, Worker já. Junto: aceitar que, depois do teto, "50 novos por dia" vira "até 50 trocas por dia" com margem de 5 pontos. Nota: o Elias já aceitou o impacto da aba de curadoria no `_redirects` (`aba-curadoria.md` §0, item 3), que foi calculado com R1; falta confirmar R1 e o `ACTIVE_MAX` aqui.
2. **Fila diária da Amazon** (5.7): (a) **5 linhas por dia e 30 livros em conferência (recomendado)**; (b) 5 por dia e 20 livros, para caber nos ~10 min por dia; (c) outro N.
3. **Cobertura para o selo da Amazon** (5.7): (a) **80%, com conferência ~6 dias por semana (recomendado)**; (b) 70%, que aceita pular o fim de semana, com risco maior de o selo afirmar um mínimo que não foi o real; (c) nunca dar selo com a série manual da Amazon até a Creators API.
4. **Texto do selo restrito:** "Menor preço em 90 dias no Mercado Livre" (recomendado) ou simplesmente não mostrar selo quando a Amazon está abaixo da cobertura.

## 15. O que muda no `collector/curator.py` (não implementado)

| # | Mudança | Hoje | Vira | Agent |
|---|---|---|---|---|
| 1 | Volume | `WEEK_MAX = 10`, `GENRE_MAX = 4` | `DAY_TARGET = 50` (meta, só para o resumo: não força entrada), `GENRE_MAX = 10` | collector-engineer |
| 2 | Teto | `CATALOG_MAX = 150` | `ACTIVE_MAX = 300` (decisão 1), com troca pelo de menor score e margem de 5 pontos | collector-engineer |
| 3 | Mapa de gênero | `GENRE_MAP` com 6 ids → 4 slugs, sem Autoajuda | Os 25 ids → 10 slugs de §10.1 (inclui `7538148 → autoajuda`) | collector-engineer; catalog-curator confere |
| 4 | Tags | Não existe | `genre_of` devolve `(genre, tags, genre_source)`; `76624760 → ("ficcao", ["lgbtqia"], "padrao_lgbtqia")`. Depende de `TAGS` no `build.py` | collector-engineer (depois do frontend-developer) |
| 5 | Ordem | `select` ordena por posição e desconto | Ordena por score, depois confiança; corta pelo limiar e pela confiança antes dos tetos | collector-engineer |
| 6 | Pontuação | Não existe | Funções dos 4 componentes, agregação e confiança de §10.3 (puras, testáveis sem rede) | collector-engineer |
| 7 | Google Books | Não existe; docstring diz "só fala com api.mercadolibre.com" | Cliente por ISBN conhecido em `www.googleapis.com/books/v1/volumes?q=isbn:`, chave do env, URL nunca logada; docstring e critério 1 atualizados | collector-engineer; security-auditor revisa |
| 8 | Modo sombra | Não existe | Subcomando `shadow` que grava `curation/AAAA-MM.jsonl` (caminho recebido por argumento, como o `--history` do coletor) e o resumo de segunda | collector-engineer |
| 9 | PR semanal | `summary()`, `suggest`, passo de PR no `curator.yml` | Saem quando o `shadow` entrar. `pendente` fica, para aprovado sem link | collector-engineer |
| 10 | Filas de link | Não existe | `links-todo`/`links-apply` (§10.4) e `amazon-todo`/`amazon-apply` (§10.5), com `AMAZON_QUEUE_DAY = 5`. `asin_provavel()` é reaproveitado | collector-engineer |
| 11 | Exclusões B5 | Não existe | Bíblia, Vade Mecum e apostila fora do automático, por critério a definir que não case por título | catalog-curator define; collector-engineer implementa |
| 12 | Orçamento | `LOOKUP_MAX = 60`, `DEADLINE_S = 300` | Medir na sombra; provavelmente maior para render 50 por dia. `timeout-minutes` do job acompanha | collector-engineer |
| 13 | Testes | `tests/` do desenho antigo | Critérios 1 a 9 e 11 da seção 11 | collector-engineer |

Fora do `curator.py`, mas na mesma entrega: `build.py` (`GENRES`, `TAGS`, R1, `seal_of` com cobertura) → frontend-developer; `collect.py` (`tags`, `coverage_90d`, `AMAZON_ACTIVE_MAX` na `write_queue`, `ML_DEADLINE_S`) → collector-engineer; contrato v2 em `comparacao-lojas.md` (`tags`, `genre_source`, `coverage_90d`) → product-manager.
