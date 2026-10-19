# Spec: área "Curadoria" (livros publicados, com ou sem desconto) e vitrine de ofertas

Status: revista em 2026-10-19 pela decisão A do Elias (seção 0, item 4); decisões em aberto respondidas na rodada 5 (seção 14). Autor: product-manager. Nada implementado. A política (gates, critério "em oferta", volume) está em `curadoria-automatica.md` §10.8, que prevalece sobre este texto.

## 0. Decisões do Elias (2026-10-19)

1. **Ranking e tendências são só internos.** O `/highlights`, o `/trends` e qualquer ranking servem para descobrir e selecionar livros. O site nunca mostra posição, número de vendas nem rótulo derivado do ranking (seção 7).
2. **O site mostra, além das ofertas ativas e verificadas, outras boas opções**, com o ofertasdiscos.com como referência (seção 2). O texto novo do CLAUDE.md está na seção 13, sem edição no arquivo.
3. **Impacto aceito** no volume de links manuais e no `_redirects` (seção 8).
4. **Decisão A (rodada 4):** "vamos seguir com A para uma área do site chamada curadoria (vai ter livros com ou sem desconto), mas no geral a maior busca do site são livros em ofertas". Leitura:
   - o livro entra no catálogo publicado pelos gates de validade, sem bloqueio por desconto (`curadoria-automatica.md` §10.7, decisão 2);
   - **todo livro publicado** com loja fresca aparece na área **Curadoria**, com ou sem desconto;
   - a **vitrine de ofertas** (home, páginas de nicho e de tag, canais) continua só com os livros **em oferta**, pelo critério de `curadoria-automatica.md` §10.8, item 3.

**O que a decisão A mudou nesta spec** (versão anterior no commit da17bb5): sai o "score de curadoria" sem preço, com limiar, sombra e critério de saída próprios; sai o campo `vitrine`/`curadoria` no catálogo; sai o `/r/<id>` para livro sem loja fresca. A área passa a ser uma visão do catálogo publicado, sem regra de entrada própria. Fica bem menor.

## 1. Problema e usuário

**Em uma frase:** quem chega sem um livro em mente quer boas opções de leitura, mesmo fora de promoção; quem chega atrás de desconto (a maioria) quer só ofertas. A área Curadoria atende o primeiro sem diluir a vitrine do segundo. Cada livro dela tem link de afiliado e o botão "me avise se baixar", então o livro sem desconto vira alerta, e o alerta vira clique quando o preço cai.

**Interpretações da decisão A:**
1. **Curadoria = todo o catálogo publicado com loja fresca; vitrine = só em oferta.** **Recomendada e adotada.** Zero campo novo, zero regra de entrada nova.
2. Curadoria só com os livros **sem** oferta (o `/novidades/` de hoje com outro nome). Contradiz "com ou sem desconto". Descartada.
3. Curadoria com seleção própria por score. Era a versão anterior; a decisão A tirou o score da entrada. Descartada.

## 2. O que existe hoje (conferido na `main` em 2026-10-19)

| Item | Estado | Onde |
|---|---|---|
| Oferta × novidade | `oferta` = desconto ≥ 10% sobre o `list_price_cents` da vencedora ou selo "90d"; o resto é "novidade" | `build.py:resolve`, `OFERTA_MIN_DESCONTO` |
| Home | Hero com até 5 (ofertas primeiro, novidades completando), destaques e ofertas ativas só com oferta, seção "Novidades" abaixo | `build.py:home_sections`, `hero_items`, `news` |
| Página de nicho | Ofertas, depois Novidades | `build.py:page` |
| `/novidades/` | Página com os livros sem oferta, link no menu | `build.py` (`internal("/novidades/", …)`) |
| Canais | Só oferta | `build.py` (comentário de `OFERTA_MIN_DESCONTO`) |
| Seção "Em alta" | `<ol>` por `trending_rank`, só com oferta | `build.py:home_sections` |
| Mediana de 90 dias | **Não existe** no contrato nem no coletor | — |
| Rota `/curadoria/` | **Não existe**; o slug também não está em `RESERVED` (proposta de §10.1.1) | — |

