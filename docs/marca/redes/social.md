# Textos das redes

Proposta do brand-designer em 2026-11-04, para o Elias aprovar. O tom segue o site e o `docs/produto/distribuicao-canais.md`: curadoria e não volume, preço com horário, sem urgência falsa.

**Tom de voz**
1. Direto e calmo: dizemos o que o livro custa e quando conferimos, sem grito, caixa-alta ou "corre".
2. Prova antes de adjetivo: "menor preço em 90 dias" só com histórico real. Nada de "imperdível" nem "só hoje".
3. Leitor falando com leitor: frases curtas, "a gente", e o nome do livro e do autor sempre por extenso.
4. Transparente sem pedir desculpa: link de afiliado e "o preço final é o da loja" em todo post de oferta.
5. Pouco e bom: se não baixou de verdade, não posta.

**Regras fixas para qualquer post de oferta**
- O preço vem do site no dia, com a data e a hora da conferência. Nos 3 exemplos abaixo, o preço é placeholder (`R$ 00,00`) e o post só vai ao ar com o preço trocado.
- O selo "Menor preço em 90 dias" só entra se o site mostrar o selo para aquele livro naquele dia.
- Toda legenda de oferta termina com "Link de afiliado" e "O preço final é o da loja".
- Sem capa real e sem logo da Amazon ou do Mercado Livre na arte: a loja aparece por escrito ("na Amazon", "no Mercado Livre").

**Pendências do Elias:** o `@` do Instagram, do TikTok e do canal do Telegram ainda não existem. Onde aparece `@ofertaslivros`, é uma sugestão. O único `@` real é o do bot, `@ofertaslivros_bot`.

## Bios

