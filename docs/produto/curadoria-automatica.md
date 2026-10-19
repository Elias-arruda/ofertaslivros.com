# Spec: curadoria automática do catálogo (`curator`)

Status: proposta, 2026-10-19. Autor: product-manager. Implementação: ver "Divisão por agent".

## 1. Problema e usuário

**Em uma frase:** hoje o Elias acha cada livro, gera o link no painel do ML e escreve a entrada do `collector/catalog.json` à mão (o catálogo tem 2 livros). Ele quer que uma máquina encontre os livros que valem a pena e prepare tudo, para o catálogo crescer sem ocupar o dia dele. Mais livros bons monitorados dão mais ofertas reais na vitrine e nos canais, e portanto mais cliques de afiliado.

**Interpretações do pedido:**
1. **Webscraper que busca "todos os livros"** nas lojas. Esbarra na regra 1 (Amazon) e nos termos do ML (seção 3.3). Também vai contra "curadoria, não despejo". **Descartada.**
2. **Agente com LLM que escolhe os livros e gera os links sozinho.** Não existe caminho oficial para gerar o link do ML (seção 3.4), e um LLM não é necessário para escolher (seção 8). **Descartada no MVP.**
3. **Um job semanal que descobre candidatos pela API oficial do ML, filtra por regras objetivas e abre um PR já pronto.** Ao Elias só sobram duas coisas: gerar o link no painel e aprovar. **Recomendada.** É o `curator` previsto na decisão 6 de `alerta-de-preco.md`.

## 2. O que existe hoje (conferido no repo em 2026-10-19)

| Item | Existe? | Onde |
|---|---|---|
| Catálogo de livros monitorados | Sim, com 2 livros, só do ML | `collector/catalog.json` |
| Validação do catálogo: `id` (`ID_RE`), `genre` em `GENRES`, ISBN-13, `ml_product_id` e `ml_url` sempre juntos, `ml_url` preso ao `matt_word` | Sim | `collector/collect.py:load_catalog`, `build.py:ml_url` |
| Cliente da API do ML: token de app (`client_credentials`), backoff, um host só (`ML_HOST = api.mercadolibre.com`) | Sim | `collect.py:ml_token`, `ml_request` |
| Leitura de produto: vencedor do buy box, anúncios do produto (novo, BRL), GTIN e foto | Sim | `collect.py:winner`, `best_listing`, `product_items`, `product_gtins`, `product_image` |
| Diagnóstico de rotas do ML sem gravar nada | Sim, só para produto | `collect.py probe` |
| Nichos (conjunto fechado) | Sim: `literatura-brasileira`, `ficcao`, `negocios`, `nao-ficcao`, `manga` | `build.py:GENRES` |
| Corte por desconto no site | **Não encontrei** no `build.py`. Todo livro do catálogo com preço fresco aparece, então **o catálogo é a vitrine.** | — |
| Descoberta de livros novos | **Não** | — |
| Workflow que abre PR | **Não**. Só existe `pipeline.yml` (cron de 30 min, `permissions: {}` no topo e `contents: write` no job, sem `pull_request`) | `.github/workflows/` |
| Check de CI em PR | **Não** | — |
| Testes | Sim | `tests/test_collector.py`, `build.py --selftest` |

## 3. O que as fontes dizem (fato x inferência)

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

Ids do `BOOK_GENRE` relevantes (de `/categories/MLB437616/attributes`, 2026-10-19):
- `13061816` Mangas e HQs
- `13061825` Negócios
- `7538039` Literatura
- `13611960` Biografias
- `13464376` História
- `76624759` Ciência
- `7538148` Autoajuda

Não existe "Literatura brasileira": o `curator` sugere `ficcao`, e o Elias troca no PR quando for o caso.

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
- **Automatizar o painel com navegador (Playwright) viola os termos?** **Inferência forte: sim.** O item 7.6 cobre "outra tecnologia para acessar [...] os serviços prestados pelo Mercado Livre", e o painel é um serviço. Também exigiria guardar sessão ou senha da conta do Elias num runner, e um ban derruba toda a receita do ML. **Recomendação: não fazer.**
- **Menor atrito possível:** segundo terceiros, o Gerador de links do painel aceita "1 ou mais URLs" e só funciona no computador (grupozap, 08/10/2026). Se isso se confirmar, o PR traz um bloco com todas as URLs de produto dos candidatos, pronto para colar de uma vez. O Elias confere na decisão 5.

