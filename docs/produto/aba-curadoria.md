# Spec: aba "Curadoria" (outras boas opções, com ou sem oferta)

Status: proposta, 2026-10-19, com 3 decisões do Elias já incorporadas (seção 0). Autor: product-manager. Nada implementado. Depende da entrega 2 do `curator` (`docs/produto/curator.md`) e da pontuação de `curadoria-automatica.md` §10.3.

## 0. Decisões do Elias (2026-10-19)

1. **Ranking e tendências são só internos.** O `/highlights`, o `/trends` e qualquer ranking servem para descobrir e selecionar livros. O site nunca mostra posição, número de vendas nem rótulo derivado do ranking. É regra da aba (seção 7), não ponto em aberto.
2. **O site mostra, além das ofertas ativas e verificadas, outras boas opções**, com o ofertasdiscos.com como referência. O layout e o texto da aba seguem o que a referência faz com itens sem oferta (seção 2). O texto novo do CLAUDE.md está na seção 13, sem edição no arquivo.
3. **Impacto aceito** no volume de links manuais e no `_redirects` (seção 8). Segue a proposta.

## 1. Problema e usuário

**Pedido do Elias:** "no processo de curadoria, vamos trazer livros que seguem a regra da curadoria de muitas vendas, buscados etc. para termos uma aba que seja de curadoria e não necessariamente ofertas; pode ter ofertas, mas não é obrigatoriedade".

**Em uma frase:** o leitor que chega sem um livro em mente quer boas opções de leitura, mesmo que não estejam em promoção. A aba dá esse motivo para voltar ao site, e cada livro dela tem link de afiliado e o botão de alerta de preço ("me avise se baixar"). O livro que hoje não tem desconto vira um alerta, e o alerta vira clique quando o preço cai.

**Interpretações:**
1. **Aba com os livros que passam na pontuação sem o componente de preço** (demanda, avaliações, tendência), com preço quando houver preço fresco. **Recomendada.**
2. **Lista de "mais vendidos"** copiada do ML, da Amazon ou da Nielsen. Esbarra no item 5.4 dos termos de dev do ML e é scraping ou cópia de lista de terceiros. **Descartada.**
3. **Lista editorial à mão** do Elias. Não escala e não é o que ele pediu, mas cabe como complemento (decisão 2).

## 2. O que existe hoje (conferido em 2026-10-19)

| Item | Estado | Onde |
|---|---|---|
| Vitrine | Todo livro do catálogo com loja dentro do frescor aparece; sem nenhuma loja fresca, sai. Sem corte por desconto no build. O build falha se nenhuma oferta estiver fresca | `build.py:resolve` |
| Seção "Em alta" na home | Existe: aparece quando algum livro tem `trending_rank`, ordenada por ele, numa `<ol>` | `build.py:home_sections` |
| Seção "Destaques da curadoria" na home | Existe: livros com `featured: true` (escolha manual) | `build.py:home_sections` |
| Pontuação sem preço | **Não existe.** A de §10.3 tem os 4 componentes e ainda está só no papel | — |
| Rota `/curadoria/` | **Não existe**. O slug também não está reservado na proposta de `RESERVED` de §10.1.1 (`r`, `privacidade`, `canais`) | — |
| `/r/<id>` | Só para livro com loja fresca; o resto cai na home pelo curinga | `build.py:redirects` |
| Alerta de preço | Botão no card quando `TELEGRAM_BOT_USERNAME` existe; o bot ainda não está implementado | `build.py:tg_alert_url`, `alerta-de-preco.md` |

