# Anúncios: rodada 2, Black Friday (Instagram, Meta Ads)

Status: proposta do `brand-designer`, de 2026-11-07, aguardando a validação do Elias.
Pedido: criativos para quem quer comprar, no lugar da rodada 1 (institucional). Quem vê tem que entender em 1 segundo que é **livro, com desconto de verdade, na Black Friday**.

## Peças

| Peça | Destino | Feed 4:5 (1080x1350) | Stories e Reels 9:16 (1080x1920) |
|---|---|---|---|
| 1, Black Friday geral | `/black-friday/` | `1-black-friday-feed-1080x1350` | `1-black-friday-stories-1080x1920` |
| 2, finanças | `/negocios/` | `2-negocios-feed-1080x1350` | `2-negocios-stories-1080x1920` |
| 2b, mindset (alternativa à 2) | `/mindset/` | `2b-mindset-feed-1080x1350` | `2b-mindset-stories-1080x1920` |
| 3, romance | `/romance/` | `3-romance-feed-1080x1350` | `3-romance-stories-1080x1920` |
| 4, fantasia | `/fantasia/` | `4-fantasia-feed-1080x1350` | `4-fantasia-stories-1080x1920` |

**Por que existem a 2 e a 2b:** o pedido juntava Mindset, Babilônia e Do mil ao milhão na `/mindset/`, mas no site Babilônia e Do mil ao milhão estão no nicho `negocios`, e não aparecem na `/mindset/`. Para o anúncio só mostrar livros que estão na página de destino, a peça virou duas: **2 (finanças → `/negocios/`)** e **2b (mindset → `/mindset/`)**. Basta subir uma, ou as duas para teste.

**Fantasia e não suspense:** a fantasia tem os nomes mais conhecidos (Harry Potter, Tolkien, Duna, Sarah J. Maas). O suspense pode virar uma peça 5 depois (Freida McFadden, Agatha Christie, Dan Brown, Raphael Montes).

Nos Stories, todo o conteúdo fica entre y = 270 e y = 1630, com 250 px livres no topo e na base para a interface do Instagram.

## A arte
- **O que chama atenção é a pilha de lombadas,** cada uma com o título e o autor de um livro real que está em oferta na página de destino. Elas são desenhadas pela marca, e não há capa nem imagem de produto.
- **Título enorme,** no formato "<nicho> com desconto de verdade." Na peça 1, o título é "Black Friday de livros sem desconto falso."
- **Selo coral cheio.** É o carimbo da rodada 1, agora preenchido e mais quente. Na peça 1 ele diz "30% off ou mais", que é a regra de entrada da `/black-friday/` (hoje, o menor desconto na página é 30%). Nas peças de nicho, ele diz "Black Friday de livros" e não traz número, porque as páginas de nicho também têm ofertas com menos de 30% (Garota exemplar, −15%, por exemplo).
- **Marca:** usa a base `../rodada-1/anuncio.css` (tokens do tema escuro, Fraunces e Outfit do `static/fonts/`, grão, logo), e o `bf.css` acrescenta só a pilha e o selo. Os títulos dos livros vão em Fraunces itálico, que é a assinatura de nome de obra da `spec-visual.md`. As cores das lombadas são as do nicho no `static/style.css`. Na peça 1, cada livro vai na cor do seu nicho. Nas de nicho, as lombadas alternam entre o acento do nicho, papel e noite. O acento 2 ficou de fora porque o amarelo de negócios sobre o azul-marinho lembraria a cara de uma loja.

## Textos para o Ads Manager

O texto principal fica dentro de 125 caracteres e o título dentro de 40. O aviso de afiliado vai no texto principal (Amazon, Requisitos 6(l)).