## 4. Opções

| Opção | Prós | Contras |
|---|---|---|
| A. Raspar o HTML do ML e da Amazon | Acha tudo | Viola a regra 1 e o item 7.6 do ML. Risco de ban nos dois programas. É despejo. **Fora.** |
| B. API do ML para descobrir + Playwright no painel para o link | Zero trabalho manual | O item 7.6 (inferência forte), credencial de sessão no CI, quebra a cada mudança do painel, risco de ban do afiliado. **Fora.** |
| C. API do ML para descobrir, regras fixas para filtrar, PR com os candidatos, humano gera o link e faz o merge | Oficial, R$ 0, auditável no git, reaproveita 80% do `collect.py`, o Elias decide tudo em minutos por semana | Ainda tem um passo manual por livro (colar o link). A descoberta depende de o `/highlights` aceitar token de app (passo 0) |
| D. C + LLM para escolher e escrever o blurb | Texto mais rico | O site não mostra blurb. Traz custo, risco de prompt injection e risco de alucinar autor ou ISBN. Não melhora a escolha em relação às regras |

## 5. Recomendação

**Opção C**, sem LLM. O `curator` é um script stdlib (`collector/curator.py`) que reaproveita o cliente do ML do `collect.py` e roda num workflow semanal próprio. Ele abre **um PR por semana** com no máximo **10 candidatos**, adicionados ao `catalog.json` com `"pendente": true` e **sem `ml_url`**. Entrada pendente nunca é coletada nem vai ao ar. O Elias gera os links no painel, troca `"pendente": true` pelo `ml_url`, apaga o que não quer e faz o merge.

**Passo 0, que bloqueia o resto:** um `curator.py probe` para conferir, com o token de app, se `/highlights`, `/highlights?attribute=BOOK_GENRE`, `/trends` e `/products/search` respondem.
- Se o `/highlights` der 403, a fonte do MVP passa a ser uma **lista de ISBNs semeada pelo Elias**: `collector/seeds.txt`, por exemplo listas de editoras. O `curator` resolve cada ISBN pelo `/products/search?product_identifier=`, se essa rota responder.
- Se nada responder com token de app, a spec volta para cá. Token de usuário (`authorization_code`) exige guardar um `refresh_token` que muda a cada uso: isso é outro projeto.

## 6. Escopo do MVP

**Dentro:**
- `curator.py probe`: status HTTP e chaves de topo de cada rota de descoberta, sem gravar nada e sem logar token.
- `curator.py suggest`, com estes passos:
  1. lê o `/highlights` de `MLB437616` (top geral) e um por nicho mapeado;
  2. guarda só os itens `type=PRODUCT` (o `ml_product_id` precisa casar com `MLB_RE`; `MLBU` e `ITEM` ficam de fora);
  3. enriquece cada um com `/products/{id}` e o preço (`winner`/`best_listing`);
  4. filtra (seção 8) e ordena;
  5. grava até N entradas pendentes no `catalog.json` e o registro em `collector/curator_seen.json`.
- Suporte a `"pendente": true` no `load_catalog`. Uma entrada pendente:
  - não tem `ml_url` nem `asin`;
  - não é coletada nem exportada;
  - não entra no `offers.json`;
  - gera uma linha de log.
- Workflow `.github/workflows/curator.yml`: cron semanal e `workflow_dispatch`. Cria o branch `curator/AAAA-MM-DD` e abre o PR com `gh pr create`.
- Corpo do PR com:
  - uma tabela por candidato (título, autor, nicho sugerido, preço, desconto sobre `original_price`, posição no ranking, ISBN, "ASIN provável" e link `https://www.mercadolivre.com.br/p/<MLB>`);
  - o bloco de URLs para colar no Gerador de links;
  - o checklist "colei o link / troquei o nicho / apaguei os que não quero".
- Workflow `.github/workflows/catalog-check.yml` em `pull_request`, sem secrets e com `contents: read`. Ele roda `collect.py export` para validar o catálogo, `build.py --selftest` e `pytest`.