**Referência: como o ofertasdiscos.com mostra o que não está em oferta** (conferido em 2026-10-19, home e `/discos`):
- **Na home,** itens sem desconto aparecem misturados à grade "Ofertas ativas", com preço e selos como "Novo", "Edição especial" e "Em alta", sem riscado nem percentual. Há ordenação "Mais procurados" e uma lista numerada "Em alta agora" (1 a 10), sem preço.
- **Em `/discos`** ("Discos de vinil para sua coleção", seção "Álbuns da seleção"), a lista é só capa ou nome, artista e link para a página permanente do álbum. Não tem preço, selo nem número. A introdução diz que as páginas "acompanham títulos identificados no catálogo da curadoria" e que, "sem oferta atual, você pode acompanhar os achados pelo BIS" (o bot de lista de desejos no Telegram).
- **O que copiamos:** a separação entre "ofertas" e "seleção", a lista de seleção sem preço como padrão e a chamada para acompanhar pelo bot quando não há oferta.
- **O que não copiamos:** o "Em alta", o "Mais procurados" e a lista numerada. Lá, a popularidade parece vir dos cliques no próprio site (`placement=trending` nos links, **inferência**). Aqui ela viria do ranking do ML, e a decisão 1 proíbe exibir qualquer coisa derivada dele.

## 3. Escopo do MVP

**Dentro:**
- Pontuação de curadoria calculada no mesmo job do `curator`, em modo sombra primeiro (seção 4).
- Campos novos no catálogo e no `offers.json` (seção 6).
- Página `/curadoria/`, agrupada por nicho, com âncoras no topo para filtrar (seção 5).
- Link "Curadoria" no menu, só quando a aba tiver livro.
- Card da curadoria: o mesmo card da vitrine. Com loja fresca, mostra preço e horário. Sem loja fresca, mostra só o botão da loja, sem preço.
- Nenhum rótulo de popularidade (decisão 1 do Elias, seção 0). Card sem oferta com a chamada "Sem oferta agora" e o botão de alerta, no lugar do "acompanhe pelo BIS" da referência.
- Entrada manual (`origem: "manual"`), se o Elias aprovar a decisão 2.

**Fora (e quando vale fazer):**
- **Páginas `/curadoria/<nicho>/` ou bloco de curadoria nas páginas de nicho.** **Quando:** algum nicho passar de 12 livros na aba.
- **Nota e número de avaliações no card** (Google Books). Exige conferir os termos de exibição do Google Books e esbarra na regra de não exibir contagem. **Quando:** houver pedido e os termos permitirem.
- **Selo "Prêmio Jabuti"** e similares. **Quando:** houver um campo próprio, alimentado à mão, com a fonte.
- **Post da curadoria no canal do Telegram.** Os canais continuam só com ofertas (`distribuicao-canais.md`). **Quando:** o canal tiver volume e houver uma razão de clique que não seja popularidade.
- **Selo de popularidade medido por nós** (cliques no `/r/`, como o `placement=trending` da referência). Exige contador próprio, que `distribuicao-canais.md` deixou fora. **Quando:** houver medição de clique; mesmo assim, não pode misturar dado do ranking do ML.
- **Teaser da curadoria na home.** **Quando:** a aba tiver pelo menos 8 livros por 2 semanas seguidas.
- **Demanda pela Amazon (`salesRank`).** **Quando:** a Creators API for liberada. É o que mais vai encher a aba.

## 4. Critério de entrada

### 4.1 Score de curadoria

Mesmos componentes, fórmulas e confianças de `curadoria-automatica.md` §10.3, **sem o componente Preço**:

| Componente | Peso | Fonte hoje |
|---|---:|---|
| Demanda `s_d` | 25 | Posição no `/highlights` do ML (confiança 0,6), mais o bônus do `/trends` |
| Avaliações `s_r` | `15·min(1; v/50)` | Google Books, com `GOOGLE_BOOKS_API_KEY` (ausente com `v < 10`) |
| Tendência `s_t` | 25 | Trends API alpha (ausente até sair o acesso) |

- `score_cur = 100 × Σ w_i·s_i / Σ w_i`, só com os componentes presentes.
- `confiança_cur = Σ w_i·confidence_i / 65`. O 65 é a soma máxima dos pesos sem o preço; tem o mesmo papel do 100 em §10.3 (componente ausente baixa a confiança, não o score).

