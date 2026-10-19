# Spec em rascunho: curadoria automática de livros

Status: spec fechada para revisão do Elias. §1–9 são o handoff do Codex (2026-10-18); §10 fecha a spec (catalog-curator, 2026-10-19) e substitui §3 e §8 onde houver conflito.
Implementação bloqueada até o Elias responder às decisões de §10.5. Até lá, nada publica: no máximo modo sombra.

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

Convenção: **Fato** tem fonte com data; **Inferência** é dedução minha, a confirmar; **Não confirmado** é o que tentei e não consegui verificar. Consultas feitas em 2026-10-19. As rotas `/categories` do ML responderam sem token. Todas as outras rotas do ML citadas abaixo deram 401 ou 403 sem token. Não havia `ML_CLIENT_ID` nesta sessão, então **nenhuma delas foi testada com o token de app**. O passo 0 de §10.2 resolve isso.

Existe outra versão desta spec no branch `worktree-agent-a26264a6033900af8` (commit `22548f4`, product-manager). Ela chega aos mesmos fatos sobre a API, mas propõe "PR com aprovação humana" em vez de publicação automática. Esta seção segue a decisão do Elias de 2026-10-18 (publicação automática com gates). Qual versão vale está na decisão 1 de §10.5.

### 10.1 Gêneros: cobrir todas as áreas

**Fato:** a categoria de livro físico do ML é `MLB437616` ("Livros Físicos", filha de `MLB1196`). Ela é **folha**, sem subcategorias, e tem `catalog_domain: MLB-BOOKS` (`GET https://api.mercadolibre.com/categories/MLB437616`). Por isso não dá para descobrir livros por nicho usando subcategorias.

**Fato:** o gênero vem como atributo. `GET /categories/MLB437616/attributes` traz `BOOK_GENRE`, uma lista fechada de 25 valores, e `BOOK_SUBGENRES`, com 208 valores, `hidden` e multivalorado. Traz também `PUBLICATION_YEAR` e `GTIN` (rótulo "ISBN").

Proposta: o curador mapeia cada `BOOK_GENRE` para **um** slug do site. Os 5 slugs atuais continuam iguais, porque já são URLs (`/manga/` etc.). Entram mais 5 slugs para cobrir os 25 valores.

| Slug do site | Valores `BOOK_GENRE` do ML (id) |
|---|---|
| `ficcao` | Literatura (7538039), Humor (25743212), LGBTQ+ (76624760) |
| `manga` | Mangas e HQs (13061816) |
| `negocios` | Negócios (13061825) |
| `nao-ficcao` | História (13464376), Biografias (13611960), Ciência (76624759) |
| `autoajuda` **novo** | Autoajuda (7538148) |
| `infantojuvenil` **novo** | Infantil (7538151), Juvenil (13061823) |
| `religiao` **novo** | Religião (19912211), Esoterismo (7538147) |
| `estudo` **novo** | Escola e educação (23663384), Acadêmico (13061813), Dicionários, enciclopédias e consulta (7538149), Tecnologia (14885398) |
| `estilo-de-vida` **novo** | Saúde (13061828), Esportes (16188909), Gastronomia (13061821), Artesanato (13061814), Pets (76624758), Viagem (14973077), Arte e design (7538158), Música (13485350) |
| `literatura-brasileira` | Nenhum. O ML não tem esse valor, nem em `BOOK_SUBGENRES`, onde procurei "brasil" e "nacional". **O curador automático nunca atribui esse slug.** Ele só entra à mão. |

Três dos mapeamentos são **inferência** e estão na decisão 3: Humor e LGBTQ+ em `ficcao`, e Tecnologia em `estudo`. Produto sem `BOOK_GENRE` não é publicado, porque o build exige `genre` (gate 6 em §10.3). Ele fica no log da sombra como "sem gênero".

Mudança proposta para o `GENRES` do `build.py`. **Não editei o arquivo**: a decisão é do Elias, pelo `product-manager`.