**Fora (e quando vale fazer):**
- **Descoberta na Amazon e `asin` automático.** **Quando:** a Creators API for liberada (seção 3.1).
- **`/trends` e `/products/search?q=` como fontes extras.** **Quando:** o passo 0 mostrar que respondem e o `/highlights` não render candidatos suficientes por 4 semanas.
- **`USER_PRODUCT`/`ITEM` (MLBU, anúncio solto).** O coletor só sabe ler `/products`. **Quando:** um nicho ficar sem candidatos por falta de produto de catálogo.
- **LLM para blurb ou escolha.** **Quando:** o site passar a mostrar texto próprio por livro (seção 8).
- **Sugestão de remoção** (livro inativo há 30 dias no `price_history`). **Quando:** o catálogo passar de uns 80 livros. Hoje a vitrine já esconde o que está inativo.
- **Google Books/Open Library.** A ficha do `/products/{id}` já traz título, autor, GTIN e gênero, e o Elias recusou o Open Library para fotos (resposta 4 em `distribuicao-canais.md`). **Quando:** faltar autor ou título com frequência.
- **Aviso no Telegram de que "o PR do curator abriu".** O GitHub já notifica. **Quando:** o Elias pedir.

## 7. Fluxo

1. **Setup único (Elias):**
   - em Settings > Actions, ligar "Allow GitHub Actions to create and approve pull requests";
   - criar um ruleset na `main` exigindo PR e o check `catalog-check`;
   - conferir os termos do programa no painel (decisão 5).
2. **Segunda, 09h BRT:** o `curator.yml` roda.
   - Se já houver um PR aberto com a label `curator`, ele sai sem fazer nada: um PR por vez.
   - Se não houver, ele pega o token de app, consulta o `/highlights` geral e um por nicho mapeado (cerca de 6 chamadas) e lê `/products/{id}` dos `PRODUCT` novos (até cerca de 120 chamadas).