**Regra de entrada (recomendada, decisão em aberto 1):** `score_cur ≥ 70` **e** `confiança_cur ≥ 0,45` **e** Demanda presente. Os gates 1, 4, 6, 7, 9 e 10 de §4/§10.3 continuam valendo: identidade, sem duplicado, gênero mapeado, `id` novo, pelo menos uma loja com link de afiliado válido. O gate 2 (oferta ativa com preço fresco) **não** vale: vale o de disponibilidade da seção 5.3.

**O que isso quer dizer hoje, sem a Trends API** (conta de §10.3):
- Só `/highlights`: confiança = 25·0,6/65 = 0,23. Não entra.
- `/highlights` + Google Books com 50 avaliações ou mais: (15 + 15)/65 = 0,46. Entra se o score passar de 70.
- Com média bayesiana de 4,5 nas avaliações (`s_r` ≈ 0,67), o score passa de 70 só com `s_d ≥ 0,72`, ou seja, **até a ~7ª posição do `/highlights`** (~9ª com o bônus do `/trends`).
- Produto vindo só do `/trends` (posição a partir de 101) tem `s_d` = 0,1 e não entra.

Ou seja: com as APIs de hoje, a aba automática é **pequena** (os livros do topo do ranking do ML que também são bem avaliados no Google Books, uns 5 a 10 por vez) e cresce pela permanência de 30 dias (5.2). A aba não afirma nada sobre procura: a regra só decide quem entra. Ela enche de verdade com a Trends API e com o `salesRank` da Amazon. Por isso recomendo a entrada manual (decisão 2).

### 4.2 Encaixe no modo sombra (§10.4 de lá, §10.3 item 1 a 6)
- A mesma linha do `curation/AAAA-MM.jsonl` ganha um bloco `curadoria`: `score`, `confianca`, componentes usados e `would_curate`. Nenhum job novo, nenhuma chamada nova.
- **Critério de saída próprio** (recomendado, decisão 3), porque a curadoria não depende dos 30 dias de histórico de preço:
  - pelo menos 14 dias corridos;
  - pelo menos 30 rótulos cegos do Elias ("poria na aba de curadoria?"), metade acima do corte e metade com `score_cur` entre 50 e 70;
  - precisão ≥ 0,90 e recall ≥ 0,60;
  - os valores finais registrados aqui, com data e o "aprovado" do Elias.
- Se a precisão não chegar a 0,90, o limiar sobe de 5 em 5. O limiar não baixa para encher a aba.
- Com o critério atingido, a aba pode ligar antes da publicação automática de ofertas.

## 5. Relação com a vitrine de ofertas

### 5.1 Um livro pode estar nas duas
Sim. O livro tem uma lista `vitrine` com `"ofertas"`, `"curadoria"` ou as duas.
- **Ofertas** continua com as regras de hoje e as de §10.3 (score com preço, retirada abaixo de 60).
- **Curadoria** segue a seção 4.
- Saiu de ofertas, mas segue no critério da curadoria? Fica só na curadoria. Entrou em promoção? Aparece nas duas.
- Livro com `vitrine` sem `"ofertas"` **não aparece** na home, nas páginas de nicho nem nos canais. Isso é necessário porque hoje "catálogo = vitrine": sem esse campo, todo livro da curadoria com preço fresco viraria "oferta" sem desconto.
- Livros já publicados: sem o campo, vale `["ofertas"]`. Nada muda para eles.

### 5.2 Permanência
- Automático: o livro fica na aba enquanto `hoje − visto ≤ 30 dias`, em que `visto` é o último dia em que ele passou no critério 4.1. Assim a aba não pisca a cada mudança do `/highlights`. Decisão 9.
- Manual: sem prazo. Sai quando o Elias tira.

