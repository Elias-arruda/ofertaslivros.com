# Spec em rascunho: curadoria automática de livros

Status: **fonte da verdade da curadoria** (política, gates, pontuação, sombra, volume e lote de links). §1–9 são o handoff do Codex (2026-10-18); §10 fecha a spec (catalog-curator, 2026-10-19) e substitui §3, §7 e §8 onde houver conflito. Ordem de precedência: §10.7 > §10.6 > §10.5 > o resto.
Implementação liberada pela §10.7: publicação pelos gates de validade desde o dia 1, com o score em modo sombra (só nota). `curator.md` continua como spec técnica do `collector/curator.py` (fontes, filtros e resultados dos probes, §3.2 e §8), parcialmente substituída por esta.

## 1. Objetivo confirmado

Criar um agente que, diariamente, descubra livros e ofertas, avalie o potencial de curadoria e publique automaticamente no site os livros aprovados pelas regras. Ao longo do dia, o sistema também deve acompanhar mudanças de preço nas ofertas publicadas e atualizar ou retirar ofertas desatualizadas.

Elias confirmou que o agente pode publicar sem aprovação humana por livro, desde que passe pelas regras automáticas.

## 2. Sinais de avaliação pedidos por Elias

- Preço em promoção em relação ao histórico real de preço.
- Número de compras recentes, considerando o período desde a publicação do livro.
- Número de avaliações.
- Interesse de busca do livro no Google Trends.

## 3. Proposta inicial de pontuação (ainda não aprovada; detalhada em §10.3)

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

## 8. Próximas decisões para Claude/Elias (consolidadas e numeradas em §10.5)

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

Convenção: **Fato** tem fonte com data; **Inferência** é dedução minha, a confirmar; **Não confirmado** é o que tentei e não consegui verificar. Consultas feitas em 2026-10-18 e 2026-10-19. As rotas `/categories` do ML responderam sem token. Todas as outras rotas do ML citadas abaixo deram 401 ou 403 sem token. Não havia `ML_CLIENT_ID` nesta sessão, então **nenhuma delas foi testada com o token de app** aqui. **Atualização:** o passo 0 já rodou em Actions (probes 39258219518 e 39259800320); os resultados estão em `curator.md` §3.2 e valem sobre os "não testado" abaixo.

Existe outra versão desta spec no branch `worktree-agent-a26264a6033900af8` (commit `22548f4`, product-manager). Ela chega aos mesmos fatos sobre a API, mas propõe "PR com aprovação humana" em vez de publicação automática. Esta seção segue a decisão do Elias de 2026-10-18 (publicação automática com gates). Qual versão vale está na decisão 1 de §10.5.

**Correção de §7 e §3:** `sold_quantity` de anúncio de terceiro **não** está disponível para nós (§10.2, Sinal 2). O componente "compras recentes" de §3 deixa de ser calculável pelo ML e passa a ser "Demanda", medida pelo ranking.

### 10.1 Gêneros: cobrir todas as áreas

**Fato:** a categoria de livro físico do ML é `MLB437616` ("Livros Físicos", filha de `MLB1196`). Ela é **folha**, sem subcategorias, e tem `catalog_domain: MLB-BOOKS` (`GET https://api.mercadolibre.com/categories/MLB437616`). Por isso não dá para descobrir livros por nicho usando subcategorias.

**Fato:** o gênero vem como atributo. `GET /categories/MLB437616/attributes` traz `BOOK_GENRE`, uma lista fechada de 25 valores, e `BOOK_SUBGENRES`, com 208 valores, `hidden` e multivalorado. Traz também `PUBLICATION_YEAR` e `GTIN` (rótulo "ISBN").

**Aprovado (§10.7, decisão 6): 10 nichos.** Os 5 slugs atuais continuam iguais, porque já são URLs públicas. Entram mais 5. Didáticos e técnicos viram um só, `estudo`. Todo mapeamento sai de valores reais do `BOOK_GENRE` (lista de `/categories/MLB437616/attributes`); nenhum slug é inventado.

| Slug | Rótulo | URL do nicho | Valores `BOOK_GENRE` do ML (id) |
|---|---|---|---|
| `literatura-brasileira` | Literatura brasileira | `/literatura-brasileira/` | Nenhum. O ML não tem esse valor, nem em `BOOK_SUBGENRES`, onde procurei "brasil" e "nacional". Entra à mão ou, quando a Creators API for liberada, por browse node (abaixo) |
| `ficcao` | Ficção | `/ficcao/` | Literatura (7538039), Humor (25743212), LGBTQ+ (76624760) |
| `nao-ficcao` | Não ficção | `/nao-ficcao/` | História (13464376), Biografias (13611960), Ciência (76624759) |
| `negocios` | Negócios e finanças | `/negocios/` | Negócios (13061825) |
| `manga` | Mangá e HQ | `/manga/` | Mangas e HQs (13061816) |
| `autoajuda` **novo** | Autoajuda | `/autoajuda/` | Autoajuda (7538148) |
| `infantojuvenil` **novo** | Infantil e juvenil | `/infantojuvenil/` | Infantil (7538151), Juvenil (13061823) |
| `religiao` **novo** | Religião e espiritualidade | `/religiao/` | Religião (19912211), Esoterismo (7538147) |
| `estudo` **novo** | Estudo, técnicos e concursos | `/estudo/` | Escola e educação (23663384), Dicionários, enciclopédias e consulta (7538149), Acadêmico (13061813), Tecnologia (14885398) |
| `estilo-de-vida` **novo** | Saúde, hobbies e estilo de vida | `/estilo-de-vida/` | Saúde (13061828), Esportes (16188909), Gastronomia (13061821), Artesanato (13061814), Pets (76624758), Viagem (14973077), Arte e design (7538158), Música (13485350) |