Os limites foram conferidos em 2026-11-04. O do Telegram vem da documentação oficial da Bot API (`setChatTitle`: 1 a 128 caracteres; `setChatDescription`: 0 a 255, https://core.telegram.org/bots/api). Os 150 do Instagram são o número que a Central de Ajuda cita. Os 80 do TikTok aparecem só em fontes de terceiros, porque o TikTok não publica esse limite. Para a descrição do Canal do WhatsApp não achei fonte, então mantive o texto no limite do Telegram (255). A contagem entre parênteses inclui espaços.

| Rede | Limite | Texto |
|---|---|---|
| Instagram (bio) | 150 | Livros que baixaram de preço de verdade, conferidos na loja e no histórico de 90 dias. Links de afiliado. Canais e site no link. (128) |
| Instagram (nome) | 64 | Ofertas Livros (14) |
| TikTok (bio) | 80, não oficial | Livros que baixaram de verdade. Preço conferido na loja e no histórico. (71) |
| Telegram (nome do canal) | 128 | Ofertas Livros (14) |
| Telegram (descrição do canal) | 255 | Ofertas de livros conferidas na loja, com o preço e o horário. Poucas por dia. Links de afiliado: ganhamos com compras qualificadas, e o preço final é o da loja. Alerta de um livro: @ofertaslivros_bot. ofertaslivros.com.br (222) |
| WhatsApp (nome do Canal) | ? | Ofertas Livros (14) |
| WhatsApp (descrição do Canal) | ? (mantido ≤ 255) | Ofertas de livros conferidas na loja, com o preço e o horário. Poucas por dia, só leitura. Links de afiliado: ganhamos com compras qualificadas, e o preço final é o da loja. Site: ofertaslivros.com.br (200) |

**Link da bio (Instagram e TikTok):** `https://ofertaslivros.com.br/canais/`. A página já tem os dois canais e o aviso de afiliado, então dispensa ferramenta de terceiros como o Linktree.

**Mensagem fixada (Telegram e WhatsApp),** junto com a imagem `canal/telegram-fixada.png`:
> Bem-vindo ao Ofertas Livros. Aqui saem poucas ofertas por dia, só de livro que baixou de preço de verdade, com o preço e o horário em que conferimos na loja.
> Os links são de afiliado: como associados da Amazon e afiliados do Mercado Livre, ganhamos com compras qualificadas. O preço final é o da loja.
> Quer saber de um livro só? Peça um alerta ao @ofertaslivros_bot.
> Todas as ofertas: https://ofertaslivros.com.br

## Os 9 posts do feed

A ordem é a de publicação. O post 1 fica no canto inferior direito da grade e o 9 no superior esquerdo (veja `posts/grade-3x3.png`). Se os 9 forem publicados no mesmo dia, publique nesta ordem. Sugestão: fixar no perfil os posts 1, 5 e 8.

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

### 3. Oferta de exemplo: Torto arado (`posts/03-oferta-torto-arado`)
Antes de publicar: troque os `R$ 00,00`, o desconto e o carimbo `DD/MM às HHhMM` pelos dados do site no dia, e tire a linha "Preço ilustrativo" do SVG.
> Torto arado, de Itamar Vieira Junior, por R$ [preço] na Amazon (de R$ [preço anterior]).
> Preço conferido em [DD/MM] às [HHhMM]. O preço muda rápido: confira antes de comprar.
> Link na bio. Link de afiliado. O preço final é o da loja.

`#tortoarado #literaturabrasileira #livros #ofertasdelivros`

### 4. Curadoria, não despejo (`posts/04-curadoria`)
> Tem perfil que posta cem ofertas por dia. A gente posta poucas.
> Cada uma passa por três conferências: o preço foi visto na loja, com horário; ele é comparado com os últimos 90 dias; e a oferta sai da lista quando vence.
> Menos mensagem, mais livro bom.

`#livros #ofertasdelivros #leitores #bookstagrambrasil`

### 5. Onde seguir (`posts/05-onde-seguir`)
> As ofertas chegam no Telegram e no WhatsApp: canais gratuitos, só de leitura e sem cadastro.
> Quer acompanhar um livro específico? O @ofertaslivros_bot avisa quando ele baixar.
> Os links estão na bio.

`#livros #ofertasdelivros #promocaodelivros #leitura`

### 6. Os nichos (`posts/06-nichos`)
> Mangá, romance, fantasia, suspense, literatura brasileira, ficção, mindset, negócios, história e política.
> Cada nicho tem uma página no site, com as ofertas e a curadoria daquele assunto. Qual é o seu?

`#manga #romance #fantasia #literaturabrasileira #livros`

### 7. Oferta de exemplo: One Piece vol. 1 (`posts/07-oferta-one-piece`)
Antes de publicar: os mesmos campos do post 3.
> One Piece vol. 1, de Eiichiro Oda, por R$ [preço] na Amazon (de R$ [preço anterior]).
> Preço conferido em [DD/MM] às [HHhMM].
> Link na bio. Link de afiliado. O preço final é o da loja.

`#onepiece #manga #mangabrasil #ofertasdelivros`

### 8. Transparência (`posts/08-transparencia`)
> Como o Ofertas Livros se paga: os links são de afiliado. Como associados da Amazon e afiliados do Mercado Livre, ganhamos com compras qualificadas.
> O preço final é o da loja. A gente mostra o horário em que conferiu, mas o preço pode mudar depois disso.
> Nenhuma loja escolhe o que aparece aqui: entra o livro que passa pela curadoria (preço conferido na loja e comparado com o histórico).

`#livros #ofertasdelivros #transparencia`

### 9. Oferta de exemplo: O Hobbit (`posts/09-oferta-o-hobbit`)
Antes de publicar: os mesmos campos do post 3. O selo "Menor preço em 90 dias" só fica se o site mostrar o selo para O Hobbit no dia; se não mostrar, apague o grupo do selo no SVG.
> O Hobbit, de J.R.R. Tolkien, por R$ [preço] no Mercado Livre (de R$ [preço anterior]). [Se tiver o selo: É o menor preço dos últimos 90 dias.]
> Preço conferido em [DD/MM] às [HHhMM].
> Link na bio. Link de afiliado. O preço final é o da loja.

`#ohobbit #tolkien #fantasia #livros #ofertasdelivros`

## Stories e capas de vídeo

### S1. Chegou o Ofertas Livros (`stories/s1-chegamos`)
Story de abertura. Adesivo de link para `https://ofertaslivros.com.br`, colocado abaixo do carimbo e acima da linha do site (zona segura).
> Texto do adesivo: Ver as ofertas

### S2. Capa de reels/TikTok: "Esse desconto é de verdade?" (`stories/s2-capa-historico`)
Roteiro do vídeo, em 30 s: um livro com "-50%"; o gráfico mostrando que o preço subiu antes; o selo só quando é o menor em 90 dias; o fecho "link na bio".
> Legenda: Nem todo desconto é desconto. O histórico de 90 dias mostra se o preço baixou mesmo. Link na bio.
> `#livros #ofertasdelivros #booktokbrasil #dicasdeleitura`

### S3. Siga o canal (`stories/s3-canais`)
Os botões da arte são só desenho. Os toques vão nos adesivos de link (um para `https://ofertaslivros.com.br/canais/`), colocados sobre eles.
> Texto do adesivo: Canais gratuitos