### 5.3 Preço, frescor e disponibilidade
- **Com loja dentro do frescor** (`FRESH`: ML 2 h, Amazon 12 h): mostra o preço, o "verificado às HH:MM", a seta da outra loja, o desconto e o selo, exatamente como o card da vitrine. Nada de preço velho como atual.
- **Sem loja fresca:** mostra o livro sem preço, com o botão "Ver no Mercado Livre" (ou "Ver na Amazon"), a linha "Sem oferta agora. Preço na loja." e, com o bot no ar, "Me avise se baixar (Telegram)". Não mostra "a partir de", preço antigo nem desconto. É o equivalente do "acompanhe pelo BIS" da referência.
- **Disponibilidade:** o livro só aparece na aba se alguma loja teve anúncio novo ativo coletado nas últimas 24 h (última linha do `price_history` com `checked_at` ≤ 24 h). Sem isso, sai da aba. Isso cumpre os itens 5.2 e 5.3 dos termos de dev do ML (tirar o que não está disponível; atualizar a cada 24 h).
- **Regra 4 do CLAUDE.md:** o rodapé com o aviso de associado e "o preço final é o da loja" já sai em todas as páginas e vale para `/curadoria/`. A introdução da página repete a frase (seção 7).

### 5.4 Link de afiliado
- O mesmo `/r/<id>`, gerado pelo build com `affiliate_url` + `check_url`, a mesma allowlist de hosts e só para `id` presente no `offers.json`. Nenhum dado da requisição vira destino.
- Com loja fresca: `/r/<id>` vai para a vencedora, como hoje.
- **Sem loja fresca (novo):** `/r/<id>` vai para a loja com a coleta mais recente dentro das 24 h da seção 5.3, com o mesmo link validado. Isso muda o comportamento de hoje ("vencido cai na home") só para livros da aba: o link não afirma preço, então mandar para a página do livro é correto.
- Livro que não está na aba nem em ofertas continua caindo na home pelo curinga.
- Os canais não postam livros da curadoria, então não há `/tg` nem `/wa` estáticos para eles. Com R1 (`curator.md` 5.6), as regras dinâmicas cobrem algum link antigo.

### 5.5 Filtro por nicho e tag
- A aba é filtrável por nicho: a página `/curadoria/` tem uma seção (`<h2>`) por gênero presente, na ordem de `GENRES`, e depois uma por tag (`lgbtqia`), só as que têm livro.
- No topo vai um `<nav>` com âncoras (`/curadoria/#manga`). Não usa JS, e a CSP fica igual.
- Livro com tag aparece na seção do gênero e na da tag, como já acontece com `/ficcao/` e `/lgbtqia/` (§10.1.1).
- Dentro de cada seção, a ordem é por `desde` (entrada mais recente primeiro) e, no empate, pelo título. **Não** ordenar pelo score nem pela posição no ML (seção 7).

## 6. Dados e contrato

**`collector/catalog.json`** (nível do livro, ao lado de `genre` e `tags`):
- `vitrine`: lista, subconjunto de `["ofertas", "curadoria"]`, sem repetição. Ausente = `["ofertas"]`.
- `curadoria`: objeto, obrigatório se e só se `"curadoria"` estiver em `vitrine`:
  - `origem`: `"auto"` ou `"manual"`;
  - `desde`: data `AAAA-MM-DD`;
  - `visto`: data `AAAA-MM-DD`, obrigatória no `auto` e proibida no `manual`.
- Quem escreve: o `curator` (só no `auto`, e só depois da saída da sombra) e o Elias (no `manual`). O `curator` nunca mexe em entrada `manual`.

**`data/offers.json` v2:** os mesmos dois campos, copiados pelo coletor, mais `last_active_at` por loja (o `checked_at` da última linha com anúncio novo ativo). Mudança de contrato em `comparacao-lojas.md`, campos opcionais, pelo product-manager.

**Validação:** o build e o `load_catalog` recusam valor fora do conjunto, chave desconhecida em `curadoria`, data inválida ou `visto` no futuro, exatamente como fazem com `genre`.