Os 25 valores estão cobertos, e cada um vai para um slug só. Os mapeamentos ambíguos foram decididos pelo Elias (§10.6 e §10.7): Humor e LGBTQ+ em `ficcao`, Esoterismo em `religiao`, Tecnologia em `estudo`, Saúde em `estilo-de-vida` e Autoajuda em `autoajuda`. Produto sem `BOOK_GENRE` não é publicado, porque o build exige `genre` (gate 6 em §10.3). Ele fica no log da sombra como "sem gênero".

**Mudança proposta no `build.py`.** Não editei o arquivo: a decisão é do Elias, pelo `product-manager`. O `collect.py` importa `GENRES` do `build.py`, então a mudança vale para os dois.

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
+    "estudo": "Estudo, técnicos e concursos",
+    "estilo-de-vida": "Saúde, hobbies e estilo de vida",
 }
```

A ordem do dict é a ordem do menu (`nav`), e o menu só mostra gênero com oferta. Gênero vazio não gera link quebrado no menu, mas cada slug vira diretório em `dist/`. Os slugs passam no `ID_RE`. O mapa `BOOK_GENRE id → slug` fica no curador, não no `build.py`.

**Migração do que já existe.** Nenhum slug muda de nome e nenhum `id` muda, então `/r/<id>` e os deep links do Telegram continuam valendo. Em 2026-10-18 havia 2 livros em `collector/catalog.json`; em 2026-10-19 são 10 (`ficcao` 6, `negocios` 1, `manga` 1, `nao-ficcao` 2), 8 deles trazidos pelo curator. Em `data/offers.json` havia 10 (`ficcao` 2, `literatura-brasileira` 4, `manga` 2, `nao-ficcao` 1, `negocios` 2). A regra proposta é esta:
- O curador **não reclassifica** livro já publicado. O gênero manual prevalece.
- Na primeira execução da sombra, ele compara o gênero manual com o mapeado pelo `BOOK_GENRE` e registra as divergências. Candidatas prováveis (**inferência**): "Irmão do Jorel" (`ficcao`, mas talvez `infantojuvenil` no ML) e "Hábitos Atômicos" (`negocios`, mas talvez `autoajuda`). O Elias decide caso a caso (decisão 4). Mudar o gênero só move o livro de página de nicho; o link continua o mesmo.

**Mapeamento a partir das APIs:**
- **ML (viável hoje):** `BOOK_GENRE` do produto (`GET /products/{id}`, em `attributes`) → tabela acima. É determinístico e não usa título. Se o produto vier sem o atributo, o livro fica sem gênero e não publica.
- **Amazon (viável quando a Creators API for liberada):** `browseNodeInfo.browseNodes` + `.ancestor` devolvem `id`, `displayName` e `contextFreeName` de cada nó e a escada até a raiz ([BrowseNodeInfo](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/resources/browse-node-info)). O mapa seria `id do nó filho da raiz "Livros"` → slug. Os ids dos nós da amazon.com.br são **não confirmados**: só dá para levantá-los com a API liberada, via `GetBrowseNodes`. Se existir um nó "Literatura brasileira" (**não confirmado**), ele é o único caminho automático para esse slug.
- **Conflito entre lojas:** vale o `BOOK_GENRE` do ML. A exceção é `literatura-brasileira` vindo da Amazon, que é mais específico e prevalece sobre `ficcao`. A divergência fica registrada no log.

### 10.2 O que cada API oficial entrega de fato hoje

Passo 0: rodar um `probe`, só leitura, com o token de app (`client_credentials`, o mesmo do `collect.py`). **Já rodou** (probes 39258219518 e 39259800320; resultado em `curator.md` §3.2, sem cópia aqui). Em resumo, o que muda nas tabelas abaixo: `/highlights` geral dá 200 (20 itens, 16 `PRODUCT`); `/highlights?attribute=BOOK_GENRE` dá **400** e não é usado; `/trends` dá 200 (50 termos); `/products/search?product_identifier=<ISBN>` dá 200; e o `/products/{id}` **não traz** atributo `GTIN`, `ISBN` nem `EAN`. Reputação do vendedor e `/reviews` continuam não testados.

Legenda de risco: **Proibido** viola termo ou regra do CLAUDE.md. **Arriscado** é permitido só com ressalva, ou o termo é ambíguo.

**Sinal 1. Promoção em relação ao histórico de preço**

| Fonte | O que entrega | Status |
|---|---|---|
| ML | `price` e `original_price` em `GET /products/{id}` (`buy_box_winner`) e em `GET /products/{id}/items` | **Fato, em produção:** o `collect.py` já usa ([Buscador de produtos](https://developers.mercadolivre.com.br/pt_br/buscador-de-produtos), atualizada em 29/12/2025) |
| ML | `amount`/`regular_amount` em `GET /items/{id}/sale_price?context=channel_marketplace` | **Fato:** dá 403 com token de app (run 39178554200, registrado no `collect.py`) |
| ML | Histórico de preço de anúncio de terceiro | **Não existe na doc pública.** O histórico é o nosso, gravado em `price_history/AAAA-MM.csv` a partir do `history_since` de cada livro (o primeiro é de 2026-10-18). Termos: o item 7.4 dos [Termos do Programa de Desenvolvedores](https://developers.mercadolivre.com.br/pt_br/termos-e-condicoes) proíbe armazenar conteúdo "para desenvolver serviços que concorram" com o ML. Guardar preço para mandar tráfego afiliado ao ML não é concorrência (**inferência**, risco baixo) |
| Amazon (Creators API) | `offersV2.listings.price`: `money`, `savings` (`money`, `percentage`), `savingBasis` (`money`, `savingBasisType`: `LIST_PRICE`, `LOWEST_PRICE`, `LOWEST_PRICE_STRIKETHROUGH`, `WAS_PRICE`), `availability.type`, `isBuyBoxWinner`, `dealDetails` (`badge`, `startTime`, `endTime`, só quando há promoção) | **Fato (doc):** [OffersV2](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/resources/offersV2). Só traz a oferta em destaque (buy box). **Indisponível para nós:** a Creators API exige 10 vendas qualificadas em 30 dias ([Introdução](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction)). Até lá o preço da Amazon é o fluxo semi-automático atual |
| Amazon | Histórico de preço | **Não existe na API. Arriscado:** a [Licença das Políticas do Programa](https://associados.amazon.com.br/help/operating/policies), cláusula 2(h), permite cache do conteúdo "por até 24 horas", com atualização obrigatória. A exceção explícita é só o ASIN. Guardar preço da Amazon por 90 dias para calcular `lowest_90d_cents` **pode violar essa cláusula**. A cláusula 2(i) exige carimbo de data/hora junto ao preço, o que o site já faz. Ver decisão 7 |
| Amazon | Página de Mais Vendidos ou de produto | **Proibido:** é scraping (CLAUDE.md, regra 1; Licença, cláusula 1, "mineração de dados, robôs") |
| Google Trends | — | Não se aplica |

Consequência: até cada livro ter pelo menos 30 dias de snapshots nossos no ML, o sinal só pode usar `original_price`. É o rótulo da loja e vale pouco (§10.3). Na Amazon, o equivalente é o `savingBasis`, com a mesma ressalva.

**Sinal 2. Demanda (compras recentes, volume de vendas)**

| Fonte | O que entrega | Status |
|---|---|---|
| ML | `sold_quantity` de anúncio de terceiro | **Fato: indisponível.** No exemplo de `GET /items/{id}` da doc [Publicar produtos](https://developers.mercadolivre.com.br/pt-br/publicacao-de-produtos) (atualizada em 09/01/2026), o campo vem anotado com "Somente disponível com token proprietário". O mesmo vale para `start_time` e `historical_start_time`. Nosso token é de app, não do vendedor. O passo 0 só confirma. **Proibido** tentar obter o número pela página do anúncio (item 7.6 dos Termos) |
| ML | Top 20 mais vendidos da categoria: `GET /highlights/MLB/category/MLB437616` | **Fato (doc):** [Mais vendidos](https://developers.mercadolivre.com.br/pt_br/mais-vendidos-no-mercado-livre), atualizada em 22/06/2026. Mistura `PRODUCT`, `USER_PRODUCT` (MLBU) e `ITEM`. Exige categoria folha, e a `MLB437616` é folha. **Não testado com token** (401 sem token) |
| ML | Top 20 por gênero: `…?attribute=BOOK_GENRE&attributeValue={id}` | **Inferência:** a doc fala em filtrar por atributo, mas o exemplo usa `BRAND`. Pode dar 404 "Dimension not found". O passo 0 confere |
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
| Google Books | `averageRating`/`ratingsCount`: `GET https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}` | **Não confirmado:** a chamada anônima deu "Quota exceeded" (cota compartilhada). Precisa de chave própria (decisão 9). A amostra brasileira tende a ser pequena (**inferência**) |

**Sinal 4. Interesse de busca (Google Trends)**

| Fonte | O que entrega | Status |
|---|---|---|
| Google Trends API (oficial) | Série de interesse por termo, região e sub-região, agregada por dia, semana, mês ou ano, numa janela móvel de 5 anos. A escala é consistente entre requisições (não é 0–100 por consulta), então dá para comparar o mesmo termo ao longo do tempo e juntar consultas | **Fato:** [Google Trends API](https://developers.google.com/search/apis/trends) continua **alpha**, com acesso por formulário e prioridade para quem tem caso de uso pronto ([anúncio de 24/07/2025](https://developers.google.com/search/blog/2025/07/trends-api)). Página consultada em 2026-10-19. **Não temos acesso.** Pedir é a decisão 8 |
| `pytrends` | — | **Fato:** o repositório [GeneralMills/pytrends](https://github.com/GeneralMills/pytrends) está arquivado (`archived: true` na API do GitHub). Não é oficial e raspa o site do Trends. **Arriscado/proibido:** fere os Termos do Google sobre acesso automatizado. Não usar |
| SerpApi, DataForSEO e similares | Revendem dados do Trends | **Arriscado:** raspam o Google por nós. Não usar |
| ML (substituto parcial) | `GET /trends/MLB/MLB437616`: até 50 `keyword`, com atualização semanal | **Fato (doc):** [Tendências](https://developers.mercadolivre.com.br/pt_br/tendencias), atualizada em 27/05/2025. Não traz número, só a palavra e uma URL de busca, e essa URL é HTML, que não seguimos. Serve como bônus binário ("título ou autor aparece nas tendências"). **Não testado com token** (403 sem token) |

**Resumo honesto:** hoje só o **preço do ML** está confirmado, e o nosso histórico ainda é curto. A **posição no `/highlights`** está documentada, mas não foi testada. `sold_quantity` não vem. Avaliações de livro no ML provavelmente não vêm. Trends depende de um acesso alpha que não temos. Tudo o que é da Amazon depende da Creators API, e o histórico de preço da Amazon esbarra na regra de cache de 24 h.

### 10.3 Pontuação, limiar e modo sombra

**Componentes.** Cada componente `s_i` vai de 0 a 1 e é guardado com o valor bruto, a fonte, o `fetched_at` e a `confidence_i` (0 a 1). `clamp(x) = min(1, max(0, x))`.

| Componente | Peso `w_i` | Normalização |
|---|---:|---|
| Preço `s_p` | 35 | Com 30 dias ou mais de histórico nosso: `d = 1 − preço / mediana_90d`; `s_p = clamp(d / 0,30) + 0,2·[preço ≤ mínimo_90d]`, com teto em 1 e `confidence = 1`. Ou seja, 30% abaixo da mediana já dá nota cheia. Com menos de 30 dias: `s_p = min(0,3; clamp(desconto_rótulo / 0,30))`, em que `desconto_rótulo` vem de `original_price` (ML) ou `savings.percentage` com `savingBasisType ∈ {LIST_PRICE, WAS_PRICE}` (Amazon), e `confidence = 0,5`. Livro nas duas lojas: vale a loja de menor preço, como no build |
| Demanda `s_d` | 25 | ML: `s_ml = (21 − posição_highlights) / 20`, com `confidence = 0,6`. Amazon (quando liberar): `s_amz = clamp(1 − log10(websiteSalesRank) / 5)`, ou seja, rank 1 → 1 e rank ≥ 100.000 → 0, com `confidence = 0,7`. `s_d = max(s_ml, s_amz)`, e a confiança é a da fonte que deu o máximo. Bônus de +0,1 (teto 1) se título ou autor aparecer no `/trends` do ML. Desempate por idade: lançamento (≤ 1 ano pelo `PUBLICATION_YEAR`) ganha +0,05. Sem nenhuma fonte, o componente fica ausente |
| Avaliações `s_r` | 15 | `R̄ = (v·R + 20·4,0) / (v + 20)` (média bayesiana com prior de 4,0 e peso 20); `s_r = clamp((R̄ − 3,5) / 1,5) × min(1; v / 50)`. Fonte: ML reviews ou Google Books. `confidence = min(1; v / 50)` |
| Tendência `s_t` | 25 | Com acesso à Trends API: `s_t = clamp(média_4_semanas / média_12_semanas_anteriores − 1)`, em que +100% dá nota cheia. Termo: título + autor, região BR. `confidence = 0,8`. Sem acesso: ausente |

**Agregação.** Componente ausente não entra no cálculo e não conta como zero. `P` é o conjunto dos presentes:
- `score = 100 × Σ_{i∈P} w_i·s_i / Σ_{i∈P} w_i`
- `confiança = Σ_{i∈P} w_i·confidence_i / 100`. O divisor é 100 de propósito: a falta de componente baixa a confiança, mas não o score.

Exemplo de hoje: só preço curto (0,5) e `/highlights` (0,6) presentes dão confiança = (35·0,5 + 25·0,6)/100 = 0,325. Com 30 dias de histórico e `/highlights`: (35·1 + 25·0,6)/100 = 0,50.

*(Até a calibração, o limiar abaixo não bloqueia a publicação: §10.7, decisão 2.)* **Limiar inicial:** publicar com `score ≥ 70` e `confiança ≥ 0,5`. Retirar com `score < 60` por 2 execuções seguidas. A histerese evita que o livro entre e saia todo dia. Na prática, isso quer dizer que **nada publica antes de 30 dias de histórico no ML e sem estar no top 20**, que é exatamente o "sem histórico suficiente, não afirmar que é promoção" de §3. A decisão 5 diz se isso é aceitável.

**Gates (complemento de §4).** Gate que falha bloqueia, seja qual for a pontuação:
- (6) gênero mapeado em §10.1;
- (7) preço conferido dentro do frescor (2 h no ML, 12 h na Amazon) e identidade casada. **Reescrito em 2026-10-19:** o `/products/{id}` não traz GTIN (probe 39259800320), então "GTIN do produto igual ao ISBN" não é verificável. Regra:
  - livro só do ML: a identidade é o `ml_product_id` (`PRODUCT` ativo, com `BOOK_TITLE` e `AUTHOR`). O ISBN é opcional; presente, precisa ser ISBN-13 válido e único (`curator.md` §3.2, opção 1);
  - livro só da Amazon: a identidade é o `asin` colado pelo Elias, com o `isbn` quando houver. Se o ISBN começa com 978 e o ASIN não começa com `B0`, o ASIN precisa ser o ISBN-10 desse ISBN;
  - livro nas duas lojas: o ISBN-13 vem do lote da Amazon e é resolvido pela API em `/products/search?product_identifier=<isbn>`. Exatamente um `PRODUCT` ativo de `MLB-BOOKS` casa as lojas; zero ou mais de um deixa o livro com uma loja só. **Nunca por título.** O casamento por GTIN é feito do lado do ML (**inferência**: o `product_identifier` busca pelo GTIN da ficha);
- (8) no máximo N novos livros por dia e M por gênero: **N = 50, M = 10**, configuráveis (§10.7, decisão 1);
- (9) `id` novo, que não colide com nenhum `id` já usado, mesmo de livro retirado, porque vira deep link;
- (10) pelo menos uma loja com link de afiliado válido (§10.4). Loja sem link sai do `stores`; se não sobrar loja, o livro não publica.

**Modo sombra.** O score é calculado e logado, mas **não muda nada no site**. **Substituído em parte pela §10.7, decisão 2:** a publicação acontece desde o dia 1 pelos gates de validade; o que fica em sombra é só o score, que não bloqueia nem ordena até o critério de saída do item 6. Os itens abaixo continuam valendo para o score.
1. A execução diária grava uma linha JSON por candidato em `curation/AAAA-MM.jsonl`, só de acréscimo. Onde fica é a decisão 11.
2. Cada linha tem: `run_at`, `ml_product_id`, `asin`, `isbn`, `genre` (e a fonte do gênero), os componentes (`raw`, `s`, `confidence`, `source`, `fetched_at`), `score`, `confiança`, os `gates` (passou ou falhou, com o motivo) e `would_publish`. **Nada de dado de usuário.**
3. Toda segunda-feira sai um resumo no log do Actions: quantos candidatos teriam sido publicados por gênero, a distribuição dos scores, os 10 primeiros e os 10 logo abaixo do corte.
4. **Métricas contra a curadoria humana.** São duas réguas:
   - **Rótulo cego:** o Elias marca "publicaria ou não" numa amostra estratificada, sem ver o score: metade acima do corte, metade na faixa de 50 a 70. Com isso medimos a **precisão** (dos que o sistema publicaria, quantos ele aprovou) e o **recall** (dos que ele aprovou, quantos o sistema publicaria).
   - **Recall sobre o catálogo manual:** os livros já curados à mão (`data/offers.json`) que aparecem como candidatos e passam nos gates devem ter `would_publish = true`. Quem não tem, é investigado: ou o peso está errado, ou o livro só entrou por gosto pessoal.
   - Também medimos: volume por dia e por gênero, cobertura (quantos dos 10 gêneros têm ao menos 1 aprovado), estabilidade (quantos entrariam e sairiam em menos de 7 dias) e a taxa de "dado ausente" por componente.
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
7. **Orçamento de chamadas:** 1 `/highlights` geral, mais os 50 termos do `/trends` e uma busca por gênero via `/products/search?q=` (o filtro do `/highlights` por atributo dá 400, ver o passo 0), mais `/products/{id}` só dos `PRODUCT` novos, mais `/reviews` só de quem passou nos gates. O job é separado do coletor, porque o coletor tem prazo de 40 s (`ML_DEADLINE_S`). Os limites de taxa do ML para token de app são **não confirmados**.

### 10.4 Links do ML em lote (enquanto não houver método autorizado)

**Situação verificada em 2026-10-19:** não há API oficial documentada para gerar link de afiliado do ML. No portal de desenvolvedores, nada sobre afiliados. As páginas oficiais do programa ([gere seus links](https://www.mercadolivre.com.br/l/afiliados-gere-seus-links), [direcionamento de visitas](https://www.mercadolivre.com.br/l/afiliados-direcionamento-de-visitas)) só renderizam com JS e indicam o Gerador de links e a barra/extensão do portal. Fontes de terceiros de 2026 dizem o mesmo: [DivulgaNinja](https://www.divulganinja.com.br/blog/como-gerar-link-afiliado-mercado-livre-passo-a-passo-2026) descreve o Gerador de links do portal, e um dev no [TabNews](https://www.tabnews.com.br/marcuth/criei-uma-cli-para-gerar-links-de-afiliados-de-marketplaces) diz que o ML não tem API pública e que a ferramenta dele usa cookies. **Proibido** para nós: cookies, sessão, navegador automatizado e endpoint privado. O Busqy de §6 continua não confirmado contratualmente.

O que muda o desenho: o link do painel é `https://www.mercadolivre.com.br/social/<aff>?matt_word=<aff>&matt_tool=…&forceInApp=true&ref=<cifrado>` e **não contém o id do produto** (ver `collector/catalog.json`). O script não tem como descobrir sozinho a que produto um link pertence. Abrir o link para seguir o redirecionamento não é uma saída, por três motivos:
- seria acessar o site, não a API, o que o item 7.6 dos [Termos do Programa de Desenvolvedores](https://developers.mercadolivre.com.br/pt_br/termos-e-condicoes) proíbe;
- contaria um clique falso;
- o build não quer depender disso.

Por isso o par produto ↔ link é feito pelo Elias, linha a linha, num arquivo com chave.

**Formato substituído pela §10.7, decisão 3** (lote único das duas lojas, aplicado pelo `affiliate-linker` com `lote-apply`). A validação descrita abaixo continua valendo para as linhas do ML.

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
4. **Item sem link:** fica na fila e não publica pelo ML (gate 10). Se o livro também tem a Amazon com preço válido, ele pode publicar só com a Amazon (decisão 13). Um candidato pendente há mais de 14 dias sai da fila e volta se ainda for candidato na próxima descoberta. Isso evita fila infinita de livro que já não está em promoção.
5. **Limite conhecido.** Nenhuma validação prova que o `ref` aponta para aquele produto. Isso depende do Elias colar na linha certa. A mitigação barata: a `product_url` e o `title` ficam ao lado do link, e o resumo do `links-apply` mostra título ↔ produto para ele bater o olho. A decisão 12 diz se isso basta.
6. **Volume:** como a Amazon também é semi-automática hoje, **nenhum livro novo sai sem esse passo**. Com o gate 8 em até 50 por dia (§10.7), são até 50 links do painel por dia. É o maior custo operacional do projeto e o gatilho para retomar o Busqy (§6) se pesar.

### 10.5 Decisões em aberto para o Elias

Cada decisão traz as opções e a minha recomendação (**Rec.**).

1. **Qual versão desta spec vale.** (a) Publicação automática com gates, esta, conforme a decisão de 2026-10-18. (b) PR com aprovação humana, do branch `worktree-agent-a26264a6033900af8`. Elas não podem coexistir. **Rec.:** (a), com a sombra de §10.3 como período de prova. Na prática, a sombra já é a aprovação humana até o critério de saída ser atingido.
2. **Gêneros.** (a) Os 11 de §10.1. (b) 10, juntando `didaticos` e `tecnicos` num `estudo`. (c) Manter os 5. **Rec.:** (a). A mudança no `GENRES` sai pelo `product-manager`. *Decidido: (b), §10.7 decisão 6.*
3. **Mapeamentos ambíguos.** Humor e LGBTQ+ → `ficcao` (ou `nao-ficcao`); Esoterismo → `religiao` (ou `estilo-de-vida`); Tecnologia → `tecnicos` (ou `didaticos`); Saúde → `estilo-de-vida` (ou `nao-ficcao`). **Rec.:** os da tabela. E `literatura-brasileira` fica manual até a Creators API mostrar se existe o nó; não inferir por autor nem por título.
4. **Gênero dos livros já publicados.** (a) Manter o manual e só registrar a divergência. (b) Adotar o do ML. **Rec.:** (a). O Elias decide caso a caso as divergências que a primeira sombra listar ("Irmão do Jorel" e "Hábitos Atômicos" são as prováveis).
5. **Pesos e limiar iniciais.** (a) 35/25/15/25, `score ≥ 70`, `confiança ≥ 0,5`, retirada abaixo de 60 por 2 execuções. (b) O mesmo, com confiança mínima de 0,3, o que permite publicar já com o rótulo da loja e o top 20. **Rec.:** (a). Ela aceita que nada publique antes de 30 dias de histórico, coerente com §3 e com o selo de 90 dias.
6. **Critério de saída da sombra** de §10.3, item 6 (30 dias, 60 rótulos, precisão ≥ 0,90, recall ≥ 0,60, ≥ 1 livro por dia, ≥ 6 gêneros, churn < 10%). (a) Aceitar. (b) Afrouxar a precisão para 0,80. **Rec.:** (a). Um livro ruim publicado sozinho custa mais confiança do que um bom que ficou de fora.
7. **Histórico de preço da Amazon e a cláusula de cache de 24 h** (Licença 2(h)). (a) Guardar só o histórico do ML; a Amazon mostra o preço atual com carimbo de hora, sem `lowest_90d_cents` próprio. (b) Manter o histórico da Amazon e aceitar o risco. (c) Perguntar ao suporte dos Associados, por escrito, se guardar a série de preços para "menor preço em 90 dias" é permitido. **Rec.:** (a) agora e (c) em paralelo. Isso afeta o contrato v2 (`lowest_90d_cents` e `history_since` da Amazon) e o `amazon_prices.csv`: vai para o `product-manager` e o `collector-engineer`.
8. **Google Trends API (alpha).** (a) Pedir o acesso agora, com custo zero e o caso de uso pronto. (b) Não pedir e redistribuir os 25 pontos. **Rec.:** (a). Enquanto não sai, a agregação já ignora o componente ausente, então não há o que redistribuir. Nunca `pytrends` nem revendedores.
9. **Google Books.** (a) Criar chave própria (cota gratuita) para avaliações e metadados. (b) Só Open Library, sem avaliações. **Rec.:** (a), guardando a chave em GitHub Secrets. O peso de Avaliações fica em 15 até a sombra mostrar se a amostra brasileira é útil.
10. **Liberar o passo 0** (`probe` só leitura com o token de app) como primeira tarefa da entrega 2, antes de qualquer outra implementação. **Rec.:** sim. Sem ele, metade da tabela de §10.2 é "não testado".
11. **Onde guardar o log da sombra e da auditoria.** (a) `curation/AAAA-MM.jsonl` no branch `price-history`, só de acréscimo. (b) Artefato do Actions (90 dias). (c) Supabase. **Rec.:** (a), com retenção de 24 meses. É versionado, auditável e não tem dado de usuário.
12. **Fluxo de links em lote de §10.4.** (a) Aceitar o par por linha, com o limite de não provar o `ref`. (b) Exigir conferência dupla: o Elias abre cada link uma vez à mão antes de aplicar. **Rec.:** (a), com N = 5 novos por dia e M = 2 por gênero.
13. **Livro nas duas lojas sem link do ML.** (a) Publica só com a Amazon, se o preço dela estiver fresco. (b) Não publica. **Rec.:** (a). O contrato v2 já aceita `stores` com 1 item.
14. **Seguem pendentes de §6/§8.** (a) Confirmar com o Busqy e com o ML o método contratual de conversão. (b) Decidir se o lançamento é só ML ou espera a Creators API. (c) Definir a frequência intradiária e a política de retirada. **Rec.:** (a) por e-mail, sem integrar nada antes da resposta por escrito; (b) lançar só com ML, porque a Creators API depende de vendas que só vêm com o site no ar; (c) manter o coletor como está (frescor de 2 h no ML) e retirar após 2 execuções com score < 60 ou 6 h sem preço válido.

### 10.6 Decisões do Elias (2026-10-19)
1. **Publicação automática com gates**, conforme esta spec. A versão com "PR e aprovação humana" foi descartada.
2. Decisões 2, 3, 5, 8, 9 e 11 de §10.5 (a numeração original dizia "2. a 7."), aprovadas assim. Gêneros e decisão 7 de §10.5 foram fechados na §10.7:
   - os 5 gêneros novos;
   - Humor e LGBTQ+ em `ficcao`, Tecnologia em `estudo`, e `literatura-brasileira` só manual;
   - pesos 35/25/15/25, score ≥ 70, confiança ≥ 0,5 e retirada abaixo de 60 por 2 execuções, aceitando ~30 dias sem publicar;
   - pedir acesso à Google Trends API, sem depender dela: o peso dela é redistribuído enquanto não houver acesso;
   - criar a chave grátis do Google Books;
   - log em `curation/AAAA-MM.jsonl` no branch `price-history`, guardado por 12 meses.
8. *(Substituído pela §10.7, decisão 1: até 50 publicados por dia, do ML e/ou da Amazon.)* **Volume: pelo menos 50 livros novos por dia vindos do ML.** O teto por gênero sobe para 10/dia, configurável, para manter o equilíbrio entre os 10 gêneros. Os links do ML seguem o fluxo em lote do §10.4.
   - Custo: são cerca de 50 links do painel por dia colados à mão, o maior custo operacional do projeto. Se pesar, é o gatilho para retomar o Busqy (§6).
9. **Lançar com a Amazon, sem a Creators API.**
   - A busca na Amazon é manual: o Elias encontra o livro no site, como qualquer usuário, e coloca no lote o ISBN, o ASIN e o preço que viu. O script nunca acessa a Amazon.
   - O link da Amazon é gerado automaticamente a partir do ASIN e da tag (`affiliate_url`). O lote da Amazon só precisa do ASIN certo.
   - O preço vai para `collector/amazon_prices.csv` (`asin,price_cents,list_price_cents,checked_at`). Com o gate de frescor de 12 h, o preço manual da Amazon vence em 12 h e a loja sai da comparação. O livro continua no site se o ML estiver fresco.
   - Livro escolhido pelo Elias na Amazon não precisa do score, porque a curadoria humana é o sinal. Os gates continuam valendo: ISBN, preço fresco, link válido e sem duplicata. Se o mesmo ISBN estiver no ML, entra a comparação de lojas.
   - *(Formato substituído pela §10.7, decisão 3.)* Formato do lote único, uma linha por livro e uma loja por linha: `book_id, isbn, store, ml_product_id|asin, product_url, ml_url (só ML), price_cents/list_price_cents (só Amazon), checked_at (só Amazon)`.
10. **Passo 0 liberado:** a checagem só de leitura da API do ML com o token de app. Ela roda como `workflow_dispatch` no GitHub Actions, com `ML_CLIENT_ID`/`ML_CLIENT_SECRET` vindos dos Secrets e nada ecoado no log, porque o token não pode ficar na máquina do agent nem no repo. **Já executado:** probes 39258219518 e 39259800320, com o resultado em `curator.md` §3.2 e o resumo em §10.2.

### 10.7 Decisões do Elias (2026-10-19, segunda rodada)

Prevalecem sobre a §10.6 e sobre o resto da spec onde houver conflito.

1. **Volume: até 50 livros novos *publicados* por dia**, para popular o site agora, com teto de 10 por gênero, os dois configuráveis. Podem vir do ML, da Amazon ou das duas lojas. A meta é "até 50": o rendimento real das fontes é medido na primeira execução e registrado aqui. Fontes do ML:
   - `/highlights` geral de `MLB437616`;
   - os 50 termos do `/trends`, cada um resolvido por `/products/search?q=`;
   - uma busca por gênero via `/products/search?q=`.
2. **Publicação pelos gates de validade desde o dia 1.** Um livro publica quando passa em todos estes:
   - preço real conferido dentro do frescor;
   - link de afiliado válido da nossa conta (`build.py:affiliate_url`);
   - gênero dentro dos 10;
   - identidade casada conforme o gate 7 reescrito (§10.3);
   - em estoque (item novo ativo);
   - sem duplicata (gates 4 e 9).

   **O score fica em modo sombra só como nota:** é calculado e logado, mas não bloqueia nem ordena. Até a calibração, a ordem é pela posição no `/highlights` e depois no `/trends`. Atingido o critério de saída da §10.3 item 6, o score passa a ordenar e a retirar.
3. **Fluxo de links.**
   - **ML:** o PR diário do curator traz até 50 candidatos num TSV com `book_id`, `ml_product_id`, `title`, a URL do produto (`https://www.mercadolivre.com.br/p/<MLB>`, montada pelo código, só para o Elias abrir no painel) e `ml_url` vazia. O Elias gera os links no painel e cola de volta. O `affiliate-linker` aplica com `lote-apply`, que valida cada linha (§10.4, item 3), abre o PR e faz o merge.
   - **Amazon:** o código **nunca** busca na Amazon (CLAUDE.md, regra 1). O PR lista o título e o ISBN (quando houver) dos candidatos para o Elias procurar à mão. Ele cola de volta o ASIN e o preço que viu, e o preço vai para o `collector/amazon_prices.csv`. O link é montado pelo build a partir do ASIN e da tag, e nunca é gravado.
   - **Merge:** fica com o `affiliate-linker`. Um PR aberto pelo `GITHUB_TOKEN` não dispara o `catalog-check`; quem dispara é o push dele.
4. **Teto: 500 livros ativos no total**, com retirada automática por score < 60 em 2 execuções (só depois da calibração) ou por 30 dias sem oferta. Os 500 não cabem no `_redirects` de hoje: são 4 regras por livro só do ML e 5 por livro nas duas lojas, num limite de 2.000 (`build.py:MAX_REDIRECTS`). Ficam três requisitos:
   - **Requisito para o `collector-engineer` e o `frontend-developer`:** compactar as regras com um placeholder genérico `/r/:id/* /r/:id 302` (`_redirects` da Cloudflare) para os casos em que o destino é o mesmo do `/r/<id>`. Regras explícitas ficam só onde o destino difere: a tag de canal da Amazon e a loja que não venceu. Antes, confirmar na documentação da Cloudflare a ordem de avaliação entre regra estática e placeholder.
   - O `catalog-check` falha o PR se o catálogo passar do limite de regras ou de 500 ativos.
   - Capacidade do coletor para 500 livros dentro do frescor de 2 h do ML: **não medida** (`ML_DEADLINE_S` = 40 s por execução). É o `collector-engineer` quem mede.
5. **Histórico de preço da Amazon (decisão 7 de §10.5): opção (b).** O histórico da Amazon fica no `price_history` e alimenta o gráfico de variação de preço, aceitando o risco da cláusula 2(h) da Licença. Em paralelo, a opção (c): o Elias pergunta por escrito ao suporte dos Associados. Se a resposta for negativa, o histórico é desligado.
6. **Gêneros: 10**, todos mapeados a partir de valores reais do `BOOK_GENRE` do ML, sem nenhum slug inventado (tabela da §10.1). Didáticos e técnicos viram `estudo`, Esoterismo vai para `religiao`, Saúde para `estilo-de-vida`, e Autoajuda entra. A mudança no `GENRES` do `build.py` sai pelo `product-manager`.
7. **Log da sombra e da auditoria:** `curation/AAAA-MM.jsonl` no branch `price-history`, com retenção de 12 meses.
8. **Ideia em aberto, fora do escopo, para o `product-manager`:** usar grupos de ofertas do Telegram como fonte, no estilo da ferramenta Mandaboa, que reescreve os links com o affiliate id. Não especificado.