```python
GENRES = {
    "literatura-brasileira": "Literatura brasileira",
    "ficcao": "Ficção",
    "negocios": "Negócios e finanças",
    "nao-ficcao": "Não ficção",
    "manga": "Mangá e HQ",
    "autoajuda": "Autoajuda",
    "infantojuvenil": "Infantil e juvenil",
    "religiao": "Religião e espiritualidade",
    "estudo": "Estudo e técnicos",
    "estilo-de-vida": "Saúde, hobbies e estilo de vida",
}
```

A ordem do dict é a ordem do menu (`nav`), e o menu só mostra gênero com oferta. Gênero vazio não gera link quebrado no menu, mas cada slug vira diretório em `dist/`. O mapa `BOOK_GENRE id → slug` fica no curador, não no `build.py`.

### 10.2 O que cada API entrega de fato hoje

Passo 0, que bloqueia a calibração: rodar um `probe`, só leitura, com o token de app (`client_credentials`, o mesmo do `collect.py`). Ele chama cada rota "a verificar" abaixo e registra o status HTTP e as chaves da resposta nesta tabela. Não grava nada.

**Sinal 1. Promoção em relação ao histórico**

| O quê | Endpoint | Status |
|---|---|---|
| Preço atual e "preço de" (`price`, `original_price`) | `GET /products/{id}` (`buy_box_winner`) e `GET /products/{id}/items` | **Fato, em produção:** o `collect.py` já usa (doc [Buscador de produtos](https://developers.mercadolivre.com.br/pt_br/buscador-de-produtos), atualizada em 29/12/2025) |
| `amount`/`regular_amount` | `GET /items/{id}/sale_price?context=channel_marketplace` | **Fato:** dá 403 com token de app (run 39178554200, registrado no `collect.py`) |
| Histórico de preço de um anúncio de terceiro | — | **Não confirmado:** não achei endpoint na doc pública. O histórico é o nosso, gravado em `price_history/AAAA-MM.csv`, e começa no `history_since` de cada livro (o primeiro é de 2026-10-18) |

Consequência: até cada livro ter pelo menos 30 dias de snapshots nossos, esse sinal só pode usar `original_price`. É o rótulo da loja e vale pouco (§10.3).

**Sinal 2. Compras recentes ajustadas à idade**

| O quê | Endpoint | Status |
|---|---|---|
| `sold_quantity` de anúncio de terceiro | `GET /items/{id}` ou `/items/bulk?ids=` (`/items?ids=` será descontinuado em 25/10/2026, segundo a doc [Busca de itens](https://developers.mercadolivre.com.br/pt_br/itens-e-buscas), de 31/08/2026) | **Não confirmado.** O campo aparece em exemplos da doc de publicação. Não achei regra que diga se ele vem exato, em faixa ou se vem com token que não é do vendedor. O passo 0 confere |
| Ranking de mais vendidos (top 20) | `GET /highlights/MLB/category/MLB437616` | **Fato:** documentado em [Mais vendidos](https://developers.mercadolivre.com.br/pt_br/mais-vendidos-no-mercado-livre) (22/06/2026). Mistura `PRODUCT`, `USER_PRODUCT` (MLBU) e `ITEM`. Exige categoria folha, e a `MLB437616` é folha. **Não testado com token de app** (401 sem token) |
| Top 20 por gênero | `GET /highlights/MLB/category/MLB437616?attribute=BOOK_GENRE&attributeValue={id}` | **Inferência:** a doc diz "qualquer atributo suportado", mas o exemplo usa `BRAND`. Pode dar 404 "Dimension not found". O passo 0 confere |
| Posição de um produto | `GET /highlights/MLB/product/{id}` | **Fato** (mesma doc). 404 quando o produto não está no top 20 de nenhuma dimensão. Isso é dado ausente, não zero |
| Idade do livro | atributo `PUBLICATION_YEAR` do produto; alternativa: `publish_date` da [Open Library](https://openlibrary.org/dev/docs/api/books) (`GET https://openlibrary.org/isbn/{isbn13}.json`) | **Fato:** o atributo existe na categoria. A Open Library respondeu para `9788550807560` com "Oct 27, 2019". Se o atributo vem preenchido nos produtos de livro é **não confirmado** |

Consequência: "compras recentes" só existe depois de 30 dias de snapshots de `sold_quantity`, e isso se o campo vier. Até lá, a demanda vem da posição no `/highlights`, que é o sinal oficial de demanda que a doc confirma. Nas avaliações do ML, `reviews[].buying_date` daria um terceiro indicador de compras recentes (é a data de compra de quem avaliou), mas depende do Sinal 3.

**Sinal 3. Avaliações**

| O quê | Endpoint | Status |
|---|---|---|
| Total, média, distribuição e `buying_date` | `GET /reviews/item/{item_id}?catalog_product_id={MLB}` | **Fato:** documentado em [Opiniões de Produtos](https://developers.mercadolivre.com.br/pt-br/opinioes-sobre-um-produto) (18/08/2026). Traz `paging.total`, `rating_average` e `rating_levels`. O item precisa estar ativo. Use o `item_id` da buy box, que o coletor já tem |
| Avaliação habilitada para livros? | `GET /categories/MLB437616` → `settings.items_reviews_allowed: false` | **Fato:** o campo vem `false`. **Inferência:** livros podem não ter avaliação no ML, e o sinal ficaria sempre ausente. O passo 0 confere com um livro popular |
| Google Books `averageRating`/`ratingsCount` | `GET https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}` | **Não confirmado:** a chamada anônima deu "Quota exceeded" (a cota é compartilhada). Precisa de chave de API própria (decisão 6) |
| Amazon (avaliações, ranking de vendas) | Creators API | Indisponível: a API não está liberada para a conta. Nunca scraping |

**Sinal 4. Google Trends**

| O quê | Fonte | Status |
|---|---|---|
| API oficial | [Google Trends API (alpha)](https://developers.google.com/search/apis/trends) e [anúncio de 24/07/2025](https://developers.google.com/search/blog/2025/07/trends-api) | **Fato:** é alpha com acesso por formulário, e o Google prioriza quem já tem caso de uso. A escala é consistente entre requisições (dá para comparar o mesmo termo no tempo), e a janela é de 5 anos. **Não temos acesso.** Pedir o acesso é a decisão 5 |
| `pytrends` / scraping do site | — | Não usar. Não é oficial, e terceiros relatam que o projeto foi arquivado em 2025 |
| Substituto oficial do ML | `GET /trends/MLB/MLB437616` ([Tendências](https://developers.mercadolivre.com.br/pt_br/tendencias), de 27/05/2025) | **Fato:** devolve até 50 `keyword` com atualização semanal. Não dá número, só a palavra e uma URL de busca, e essa URL é HTML, que não seguimos. Serve só como bônus binário ("título ou autor aparece nas tendências"). **Não testado com token** (403 sem token) |

Resumo honesto: hoje só o **preço** (com o nosso histórico ainda curto) está confirmado. A **posição no ranking** está documentada, mas não foi testada. `sold_quantity`, avaliações de livro e Trends podem estar ausentes no lançamento.

### 10.3 Pontuação, limiar e modo sombra

**Componentes.** Cada componente `s_i` vai de 0 a 1 e é guardado com o valor bruto, a fonte, o `fetched_at` e a `confidence_i` (0 a 1).

| Componente | Peso `w_i` | Regra inicial |
|---|---:|---|
| Preço | 35 | Com 30 dias ou mais de histórico nosso: `s = clamp(desconto_sobre_mediana_90d / 0,30)`, com +0,2 (até o teto de 1) se o preço for ≤ ao mínimo da janela. Com menos de 30 dias: `s = min(0,3; desconto_sobre_original_price / 0,30)` e `confidence = 0,5` (§3: "no máximo pontuação neutra/baixa") |
| Demanda | 25 | Com `sold_quantity` e 30 dias de snapshots: percentil de `Δsold_30d` dentro da faixa de idade (lançamento ≤ 1 ano, 1 a 3 anos, mais de 3 anos), com `confidence = 1`. Sem isso, usa o `/highlights`: `s = (21 − posição) / 20` e `confidence = 0,6`. Fora do top 20, o componente fica ausente |
| Avaliações | 15 | `s = norm(média_bayesiana) × min(1; total / 50)`, com a média bayesiana `(v·R + 20·4,0) / (v + 20)` e `norm` levando 3,5→0 e 5,0→1 |
| Tendência | 25 | Com acesso à Trends API: `s = clamp(média_4_semanas / média_12_semanas_anteriores − 1)`. Sem acesso: ausente. O `/trends` do ML só soma +0,1 em Demanda, sem passar de 1 |

**Agregação.** Componente ausente não entra no cálculo e não conta como zero:
- `score = 100 × Σ(w_i·s_i) / Σ(w_i)`, somando só os componentes presentes;
- `confiança = Σ(w_i·confidence_i) / 100`, somando só os componentes presentes.

Exemplo de hoje: só preço curto (0,5) e `/highlights` (0,6) presentes dão confiança = (35·0,5 + 25·0,6)/100 = 0,325.

**Limiar inicial, a aprovar:** publicar com `score ≥ 70` e `confiança ≥ 0,5`. Retirar com `score < 60` por 2 execuções seguidas. A histerese evita que o livro entre e saia todo dia. Com os sinais de hoje, a confiança não chega a 0,5. Esse é o motivo de existir o modo sombra: o próprio limiar impede publicar antes de ter 30 dias de histórico. A decisão 4 diz se isso é aceitável.

**Gates (complemento de §4).** Gate que falha bloqueia, seja qual for a pontuação:
- (6) gênero mapeado em §10.1;
- (7) preço do ML conferido dentro do frescor (2 h) e GTIN igual ao ISBN;
- (8) no máximo N novos livros por dia e M por gênero (sugestão: 5 e 2);
- (9) `id` novo, que não colide com nenhum `id` já usado, mesmo de livro retirado, porque vira deep link.

**Modo sombra.**
1. A execução diária calcula tudo e grava uma linha JSON por candidato em `curation/AAAA-MM.jsonl`, só de acréscimo, no mesmo branch `price-history`. Onde guardar é a decisão 7.
2. Cada linha tem: `run_at`, `ml_product_id`, `isbn`, `genre`, os componentes (`raw`, `s`, `confidence`, `source`, `fetched_at`), `score`, `confiança`, os `gates` (passou ou falhou, com o motivo) e `would_publish`. **Nada de dado de usuário.**
3. Toda segunda-feira sai um resumo no log do Actions: quantos candidatos teriam sido publicados por gênero, a distribuição dos scores e a lista dos 10 primeiros e dos 10 logo abaixo do corte.
4. **Calibração**, depois de pelo menos 2 semanas e com o passo 0 resolvido:
   1. O Elias marca "publicaria ou não" em uma amostra de cerca de 30 candidatos, metade acima do corte e metade abaixo.
   2. Escolhemos o limiar com precisão de pelo menos 90% nessa amostra que ainda dê pelo menos 1 livro por dia.
   3. Ajustamos os pesos se um componente sozinho decidir mais de 70% dos casos.
   4. Quando houver 30 dias de histórico, refazemos o componente de preço.
   5. Os pesos e o limiar aprovados ficam registrados aqui, com a data. Só então a publicação é ligada.
5. **Orçamento de chamadas:** 1 `/highlights` geral, mais até 25 por gênero, mais `/products/{id}` só dos `PRODUCT` novos, mais `/reviews` só de quem passou nos gates. O job é separado do coletor, porque o coletor tem prazo de 40 s (`ML_DEADLINE_S`). Os limites de taxa do ML para token de app são **não confirmados**.

### 10.4 Links do ML em lote (enquanto não houver método autorizado)

O que muda o desenho: o link do painel é `https://www.mercadolivre.com.br/social/<aff>?matt_word=<aff>&matt_tool=…&forceInApp=true&ref=<cifrado>` e **não contém o id do produto** (ver `collector/catalog.json`). O script não tem como descobrir sozinho a que produto um link pertence. Abrir o link para seguir o redirecionamento não é uma saída, por três motivos:
- seria acessar o site, não a API, o que os termos do programa de desenvolvedores proíbem no item 7.6 (citado na versão do PM, `22548f4`);
- contaria um clique falso;
- o build não quer depender disso.

Por isso o par produto ↔ link é feito pelo Elias, linha a linha, num arquivo com chave.

1. **Fila.** `curator links-todo` escreve `ml_links.tsv` com uma linha por candidato que passou em todos os gates, menos o do link. As colunas são `book_id`, `ml_product_id`, `product_url` e `ml_url` (vazia). O `product_url` é montado pelo código como `https://www.mercadolivre.com.br/p/<MLB>`, validado por `MLB_RE`, e nunca vem de texto da API.
2. **Painel (manual).** O Elias cola as `product_url` no Gerador de links. Segundo terceiros, o gerador aceita "1 ou mais URLs" e só funciona no computador (**não confirmado**: as páginas oficiais deram 403 na pesquisa do PM). Ele cola cada link gerado na coluna `ml_url` da **mesma linha**. O par é feito pelo `book_id` da linha, nunca pela ordem entre arquivos.
3. **Aplicação.** `curator links-apply ml_links.tsv` confere cada linha, uma a uma:
   - o `book_id` e o `ml_product_id` existem entre os candidatos e conferem um com o outro;
   - `affiliate_url({"store": "mercadolivre", "ml_url": raw}, tag, ml_affiliate())` passa, o que roda o `ml_url` e o `check_url` do `build.py` sem afrouxar nada (só o link completo `/social/<aff>`, `matt_word` igual a `ML_AFFILIATE_ID`, chaves em allowlist, sem `meli.la`, ASCII, até 1000 caracteres);
   - o `ref` não se repete no arquivo nem no catálogo, porque `ref` duplicado indica colagem errada;
   - o livro ainda não tem `ml_url`, a não ser com `--replace`.

   A linha válida grava o `ml_url` no `catalog.json`. A linha inválida é listada com o motivo e não grava nada. A linha vazia continua pendente. O teste pytest cobre: link válido, `meli.la`, `matt_word` de outra conta, `ref` duplicado e produto desconhecido.
4. **Limite conhecido.** Nenhuma validação prova que o `ref` aponta para aquele produto. Isso depende do Elias colar na linha certa. A mitigação barata: a coluna `product_url` fica ao lado do link, e o resumo do `links-apply` mostra título ↔ produto para ele bater o olho. A decisão 8 diz se isso basta.
5. **Sem link válido não publica.** Como a Amazon também é manual hoje, isso quer dizer que **nenhum livro sai sem esse passo**. O volume diário do gate 8 deve caber em poucos minutos de painel.
6. O arquivo `ml_links.tsv` não tem segredo, porque o `ml_url` já é público no `catalog.json`. Mesmo assim, não deve ser commitado: é transitório. Sugestão: pô-lo no `.gitignore`.

### 10.5 Decisões em aberto para o Elias

1. **Qual versão desta spec vale:** publicação automática com gates (esta, conforme a decisão de 2026-10-18) ou PR com aprovação humana (branch `worktree-agent-a26264a6033900af8`)? Elas não podem coexistir.
2. **Aprovar os 5 gêneros novos** e os rótulos de §10.1, e a mudança no `GENRES` do `build.py`, pelo `product-manager`.
3. **Mapeamentos ambíguos:** Humor em `ficcao`, LGBTQ+ em `ficcao` e Tecnologia em `estudo`. E também: `literatura-brasileira` fica só manual?
4. **Pesos e limiar iniciais** de §10.3 (35/25/15/25, `score ≥ 70`, `confiança ≥ 0,5`, retirada abaixo de 60 por 2 execuções). Aceita que, na prática, nada publica antes de 30 dias de histórico?
5. **Pedir acesso à Google Trends API (alpha)?** Se não, o peso de Tendência fica ausente para sempre, e talvez seja melhor redistribuí-lo.
6. **Chave de API do Google Books** (cota própria, R$ 0) para avaliações e metadados, ou só Open Library?
7. **Onde guardar o log da sombra e da auditoria:** `curation/AAAA-MM.jsonl` no branch `price-history`? Por quanto tempo?
8. **Fluxo de links em lote de §10.4:** aceita o par por linha, com o limite de não provar o `ref`? Qual o volume máximo por dia (N e M do gate 8)?
9. **Seguem pendentes de §6/§8:** confirmar com o Busqy e com o ML o método contratual; decidir se o lançamento é só ML ou espera a Creators API; definir frequência intradiária e política de retirada.
10. **Liberar o passo 0** (`probe` só leitura com o token de app) como primeira tarefa da entrega 2, antes de qualquer outra implementação.