**Dado de usuário:** nenhum novo. O botão de alerta segue `alerta-de-preco.md`, que já define onde fica o `chat_id`, por quanto tempo e como o usuário apaga.

## 7. Termos de uso: regra da aba (decisão 1 do Elias)

**Fato** (`curadoria-e-links.md` A.1): o item 5.4 dos [Termos do Programa de Desenvolvedores do ML](https://developers.mercadolivre.com.br/pt_br/termos-e-condicoes) exige autorização expressa para publicar estatística de vendas, volume vendido por categoria e taxas de conversão. A posição no `/highlights` é ranking de vendas do ML.

**Regra:** `/highlights`, `/trends`, `salesRank` e qualquer outro ranking são **só internos**. Servem para descobrir e pontuar. Nada derivado deles aparece no site.

**Proibido na aba e em qualquer página:**
- posição ou número: "nº 3", "3º", "top 10", "#1";
- "mais vendido", "best-seller", "campeão de vendas", "mais procurado";
- **rótulo derivado do ranking, mesmo sem número:** "Em alta", "Tendência", "Popular", "Bombando" e afins. Neste projeto, "Em alta" só pode significar "está no ranking do ML ou no `/trends`", porque não temos outra medida de procura. Pelo item 5.4, ele pode ser lido como publicação de estatística de vendas. **O caminho mais seguro é não usar rótulo nenhum de popularidade**;
- contagem de vendas, compras ou avaliações;
- ordem que reproduza o ranking: nada de `<ol>` e nada de ordenar pelo `score_cur`, que hoje é quase todo demanda;
- listas de terceiros (Nielsen-PublishNews, Veja, Mais Vendidos da Amazon): nem copiar, nem citar, nem coletar;
- logo ou selo de loja ou de ranking.

**Permitido** (descreve a seleção, não o livro):
- Menu: **"Curadoria"**.
- `<h1>`: **"Curadoria: outras boas opções"**.
- Introdução (texto fixo):
  > Além das ofertas, uma seleção de livros que valem a leitura, escolhidos por regras a partir de sinais públicos e por nós. Nem todo livro daqui está em promoção. Quando aparece preço, ele foi verificado no horário indicado, e o preço final é o da loja. Sem oferta agora? Crie um alerta e avisamos quando o preço baixar.
- No card: nenhum rótulo de popularidade. Os selos que já existem e não vêm de ranking continuam: desconto, "menor preço em 90 dias" e o horário da verificação, só quando há loja fresca.
- `<meta name="description">`: "Outras boas opções de livros, com e sem oferta, por nicho."

**Na home** (consequência da regra): a seção "Em alta" usa `<ol>` ordenada por `trending_rank`. O `trending_rank` **nunca** pode vir do `/highlights`, do `/trends` nem do `salesRank`. Como não há outra fonte hoje, a seção fica desligada (é o que acontece sem `trending_rank`). O frontend-developer troca a `<ol>` por `<ul>` e documenta essa regra no `BOOK_KEYS`.

## 8. Impacto no `_redirects` e no trabalho manual

- **`_redirects`:** cada livro da aba gera regra só para o que ele usa: `/r/<id>` e `/r/<id>/<loja>` por loja fresca. Sem loja fresca, só `/r/<id>`. Com R1 (`curator.md` 5.6), são 1 a 3 regras por livro; sem R1, 4 a 5. A aba deve ter uns 5 a 30 livros enquanto não houver Trends nem Creators API, ou seja, até 90 regras. Os livros da aba **contam no `ACTIVE_MAX`**, porque o coletor também os monitora.
- **Coletor:** os livros da aba entram no rodízio do `collect_ml` como os outros. É o gargalo real (`curator.md` 5.6), mas o volume da aba é pequeno.
- **Links do ML:** cada livro automático da aba precisa de um link do painel, pela mesma fila `ml_links.tsv`. Com a fonte de hoje, são poucos por semana. **Não conta** na meta de 50 por dia, que é de ofertas.
- **Amazon manual:** os livros da aba disputam as mesmas 5 linhas por dia da `amazon-todo` (`curator.md` 5.7), ordenados por `max(score, score_cur)`. Como são os de maior procura, são bons candidatos para chegar às 10 vendas que liberam a Creators API. Não há linha extra.

## 9. Fluxo do usuário

1. O leitor abre o site e vê "Curadoria" no menu, ao lado de "Todos" e dos nichos.
2. Em `/curadoria/`, lê a introdução e toca no nicho que quer (âncora), por exemplo "Mangá e HQ".
3. Vê os cards. Alguns têm preço e horário ("Ver no Mercado Livre por R$ 39,90", "verificado às 10h12"); outros, "Sem oferta agora. Preço na loja." e o botão da loja.
4. Toca no botão e vai, por `/r/<id>`, para a loja com o nosso link de afiliado.
5. Ou toca em "Me avise se baixar (Telegram)" e cria um alerta de preço no bot, quando o bot estiver no ar.

**Elias:**
1. Durante a sombra, rotula a amostra da curadoria junto com a das ofertas (segunda-feira).
2. Depois da saída da sombra, gera os links do ML dos livros novos da aba pela mesma fila de sempre.
3. Se aprovar a decisão 2, põe à mão no `catalog.json` os livros que quer na aba (por exemplo, `literatura-brasileira`, que o ML não mapeia).

## 10. Critérios de aceite

Pontuação (pytest, sem rede):
1. `score_cur` e `confiança_cur` ignoram o componente Preço. Com só `/highlights`, a confiança é 0,23; com `/highlights` e Google Books com `v ≥ 50`, é 0,46.
2. Sem Demanda presente, `would_curate` é falso, mesmo com score ≥ 70.
3. Na sombra, `catalog.json` e `offers.json` não mudam; só o bloco `curadoria` do `jsonl`.

Dados:
4. `vitrine` fora de `{"ofertas","curadoria"}`, com repetição ou sem `curadoria` quando a lista tem `"curadoria"` quebra o build e o `load_catalog`. `visto` em entrada `manual` também.
5. Livro sem `vitrine` se comporta como hoje (selftest atual verde sem mudança de dado).
6. Livro com `vitrine: ["curadoria"]` e preço fresco **não** aparece na home, nas páginas de nicho nem na seleção dos canais.

Página:
7. `/curadoria/index.html` só é gerado se houver livro na aba; sem ele, o menu não tem o link e o build não falha. O build também não falha quando há curadoria e nenhuma oferta fresca.
8. Uma seção por gênero presente, na ordem de `GENRES`, depois as tags; `<nav>` com âncoras; dentro da seção, ordem por `desde` desc e título. Nenhuma `<ol>` na página.
9. Card sem loja fresca: sem preço, sem desconto, sem selo, com "Preço na loja" e o botão `/r/<id>`. Card com loja fresca: igual ao da vitrine, com o horário.
10. Livro cuja última coleta com anúncio ativo tem mais de 24 h não aparece. Automático com `visto` de mais de 30 dias não aparece.
11. O HTML de `/curadoria/` e da home não casa com `(?i)\bn[º°o]\.?\s*\d|\b\d+\s*[ºª°]|\btop\s*\d|mais\s+vendid|mais\s+procurad|best.?seller|em\s+alta|tend[êe]ncia|\d+\s*(vendid|compra|avalia)`. O teste roda com dados de exemplo que incluem `trending_rank` e `curadoria`. A home não tem `<ol>` de livros.
12. O rodapé com o aviso de associado e "o preço final é o da loja" está em `/curadoria/`, e a introdução tem "o preço final é o da loja".
13. Título e autor saem escapados (`html.escape`), sem `innerHTML`. Os testes de XSS do selftest valem para a página nova.

Links:
14. Todo `/r/<id>` de livro da aba tem destino validado por `check_url` e host em `ALLOWED_HOSTS`. Livro da aba sem loja fresca gera exatamente uma regra `/r/<id>`, para a loja com a coleta ativa mais recente.
15. Livro fora da aba e sem loja fresca continua sem regra própria e cai no curinga.
16. `curadoria` é slug reservado: `GENRES` e `TAGS` não podem usá-lo (verificação de `RESERVED`).

## 11. Divisão por agent (ordem de execução)

Pré-requisitos: a entrega 2 do `curator` (pontuação e sombra) e o `GENRES`/`TAGS` de §10.1.

1. **collector-engineer:**
   - bloco `curadoria` no `jsonl` da sombra (`score_cur`, `confiança_cur`, `would_curate`) no `curator.py`;
   - `vitrine` e `curadoria` no `load_catalog`/`BOOK_FIELDS`, cópia para o `offers.json`, `last_active_at` por loja;
   - depois da saída da sombra, o `curator` escreve e renova `curadoria.visto` e tira a curadoria vencida;
   - critérios 1 a 5.
2. **frontend-developer:**
   - validação dos campos no `build.py`, filtro de `vitrine` em `resolve`/`page`/seleção dos canais;
   - função que monta a aba (sem levantar erro quando vazia), página `/curadoria/`, link no menu, card sem preço com "Sem oferta agora";
   - `<ol>` → `<ul>` na seção "Em alta" da home e a regra do `trending_rank` (seção 7);
   - `/r/<id>` para livro da aba sem loja fresca em `redirects()`;
   - `curadoria` em `RESERVED`;
   - critérios 6 a 16, com `frontend-design` e `web-design-guidelines`.
3. **catalog-curator:** se a decisão 2 for sim, as primeiras entradas manuais (por exemplo, os de `literatura-brasileira` em `curadoria-e-links.md` A.5 que tiverem link) e a revisão dos textos da seção 7.
4. **security-auditor:** `/r/<id>` de livro sem loja fresca (só destino validado, só `id` conhecido); XSS na página nova; a CSP igual; o filtro do critério 11. Rodar `/security-review`.
5. **code-reviewer:** um PR para o coletor e o curador (1), um para o build (2), com `web-design-guidelines`.
- **alerts-engineer:** nada no MVP. Os canais continuam só com ofertas. O botão de alerta já existe no card.

## 12. Riscos

**Regras inegociáveis**
- *Regra 1 (Amazon):* nada na aba vem de página da Amazon, nem a lista de Mais Vendidos. A demanda da Amazon só entra com a Creators API (`salesRank`).
- *Regra 2 (ML):* o link continua sendo o do painel; a aba não cria link novo, só usa o do catálogo.
- *Regra 3:* nenhuma credencial nova além da `GOOGLE_BOOKS_API_KEY`, que já foi decidida.
- *Regra 4:* o preço só aparece fresco, com horário, e com "o preço final é o da loja" (critérios 9 e 12).

**Termos**
- ML 5.4: o ranking entra só na seleção, nunca na tela (decisão 1 do Elias, seção 7, critério 11). Risco residual: um livro estar na aba já é, em parte, consequência do ranking. **Inferência, risco baixo:** sem posição, sem número, sem rótulo e sem a ordem do ranking, a aba não publica estatística de vendas. Vale incluir a aba no pedido de autorização por escrito que já está pendente (B1 de `curadoria-e-links.md`).
- ML 5.2/5.3: livro sem anúncio ativo em 24 h sai da aba (critério 10).
- Google Books: a nota entra só na pontuação, sem exibir (seção 3, "Fora").

**Produto**
- **Aba magra:** sem Trends e sem Creators API, a aba automática deve ter de 5 a 10 livros por vez (seção 4.1). Mitigação: entrada manual (decisão 2) e a permanência de 30 dias.
- **Parecer "top do ML com outro nome":** é o efeito da fonte de hoje. Mitigação: ordem por data de entrada, agrupada por nicho, sem rótulo de popularidade, e a entrada manual misturando escolhas do Elias.
- **Confusão de nome** com "Destaques da curadoria" da home, que é escolha manual (`featured`). Decisão 7.

**Custo:** R$ 0. Nenhuma chamada nova de API (a pontuação reaproveita a da sombra). O custo é o tempo do Elias com os links dos livros novos da aba, poucos por semana.

**LGPD:** nenhum dado de usuário novo.

## 13. Mudança proposta no CLAUDE.md (não aplicada; o Elias aprova)

Hoje, em "Decisões tomadas":
> **Curadoria, não despejo.** O site mostra ofertas ativas e verificadas. Oferta vencida sai da lista.

Proposta (decisão 2 do Elias):
> **Curadoria, não despejo.** O site mostra as ofertas ativas e verificadas e, além delas, outras boas opções (a aba Curadoria), com ou sem desconto, como o ofertasdiscos.com faz com a "seleção". Oferta vencida sai da lista de ofertas; livro que não está mais à venda sai da curadoria. Preço só aparece dentro do prazo de frescor, com o horário da verificação e o aviso de que o preço final é o da loja; sem preço fresco, o livro da curadoria aparece sem preço. Rankings e tendências das lojas servem só para escolher livros: o site nunca mostra posição, número de vendas, rótulo derivado de ranking nem lista copiada de terceiros.

## 14. Decisões em aberto para o Elias

Saíram desta lista, por já estarem decididas (seção 0): o texto e os rótulos ligados a ranking, o impacto no `_redirects` e nos links manuais, e a direção do texto do CLAUDE.md.

1. **Limiar de entrada:** (a) **`score_cur ≥ 70`, `confiança_cur ≥ 0,45` e Demanda presente (recomendado)**; (b) o mesmo com 65, para a aba encher mais rápido; (c) `confiança ≥ 0,5`, que na prática só liga quando sair a Trends API.
2. **Entrada manual na aba** (`origem: "manual"`, sem prazo): (a) **sim (recomendado)**, porque a automática vai ser pequena e porque `literatura-brasileira` só entra à mão; (b) não, só automática.
3. **Quando ligar:** (a) **com critério de saída próprio (14 dias, 30 rótulos, precisão ≥ 0,90), antes da publicação automática de ofertas (recomendado)**; (b) junto com as ofertas, depois dos 30 dias de histórico.
4. **Preço quando não há oferta:** (a) **mostrar o preço quando estiver fresco, como na vitrine (recomendado)**; (b) nunca mostrar preço na aba, como o `/discos` da referência, só o botão da loja e o alerta.
5. **Livro sem preço fresco, mas com anúncio ativo nas últimas 24 h:** (a) **aparece sem preço, com `/r/<id>` para a loja (recomendado)**; (b) some da aba até ter preço fresco. A (b) é mais simples, mas a aba vai piscar com o rodízio do coletor.
6. **Filtro por nicho:** (a) **página única com âncoras (recomendado)**; (b) `/curadoria/<nicho>/`; (c) um bloco "Outras boas opções" dentro de cada página de nicho.
7. **Nome da seção "Destaques da curadoria" da home:** (a) **renomear para "Destaques" (recomendado)**, para não confundir com a aba; (b) manter.
8. **Texto exato do CLAUDE.md:** aprovar a redação da seção 13 ou ajustar.
9. **Permanência na aba:** (a) **30 dias depois da última qualificação (recomendado)**; (b) 14 dias; (c) 60 dias.
10. **Pendências do CLAUDE.md que afetam a aba:** a Creators API ainda não liberada deixa a aba sem demanda da Amazon, e a pergunta por escrito aos Associados (histórico de preço, §10.6, item 7) vale também para os preços mostrados aqui. Nada a decidir agora; fica registrado.
