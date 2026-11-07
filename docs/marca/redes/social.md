# Textos das redes

Proposta do brand-designer em 2026-11-04, atualizada em 2026-11-07, para o Elias aprovar. O tom segue o site e o `docs/produto/distribuicao-canais.md`: curadoria e não volume, preço com horário, sem urgência falsa.

**Tom de voz**
1. Direto e calmo: dizemos o que o livro custa e quando conferimos, sem grito, caixa-alta ou "corre".
2. Prova antes de adjetivo: "menor preço em 90 dias" só com histórico real. Nada de "imperdível" nem "só hoje".
3. Leitor falando com leitor: frases curtas, "a gente", e o nome do livro e do autor sempre por extenso.
4. Transparente sem pedir desculpa: link de afiliado e "o preço final é o da loja" em todo post de oferta.
5. Pouco e bom: se não baixou de verdade, não posta.

**Regras fixas para qualquer post de oferta**
- O preço vem do site, com a data e a hora da conferência. Ele é o daquele horário e pode mudar: se o post sair depois, confira no site e troque (ou refaça o post com `gerar.py --captura`).
- O selo "Menor preço em 90 dias" só entra se o site mostrar o selo para aquele livro naquele dia.
- Toda legenda de oferta termina com "Link de afiliado" e "O preço final é o da loja".
- A capa é a mesma imagem que o site mostra (o `image_url` do `offers.json`), nunca baixada da Amazon. Sem logo da Amazon ou do Mercado Livre na arte: a loja aparece por escrito ("na Amazon", "no Mercado Livre").
- O selo é o que o site mostra para o livro naquele horário: "Menor preço em 90 dias" só com 90 dias de histórico; com menos, "Menor preço desde DD/MM"; sem nenhum dos dois, sem selo.
- Toda arte com preço leva no rodapé "Link de afiliado. O preço final é o da loja."

**Regras fixas para falar do bot (a Mavi)**
- O bot avisa quando o livro **entrar em oferta**, com o mesmo critério do site e do canal. Não dizer "avisa quando o preço baixar" nem "avisa no preço que você quiser" (preço-alvo não existe).
- Ele aceita livro do catálogo ou autor. Livro fora do catálogo vira pedido para a curadoria, não alerta.
- Avisos das 8h às 22h. Para apagar tudo: `/parar`.
- Nada de print de conversa real com o bot nas artes ou nos vídeos.