### Peça 1, Black Friday geral → `https://ofertaslivros.com.br/black-friday/`
- **Arte:** "Black Friday de livros sem desconto falso." + "Comparamos cada preço com o nosso histórico." + selo "30% off ou mais" + lombadas: Mindset, É assim que acaba, Harry Potter e a pedra filosofal, O homem mais rico da Babilônia, O pequeno príncipe e, nos Stories, Torto arado.
- **Texto principal** (118 car.): `Black Friday de livros: só entra livro com 30% off ou no menor preço que vimos. Link de afiliado; preço final na loja.`
- **Título** (40 car.): `Black Friday de livros sem desconto falso` (o selo "30% off ou mais" fica só na arte, e o `gerar.py --conferir` exige `data-off >= 30` em cada título dela)
- **Descrição** (40 car.): `Comparado com o nosso histórico de preço`
- **CTA:** Ver ofertas. A página é uma lista, e o livro se escolhe lá.
- **Público sugerido:** Brasil, 18+. Interesses: Livros, Leitura, Literatura, Clube do livro, BookTok, Black Friday, Compras online.

### Peça 2, finanças → `https://ofertaslivros.com.br/negocios/`
- **Arte:** "Finanças com desconto de verdade." + "Dinheiro e negócios, comparados com o nosso histórico." + selo + lombadas: Do mil ao milhão, Pai rico, pai pobre, O homem mais rico da Babilônia, A psicologia financeira, De zero a um e, nos Stories, O investidor inteligente.
- **Texto principal** (122 car.): `Babilônia, Pai rico, pai pobre e mais finanças na Black Friday, sem desconto falso. Link de afiliado; preço final na loja.`
- **Título** (34 car.): `Livros de finanças na Black Friday`
- **Descrição** (40 car.): `Comparado com o nosso histórico de preço`
- **CTA:** Comprar agora
- **Público sugerido:** Brasil, 18+. Interesses: Finanças pessoais, Educação financeira, Investimentos, Bolsa de valores, Empreendedorismo e Livros, de preferência com a interseção "e também" com Livros ou Leitura, para não pagar clique de quem só quer investir.

### Peça 2b, mindset → `https://ofertaslivros.com.br/mindset/`
- **Arte:** "Mindset com desconto de verdade." + "Hábitos e psicologia, comparados com o nosso histórico." + selo + lombadas: Mindset, Hábitos atômicos, O poder do hábito, Rápido e devagar, Em busca de sentido e, nos Stories, Essencialismo.
- **Texto principal** (121 car.): `Mindset, Hábitos atômicos e O poder do hábito na Black Friday, sem desconto falso. Link de afiliado; preço final na loja.`
- **Título** (33 car.): `Mindset e hábitos na Black Friday`
- **Descrição** (40 car.): `Comparado com o nosso histórico de preço`
- **CTA:** Comprar agora
- **Público sugerido:** Brasil, 18+. Interesses: Desenvolvimento pessoal, Autoajuda, Produtividade, Psicologia, Livros, com interseção com Livros ou Leitura.

### Peça 3, romance → `https://ofertaslivros.com.br/romance/`
- **Arte:** "Colleen Hoover com desconto de verdade." + "E outros romances, comparados com o nosso histórico." + selo + lombadas: Um dia, É assim que acaba, É assim que começa, Os sete maridos de Evelyn Hugo, Como eu era antes de você e, nos Stories, Uma segunda chance.
- **Texto principal** (122 car.): `É assim que acaba, Evelyn Hugo e mais romances na Black Friday, sem desconto falso. Link de afiliado; preço final na loja.`
- **Título** (30 car.): `Colleen Hoover na Black Friday`
- **Descrição** (40 car.): `Comparado com o nosso histórico de preço`
- **CTA:** Comprar agora
- **Público sugerido:** Brasil, 18+. Interesses: Colleen Hoover, BookTok, Romance (literatura), Literatura young adult, Taylor Jenkins Reid, Livros.

### Peça 4, fantasia → `https://ofertaslivros.com.br/fantasia/`
- **Arte:** "Fantasia com desconto de verdade." + "Sagas e clássicos, comparados com o nosso histórico." + selo + lombadas: O Hobbit, Quarta asa, Harry Potter e a pedra filosofal, Corte de espinhos e rosas, Duna e, nos Stories, O nome do vento.
- **Texto principal** (120 car.): `Harry Potter, O Hobbit, Duna e mais fantasia na Black Friday, sem desconto falso. Link de afiliado; preço final na loja.`
- **Título** (24 car.): `Fantasia na Black Friday`
- **Descrição** (40 car.): `Comparado com o nosso histórico de preço`
- **CTA:** Comprar agora
- **Público sugerido:** Brasil, 18+. Interesses: Literatura fantástica, Harry Potter, J. R. R. Tolkien, O Senhor dos Anéis, Sarah J. Maas, Rebecca Yarros, Livros.