**Referência: como o ofertasdiscos.com mostra o que não está em oferta** (conferido em 2026-10-19, home e `/discos`):
- Na home, itens sem desconto aparecem com preço e selos, sem riscado nem percentual.
- Em `/discos` ("Álbuns da seleção"), a lista é só capa ou nome, artista e link, e a introdução diz que, "sem oferta atual, você pode acompanhar os achados pelo BIS" (o bot de lista de desejos).
- **Copiamos:** a separação entre "ofertas" e "seleção" e a chamada para acompanhar pelo bot quando não há oferta.
- **Não copiamos:** "Em alta", "Mais procurados" e a lista numerada (decisão 1).

## 3. Escopo do MVP

**Dentro:**
- Critério "em oferta" de `curadoria-automatica.md` §10.8, item 3, no `resolve` (regra de hoje até 30 dias de histórico; mediana ou selo depois).
- `median_90d_cents` por loja no `offers.json`, calculado pelo coletor.
- Página `/curadoria/` com todos os livros publicados com loja fresca, agrupada por nicho, com âncoras no topo.
- "Curadoria" no menu, no lugar de "Novidades". `/novidades/` passa a redirecionar para `/curadoria/` (301).
- Home e páginas de nicho: a seção "Novidades" vira "Da curadoria" (até 8 livros sem oferta) com o link "Ver toda a curadoria".
- Card sem oferta: preço e horário (há loja fresca, sempre), sem riscado, sem percentual, sem selo de oferta, com "Sem oferta agora" e o botão de alerta.

**Fora (e quando vale fazer):**
- **Páginas `/curadoria/<nicho>/`.** **Quando:** algum nicho passar de 24 livros na área.
- **Livro sem loja fresca na área, sem preço.** Exigiria `/r/<id>` sem preço fresco e `last_active_at` (versão anterior). **Quando:** a área piscar demais com o rodízio do coletor.
- **Nota e número de avaliações no card** (Google Books). **Quando:** os termos de exibição permitirem e houver pedido.
- **Post da curadoria nos canais.** Os canais seguem só com ofertas. **Quando:** houver uma razão de clique que não seja popularidade.
- **Selo de popularidade medido por nós** (cliques no `/r/`). **Quando:** houver contador próprio, sem dado do ranking do ML.

## 4. Quem aparece na área

- **Todo livro do `offers.json` com pelo menos uma loja dentro do frescor** (o mesmo conjunto que o `resolve` devolve hoje). Não há regra de entrada própria: quem passou nos gates de validade e tem preço fresco está na área.
- Livros manuais (escolhidos pelo Elias) e automáticos aparecem do mesmo jeito.
- Ordem: uma seção (`<h2>`) por gênero presente, na ordem de `GENRES`, e depois uma por tag (`lgbtqia`), só as que têm livro. Dentro da seção, entrada mais recente primeiro (`history_since`) e, no empate, o título. **Nunca** pelo score nem pela posição no ML (seção 7).
- No topo, um `<nav>` com âncoras (`/curadoria/#manga`). Sem JS; a CSP fica igual.

## 5. Relação com a vitrine de ofertas

- **Em oferta** (critério de §10.8, item 3): aparece na área Curadoria **e** na vitrine (hero, destaques, ofertas ativas, página de nicho, canais).
- **Sem oferta:** aparece só na área Curadoria e, como complemento, na seção "Da curadoria" da home e do nicho. Nunca nos destaques, nas ofertas ativas, na contagem de ofertas nem nos canais.
- **Hero:** continua como está na `main` (ofertas primeiro, completando com livros sem oferta quando há menos de 5). Decidido na rodada 5.
- **Sem loja fresca:** sai de tudo, como hoje.
- **Regra 4 do CLAUDE.md:** o rodapé com o aviso de associado e "o preço final é o da loja" já sai em todas as páginas. A introdução da área repete a frase (seção 7).

## 6. Dados e contrato

- **Catálogo:** nenhum campo novo.
- **`data/offers.json` v2:** `median_90d_cents` por loja, opcional. Mediana do menor preço de cada dia BRT nos dias 8 a 90 antes da coleta, a partir do `price_history`. Sem histórico suficiente, ausente. Mudança de contrato em `comparacao-lojas.md`, pelo product-manager.
- **Validação:** o build recusa `median_90d_cents` não inteiro ou ≤ 0, como faz com `lowest_90d_cents`.
- **Dado de usuário:** nenhum novo. O botão de alerta segue `alerta-de-preco.md`, que já define onde fica o `chat_id`, por quanto tempo e como o usuário apaga.

