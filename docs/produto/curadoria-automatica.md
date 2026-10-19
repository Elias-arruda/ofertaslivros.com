# Spec em rascunho: curadoria automática de livros

Status: spec fechada para revisão do Elias. §1–9 são o handoff do Codex (2026-10-18); §10 fecha a spec (catalog-curator, 2026-10-19) e substitui §3, §7 e §8 onde houver conflito.
Decisões do Elias registradas em §10.6 (2026-10-19). A publicação continua desligada até o critério de saída do modo sombra (§10.3) ser atingido; até lá, nada publica.

## 1. Objetivo confirmado

Criar um agente que, diariamente, descubra livros e ofertas, avalie o potencial de curadoria e publique automaticamente no site os livros aprovados pelas regras. Ao longo do dia, o sistema também deve acompanhar mudanças de preço nas ofertas publicadas e atualizar ou retirar ofertas desatualizadas.

Elias confirmou que o agente pode publicar sem aprovação humana por livro, desde que passe pelas regras automáticas.

## 2. Sinais de avaliação pedidos por Elias

- Preço em promoção em relação ao histórico real de preço.
- Número de compras recentes, considerando o período desde a publicação do livro.
- Número de avaliações.
- Interesse de busca do livro no Google Trends.

## 3. Proposta inicial de pontuação (aprovada em §10.6; detalhada em §10.3)

Pontuar de 0 a 100 e guardar os componentes, dados de origem, instante de coleta e confiança. Pesos sugeridos para discussão:

| Componente | Peso | Regra candidata |
|---|---:|---|
| Preço/histórico | 35 | Comparar preço atual à mediana e ao mínimo observados nos últimos 90 dias. Sem histórico suficiente, não afirmar que é promoção; atribuir no máximo pontuação neutra/baixa. |
| Compras recentes ajustadas à idade | 25 | A API pode expor `sold_quantity` acumulado; guardar snapshots e estimar a variação em 30 dias. Comparar o ritmo com livros da mesma faixa de idade editorial. |
| Avaliações | 15 | Combinar quantidade e nota média, reduzindo a confiança de amostras pequenas. |
| Google Trends | 25 | Medir crescimento recente do interesse pelo título e autor, em vez de comparar índices absolutos de livros diferentes. |

Limiar candidato: publicar com pontuação >=70, desde que todos os gates da seção 4 passem. Limite, pesos, janelas e faixas precisam ser calibrados e aprovados antes da implementação.

## 4. Gates de publicação automática

Um candidato só pode ser publicado quando:

1. A identidade do livro/edição tiver correspondência forte, preferencialmente ISBN exato. Não misturar capa dura, brochura, edição revisada, box ou idioma diferente.
2. A oferta estiver ativa, com preço válido e consultado dentro do prazo máximo de frescor definido.
3. O link de afiliado for gerado por um provedor autorizado e validado pelas regras existentes do site.
4. O candidato não duplicar um livro/edição já publicado.
5. A pontuação e a confiança atingirem os limiares aprovados.

Falha em gate essencial bloqueia a publicação, mesmo com pontuação alta. Falha ou indisponibilidade de uma fonte de sinal deve ser registrada como dado ausente, nunca interpretada automaticamente como zero nem substituída por scraping não autorizado.

## 5. Descoberta, atualização e retirada

- **Descoberta diária:** buscar livros e ofertas em APIs/fontes autorizadas; normalizar por ISBN e edição; calcular e registrar a pontuação; publicar candidatos que passem nos gates.
- **Monitoramento intradiário:** revisitar ofertas publicadas várias vezes ao dia. O intervalo deve respeitar limites do provedor e ser configurável. Aumentar a frequência só para ofertas com variação recente ou grande interesse.
- **Preço no site:** informar horário da última consulta. Não apresentar preço velho como atual. Após erro repetido, indisponibilidade, link inválido ou oferta encerrada, despublicar ou marcar indisponível segundo prazo aprovado.
- **Histórico:** manter snapshots de preço para detectar queda real e não depender do rótulo promocional da loja.
- **Auditoria:** registrar por que o agente publicou, atualizou ou retirou cada oferta, com valores dos componentes e referências às fontes.

## 6. Geração de links Mercado Livre: descoberta e pendência principal

Busca feita em 2026-10-18:

- Não foi encontrada API pública oficial do Mercado Livre, documentada para criação de links de afiliado.
- A documentação oficial pública indica o Gerador de Links e a Barra de Afiliados. Também orienta que afiliados usem as ferramentas de criação do programa para divulgar links.
- Foi encontrado um caminho de terceiros: o Busqy documenta conversão automática usando uma conta colaboradora, uma extensão Busqy Tools que obtém um token no perfil de afiliado, e uma etiqueta. O artigo diz que o token da conta colaboradora precisa ser renovado mensalmente.
- Isso comprova que o Busqy oferece conversão dentro do próprio serviço; não comprova que tenha API pública para nosso backend, nem que o Mercado Livre tenha autorizado esse token para uso independente pelo nosso sistema.
- Não automatizar o portal do afiliado, não extrair cookies/sessões e não chamar endpoints privados descobertos por engenharia reversa.

### Verificações necessárias antes de escolher o provedor

1. Perguntar ao Busqy se existe endpoint/API contratual para converter URL do produto em link afiliado, utilizável pelo backend do ofertaslivros.com; pedir documentação, autenticação, limites, preço, SLA, política de retenção do token e procedimento de revogação.
2. Confirmar com o Mercado Livre se o fluxo do Busqy/token de colaborador está autorizado para conversão automatizada e publicação em site próprio.
3. Confirmar a renovação mensal do token, escopo mínimo da conta colaboradora e impacto de expiração/revogação.
4. Se qualquer resposta for negativa ou não houver interface contratual, manter geração de links manual até o programa oferecer método oficialmente autorizado. O agente pode continuar descobrindo e pontuando, mas não publica oferta sem link válido.

Fontes consultadas:

- [Mercado Livre: gerar links de afiliado](https://www.mercadolivre.com.br/l/afiliados-gere-seus-links)
- [Mercado Livre: direcionamento de visitas e links](https://www.mercadolivre.com.br/l/afiliados-direcionamento-de-visitas)
- [Busqy: token de autenticação do Mercado Livre](https://ajuda.busqy.app/pt-br/article/mercado-livre-como-gerar-o-token-de-autenticacao-n05jrz/)
- [Busqy: configuração dos programas de afiliado](https://ajuda.busqy.app/pt-br/article/como-configurar-os-programas-de-afiliado-shopee-amazon-etc-111nwhn/)

## 7. Fontes de dados e limitações já identificadas

- Mercado Livre: a API pública de itens permite consulta de anúncios e preço; `sold_quantity` é acumulado. Para estimar compras recentes, o sistema precisa salvar snapshots próprios. A API de avaliações documenta total e avaliações, sujeita a disponibilidade para o item/produto.
- Google Trends: a API oficial encontrada está em alpha e requer acesso. Os dados são normalizados; usar crescimento temporal do mesmo termo, não ranking direto entre títulos. Sem acesso, esse sinal fica ausente e a pontuação deve ser recalculada com confiança reduzida; não usar scraping de Trends como dependência obrigatória.
- Amazon: nunca fazer scraping. Descoberta, preços e links automatizados só podem usar a Creators API quando habilitada para a conta. Até lá, manter o fluxo manual/semi-automático já definido em `CLAUDE.md`.
- Catálogos como Google Books/Open Library podem ajudar a descobrir metadados, mas não substituem a confirmação de edição/oferta nem são sinal de preço ou vendas.

## 8. Próximas decisões para Claude/Elias (decididas em §10.6)

1. Confirmar com Busqy e Mercado Livre o método contratual de conversão e uso em site próprio.
2. Decidir se o lançamento começa só com Mercado Livre ou espera também a Creators API da Amazon.
3. Aprovar ou ajustar pesos, limiar de publicação, confiança mínima, histórico mínimo de preço e idade do preço.
4. Definir frequência intradiária, quantidade máxima de novos livros/dia, regras de retirada e política para fontes indisponíveis.
5. Quando esses pontos estiverem definidos, atualizar `docs/produto/alerta-de-preco.md` seção 11 e a spec de comparação de lojas, sem alterar o contrato `data/offers.json` sem atualizar a documentação correspondente.

## 9. Estado técnico relacionado ao handoff anterior

- PR #2 foi merged (`fa914b18daac60cb3f5a186090ca30da6b4297c8`), com paginação na consulta de itens do ML e limite de segurança.
- PR #1 continua aberto, limpo, base `main`: https://github.com/Elias-arruda/ofertaslivros.com/pull/1
- PR #3 continua aberto como draft, base PR #1, com workflow de deploy para Workers Static Assets: https://github.com/Elias-arruda/ofertaslivros.com/pull/3
- O deploy não foi executado. A revisão de segurança no HEAD `82cbb61` não achou bloqueios; `pip-audit` ficou limpo após atualizar pytest para 9.0.3.
- O worktree `hind` está no commit `ecfd277` e limpo antes deste handoff. O trabalho de PRs está nos worktrees `collector-pr2-pagination`, `front-reconcile` e `deploy-workflow`.

## 10. Fechamento da spec (catalog-curator, 2026-10-19)

Convenção: **Fato** tem fonte com data; **Inferência** é dedução minha, a confirmar; **Não confirmado** é o que tentei e não consegui verificar. Consultas feitas em 2026-10-18 e 2026-10-19. As rotas `/categories` do ML responderam sem token. Todas as outras rotas do ML citadas abaixo deram 401 ou 403 sem token. Não havia `ML_CLIENT_ID` nesta sessão, então **nenhuma delas foi testada com o token de app**. O passo 0 (`curator.py probe`) já rodou com token de app; o resultado está em §10.2 e em `docs/produto/curator.md` §3.2.

Existe outra versão desta spec no branch `worktree-agent-a26264a6033900af8` (commit `22548f4`, product-manager). Ela chega aos mesmos fatos sobre a API, mas propõe "PR com aprovação humana" em vez de publicação automática. Esta seção segue a decisão do Elias de 2026-10-18 (publicação automática com gates). Vale esta: decisão 1 de §10.6.

**Correção de §7 e §3:** `sold_quantity` de anúncio de terceiro **não** está disponível para nós (§10.2, Sinal 2). O componente "compras recentes" de §3 deixa de ser calculável pelo ML e passa a ser "Demanda", medida pelo ranking.

### 10.1 Gêneros: cobrir todas as áreas

**Fato:** a categoria de livro físico do ML é `MLB437616` ("Livros Físicos", filha de `MLB1196`). Ela é **folha**, sem subcategorias, e tem `catalog_domain: MLB-BOOKS` (`GET https://api.mercadolibre.com/categories/MLB437616`). Por isso não dá para descobrir livros por nicho usando subcategorias.

**Fato:** o gênero vem como atributo. `GET /categories/MLB437616/attributes` traz `BOOK_GENRE`, uma lista fechada de 25 valores, e `BOOK_SUBGENRES`, com 208 valores, `hidden` e multivalorado. Traz também `PUBLICATION_YEAR` e `GTIN` (rótulo "ISBN").

**Proposta: 11 nichos.** Os 5 slugs atuais continuam iguais, porque já são URLs públicas. Entram mais 6. "Técnicos" e "didáticos" ficam separados porque são públicos diferentes: o profissional e o estudante ou concurseiro.

| Slug | Rótulo | URL do nicho | Valores `BOOK_GENRE` do ML (id) |
|---|---|---|---|
| `literatura-brasileira` | Literatura brasileira | `/literatura-brasileira/` | Nenhum. O ML não tem esse valor, nem em `BOOK_SUBGENRES`, onde procurei "brasil" e "nacional". Entra à mão ou, quando a Creators API for liberada, por browse node (abaixo) |
| `ficcao` | Ficção | `/ficcao/` | Literatura (7538039), Humor (25743212). Também LGBTQ+ (76624760), como gênero padrão, sempre com a tag `lgbtqia` (§10.1.1) |
| `nao-ficcao` | Não ficção | `/nao-ficcao/` | História (13464376), Biografias (13611960), Ciência (76624759) |
| `negocios` | Negócios e finanças | `/negocios/` | Negócios (13061825) |
| `manga` | Mangá e HQ | `/manga/` | Mangas e HQs (13061816) |
| `autoajuda` **novo** | Autoajuda | `/autoajuda/` | Autoajuda (7538148) |
| `infantojuvenil` **novo** | Infantil e juvenil | `/infantojuvenil/` | Infantil (7538151), Juvenil (13061823) |
| `religiao` **novo** | Religião e espiritualidade | `/religiao/` | Religião (19912211), Esoterismo (7538147) |
| `didaticos` **novo** | Didáticos e concursos | `/didaticos/` | Escola e educação (23663384), Dicionários, enciclopédias e consulta (7538149) |
| `tecnicos` **novo** | Técnicos e acadêmicos | `/tecnicos/` | Acadêmico (13061813), Tecnologia (14885398) |
| `estilo-de-vida` **novo** | Saúde, hobbies e estilo de vida | `/estilo-de-vida/` | Saúde (13061828), Esportes (16188909), Gastronomia (13061821), Artesanato (13061814), Pets (76624758), Viagem (14973077), Arte e design (7538158), Música (13485350) |

Os 25 valores estão cobertos, e cada um vai para um slug só. Os mapeamentos de Humor em `ficcao`, Esoterismo em `religiao`, Tecnologia em `tecnicos` e Saúde em `estilo-de-vida` foram aprovados como estão (decisão 3). LGBTQ+ deixou de ser só `ficcao` e virou tag (§10.1.1). Produto sem `BOOK_GENRE` não é publicado, porque o build exige `genre` (gate 6 em §10.3). Ele fica no log da sombra como "sem gênero".

**Mudança aprovada no `build.py`** (decisão 2), a aplicar pelo `product-manager`/`frontend-developer`. Não editei o arquivo. O `collect.py` importa `GENRES` do `build.py`, então a mudança vale para os dois. O diff das tags está em §10.1.1.

```diff
 GENRES = {
     "literatura-brasileira": "Literatura brasileira",
     "ficcao": "Ficção",
     "negocios": "Negócios e finanças",
     "nao-ficcao": "Não ficção",
     "manga": "Mangá e HQ",
+    "autoajuda": "Autoajuda",
+    "infantojuvenil": "Infantil e juvenil",
+    "religiao": "Religião e espiritualidade",
+    "didaticos": "Didáticos e concursos",
+    "tecnicos": "Técnicos e acadêmicos",
+    "estilo-de-vida": "Saúde, hobbies e estilo de vida",
 }
```

A ordem do dict é a ordem do menu (`nav`), e o menu só mostra gênero com oferta. Gênero vazio não gera link quebrado no menu, mas cada slug vira diretório em `dist/`. Os slugs passam no `ID_RE`. O mapa `BOOK_GENRE id → slug` fica no curador, não no `build.py`.

**Migração do que já existe.** Nenhum slug muda de nome e nenhum `id` muda, então `/r/<id>` e os deep links do Telegram continuam valendo. Hoje existem 2 livros em `collector/catalog.json` (os dois em `ficcao`) e 10 em `data/offers.json` (`ficcao` 2, `literatura-brasileira` 4, `manga` 2, `nao-ficcao` 1, `negocios` 2). A regra proposta é esta:
- O curador **não reclassifica** livro já publicado. O gênero manual prevalece (decisão 4).
- Na primeira execução da sombra, ele compara o gênero manual com o mapeado pelo `BOOK_GENRE` e registra as divergências, só para informação. Candidatas prováveis (**inferência**): "Irmão do Jorel" (`ficcao`, mas talvez `infantojuvenil` no ML) e "Hábitos Atômicos" (`negocios`, mas talvez `autoajuda`). Mudar o gênero só move o livro de página de nicho; o link continua o mesmo.
- **Tags nos livros atuais:** entram `tags: []` em todos. Nenhum dos 10 livros de `collector/catalog.json` nem dos 10 de `data/offers.json` (conferido em 2026-10-19) é, pelo que sei, LGBTQIA+ (**inferência**: não li as sinopses). Se o Elias souber de algum, a tag entra à mão. A sombra também registra quem tem `BOOK_GENRE` = LGBTQ+ no ML.

**Mapeamento a partir das APIs:**
- **ML (viável hoje):** `BOOK_GENRE` do produto (`GET /products/{id}`, em `attributes`) → tabela acima. É determinístico e não usa título. Se o produto vier sem o atributo, o livro fica sem gênero e não publica.
- **Amazon (viável quando a Creators API for liberada):** `browseNodeInfo.browseNodes` + `.ancestor` devolvem `id`, `displayName` e `contextFreeName` de cada nó e a escada até a raiz ([BrowseNodeInfo](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/resources/browse-node-info)). O mapa seria `id do nó filho da raiz "Livros"` → slug. Os ids dos nós da amazon.com.br são **não confirmados**: só dá para levantá-los com a API liberada, via `GetBrowseNodes`. Se existir um nó "Literatura brasileira" (**não confirmado**), ele é o único caminho automático para esse slug.
- **Conflito entre lojas:** vale o `BOOK_GENRE` do ML. A exceção é `literatura-brasileira` vindo da Amazon, que é mais específico e prevalece sobre `ficcao`. A divergência fica registrada no log.
- **Fato (probe 39258219518):** o `/highlights` filtrado por `BOOK_GENRE` dá **400**. O top 20 por nicho não existe; o gênero só vem da ficha do produto.

#### 10.1.1 Tags: subcategorias transversais (decisão 3)

O livro tem **um** `genre` (o nicho principal, de `GENRES`) e uma lista `tags` de um segundo conjunto fechado, `TAGS`. Cada tag também gera página. Exemplo: "Vermelho, Branco e Sangue Azul" tem `genre: "ficcao"` e `tags: ["lgbtqia"]`, e aparece em `/ficcao/` e em `/lgbtqia/`.

- **Campo:** `tags`, lista de slugs, opcional (ausente = `[]`), sem repetição, no máximo 3. Vale no `collector/catalog.json` e no `data/offers.json` (nível do livro, ao lado de `genre`).
- **Conjunto inicial:** só `"lgbtqia": "LGBTQIA+"`. Não proponho outras agora: tag sem fonte automática e sem volume vira página vazia. Candidatas para depois, se o volume justificar: `classicos`, `lancamentos`, `box-e-colecoes`. Cada tag nova passa pelo mesmo caminho de um gênero novo (Elias, pelo `product-manager`).
- **Página:** `/lgbtqia/`, no mesmo nível dos nichos de gênero, porque é um "nicho próprio". Para isso, os slugs de `TAGS` e de `GENRES` não podem se repetir nem usar rotas reservadas (`r`, `privacidade`, `canais`). O build verifica isso ao carregar o módulo. O menu mostra os gêneros e, depois, as tags, só as que têm oferta.
- **Preenchimento:**
  - automático: `BOOK_GENRE` = LGBTQ+ (76624760) no ML → `tags: ["lgbtqia"]` e `genre: "ficcao"`. **Fato:** `BOOK_GENRE` é de valor único (sem `multivalued` em `/categories/MLB437616/attributes`), então o ML não diz qual é o gênero "de verdade" desses livros. A sombra marca `genre_source: "padrao_lgbtqia"`, e o Elias corrige à mão quando for não ficção (por exemplo, biografia). Os 208 `BOOK_SUBGENRES` não têm nada de LGBTQ (conferido);
  - manual: nos demais casos (por exemplo, romance que o ML classificou como Literatura), o Elias acrescenta a tag no `catalog.json`. O curador nunca tira tag posta à mão;
  - Amazon (quando a Creators API sair): browse node equivalente, se existir (**não confirmado**).
- **Validação no build:** tag fora de `TAGS`, valor que não é texto, repetição ou mais de 3 quebram o build, exatamente como `genre` inválido. O `load_catalog` do `collect.py` faz o mesmo, porque hoje rejeita campo desconhecido (`BOOK_FIELDS`); isso é do `collector-engineer`.
- **Contrato:** `tags` entra no contrato v2 de `docs/produto/comparacao-lojas.md` como campo opcional. Mudança de contrato: passa pelo `product-manager`.

Diff proposto, **não aplicado**:

```diff
 GENRES = {
     ... (os 11 de §10.1)
 }
+# Segundo conjunto fechado: subcategorias transversais. Também viram diretório em dist/.
+TAGS = {
+    "lgbtqia": "LGBTQIA+",
+}
+NICHES = {**GENRES, **TAGS}  # ordem do menu: gêneros, depois tags
+RESERVED = {"r", "privacidade", "canais"}
+if set(GENRES) & set(TAGS) or set(NICHES) & RESERVED:
+    raise SystemExit("slug de GENRES/TAGS repetido ou reservado")
+TAGS_MAX = 3
@@
-BOOK_KEYS = {"id", "isbn", "genre", "title", "author", "image_url", "stores", "featured", "trending_rank",
-             "blurb"}
+BOOK_KEYS = {"id", "isbn", "genre", "tags", "title", "author", "image_url", "stores", "featured",
+             "trending_rank", "blurb"}
@@ def validate_offer(o, tag, aff):
+    tags = o.get("tags", [])
+    if (not isinstance(tags, list) or len(tags) > TAGS_MAX or len(set(map(str, tags))) != len(tags)
+            or any(not isinstance(t, str) or t not in TAGS for t in tags)):
+        raise Invalid(f"tags inválidas: {tags!r} (até {TAGS_MAX} de {sorted(TAGS)}, sem repetir)")
+    out["tags"] = tags
@@
+def in_niche(o, slug):
+    return o["genre"] == slug or slug in o["tags"]
+
 def nav(offers, current):
-    present = [g for g in GENRES if any(o["genre"] == g for o in offers)]
-    items = [("/", "Todos", current is None)] + [(f"/{g}/", GENRES[g], g == current) for g in present]
+    present = [g for g in NICHES if any(in_niche(o, g) for o in offers)]
+    items = [("/", "Todos", current is None)] + [(f"/{g}/", NICHES[g], g == current) for g in present]
@@ def page(all_offers, genre=None, bot=None, ch=()):
-    offers = [o for o in all_offers if genre is None or o["genre"] == genre]
+    offers = [o for o in all_offers if genre is None or in_niche(o, genre)]
     (e GENRES[genre] -> NICHES[genre] nas 3 linhas de título/descrição)
@@ def build(dev=False):
-    for g in {o["genre"] for o in offers}:
+    for g in {o["genre"] for o in offers} | {t for o in offers for t in o["tags"]}:
         pages[f"{g}/index.html"] = page(offers, g, bot, ch)
```

O `isinstance(t, str)` vem antes do `in TAGS`, porque uma lista dentro de `tags` levantaria `TypeError` no `in` do dict, em vez de `Invalid`. O selftest do build ganha 4 casos: tag válida, tag desconhecida, tag repetida e tag não texto. O `resolve` já repassa todos os campos do livro (`{**b, ...}`), então `tags` chega à página sem mudança.

### 10.2 O que cada API oficial entrega de fato hoje

Passo 0: `probe` só leitura com o token de app (`client_credentials`), rodando por `workflow_dispatch` com os Secrets (decisão 10). A primeira parte **já rodou** (`curator.py probe`, runs 39258219518 e 39259800320, registrados em `docs/produto/curator.md` §3.2):
- `/highlights/MLB/category/MLB437616`: **200**, 20 itens (16 `PRODUCT`, 4 `USER_PRODUCT`). Um deles era papelaria, não livro;
- `/highlights` com `attribute=BOOK_GENRE`: **400**;
- `/trends/MLB/MLB437616`: **200**, 50 termos;
- `/products/search?product_identifier=<ISBN>`: **200**;
- `/products/{id}`: traz `BOOK_GENRE`, `AUTHOR`, `BOOK_TITLE`, `LANGUAGE` etc., mas **nenhum `GTIN`, `ISBN` ou `EAN`**. Isso afeta o gate 7 (ver §10.3).

Falta conferir na entrega 2, como primeira tarefa: `/highlights/MLB/product/{id}`, `/reviews/item/{id}` num livro popular, `sold_quantity` em `/items/{id}` (deve vir ausente) e se `PUBLICATION_YEAR` vem preenchido. As células "o passo 0 confere" nas tabelas abaixo são isso.

Legenda de risco: **Proibido** viola termo ou regra do CLAUDE.md. **Arriscado** é permitido só com ressalva, ou o termo é ambíguo.

**Sinal 1. Promoção em relação ao histórico de preço**

| Fonte | O que entrega | Status |
|---|---|---|
| ML | `price` e `original_price` em `GET /products/{id}` (`buy_box_winner`) e em `GET /products/{id}/items` | **Fato, em produção:** o `collect.py` já usa ([Buscador de produtos](https://developers.mercadolivre.com.br/pt_br/buscador-de-produtos), atualizada em 29/12/2025) |
| ML | `amount`/`regular_amount` em `GET /items/{id}/sale_price?context=channel_marketplace` | **Fato:** dá 403 com token de app (run 39178554200, registrado no `collect.py`) |
| ML | Histórico de preço de anúncio de terceiro | **Não existe na doc pública.** O histórico é o nosso, gravado em `price_history/AAAA-MM.csv` a partir do `history_since` de cada livro (o primeiro é de 2026-10-18). Termos: o item 7.4 dos [Termos do Programa de Desenvolvedores](https://developers.mercadolivre.com.br/pt_br/termos-e-condicoes) proíbe armazenar conteúdo "para desenvolver serviços que concorram" com o ML. Guardar preço para mandar tráfego afiliado ao ML não é concorrência (**inferência**, risco baixo) |
| Amazon (Creators API) | `offersV2.listings.price`: `money`, `savings` (`money`, `percentage`), `savingBasis` (`money`, `savingBasisType`: `LIST_PRICE`, `LOWEST_PRICE`, `LOWEST_PRICE_STRIKETHROUGH`, `WAS_PRICE`), `availability.type`, `isBuyBoxWinner`, `dealDetails` (`badge`, `startTime`, `endTime`, só quando há promoção) | **Fato (doc):** [OffersV2](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/resources/offersV2). Só traz a oferta em destaque (buy box). **Indisponível para nós:** a Creators API exige 10 vendas qualificadas em 30 dias ([Introdução](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction)). Até lá o preço da Amazon é o fluxo semi-automático atual |
| Amazon | Histórico de preço | **Não existe na API. Arriscado:** a [Licença das Políticas do Programa](https://associados.amazon.com.br/help/operating/policies), cláusula 2(h), permite cache do conteúdo "por até 24 horas", com atualização obrigatória. A exceção explícita é só o ASIN. Guardar preço da Amazon por 90 dias para calcular `lowest_90d_cents` **pode violar essa cláusula**. A cláusula 2(i) exige carimbo de data/hora junto ao preço, o que o site já faz. **Risco aceito pelo Elias** (decisão 7, ver §10.5) |
| Amazon | Página de Mais Vendidos ou de produto | **Proibido:** é scraping (CLAUDE.md, regra 1; Licença, cláusula 1, "mineração de dados, robôs") |
| Google Trends | — | Não se aplica |

Consequência: até cada livro ter pelo menos 30 dias de snapshots nossos no ML, o sinal só pode usar `original_price`. É o rótulo da loja e vale pouco (§10.3). Na Amazon, o equivalente é o `savingBasis`, com a mesma ressalva.

**Sinal 2. Demanda (compras recentes, volume de vendas)**

| Fonte | O que entrega | Status |
|---|---|---|
| ML | `sold_quantity` de anúncio de terceiro | **Fato: indisponível.** No exemplo de `GET /items/{id}` da doc [Publicar produtos](https://developers.mercadolivre.com.br/pt-br/publicacao-de-produtos) (atualizada em 09/01/2026), o campo vem anotado com "Somente disponível com token proprietário". O mesmo vale para `start_time` e `historical_start_time`. Nosso token é de app, não do vendedor. O passo 0 só confirma. **Proibido** tentar obter o número pela página do anúncio (item 7.6 dos Termos) |
| ML | Top 20 mais vendidos da categoria: `GET /highlights/MLB/category/MLB437616` | **Fato (doc):** [Mais vendidos](https://developers.mercadolivre.com.br/pt_br/mais-vendidos-no-mercado-livre), atualizada em 22/06/2026. Mistura `PRODUCT`, `USER_PRODUCT` (MLBU) e `ITEM`. Exige categoria folha, e a `MLB437616` é folha. **Testado:** 200 com token de app (probe 39258219518) |
| ML | Top 20 por gênero: `…?attribute=BOOK_GENRE&attributeValue={id}` | **Fato:** dá **400** com `BOOK_GENRE` (probe 39258219518). Não existe top 20 por nicho |
| ML | Posição de um produto: `GET /highlights/MLB/product/{id}` | **Fato (mesma doc):** dá 404 quando o produto não está no top 20 de nenhuma dimensão. Isso é dado ausente, não zero |
| ML | Idade do livro: atributo `PUBLICATION_YEAR` | **Fato:** o atributo existe na categoria. Se ele vem preenchido nos produtos é **não confirmado**. Alternativa: `publish_date` da [Open Library](https://openlibrary.org/dev/docs/api/books), que respondeu "Oct 27, 2019" para `9788550807560` |
| Amazon (Creators API) | `browseNodeInfo.websiteSalesRank.salesRank` (posição geral) e `browseNodeInfo.browseNodes.salesRank` (posição no nó) | **Fato (doc):** [BrowseNodeInfo](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/resources/browse-node-info), com a ressalva de que "nem todo item tem sales rank". É o equivalente ao SalesRank da PA-API. Não há operação de "mais vendidos": as operações são `GetItems`, `SearchItems`, `GetBrowseNodes` e `GetVariations` ([Operations](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/operations)). **Indisponível para nós** até liberar. Vendas absolutas: não existe |
| Google Trends | — | Não é sinal de compra. Ver Sinal 4 |

Consequência: "compras recentes ajustadas à idade" (§2) **não é calculável** com API oficial hoje. A demanda vem da posição no `/highlights` do ML e, depois, do `salesRank` da Amazon. Os dois já são ritmo recente de vendas, então o ajuste pela idade passa a ser só um desempate (§10.3). As avaliações do ML trazem `reviews[].buying_date`, a data de compra de quem avaliou, que seria um terceiro indicador, mas depende do Sinal 3.

**Sinal 3. Avaliações e nota**

| Fonte | O que entrega | Status |
|---|---|---|
| ML | Total, média, distribuição e `buying_date`: `GET /reviews/item/{item_id}?catalog_product_id={MLB}` | **Fato (doc):** [Opiniões de Produtos](https://developers.mercadolivre.com.br/pt-br/opinioes-sobre-um-produto), atualizada em 18/08/2026. Traz `paging.total`, `rating_average` e `rating_levels`. O item precisa estar ativo. Use o `item_id` da buy box, que o coletor já tem |
| ML | Avaliação habilitada para livros? | **Fato:** `GET /categories/MLB437616` devolve `settings.items_reviews_allowed: false`. **Inferência:** livros podem não ter avaliação no ML, e o sinal ficaria sempre ausente. O passo 0 confere com um livro popular |
| Amazon (Creators API) | Avaliações | **Fato: não existe.** A lista oficial de recursos ([Resources](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/resources)) tem `BrowseNodeInfo`, `BrowseNodes`, `Images`, `ItemInfo`, `OffersV2`, `ParentASIN`, `SearchRefinements` e `VariationSummary`, e nenhum `CustomerReviews`. Um cliente de terceiros cita `customerReviews.count`; isso é **não confirmado** na doc oficial. **Proibido:** tirar as estrelas da página |
| Google Books | `averageRating`/`ratingsCount`: `GET https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}` | **Não confirmado:** a chamada anônima deu "Quota exceeded" (cota compartilhada). Precisa de chave própria (decisão 9, **pendente**). A amostra brasileira tende a ser pequena (**inferência**). Busca por título para descobrir o ISBN **não vale como casamento** (regra "não case por título") |

**Sinal 4. Interesse de busca (Google Trends)**

| Fonte | O que entrega | Status |
|---|---|---|
| Google Trends API (oficial) | Série de interesse por termo, região e sub-região, agregada por dia, semana, mês ou ano, numa janela móvel de 5 anos. A escala é consistente entre requisições (não é 0–100 por consulta), então dá para comparar o mesmo termo ao longo do tempo e juntar consultas | **Fato:** [Google Trends API](https://developers.google.com/search/apis/trends) continua **alpha**, com acesso por formulário e prioridade para quem tem caso de uso pronto ([anúncio de 24/07/2025](https://developers.google.com/search/blog/2025/07/trends-api)). Página consultada em 2026-10-19. **Não temos acesso.** O Elias decidiu pedir (decisão 8) |
| `pytrends` | — | **Fato:** o repositório [GeneralMills/pytrends](https://github.com/GeneralMills/pytrends) está arquivado (`archived: true` na API do GitHub). Não é oficial e raspa o site do Trends. **Arriscado/proibido:** fere os Termos do Google sobre acesso automatizado. Não usar |
| SerpApi, DataForSEO e similares | Revendem dados do Trends | **Arriscado:** raspam o Google por nós. Não usar |
| ML (substituto parcial) | `GET /trends/MLB/MLB437616`: até 50 `keyword`, com atualização semanal | **Fato (doc):** [Tendências](https://developers.mercadolivre.com.br/pt_br/tendencias), atualizada em 27/05/2025. Não traz número, só a palavra e uma URL de busca, e essa URL é HTML, que não seguimos. Serve como bônus binário ("título ou autor aparece nas tendências"). **Testado:** 200, 50 termos (probe 39258219518) |

**Resumo honesto:** hoje só o **preço do ML** está confirmado, e o nosso histórico ainda é curto. A **posição no `/highlights`** responde com token de app (probe), mas o filtro por gênero não. `sold_quantity` não vem. Avaliações de livro no ML provavelmente não vêm. Trends depende de um acesso alpha que não temos. Tudo o que é da Amazon depende da Creators API, e o histórico de preço da Amazon esbarra na regra de cache de 24 h.

### 10.3 Pontuação, limiar e modo sombra

**Componentes.** Cada componente `s_i` vai de 0 a 1 e é guardado com o valor bruto, a fonte, o `fetched_at` e a `confidence_i` (0 a 1). `clamp(x) = min(1, max(0, x))`.

| Componente | Peso `w_i` | Normalização |
|---|---:|---|
| Preço `s_p` | 35 | Com 30 dias ou mais de histórico nosso: `d = 1 − preço / mediana_90d`; `s_p = clamp(d / 0,30) + 0,2·[preço ≤ mínimo_90d]`, com teto em 1 e `confidence = 1`. Ou seja, 30% abaixo da mediana já dá nota cheia. Com menos de 30 dias: `s_p = min(0,3; clamp(desconto_rótulo / 0,30))`, em que `desconto_rótulo` vem de `original_price` (ML) ou `savings.percentage` com `savingBasisType ∈ {LIST_PRICE, WAS_PRICE}` (Amazon), e `confidence = 0,5`. Livro nas duas lojas: vale a loja de menor preço, como no build |
| Demanda `s_d` | 25 | ML: `s_ml = (21 − posição_highlights) / 20`, com `confidence = 0,6`. Amazon (quando liberar): `s_amz = clamp(1 − log10(websiteSalesRank) / 5)`, ou seja, rank 1 → 1 e rank ≥ 100.000 → 0, com `confidence = 0,7`. `s_d = max(s_ml, s_amz)`, e a confiança é a da fonte que deu o máximo. Bônus de +0,1 (teto 1) se título ou autor aparecer no `/trends` do ML. Desempate por idade: lançamento (≤ 1 ano pelo `PUBLICATION_YEAR`) ganha +0,05. Sem nenhuma fonte, o componente fica ausente |
| Avaliações `s_r` | 15 × `min(1; v / 50)` | `R̄ = (v·R + 20·4,0) / (v + 20)` (média bayesiana com prior de 4,0 e peso 20); `s_r = clamp((R̄ − 3,5) / 1,5)`. Com `v < 10`, ausente. Fonte: ML reviews ou Google Books (decisão 9, pendente). `confidence = 1`. **Correção de 2026-10-19:** antes o `min(1; v/50)` multiplicava o `s_r`, e um livro com 5 avaliações perdia até 13 pontos para um sem nenhuma. Agora ele reduz o peso: pouca avaliação pesa pouco, em vez de puxar a nota para baixo |
| Tendência `s_t` | 25 | Com acesso à Trends API: `s_t = clamp(média_4_semanas / média_12_semanas_anteriores − 1)`, em que +100% dá nota cheia. Termo: título + autor, região BR. `confidence = 0,8`. Sem acesso: ausente |

**Agregação.** Componente ausente não entra no cálculo e não conta como zero. `P` é o conjunto dos presentes:
- `score = 100 × Σ_{i∈P} w_i·s_i / Σ_{i∈P} w_i`
- `confiança = Σ_{i∈P} w_i·confidence_i / 100`. O divisor é 100 de propósito: a falta de componente baixa a confiança, mas não o score.

Exemplo de hoje: só preço curto (0,5) e `/highlights` (0,6) presentes dão confiança = (35·0,5 + 25·0,6)/100 = 0,325. Com 30 dias de histórico e `/highlights`: (35·1 + 25·0,6)/100 = 0,50.

**Limiar aprovado (decisão 5, 2026-10-19):** pesos 35/25/15/25, publicar com `score ≥ 70` e `confiança ≥ 0,5`. Retirar com `score < 60` por 2 execuções seguidas. A histerese evita que o livro entre e saia todo dia. Na prática, isso quer dizer que **nada publica antes de 30 dias de histórico no ML e sem estar no top 20**, que é exatamente o "sem histórico suficiente, não afirmar que é promoção" de §3. O Elias aceitou.

**Gates (complemento de §4).** Gate que falha bloqueia, seja qual for a pontuação:
- (6) gênero mapeado em §10.1;
- (7) preço conferido dentro do frescor da loja (ML 2 h, Amazon manual 12 h). Para livro com as **duas** lojas, o ISBN-13 do catálogo tem de ser confirmado pela API do ML: `/products/search?product_identifier=<ISBN>` precisa devolver o mesmo `ml_product_id`. É o substituto do "GTIN igual ao ISBN", já que a ficha não traz GTIN (probe 39259800320). Sem essa confirmação, o livro fica com uma loja só. Livro só no ML tem identidade pelo `ml_product_id` (`curator.md` §3.2). Nunca casamento por título;
- (8) no máximo **5** novos livros por dia e **2** por gênero (decisão 12). Tag não conta para o teto de gênero;
- (9) `id` novo, que não colide com nenhum `id` já usado, mesmo de livro retirado, porque vira deep link;
- (10) pelo menos uma loja com link de afiliado válido (§10.4 e §10.5). A regra é simétrica (decisão 13): sem link do ML, publica só com a Amazon; sem ASIN confirmado da Amazon, publica só com o ML; sem nenhum dos dois, não publica.

**Modo sombra.** O score é calculado e logado, mas **não muda nada no site**: não escreve no `catalog.json` nem no `offers.json`.
1. A execução diária grava uma linha JSON por candidato em `curation/AAAA-MM.jsonl`, só de acréscimo, no branch `price-history`, com retenção de 24 meses (decisão 11).
2. Cada linha tem: `run_at`, `ml_product_id`, `asin`, `isbn`, `genre` (e a fonte do gênero), `tags`, os componentes (`raw`, `s`, `confidence`, `source`, `fetched_at`), `score`, `confiança`, os `gates` (passou ou falhou, com o motivo) e `would_publish`. **Nada de dado de usuário.**
3. Toda segunda-feira sai um resumo no log do Actions: quantos candidatos teriam sido publicados por gênero, a distribuição dos scores, os 10 primeiros e os 10 logo abaixo do corte.
4. **Métricas contra a curadoria humana.** São duas réguas:
   - **Rótulo cego:** o Elias marca "publicaria ou não" numa amostra estratificada, sem ver o score: metade acima do corte, metade na faixa de 50 a 70. Com isso medimos a **precisão** (dos que o sistema publicaria, quantos ele aprovou) e o **recall** (dos que ele aprovou, quantos o sistema publicaria).
   - **Recall sobre o catálogo manual:** os livros já curados à mão (`data/offers.json`) que aparecem como candidatos e passam nos gates devem ter `would_publish = true`. Quem não tem, é investigado: ou o peso está errado, ou o livro só entrou por gosto pessoal.
   - Também medimos: volume por dia e por gênero, cobertura (quantos dos 11 gêneros têm ao menos 1 aprovado), estabilidade (quantos entrariam e sairiam em menos de 7 dias) e a taxa de "dado ausente" por componente.
5. **Duração:** no mínimo 30 dias corridos, que é o necessário para ter histórico de preço, e no mínimo 60 rótulos (30 acima e 30 abaixo do corte), com o passo 0 resolvido.
6. **Critério de saída**, todos juntos:
   - precisão ≥ 0,90 nos rótulos, ou seja, no máximo 3 erros em 30 "publicaria";
   - recall ≥ 0,60;
   - média ≥ 1 livro por dia que passaria em todos os gates, link incluído;
   - ≥ 6 gêneros com pelo menos 1 aprovado no período;
   - churn < 10% (entrou e saiu em menos de 7 dias);
   - nenhum componente decide sozinho mais de 70% dos `would_publish`;
   - os pesos e o limiar finais registrados aqui, com data e o "aprovado" do Elias.

   Só então a publicação é ligada. Se a precisão não chegar a 0,90, sobe o limiar em passos de 5 e mede de novo; se o recall cair abaixo de 0,60 com isso, revemos os pesos.
7. **Orçamento de chamadas:** 1 `/highlights` geral (o filtro por gênero dá 400), mais `/products/{id}` só dos `PRODUCT` novos, mais `/reviews` só de quem passou nos gates. O job é separado do coletor, porque o coletor tem prazo de 40 s (`ML_DEADLINE_S`). Os limites de taxa do ML para token de app são **não confirmados**.

### 10.4 Links do ML em lote (enquanto não houver método autorizado)

**Situação verificada em 2026-10-19:** não há API oficial documentada para gerar link de afiliado do ML. No portal de desenvolvedores, nada sobre afiliados. As páginas oficiais do programa ([gere seus links](https://www.mercadolivre.com.br/l/afiliados-gere-seus-links), [direcionamento de visitas](https://www.mercadolivre.com.br/l/afiliados-direcionamento-de-visitas)) só renderizam com JS e indicam o Gerador de links e a barra/extensão do portal. Fontes de terceiros de 2026 dizem o mesmo: [DivulgaNinja](https://www.divulganinja.com.br/blog/como-gerar-link-afiliado-mercado-livre-passo-a-passo-2026) descreve o Gerador de links do portal, e um dev no [TabNews](https://www.tabnews.com.br/marcuth/criei-uma-cli-para-gerar-links-de-afiliados-de-marketplaces) diz que o ML não tem API pública e que a ferramenta dele usa cookies. **Proibido** para nós: cookies, sessão, navegador automatizado e endpoint privado. O Busqy de §6 continua não confirmado contratualmente.

O que muda o desenho: o link do painel é `https://www.mercadolivre.com.br/social/<aff>?matt_word=<aff>&matt_tool=…&forceInApp=true&ref=<cifrado>` e **não contém o id do produto** (ver `collector/catalog.json`). O script não tem como descobrir sozinho a que produto um link pertence. Abrir o link para seguir o redirecionamento não é uma saída, por três motivos:
- seria acessar o site, não a API, o que o item 7.6 dos [Termos do Programa de Desenvolvedores](https://developers.mercadolivre.com.br/pt_br/termos-e-condicoes) proíbe;
- contaria um clique falso;
- o build não quer depender disso.

Por isso o par produto ↔ link é feito pelo Elias, linha a linha, num arquivo com chave.

**Arquivo:** `collector/ml_links.tsv`, local, fora do git (entra no `.gitignore`). Não tem segredo, porque o `ml_url` já é público no `catalog.json`, mas é transitório. Formato: UTF-8, separado por TAB, com cabeçalho fixo e uma linha por livro.

```
book_id	ml_product_id	title	product_url	ml_url
irmao-do-jorel	MLB19446507	Irmão do Jorel (capa dura)	https://www.mercadolivre.com.br/p/MLB19446507	
```

1. **Fila.** `curator links-todo` reescreve o arquivo com uma linha por candidato que passou em todos os gates, menos o do link, mais os livros do catálogo sem `ml_url`. Linhas já preenchidas e ainda não aplicadas são preservadas. A `product_url` é montada pelo código como `https://www.mercadolivre.com.br/p/<MLB>`, validado por `MLB_RE`, e nunca vem de texto da API. O `title` serve só para conferência visual e é limpo de TAB e quebra de linha.
2. **Painel (manual).** O Elias cola as `product_url` no Gerador de links. Terceiros dizem que o gerador aceita várias URLs de uma vez; isso é **não confirmado** na doc oficial. Ele cola cada link gerado na coluna `ml_url` da **mesma linha**. O par é feito pelo `book_id` da linha, nunca pela ordem entre arquivos. Só o link completo `/social/...`; **nunca `meli.la`**.
3. **Aplicação.** `curator links-apply collector/ml_links.tsv` confere cada linha, uma a uma:
   - cabeçalho exato e 5 colunas, nada a mais;
   - o `book_id` e o `ml_product_id` existem entre os candidatos ou no catálogo e conferem um com o outro;
   - `affiliate_url({"store": "mercadolivre", "ml_url": raw}, tag, ml_affiliate())` passa, o que roda o `ml_url` e o `check_url` do `build.py` sem afrouxar nada: só o link completo `https://www.mercadolivre.com.br/social/<ML_AFFILIATE_ID>`, `matt_word` igual a `ML_AFFILIATE_ID`, chaves em allowlist e sem repetição, sem `meli.la`, só ASCII imprimível, até 1000 caracteres, host em allowlist;
   - o `ref` não se repete no arquivo nem no catálogo, porque `ref` duplicado indica colagem errada;
   - o livro ainda não tem `ml_url`, a não ser com `--replace`.

   A linha válida grava o `ml_url` no `catalog.json` e sai do arquivo. A linha inválida é listada com o motivo, não grava nada e fica no arquivo para correção. A linha vazia continua pendente. Depois, o `build.py` valida de novo todo `ml_url` em cada build: é a segunda barreira. O pytest cobre: link válido, `meli.la`, `matt_word` de outra conta, chave fora da allowlist, `ref` duplicado, produto desconhecido e `book_id` que não bate com o `ml_product_id`.
4. **Item sem link:** fica na fila e não publica pelo ML (gate 10). Se o livro também tem a Amazon com ASIN confirmado e preço fresco, publica só com a Amazon (decisão 13). Um candidato pendente há mais de 14 dias sai da fila e volta se ainda for candidato na próxima descoberta. Isso evita fila infinita de livro que já não está em promoção.
5. **Limite conhecido.** Nenhuma validação prova que o `ref` aponta para aquele produto. Isso depende do Elias colar na linha certa. A mitigação barata: a `product_url` e o `title` ficam ao lado do link, e o resumo do `links-apply` mostra título ↔ produto para ele bater o olho. O Elias aceitou esse limite (decisão 12).
   - **Conflito com o agent `affiliate-linker`** (`.claude/agents/affiliate-linker.md`, commit c4e6d54): ele faz GET em cada link do painel e casa pelo `og:title`. Isso é acessar o site do ML (item 7.6), conta clique e casa por título. O fluxo aprovado aqui é o par por linha, sem request. Quem decide o ajuste do agent é o Elias; não editei o agent.
6. **Volume:** como a Amazon também é semi-automática hoje, **nenhum livro novo sai sem esse passo**. Com o teto do gate 8 (5 por dia), são no máximo 5 links do ML e 5 da Amazon por dia.

### 10.5 Amazon em fluxo manual até a Creators API (decisão 14)

Espelha o §10.4. Vale até a Creators API ser liberada (10 vendas qualificadas em 30 dias). Depois, `GetItems` traz ASIN, ISBN (`itemInfo.externalIds`), preço e ranking, e este fluxo sai.

**Regra inegociável:** o código **não faz nenhuma request** para domínio da Amazon. Nada de fetch de página, busca, Mais Vendidos, SiteStripe ou link encurtado, nem para "só conferir". As URLs da Amazon abaixo são texto montado pelo código, para o Elias abrir no navegador dele. É o mesmo princípio do "ASIN provável" de `curator.md` §3.1.

**Por que o Elias gera o link no SiteStripe se o link da Amazon é determinístico.** O `build.py` monta `https://www.amazon.com.br/dp/<ASIN>?tag=<tag>`, com a tag por canal (`AMAZON_TAG_TG`/`_WA`), e valida com `affiliate_url` + `check_url`. O que falta é o **ASIN certo**, que sem a API só um humano confirma. O link do SiteStripe serve de comprovante: prova que o Elias estava na página daquele ASIN, logado na conta de associado com a nossa tag. **Só o ASIN é guardado**; a URL colada é descartada depois de validada.

**Arquivo:** `collector/amazon_links.tsv`, local, fora do git (entra no `.gitignore`). Formato: UTF-8, TAB, cabeçalho fixo, uma linha por livro.

```
book_id	isbn	ml_product_id	title	asin_provavel	product_url	isbn_confirmado	amazon_url
verity	9788584391509	MLB...	Verity	8584391509	https://www.amazon.com.br/dp/8584391509		
```

(Linha ilustrativa: o ISBN e o ASIN do exemplo não foram conferidos.)

1. **Fila.** `curator amazon-todo` escreve uma linha por candidato que passou nos gates (menos o do link) e ainda não tem `asin`, até o teto do gate 8.
   - `asin_provavel`: ISBN-10 calculado do ISBN-13 (só prefixo 978; é o `asin_provavel()` que já existe no `curator.py`). Sem ISBN ou com prefixo 979, fica `-`.
   - `product_url`: `https://www.amazon.com.br/dp/<asin_provavel>`. Sem ASIN provável, é `https://www.amazon.com.br/s?k=<ISBN-13>`; sem ISBN, `https://www.amazon.com.br/s?k=<título autor>`, com URL-encoding. Todas são montadas pelo código e **nunca chamadas**.
2. **Navegador (manual).** O Elias abre a `product_url` e confere se é a mesma edição física (capa dura × brochura, box, idioma; Kindle não). Ele preenche:
   - `isbn_confirmado`: o ISBN-13 que a página mostra;
   - `amazon_url`: o link de **texto completo** do SiteStripe (`https://www.amazon.com.br/.../dp/<ASIN>?...&tag=<tag>...`). **Nunca** `amzn.to`: o encurtador só se confere seguindo o redirect, que é request à Amazon.

   Na mesma conferência ele lança o primeiro preço no `collector/amazon_prices.csv`, que é o fluxo de preço que já existe (abaixo).
3. **Aplicação.** `curator amazon-apply collector/amazon_links.tsv` confere cada linha, sem rede:
   - cabeçalho exato e 8 colunas; `book_id` existe e confere com o `ml_product_id`;
   - `amazon_url`: só ASCII imprimível, até 1000 caracteres, `https`, host `www.amazon.com.br` ou `amazon.com.br` (a allowlist do `check_url`), sem usuário, porta ou fragmento;
   - ASIN extraído do caminho, que tem de ser `/dp/<ASIN>`, `/<slug>/dp/<ASIN>` ou `/gp/product/<ASIN>`, e o ASIN passa no `ASIN_RE`;
   - `tag` aparece **uma vez** na query e é igual a `AMAZON_PARTNER_TAG`. Tag de outra conta, tag de canal ou tag ausente: linha recusada. Isso garante que o Elias gerou o link logado na nossa conta;
   - `isbn_confirmado` é ISBN-13 válido (`isbn_ok`) e igual ao `isbn` do catálogo, quando o catálogo já tem ISBN. Quando não tem, ele vira o ISBN do livro, desde que `/products/search?product_identifier=<isbn>` (API do ML, a única request do passo) devolva o mesmo `ml_product_id`. Senão, o livro fica só com o ML (gate 7);
   - ASIN igual ao `asin_provavel` → `amazon_match: "isbn10"`. ASIN diferente (por exemplo, começando com `B0`, comum em Kindle) → só com `--confirm-asin <book_id>`, e o log grava `amazon_match: "manual"`. A conferência ISBN × ASIN fica para o `GetItems` da Creators API;
   - ASIN que ainda não está no catálogo;
   - por fim, o link que o build vai gerar, `affiliate_url({"store": "amazon", "asin": asin}, partner_tag(), ml_affiliate())`, passa no `check_url`. É o teste exigido para todo link antes de entrar no catálogo.

   Linha válida grava `asin` (e `isbn`, se faltava) no `catalog.json` e sai do arquivo. Linha inválida fica no arquivo com o motivo. O pytest cobre: link válido; `amzn.to`; tag de outra conta; tag repetida; host fora da allowlist; caminho sem `/dp/`; ASIN divergente sem `--confirm-asin`; ISBN que não bate; e o fato de nenhuma URL chamada ter host da Amazon (o `urlopen` é trocado no teste, como no critério 1 de `curator.md` §11).
4. **Sem link:** o livro publica só com o ML, se o ML tiver link (decisão 13). Pendente há mais de 14 dias sai da fila, como no §10.4.

**Preço da Amazon neste período: só entrada manual.** É o fluxo que já existe no `collect.py`:
- o Elias digita `asin,price_cents,list_price_cents,checked_at` em `collector/amazon_prices.csv`, a partir do que vê na página no navegador dele;
- a ordem de conferência sai em `amazon_queue.csv`;
- o coletor grava com `source=manual` e não faz request nenhuma.

Não há outra fonte. Sem linha nova, não há preço.

- **Frescor:** continua **12 h** (`FRESH["amazon"]` no `build.py`, alinhado com `distribuicao-canais.md`). Com conferência de manhã, cobre o dia. Baixar para 2 h, como no ML, exigiria conferir 6 vezes por dia, e manual não sustenta isso. Subir para 24 h passaria do limite dos posts dos canais. Sem preço fresco, a Amazon sai da comparação e o livro segue pelo ML.
- **Retirada:** as 6 h sem preço válido contam por livro: ele sai quando **nenhuma** loja está fresca há 6 h. Um livro só na Amazon, portanto, sai 18 h depois da última conferência manual (12 h de frescor + 6 h). A outra regra de retirada (2 execuções com `score < 60`) não muda.
- **"Menor preço em 90 dias" do lado da Amazon** depende inteiramente dessa digitação. Com amostras esparsas, o mínimo que guardamos é **maior ou igual** ao mínimo real, porque perdemos os dias de queda. O risco é o selo afirmar "menor preço em 90 dias" sem ser. Proposta, a decidir pelo `product-manager` e pelo `collector-engineer`: o selo só considera a série da Amazon com amostra em pelo menos 80% dos dias da janela. Senão, o selo usa só o ML ou não aparece. O mesmo vale para o componente Preço da pontuação.
- **Pontuação:** a Amazon manual não traz demanda nem avaliação. O score do livro vem dos sinais do ML; a Amazon só soma a loja e o preço. Um livro que só existe na Amazon não entra pela descoberta automática neste período.

### 10.6 Decisões tomadas (2026-10-19)

Respostas do Elias às 14 decisões, registradas no fim do dia. **Substituem** o registro anterior do mesmo dia (antigo §10.6, commit 5056577) onde houver diferença; as diferenças estão listadas no fim.

1. **Publicação automática com gates**, com o modo sombra como período de prova. A versão "PR com aprovação humana" do branch `worktree-agent-a26264a6033900af8` foi descartada.
2. **Os 11 gêneros** de §10.1, como propostos (com `didaticos` e `tecnicos` separados).
3. **LGBTQIA+ vira nicho próprio, como tag.** O livro passa a ter `genre` (um, de `GENRES`) e `tags` (lista, de `TAGS`), e cada tag gera página. Modelo e diff em §10.1.1. Os outros mapeamentos ambíguos ficam como na tabela de §10.1.
4. **Livros já publicados mantêm o gênero manual.** Recebem `tags: []` e, onde couber, a tag à mão (nenhum caso identificado hoje).
5. **Pesos 35/25/15/25, `score ≥ 70`, `confiança ≥ 0,5`**, retirada abaixo de 60 por 2 execuções. Aceito que nada publica antes de 30 dias de histórico.
6. **Critério de saída da sombra** de §10.3, item 6, aceito como está.
7. **O Elias aceita o risco e guarda o histórico de preço da Amazon.**
   - **Risco, registrado de forma explícita:** a Licença das [Políticas do Programa de Associados](https://associados.amazon.com.br/help/operating/policies), cláusula 2(h), só permite guardar o conteúdo dos produtos "por até 24 horas", com a exceção explícita do ASIN. A série de 90 dias que dá o `lowest_90d_cents` e o selo "menor preço em 90 dias" pode ser lida como violação. A consequência possível é o encerramento da conta de associado, com perda de comissões. **Não conferi** a cláusula exata de encerramento do Contrato Operacional; trate isso como possível, não como confirmado. Isso valeria também para a futura Creators API, que depende da mesma conta.
   - Hoje o preço da Amazon é digitado à mão pelo Elias (§10.5). Se isso conta como "Conteúdo de Anúncio de Produtos" é **não confirmado**; o risco vale do mesmo jeito.
   - **Mitigações:** guardar só `asin`, `price_cents`, `list_price_cents` e `checked_at` (nada de título, imagem ou texto da Amazon); manter a série separada por loja, para poder apagar só a da Amazon com um comando se a resposta for negativa.
   - **Ação paralela:** perguntar por escrito ao suporte dos Associados se guardar a série de preços para exibir "menor preço em 90 dias" é permitido. Registrar a resposta aqui. Se for negativa, apagar a série da Amazon e o selo passa a usar só o ML.
8. **Pedir acesso à Google Trends API (alpha).** Enquanto não sai, o componente Tendência fica ausente e a agregação o ignora. Nunca `pytrends` nem revendedores.
9. **PENDENTE: Google Books.** Para que serve: é a única fonte provável do sinal de Avaliações, já que livro no ML vem com `items_reviews_allowed: false` e a Creators API não tem reviews. Também completa categoria e metadados **a partir de um ISBN já conhecido**. Completar o ISBN buscando por título não vale como casamento (regra "não case por título"). As duas opções:
   - **(a) Chave própria em GitHub Secrets** (cota gratuita; sem chave, a cota anônima é 0). O componente Avaliações entra com peso `15·min(1; v/50)`. Quando há pelo menos 10 avaliações, o score muda em `Δ = w_r/(W + w_r) × (100·s_r − S₀)`, em que `S₀` é o score sem avaliações e `W` a soma dos outros pesos presentes. Hoje (preço + demanda, sem Trends), `W = 60`. Com `v ≥ 50` (`w_r = 15`), o fator é 0,2. Exemplos com `S₀ = 75`: média 4,0 com 50 avaliações (`R̄ = 4,0`, `s_r = 0,33`) cai para **67** e deixa de publicar; média 4,7 com 50 (`R̄ = 4,5`, `s_r = 0,67`) fica em **73**; média 4,9 com 200 (`R̄ = 4,82`, `s_r = 0,88`) sobe para **78**. Como a média bayesiana encolhe para 4,0, as avaliações tendem a puxar para baixo livros de score alto e só ajudam com nota muito boa e muitas avaliações. Com `v = 20` (`w_r = 6`), o fator é 0,09, e o efeito fica em ±4 pontos. A confiança sobe até +0,15: com 30 dias de histórico e top 20, vai de 0,50 para até 0,65.
   - **(b) Tirar Avaliações da fórmula** e redistribuir os 15 pontos em proporção: 35/25/25 vira **41,2/29,4/29,4**. O **score não muda** em relação a hoje, porque a agregação já ignora o componente ausente, e hoje ele está sempre ausente. O que muda é a **confiança**, que com os mesmos dados sobe: preço curto + top 20 vai de 0,325 para 0,38, e 30 dias + top 20 vai de 0,50 para 0,59. Na prática, isso afrouxa o limiar de 0,5. Se escolher (b), recomendo subir a confiança mínima para 0,59, para manter o mesmo rigor.
   - Sem decisão, vale (b) sem redistribuir: Avaliações ausente, pesos e limiar como no item 5.
10. **Passo 0** (`probe` só leitura com o token de app, por `workflow_dispatch` com os Secrets e nada ecoado no log) é a primeira tarefa da entrega 2. Parte dele já rodou (§10.2); falta o resto da lista de §10.2.
11. **Log da sombra e da auditoria** em `curation/AAAA-MM.jsonl` no branch `price-history`, com retenção de **24 meses**.
12. **Fluxo de links por linha** de §10.4 aceito, com no máximo **5 livros novos por dia** e **2 por gênero** (gate 8).
13. **Regra simétrica:** livro sem link do ML publica só com a Amazon; livro sem ASIN confirmado da Amazon publica só com o ML (gate 10).
14. **Não usar o Busqy por enquanto.** A Amazon fica em fluxo **manual** até a Creators API (§10.5): o curador traz os candidatos com o link do produto na Amazon (ASIN provável e ISBN), o Elias confere, gera o link no SiteStripe e devolve, e a curadoria segue. O preço da Amazon nesse período é só o digitado em `amazon_prices.csv`. Frescor do ML: 2 h. Frescor da Amazon manual: 12 h. Retirada após 2 execuções com `score < 60` ou 6 h sem nenhuma loja fresca.

**O que mudou em relação ao registro anterior (antigo §10.6, commit 5056577):**
- gêneros: de 10 (com `estudo`) para 11 (`didaticos` e `tecnicos`), mais a tag `lgbtqia`. Antes, LGBTQ+ ia para `ficcao`;
- volume: de "pelo menos 50 livros por dia, até 10 por gênero" para **no máximo 5 por dia e 2 por gênero**;
- Google Books: de "criar a chave" para **pendente**;
- retenção do log: de 12 para **24 meses**;
- Amazon: antes, o Elias achava o livro na Amazon por conta própria e o livro dele dispensava o score. Agora o curador traz os candidatos, o Elias devolve o link do SiteStripe, e o score vale para todos;
- histórico da Amazon: antes não estava decidido; agora **risco aceito**, com a pergunta por escrito em paralelo.

**Pendências novas, para o Elias ou para o agent indicado:**
- decisão 9 (Google Books);
- regra de cobertura de 80% para o selo de 90 dias da Amazon (§10.5) → `product-manager` e `collector-engineer`;
- campo `tags` no contrato v2 e no `load_catalog` → `product-manager` e `collector-engineer`; diff do `build.py` → `frontend-developer`;
- gate 7 reescrito, porque a ficha do ML não traz GTIN (§10.3) → confirmar com o Elias;
- conciliar `docs/produto/curator.md` (aprovada: 10 por semana, 4 por nicho, sem `autoajuda`, só 5 gêneros) e o agent `affiliate-linker` (GET + `og:title`) com as decisões acima → `product-manager`.