3. O script filtra e ordena (seção 8) e grava no máximo `min(10, CATALOG_MAX − tamanho atual)` entradas pendentes, além do `curator_seen.json`. Com zero candidatos, não abre PR e só registra no log.
4. Ele faz commit e push só no branch `curator/AAAA-MM-DD` e abre o PR com a label `curator`. **Fato:** um PR aberto pelo `GITHUB_TOKEN` não dispara outros workflows ([GitHub Docs, GITHUB_TOKEN](https://docs.github.com/en/actions/concepts/security/github_token): "events triggered by the GITHUB_TOKEN will not create a new workflow run"). Por isso o `catalog-check` só roda no primeiro push do Elias, e isso basta, porque o ruleset bloqueia o merge sem o check.
5. **Elias, cerca de 5 a 10 minutos:**
   - abre o PR;
   - cola o bloco de URLs no Gerador de links do painel;
   - em cada entrada que quer, troca `"pendente": true` por `"ml_url": "<link do painel>"` e ajusta o `genre` se precisar;
   - apaga as que não quer, que ficam no `curator_seen.json` e não voltam por 180 dias;
   - pode adicionar o `asin` se conferir o "ASIN provável";
   - dá push.
6. O `catalog-check` valida (`ml_url` preso ao `matt_word`, ISBN, `genre`, `id` único). Com o check verde, o Elias faz o merge.
7. Na próxima execução do `pipeline.yml`, os livros com `ml_url` entram na coleta e aparecem na vitrine com preço fresco. Os que continuaram pendentes seguem fora do ar.

## 8. Critérios de seleção (o "agente" de curadoria)

As regras são determinísticas e ficam em constantes no topo do `curator.py`, com os valores iniciais abaixo.

| Regra | Valor inicial | Por quê |
|---|---|---|
| Fonte | `/highlights` de `MLB437616`: geral e por `BOOK_GENRE` mapeado | A popularidade vem da própria API |
| Tipo | Só `PRODUCT`, com `status=active` | Compatível com o coletor (`ml_product_id`) |
| ISBN | GTIN presente, `isbn_ok`, prefixo 978/979, e um só ISBN por produto | Casa com a Amazon no futuro e evita ficha errada |
| Condição e moeda | Novo, BRL (`winner`/`best_listing`) | Os afiliados do ML só geram link para produto novo (terceiros: grupozap). É também a regra do coletor |
| Preço | R$ 15 a R$ 400 | Abaixo disso a comissão não paga o esforço; acima, é box raro (decisão 3) |
| Idioma | `LANGUAGE` = Português | Público do site (decisão 3) |
| Nicho | `BOOK_GENRE` mapeado para `GENRES`. Sem mapeamento, o livro é descartado | O `GENRES` é fechado |
| Duplicado | Fora se o ISBN ou o `ml_product_id` já estiver no catálogo, ou se estiver no `curator_seen.json` há menos de 180 dias | Não insistir no que o Elias recusou |
| Ordem | Posição no ranking (menor primeiro); no empate, maior desconto sobre `original_price` | Mais vendido converte mais |
| Volume | No máximo 10 por semana, no máximo 4 por nicho, catálogo total ≤ `CATALOG_MAX` = 150 (ativos + pendentes) | "Curadoria, não despejo" (decisão 2). 150 livros × 3 regras cabem com folga no limite de 2.000 do `_redirects` |

**Desconto real contra o histórico:** um livro descoberto agora não tem histórico, então o desconto sobre `original_price` serve só para desempate. O desconto real vale depois, na vitrine e nos canais: o selo de 90 dias e o limiar de 30% de `distribuicao-canais.md`. O `curator` escolhe o que **monitorar**, e o pipeline decide o que **destacar**.

**LLM: não precisa no MVP.**
- Popularidade, nicho, ISBN, preço e idioma vêm como campos estruturados da API, e o título e o autor vêm dos atributos `BOOK_TITLE` e `AUTHOR` da ficha.
- O site não exibe blurb.
- Um LLM só traria risco de alucinar autor ou ISBN, além de custo.

Se um dia entrar:
- **Onde roda:** num passo do mesmo workflow, com a chave em Secret e sem nenhuma ferramenta ou token no contexto.
- **Saída:** só o slug de um enum (`GENRES`) ou um texto curto validado por `build.py:_text` e revisado no PR.
- **Prompt injection:** título e descrição de anúncio são dado de terceiro, e um vendedor pode escrever "ignore as instruções". O LLM nunca decide sozinho o que vai ao ar.
- **Custo:** cerca de 10 candidatos × 1 a 2 mil tokens por semana, centavos por mês.

## 9. Dados

- **`collector/catalog.json`:** ganha o campo opcional `"pendente": true`. Uma entrada pendente tem `id`, `isbn`, `genre`, `title`, `author` e `ml_product_id`. **Pendente com `ml_url` ou `asin` é `Invalid`**, porque é ambíguo. O `_nota` do arquivo e o `BOOK_FIELDS` do `collect.py` são atualizados.
- **`collector/curator_seen.json`:** `{ "MLB19698440": "2026-10-19", ... }`, com o `ml_product_id` e a data em que foi sugerido pela primeira vez. Só cresce, é podado depois de 180 dias e fica público no repo (não é dado pessoal).
- **`id`:** slug ASCII do título (`ID_RE`). Em caso de colisão, ganha o sufixo `-2`. O `id` é estável para sempre (vira deep link), então o Elias pode corrigir no PR, **nunca depois do merge**.
- **Dado de usuário:** nenhum. Não há LGPD envolvida.

## 10. Onde roda e permissões

| | GitHub Actions (recomendado) | Local |
|---|---|---|
| Disparo | Cron semanal + `workflow_dispatch` | O Elias lembra de rodar |
| Secrets | `ML_CLIENT_ID`/`ML_CLIENT_SECRET`, já existem | `.env` local |
| Custo | Grátis (repo público) | Grátis |
| Auditoria | Log e PR públicos | Nenhuma |

**`curator.yml`:**
- `permissions: {}` no topo. No job, só `contents: write` (push no branch `curator/*`) e `pull-requests: write`;
- actions fixadas por SHA, `persist-credentials: false` e o mesmo padrão de `extraheader` do `pipeline.yml`;
- `ML_AFFILIATE_ID` em `vars`, e os secrets só no `env` do passo de descoberta, nunca no passo do `gh`;
- push só para `refs/heads/curator/*`, nunca para a `main`. A proteção real é o ruleset da `main`, porque `contents: write` sozinho permitiria o push.
- `concurrency: curator`, `timeout-minutes: 10`.

**`catalog-check.yml`:**
- só `pull_request`, nunca `pull_request_target`;
- `permissions: contents: read`, sem secrets;
- `ML_AFFILIATE_ID` fixo no `env`. Ele não é segredo, porque aparece em todo link público.

## 11. Critérios de aceite

1. **Nenhuma request para a Amazon:** um teste troca o `urlopen` e confirma que toda URL chamada pelo `curator` tem host `api.mercadolibre.com`. Além disso, `grep -n "amazon\." collector/curator.py` não acha nenhuma URL.
2. **Nenhum scraping de HTML:**
   - resposta com `Content-Type` diferente de `application/json` aborta a execução;
   - o código não importa `html.parser`, BeautifulSoup nem Playwright;
   - nenhuma URL de `lista.mercadolivre.com.br` ou `www.mercadolivre.com.br` é chamada (ela só aparece como texto no PR);
   - o `requirements-dev.txt` não muda.
3. **O `curator` nunca escreve `ml_url` nem `asin`:** teste sobre a saída do `suggest`.
4. **Pendente não vai ao ar:**
   - um catálogo com pendentes roda `collect.py run`;
   - as entradas pendentes não aparecem no `offers.json`, no `_redirects` nem no histórico;
   - um pendente com `ml_url` dá `Invalid`.
5. **Merge sem preencher não quebra o pipeline:** o mesmo teste do critério 4 passa com 100% das entradas novas pendentes.
6. **Limite de volume:** nenhuma execução sugere mais de 10 livros, nem mais de 4 por nicho, nem passa de `CATALOG_MAX`. Testes com `/highlights` de 20 itens simulado.
7. **Sem duplicado:** um candidato com ISBN ou `ml_product_id` já no catálogo, ou no `curator_seen.json` há menos de 180 dias, não é sugerido.
8. **Cada candidato passa por:** ISBN-13 válido (978/979) e igual ao GTIN, novo, BRL, preço na faixa, `genre ∈ GENRES`, `id` com `ID_RE.fullmatch` e único, título e autor por `_text`.
9. **Um PR por vez:** com um PR `curator` aberto, a execução sai com código 0 e não abre outro. Com zero candidatos, não abre PR.
10. **Aprovação humana obrigatória:**
    - o workflow não contém `gh pr merge`, `--admin` nem push para a `main`;
    - o ruleset da `main` exige PR e o check `catalog-check` (conferência manual no setup).
11. **Corpo do PR seguro:**
    - título e autor saem dentro de code span, sem `|`, crase, `<`, `>`, `[`, `]` nem `@` crus;
    - o corpo tem no máximo 60 mil caracteres;
    - nenhum link no corpo sai de dado da API, além de `https://www.mercadolivre.com.br/p/<MLB_RE>`, montado pelo código.
12. **Segredos:** token e secret nunca aparecem no log (teste que captura o stdout do `probe` e do `suggest`). Actions fixadas por SHA.
13. **O `probe` responde à pergunta do passo 0:** imprime o status HTTP de `/highlights` (geral e com `BOOK_GENRE`), `/trends` e `/products/search` com o token de app, sem gravar nada.
14. `python3 build.py --selftest` e `pytest` verdes. O `catalog-check` fica vermelho com um `ml_url` de `matt_word` alheio.

## 12. Divisão por agent (ordem de execução)

1. **collector-engineer, passo 0:** `curator.py probe` e uma execução manual. O resultado é registrado nesta spec (tabela 3.2) e decide entre o `/highlights` e o plano B das sementes de ISBN.
2. **collector-engineer:**
   - `pendente` no `load_catalog`/`BOOK_FIELDS` e no `_nota`;
   - `curator.py suggest`, reaproveitando `ml_request`, `ml_token`, `winner`, `best_listing`, `product_gtins`, `isbn_ok` e `load_catalog`, sem duplicar código;
   - `curator_seen.json`;
   - testes dos critérios 1 a 9, 11 e 12.
3. **collector-engineer:** `curator.yml` e `catalog-check.yml`, e o passo a passo do setup no `SETUP.md`.
4. **security-auditor:** permissões dos dois workflows, push restrito a `curator/*`, ausência de `pull_request_target`, injeção de markdown no corpo do PR e o critério 2. Rodar `/security-review`.
5. **code-reviewer:** um PR para os passos 0 a 2 e outro para os workflows.
- **frontend-developer:** nada. A vitrine não muda.
- **alerts-engineer:** nada no MVP.

## 13. Riscos

**Regras inegociáveis**
- *Regra 1 (Amazon):* o `curator` não toca nenhum domínio da Amazon (critério 1). O "ASIN provável" é aritmética sobre o ISBN, e o Elias confirma no navegador dele, como já faz com o preço.
- *Regra 2 (link do ML):* o link continua vindo do painel, gerado por humano, e o `ml_url` continua validado pelo `matt_word`. Nada de link montado à mão nem de Playwright (seção 3.4).
- *Regra 3 (credenciais):* reaproveita os secrets que já existem. Não entra credencial nova.
- *Regra 4 (transparência):* não muda. Livro novo usa o mesmo card e o mesmo rodapé.

**Termos do ML**
- O item 7.6 proíbe scraping, e o item 7.8 proíbe volume abusivo. Cerca de 130 chamadas por semana, com o backoff do `ml_request`, é volume baixo.
- Os termos do programa de afiliados não foram lidos no original (403). Os pontos sobre editar link, automação e canais declarados vêm de terceiros (decisão 5).
- A descoberta pode não funcionar com token de app (passo 0). O `/sites/MLB/search` já dá 403, e o `/highlights` pode seguir o mesmo caminho.

**Qualidade da curadoria**
- O "mais vendido" do ML puxa didático, concurso e autoajuda. O mapeamento por nicho e o teto de 4 por nicho contêm isso, e o Elias apaga no PR.
- O ranking pode repetir os mesmos 20 por semanas. O `curator_seen.json` evita a repetição, e o volume cai sozinho. Isso é aceitável.
- Link colado na entrada errada: o `ref` é opaco e não dá para conferir no código que o link é daquele produto. Mitigação: o checklist mostra a URL do produto ao lado de cada entrada, e o Elias abre o link no navegador antes do merge (sem comprar: compra própria não conta).

**Operação e custo**
- O cron do GitHub para depois de 60 dias sem atividade no repo. O commit do `pipeline.yml` no branch `price-history` mantém o repo ativo; conferir isso no primeiro mês.
- Custo: R$ 0, porque os minutos do Actions são ilimitados em repo público. O custo real é o tempo do Elias: 5 a 10 min por semana para até 10 links.
- Um catálogo maior aumenta o tempo do `pipeline.yml`, que lê `/products/{id}` de cada livro a cada 30 min. Com 150 livros ainda cabe nos 10 min do job; medir quando passar de 80.

## 14. Decisões para o Elias

1. **Quando ligar o cron:** a decisão 6 dizia "4 semanas de curadoria manual, depois o `curator`". **Recomendo implementar agora**, porque a etapa 1 (coletor) já está pronta, e rodar só por `workflow_dispatch` até o passo 0 confirmar a fonte. O cron semanal liga depois de 2 PRs bons.
2. **Volume:** 10 candidatos por semana, no máximo 4 por nicho, e teto de 150 livros no catálogo. **Recomendo esses valores**, como constantes fáceis de ajustar.
3. **Filtro de preço e idioma:** R$ 15 a R$ 400, só português. **Recomendo**, e revisar depois de 4 PRs, vendo o que você apagou.
4. **Mapeamento de nichos:**
   - `manga` ← Mangas e HQs;
   - `negocios` ← Negócios;
   - `ficcao` ← Literatura;
   - `nao-ficcao` ← Biografias + História + Ciência.

   Autoajuda fica **fora** (pesa muito no ranking e foge da curadoria), e `literatura-brasileira` continua manual, trocada por você no PR. **Recomendo esse mapeamento.**
5. **Conferir no painel do ML, logado** (eu recebi 403), antes do primeiro PR:
   - o texto dos Termos do programa sobre "editar link", ferramentas automatizadas e canais declarados;
   - se o Gerador de links aceita várias URLs de uma vez;
   - se o site, o Telegram e o WhatsApp estão declarados como canais.

   **Recomendo fazer isso antes do primeiro merge**, porque fecha os únicos pontos da seção 3.4 que se apoiam só em terceiros.