## 7. Termos de uso: regra da área (decisão 1 do Elias)

**Fato** (`curadoria-e-links.md` A.1): o item 5.4 dos [Termos do Programa de Desenvolvedores do ML](https://developers.mercadolivre.com.br/pt_br/termos-e-condicoes) exige autorização expressa para publicar estatística de vendas, volume vendido por categoria e taxas de conversão. A posição no `/highlights` é ranking de vendas do ML.

**Regra:** `/highlights`, `/trends`, `salesRank` e qualquer outro ranking são **só internos**. Nada derivado deles aparece no site.

**Proibido na área e em qualquer página:**
- posição ou número: "nº 3", "3º", "top 10", "#1";
- "mais vendido", "best-seller", "campeão de vendas", "mais procurado";
- rótulo derivado do ranking, mesmo sem número: "Em alta", "Tendência", "Popular", "Bombando" e afins;
- contagem de vendas, compras ou avaliações;
- ordem que reproduza o ranking: nada de `<ol>` de livros e nada de ordenar pela posição ou pelo score;
- listas de terceiros (Nielsen-PublishNews, Veja, Mais Vendidos da Amazon): nem copiar, nem citar, nem coletar;
- logo ou selo de loja ou de ranking.

**Permitido:**
- Menu: **"Curadoria"**.
- `<h1>`: **"Curadoria: livros que valem a leitura"**.
- Introdução (texto fixo):
  > Uma seleção de livros escolhidos por regras a partir de sinais públicos e por nós. Alguns estão em oferta, outros não. O preço foi verificado no horário indicado, e o preço final é o da loja. Sem oferta agora? Crie um alerta e avisamos quando o preço baixar.
- No card: desconto, "menor preço em 90 dias" e o horário da verificação, só quando o livro está em oferta ou tem o selo.
- `<meta name="description">`: "Livros selecionados, com e sem oferta, por nicho."

**Na home:** a seção "Em alta" usa `<ol>` ordenada por `trending_rank`. O `trending_rank` **nunca** pode vir do `/highlights`, do `/trends` nem do `salesRank`. Como não há outra fonte hoje, a seção fica desligada. O frontend-developer troca a `<ol>` por `<ul>` e documenta a regra no `BOOK_KEYS`.

## 8. Impacto no `_redirects` e no trabalho manual

- **`_redirects`:** a área não cria livro novo; ela mostra o catálogo publicado, que já conta nos 500 ativos (`curator.md` 5.6). Entra só uma regra: `/novidades/ /curadoria/ 301`.
- **Links do ML e Amazon:** nenhum link extra. O custo é o do volume de 50 por dia, já decidido.
- **Coletor:** sem mudança de volume; só o cálculo da mediana a partir do `price_history`, que já é lido para o `lowest_90d_cents`.

## 9. Fluxo do usuário

1. O leitor abre o site. A home mostra as ofertas (hero, destaques, ofertas ativas) e, mais abaixo, "Da curadoria", com alguns livros sem oferta e o link "Ver toda a curadoria".
2. Em `/curadoria/`, lê a introdução e toca no nicho que quer (âncora), por exemplo "Mangá e HQ".
3. Vê os cards. Os em oferta têm riscado, percentual e selo; os outros têm preço, horário e "Sem oferta agora".
4. Toca no botão e vai, por `/r/<id>`, para a loja com o nosso link de afiliado.
5. Ou toca em "Me avise se baixar (Telegram)" e cria um alerta no bot, quando o bot estiver no ar.

**Elias:** nada novo. O que ele publica (manual ou pelo `curator`) aparece na área sozinho.

## 10. Critérios de aceite

Critério "em oferta" (`python3 build.py --selftest`, sem rede):
1. Loja vencedora com menos de 30 dias de histórico: oferta se e só se o "de/por" dá ≥ 10%. É o comportamento de hoje.
2. Com 30 dias ou mais e `median_90d_cents`: oferta se `price_cents ≤ 0,85 × median_90d_cents` ou selo `"90d"`; um "de/por" de 40% sem isso **não** é oferta.
3. Com 30 dias ou mais e sem `median_90d_cents`: cai na regra do critério 1.
4. Amazon vencedora com série manual abaixo da cobertura mínima (80%, padrão provisório, `curator.md` 5.7): regra do critério 1. Com 80% ou mais, vale o critério 2.
5. "Menor preço desde" (selo `"since"`) não torna o livro oferta.

Página e vitrine:
6. Livro fresco sem oferta aparece em `/curadoria/` e em "Da curadoria", e **não** aparece nos destaques, nas ofertas ativas, na contagem de ofertas nem na seleção dos canais.
7. Livro em oferta aparece em `/curadoria/` e na vitrine.
8. `/curadoria/index.html` sai sempre que houver livro fresco; o menu tem "Curadoria" e não tem mais "Novidades"; `_redirects` tem `/novidades/ /curadoria/ 301`.
9. Uma seção por gênero presente, na ordem de `GENRES`, depois as tags; `<nav>` com âncoras; dentro da seção, ordem por `history_since` desc e título. Nenhuma `<ol>` na página.
10. O HTML de `/curadoria/` e da home não casa com `(?i)\bn[º°o]\.?\s*\d|\b\d+\s*[ºª°]|\btop\s*\d|mais\s+vendid|mais\s+procurad|best.?seller|em\s+alta|tend[êe]ncia|\d+\s*(vendid|compra|avalia)`. O teste roda com dados de exemplo que incluem `trending_rank`. A home não tem `<ol>` de livros.
11. O rodapé com o aviso de associado e "o preço final é o da loja" está em `/curadoria/`, e a introdução tem "o preço final é o da loja".
12. Título e autor saem escapados (`html.escape`), sem `innerHTML`. Os testes de XSS do selftest valem para a página nova.
13. `curadoria` e `novidades` são slugs reservados: `GENRES` e `TAGS` não podem usá-los.
14. `median_90d_cents` inválido quebra o build; o coletor calcula a mediana só com os dias 8 a 90 (pytest com uma alta nos últimos 7 dias que não muda a mediana).

## 11. Divisão por agent (ordem de execução)

1. **collector-engineer:** `median_90d_cents` por loja no `offers.json` (critério 14); `curator.py` sem filtro nem ordenação por desconto na entrada (`curator.md` §15, item 5).
2. **frontend-developer:** critério "em oferta" no `resolve` (critérios 1 a 5); página `/curadoria/`, menu, seção "Da curadoria" no lugar de "Novidades", `/novidades/` → `/curadoria/` no `_redirects`, `curadoria` e `novidades` em `RESERVED`, `<ol>` → `<ul>` no "Em alta" (critérios 6 a 13). Com `frontend-design` e `web-design-guidelines`.
3. **security-auditor:** a regra nova do `_redirects` (destino interno, sem open redirect), XSS na página nova, CSP igual, o filtro do critério 10. Rodar `/security-review`.
4. **code-reviewer:** um PR para o coletor (1), um para o build (2), com `web-design-guidelines`. O PR do build é sensível (toca o `_redirects`).
- **alerts-engineer:** nada. Os canais continuam só com ofertas, e o botão de alerta já existe no card.

## 12. Riscos

**Regras inegociáveis**
- *Regra 1 (Amazon):* nada da área vem de página da Amazon. O preço da Amazon é o digitado pelo Elias (§10.5).
- *Regra 2 (ML):* o link continua sendo o do painel; a área não cria link novo.
- *Regra 3:* nenhuma credencial nova.
- *Regra 4:* o preço só aparece fresco, com horário, e com "o preço final é o da loja" (critério 11). O rótulo de oferta só aparece pelo critério de §10.8, que evita chamar de oferta um "de/por" maquiado depois de 30 dias de histórico.

**Termos**
- ML 5.4: o ranking entra só na seleção, nunca na tela (seção 7, critério 10). **Inferência, risco baixo:** sem posição, número, rótulo e ordem de ranking, a área não publica estatística de vendas. Vale incluir a área no pedido de autorização por escrito ao ML que já está pendente (B1 de `curadoria-e-links.md`).
- Amazon 2(h): a mediana da Amazon usa a mesma série de preço guardada com risco aceito (decisão 7 de §10.6). Se a resposta dos Associados for negativa, a série da Amazon é apagada e a Amazon cai na regra de menos de 30 dias.

**Produto**
- **Vitrine magra no começo:** livro sem "de/por" ≥ 10% fica só na Curadoria. Mitigação: o volume de 50 por dia e a seção "Da curadoria" na home.
- **Menos ofertas depois de 30 dias:** a regra da mediana é mais dura que o "de/por". É o objetivo (oferta de verdade), mas a contagem de ofertas vai cair quando os primeiros livros completarem 30 dias. O Elias pode ajustar os 85% (decisão 4).
- **Confusão de nome** com "Destaques da curadoria" da home, que são ofertas com `featured`. O Elias decidiu manter o nome (rodada 5); a introdução da área e o menu dizem "Curadoria" sem "Destaques".

**Custo:** R$ 0. Nenhuma chamada nova de API.

**LGPD:** nenhum dado de usuário novo.

## 13. Mudança no CLAUDE.md (texto aprovado pelo Elias na rodada 5; aplicar em outro PR)

Hoje, em "Decisões tomadas":
> **Curadoria, não despejo.** O site mostra ofertas ativas e verificadas. Oferta vencida sai da lista.

Proposta:
> **Curadoria, não despejo.** A vitrine (home, nichos e canais) mostra ofertas ativas e verificadas: "de/por" de pelo menos 10% enquanto o livro tem menos de 30 dias de histórico, e depois preço até 85% da mediana de 90 dias ou o menor preço em 90 dias. A área Curadoria mostra todos os livros publicados, com ou sem desconto, como o ofertasdiscos.com faz com a "seleção". Livro sem preço fresco sai das duas. Preço só aparece dentro do prazo de frescor, com o horário da verificação e o aviso de que o preço final é o da loja. Rankings e tendências das lojas servem só para escolher livros: o site nunca mostra posição, número de vendas, rótulo derivado de ranking nem lista copiada de terceiros.

## 14. Decisões do Elias (rodada 5, 2026-10-19)

Registro em `curadoria-automatica.md` §10.8, "Respostas do Elias". Resumo:
1. **Retirada:** mix de (a) e (b): sai após 30 dias sem anúncio ativo (todos) e após 30 dias sem entrar em oferta (só automáticos; manuais isentos). Detalhe em §10.8, item 6.
2. **Hero:** (a), completa com livros sem oferta.
3. **"Destaques da curadoria":** mantém o nome.
4. **Critério "em oferta":** aprovado como está.
5. **Texto do CLAUDE.md** (seção 13): aprovado; a edição sai em outro PR.
6. **Pendências do CLAUDE.md:** continuam registradas abaixo. Cobertura mínima da série da Amazon: 80% como padrão provisório, até o Elias decidir.

Texto original das opções, para histórico:

1. **Retirada "por 30 dias sem oferta"** (§10.7, decisão 4): (a) **sai quem passou 30 dias sem anúncio ativo em nenhuma loja (recomendado e provisório)**, porque a Curadoria aceita livro sem desconto; (b) sai quem passou 30 dias sem entrar em oferta, com exceção dos livros manuais, o que gira o catálogo para promoções e abre espaço nos 500. A (b) faz sentido se o teto de 500 encher rápido.
2. **Hero da home:** (a) **manter como está, completando com livros sem oferta quando há menos de 5 (recomendado)**; (b) só ofertas, mesmo que o hero fique menor ou some.
3. **Nome da seção "Destaques da curadoria" da home:** (a) **renomear para "Destaques" (recomendado)**, para não confundir com a área; (b) manter.
4. **Números do critério "em oferta"** (decisão de produto derivada da escolha A, §10.8): (a) **10% no "de/por", 30 dias, 85% da mediana dos dias 8 a 90, ou o selo de 90 dias (recomendado)**; (b) ajustar algum deles.
5. **Texto exato do CLAUDE.md:** aprovar a redação da seção 13 ou ajustar.
6. **Pendências do CLAUDE.md que afetam a área:** a Creators API ainda não liberada mantém a Amazon manual, com histórico esparso, e a pergunta por escrito aos Associados (decisão 7 de §10.6) vale também para a mediana da Amazon. A cobertura mínima da série manual está em 80% como padrão provisório (`curator.md` 5.7).