**Sobre os públicos:**
- São sugestões. O nome exato de cada interesse e se ele existe no Meta (BookTok e nomes de autor, principalmente) precisam ser conferidos na busca de "Segmentação detalhada" do Ads Manager.
- No público Advantage+, os interesses viram só uma sugestão, e o Meta pode ir além deles. Para que a segmentação filtre de verdade, é preciso usar as opções de público originais. Isso fica para o Elias decidir com o `product-manager`, porque a `anuncios-lancamento.md` prevê o Advantage+.
- **Exclusões:** sem interesse "Kindle" ou "Amazon", como já diz a `anuncios-lancamento.md` §6.

## Regras seguidas
- **Nenhum preço nem percentual de livro.** O único número é "30% off ou mais", que aparece só na peça 1, porque é a regra da `/black-friday/`.
- **Sem "90 dias"**, tanto na arte quanto nos textos. O texto usa "comparado com o nosso histórico".
- **Sem nome, logo ou cor de loja.** O coral e as cores de nicho são da marca, e nenhum amarelo ou laranja de loja domina a peça.
- **Sem capa real nem imagem de produto.** As lombadas são desenhadas, só com o título e o autor em texto.
- **Sem urgência inventada,** como contagem regressiva, "últimas unidades" ou "mais vendido". O "sem desconto falso" está apoiado na comparação com o histórico, que o site mostra em cada livro.
- **Títulos reais:** todos foram tirados do HTML ao vivo em 07/11/2026 e conferidos como oferta ativa na página de destino.

## Antes de subir (e a cada renovação)
Os títulos saem da lista quando a oferta vence. Rode:
```
python3 gerar.py --conferir
```
O comando lê as páginas de destino no ar e marca `SAIU` em qualquer título que não seja mais oferta ativa. Se algum sair, troque o título na tabela `PECAS` do `gerar.py` por outro da mesma página e rode `./render.sh`.

## Contraste (WCAG, calculado)

| Par | Cores | Razão | Mínimo |
|---|---|---|---|
| Título sobre o fundo | #e6ebf3 / #0f1729 | 14,93:1 | 4,5 |
| Título sobre o pior trecho do fundo tingido (coral a 30%) | #e6ebf3 / #573a48 | 8,34:1 | 4,5 |
| Frase (texto a 86%) sobre o fundo | #c8cdd7 / #0f1729 | 11,21:1 | 4,5 |
| Frase sobre o fundo tingido (coral a 30%) | #d2d2db / #573a48 | 6,65:1 | 4,5 |
| Selo: texto sobre o coral | #0f1729 / #ff8a8f | 7,90:1 | 4,5 |
| Lombada de romance (tinta / acento) | #26070c / #e3526b | 5,08:1 | 4,5 |
| Lombada de fantasia | #041514 / #119590 | 5,10:1 | 4,5 |
| Lombada de negócios | #1a1000 / #b87d00 | 5,34:1 | 4,5 |
| Lombada de mindset | #0e1303 / #689215 | 5,13:1 | 4,5 |
| Lombada de ficção | #0d0626 / #9468f5 | 5,19:1 | 4,5 |
| Lombada de literatura brasileira | #04140b / #1f9a5a | 5,25:1 | 4,5 |
| Lombada papel | #0f1729 / #dfe5ee | 14,11:1 | 4,5 |
| Lombada noite | #e6ebf3 / #1c2b4a | 11,74:1 | 4,5 |

## Arquivos e como renderizar
- `gerar.py`: a tabela das peças (títulos, textos, cores), que gera os HTML.
- `bf.css`: a pilha e o selo, por cima de `../rodada-1/anuncio.css`.
- `render.sh`: roda o `gerar.py` e tira o PNG de cada HTML com o Chrome da máquina, em modo headless. Nesta máquina, cada PNG leva cerca de 40 s por causa do atualizador do Chrome. O tempo é esse mesmo, não é travamento.