**Nomes reais (conferidos em 2026-11-07 no https://ofertaslivros.com.br, em `/canais/` e nas páginas públicas `t.me/maviOfertaslivros`, `t.me/ofertaslivros_bot` e no link do Canal do WhatsApp):**

| O quê | Nome | Link |
|---|---|---|
| Canal do Telegram | Só Mais um Livro - Ofertas Livros (`@maviOfertaslivros`) | https://t.me/maviOfertaslivros |
| Canal do WhatsApp | Só Mais um Livro - Ofertas Livros | https://whatsapp.com/channel/0029Vb9Za8e0VycKAGgPgz0S |
| Bot de alerta | Mavi · Ofertaslivros.com (`@ofertaslivros_bot`) | https://t.me/ofertaslivros_bot |
| Botões do site | "Canal no WhatsApp", "Canal no Telegram", "Me avise se baixar" (o sino), "Pedir um livro" | |

O site diz o ritmo de cada canal: Telegram, "até 8 por dia, das 8h às 22h"; WhatsApp, "um resumo por dia com até 5 ofertas".

**Pendências do Elias:** o `@` do Instagram e do TikTok ainda não existem. Onde aparece `@ofertaslivros` para essas redes, é uma sugestão.

## Bios

Os limites foram conferidos em 2026-11-04. O do Telegram vem da documentação oficial da Bot API (`setChatTitle`: 1 a 128 caracteres; `setChatDescription`: 0 a 255, https://core.telegram.org/bots/api). Os 150 do Instagram são o número que a Central de Ajuda cita. Os 80 do TikTok aparecem só em fontes de terceiros, porque o TikTok não publica esse limite. Para a descrição do Canal do WhatsApp não achei fonte, então mantive o texto no limite do Telegram (255). A contagem entre parênteses inclui espaços.

| Rede | Limite | Texto |
|---|---|---|
| Instagram (bio) | 150 | Livros que baixaram de preço de verdade, conferidos na loja e no histórico de 90 dias. Alerta grátis no Telegram. Links de afiliado. Canais no link. (148) |
| Instagram (nome) | 64 | Ofertas Livros (14) |
| TikTok (bio) | 80, não oficial | Livros que baixaram de verdade. Preço conferido na loja. Alerta no Telegram. (76) |
| Telegram (nome do canal) | 128 | Só Mais um Livro - Ofertas Livros (33). É o nome no ar; manter. |
| Telegram (descrição do canal) | 255 | Ofertas de livros conferidas na loja, com o preço e o horário. Até 8 por dia, das 8h às 22h. Links de afiliado: ganhamos com compras qualificadas, e o preço final é o da loja. Alerta de um livro: @ofertaslivros_bot. ofertaslivros.com.br (236) |
| WhatsApp (nome do Canal) | ? | Só Mais um Livro - Ofertas Livros (33). É o nome no ar; manter. |
| WhatsApp (descrição do Canal) | ? (mantido ≤ 255) | Ofertas de livros conferidas na loja, com o preço e o horário. Um resumo por dia, só leitura. Links de afiliado: ganhamos com compras qualificadas, e o preço final é o da loja. Alerta de um livro no Telegram: @ofertaslivros_bot. Site: ofertaslivros.com.br (255) |
| Bot (nome) | 64 | Mavi · Ofertas Livros (21). Hoje está "Mavi · Ofertaslivros.com". |
| Bot (descrição curta, `setMyShortDescription`) | 120 | Aviso no Telegram quando o livro que você quer entrar em oferta. ofertaslivros.com.br (85). É a que está no ar; manter. |
| Bot (descrição, `setMyDescription`, a tela antes do Iniciar) | 512 | Oi, eu sou a Mavi, do Ofertas Livros. Mande o título ou o autor de um livro, ou toque no sino "Me avise se baixar" no site, e eu aviso aqui quando ele entrar em oferta: uma vez por oferta, das 8h às 22h. /lista mostra a sua lista, /pausar pausa os avisos e /parar apaga tudo. Os links são de afiliado: ganhamos com compras qualificadas, e o preço final é o da loja. (365) |

**O que está no ar hoje (2026-11-07), para comparar:**
- Descrição do canal do Telegram: "Melhor canal do melhor site de ofertas de livros do Brasil! Livros que baixaram de preço de verdade! ofertaslivros.com.br". O superlativo e os pontos de exclamação fogem do tom (regra 2), e falta o aviso de afiliado que a `distribuicao-canais.md` pede no canal. Sugestão: trocar pela da tabela.
- Descrição do Canal do WhatsApp: "Ofertas de livros com preço verificado. Os links são de afiliado: ganhamos uma comissão nas compras qualificadas, sem custo para você. O preço final é o da loja. https://ofertaslivros.com.br". Já cumpre o tom e o aviso; a da tabela só acrescenta o ritmo e o bot. Pode ficar como está.

Os limites do bot (64, 120 e 512) são os da Bot API (`setMyName`, `setMyShortDescription`, `setMyDescription`, https://core.telegram.org/bots/api, conferido em 2026-11-07).

**Link da bio (Instagram e TikTok):** `https://ofertaslivros.com.br/canais/`. A página já tem os dois canais e o aviso de afiliado, então dispensa ferramenta de terceiros como o Linktree.

**Mensagem fixada (Telegram e WhatsApp),** junto com a imagem `canal/telegram-fixada.png`:
> Bem-vindo ao Ofertas Livros. Aqui saem poucas ofertas por dia, só de livro que baixou de preço de verdade, com o preço e o horário em que conferimos na loja.
> Os links são de afiliado: como associados da Amazon e afiliados do Mercado Livre, ganhamos com compras qualificadas. O preço final é o da loja.
> Quer saber de um livro só? A Mavi avisa quando ele entrar em oferta: @ofertaslivros_bot.
> Não achou um livro? Peça no site, no botão "Pedir um livro".
> Todas as ofertas: https://ofertaslivros.com.br

## Os 9 posts do feed

A ordem é a de publicação. O post 1 fica no canto inferior direito da grade e o 9 no superior esquerdo (veja `posts/grade-3x3.png`). A grade é um xadrez: os ímpares são escuros (cantos e centro) e os pares, claros. Publique nesta ordem. Sugestão: fixar no perfil os posts 5 (onde seguir), 7 (a Mavi) e 9 (alerta em três passos).

Hashtags: de 3 a 5 por post, só de assunto. O Instagram recomenda poucas e relevantes.

### 1. O que é (`posts/01-o-que-e`)
> O Ofertas Livros mostra só livro que baixou de preço de verdade.
> A gente confere o preço na loja, anota o horário e compara com os últimos 90 dias. Se não baixou, não entra.
> As ofertas do dia estão no site e nos canais. Link na bio.

`#livros #ofertasdelivros #leitura #bookstagrambrasil`

### 2. Como funciona o histórico (`posts/02-historico`)
> Desconto de 50% sobre um preço que subiu na semana anterior não é desconto.
> Por isso guardamos o preço de cada livro todo dia. Quando o preço de hoje é o menor dos últimos 90 dias, o livro ganha o selo "Menor preço em 90 dias". Sem histórico, não tem selo.
> (O gráfico do post é ilustrativo.)

`#livros #ofertasdelivros #dicasdeleitura #leitura`

### 3. Oferta: Mindset (`posts/03-oferta-mindset`)
Oferta real, a de maior desconto no site em 07/11/2026: na Amazon por R$ 25,75 (de R$ 69,90, −63%), conferida em 07/11 às 09h28, com o selo "Menor preço desde 20/10" que o site mostrava. O preço é o daquele horário e pode mudar: confira no site antes de publicar e, se mudou, troque os números (ou escolha outra oferta e rode `gerar.py --captura`).
> Mindset: a nova psicologia do sucesso, de Carol S. Dweck, por R$ 25,75 na Amazon (de R$ 69,90). É o menor preço desde 20/10.
> Preço conferido em 07/11 às 09h28. O preço muda rápido e pode já ser outro: confira no site antes de comprar.
> Link na bio. Link de afiliado. O preço final é o da loja.

`#mindset #caroldweck #desenvolvimentopessoal #livros #ofertasdelivros`

### 4. Curadoria, não despejo (`posts/04-curadoria`)
> Tem perfil que posta cem ofertas por dia. A gente posta poucas.
> Cada uma passa por três conferências: o preço foi visto na loja, com horário; ele é comparado com os últimos 90 dias; e a oferta sai da lista quando vence.
> Menos mensagem, mais livro bom.

`#livros #ofertasdelivros #leitores #bookstagrambrasil`

### 5. Onde seguir (`posts/05-onde-seguir`)
> As ofertas chegam em dois canais com o mesmo nome, Só Mais um Livro - Ofertas Livros: no Telegram, até 8 por dia, das 8h às 22h; no WhatsApp, um resumo por dia. São gratuitos, só de leitura e sem cadastro.
> Quer um livro só? A Mavi, do @ofertaslivros_bot, avisa no Telegram quando ele entrar em oferta.
> Os links estão na bio.

`#livros #ofertasdelivros #promocaodelivros #leitura`

### 6. Os nichos (`posts/06-nichos`)
> Mangá, romance, fantasia, suspense, literatura brasileira, ficção, mindset, negócios, história e política.
> Cada nicho tem uma página no site, com as ofertas e a curadoria daquele assunto. Qual é o seu?

`#manga #romance #fantasia #literaturabrasileira #livros`

### 7. A Mavi avisa (`posts/07-mavi-alerta`)
> Esta é a Mavi, a assistente do Ofertas Livros no Telegram.
> Escolha um livro (ou um autor) e ela avisa quando ele entrar em oferta, com o mesmo critério do site: preço conferido na loja. Os avisos chegam das 8h às 22h, e /parar apaga tudo.
> É grátis: @ofertaslivros_bot. Link na bio. Os links dos avisos são de afiliado, e o preço final é o da loja.

`#livros #ofertasdelivros #listadedesejos #leitura`

### 8. Pedir um livro (`posts/08-pedir-um-livro`)
> Não achou o livro que você quer? No site, toque em "Pedir um livro" e escreva o nome e o autor. Só isso: não pedimos e-mail, telefone nem cadastro. O site usa o endereço IP só para barrar envios repetidos, sem guardá-lo (veja ofertaslivros.com.br/privacidade/).
> O pedido vai para a curadoria. Se o livro entrar em oferta, ele aparece no site e nos canais.
> Link na bio.

`#livros #ofertasdelivros #leitura #bookstagrambrasil`

### 9. Alerta em três passos (`posts/09-alerta-passos`)
A imagem é a página real do livro no site (captura do Chrome headless em 07/11 às 09h28), com o botão "Me avise se baixar" marcado. Os passos 2 e 3 acontecem no Telegram e não têm print.
> 1. No site, toque no sino "Me avise se baixar" do livro.
> 2. No Telegram, toque em Iniciar.
> 3. Quando o livro entrar em oferta, a Mavi avisa.
> Também dá para mandar o título ou o autor direto ao @ofertaslivros_bot. Em /lista você vê e tira livros; /parar apaga tudo.

`#livros #ofertasdelivros #dicasdeleitura #leitura`

## Stories e capas de vídeo

### S1. Chegou o Ofertas Livros (`stories/s1-chegamos`)
Story de abertura. Adesivo de link para `https://ofertaslivros.com.br`, colocado abaixo do carimbo e acima da linha do site (zona segura).
> Texto do adesivo: Ver as ofertas

### S2. Capa de reels/TikTok: "Esse desconto é de verdade?" (`stories/s2-capa-historico`)
Roteiro do vídeo, em 30 s: um livro com "-50%"; o gráfico mostrando que o preço subiu antes; o selo só quando é o menor em 90 dias; o fecho "link na bio".
> Legenda: Nem todo desconto é desconto. O histórico de 90 dias mostra se o preço baixou mesmo. Link na bio.
> `#livros #ofertasdelivros #booktokbrasil #dicasdeleitura`

### S3. Siga o canal (`stories/s3-canais`)
Os botões da arte são só desenho. Os toques vão nos adesivos de link, colocados sobre eles: um para `https://whatsapp.com/channel/0029Vb9Za8e0VycKAGgPgz0S` e outro para `https://t.me/maviOfertaslivros`. Se preferir um adesivo só, use `https://ofertaslivros.com.br/canais/`.
> Texto dos adesivos: Canal no WhatsApp / Canal no Telegram (ou, com um só: Canais gratuitos)

### S4. Me avise se baixar (`stories/s4-mavi`)
Adesivo de link para `https://t.me/ofertaslivros_bot`, colocado entre o texto e a linha do site (zona segura). Sem print de conversa.
> Texto do adesivo: Falar com a Mavi

## Destaques do Instagram

| Capa | O que guardar nele |
|---|---|
| `ofertas` | os stories de oferta |
| `manga` | ofertas de mangá e HQ |
| `curadoria` | como escolhemos (post 4) |
| `como-funciona` | o histórico de 90 dias (post 2, S2) |
| `canais` | S3 |
| `alerta` | S4 e os passos do post 9 |
| `pedir` | um story com o post 8 e o adesivo de link para `https://ofertaslivros.com.br` |
