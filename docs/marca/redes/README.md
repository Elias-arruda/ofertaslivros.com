# Kit de redes sociais

Proposta do brand-designer em 2026-11-04, atualizada em 2026-11-07 (bot e Mavi, os dois canais com os nomes reais, "Pedir um livro", o domínio .com.br e, na rodada 2 do Elias, a grade de volta a 9, com um post de oferta real e a tela real do site no post do alerta), aguardando a aprovação do Elias. O kit não cria identidade nova. Ele usa só o que já está no site:
- a paleta do `static/style.css`: marinho `#1c2b4a`, noite `#0f1729`, marfim `#edf1f5`, vermelho do carimbo `#b3262f` (`#ff8a8f` no escuro), rosa `#f2a3a8` e os acentos por nicho;
- o logo B (`static/logo.svg` e `static/logo-negativo.svg`), com ".br" acrescentado no fim, no mesmo traço e na mesma cor do ".com" (ver "Pontos para o Elias decidir");
- o símbolo do carimbo (`docs/marca/logos/carimbo-simbolo.svg`);
- a Mavi, mascote e avatar do bot (`static/mavi.svg`, embutida sem alteração e cortada no círculo, como no avatar do Telegram);
- as fontes OFL do repo (Fraunces com SOFT 100 e WONK 1 nos títulos, Outfit no resto);
- o objeto da marca da `spec-visual.md` §11.1: a capa com o miolo saindo por trás e a fita na cor do nicho.

Os textos (bios, legendas, hashtags e descrições dos canais) estão em `social.md`.

## O que tem aqui

| Pasta | Conteúdo | Tamanho |
|---|---|---|
| `perfil/` | `perfil.svg` (mestre, escuro) e `perfil-claro.svg`. PNG: `instagram-320`, `tiktok-200`, `tiktok-720`, `telegram-640`, `whatsapp-640`, `perfil-claro-640` | quadrado |
| `destaques/` | capas dos destaques do Instagram: `ofertas`, `manga`, `curadoria`, `como-funciona`, `canais` (megafone), `alerta` (sino, o do bot) e `pedir` (lupa, a do botão "Pedir um livro") | 1080×1920 |
| `canal/` | `telegram-fixada`: imagem da mensagem fixada do Telegram e do Canal do WhatsApp | 1280×720 |
| `templates/` | `feed-oferta`, `carrossel-capa`, `carrossel-pagina`, `story-reels-tiktok`, `canal-1280x720`, com a camada de guias ligada | ver o nome |
| `posts/` | os 9 posts da grade inicial e `grade-3x3.png` (prévia do perfil) | 1080×1350 |
| `posts/fontes/` | `capa-livro.jpg` (a capa que o site mostra, do `image_url` do `offers.json`) e `tela-livro.jpg` (a página do livro no site, pelo Chrome headless, recortada no card). Os SVG dos posts 3 e 9 apontam para elas por caminho relativo | |
| `stories/` | `s1-chegamos`, `s2-capa-historico` (capa de reels/TikTok), `s3-canais` e `s4-mavi` (o alerta) | 1080×1920 |
| `gerar.py` | gera todos os SVG e PNG de novo | |

**Capa do canal:** o Telegram e o Canal do WhatsApp não têm imagem de capa, só a foto de perfil. A peça que faz esse papel é a imagem da mensagem fixada (`canal/telegram-fixada.png`), que leva o aviso de afiliado que a `distribuicao-canais.md` exige na fixada.

## Logo no perfil

- **Use o símbolo do carimbo, sem o wordmark.** "ofertaslivros.com.br" fica ilegível em 200 px, e o nome já aparece ao lado da foto em todas as redes.
- **Versão padrão:** `perfil.svg`, carimbo rosa `#f2a3a8` sobre marinho `#1c2b4a`, a mesma combinação do logo negativo do site, com contraste de 7,08:1. O fundo escuro destaca a foto tanto no app claro quanto no escuro.
- **Versão clara:** `perfil-claro.svg`, vermelho `#b3262f` sobre marfim, igual ao favicon. Use só se o Elias preferir.
- **Margem:** o carimbo ocupa 60% do lado e fica girado -10°, como no site. O anel externo fica a cerca de 20% da borda do círculo de corte. Mantenha os 60%: assim sobra respiro em volta e o símbolo tem o mesmo tamanho em todas as redes.
- **Tamanho mínimo:** o PNG de 200 px (TikTok) foi conferido. O anel fino continua visível, com cerca de 5 px.
- Sempre numa cor só, sem sombra, sem contorno extra e sem girar mais.

## Margens e grade

- **Feed 1080×1350:** margem de 72 px. A grade do perfil do Instagram mostra os posts 4:5 cortados em 3:4, ou seja, 1012 px de largura (34 px a menos de cada lado). Por isso nada importante fica fora dos 72 px. A guia amarela dos templates marca esse corte.
- **Story/reels/TikTok 1080×1920:** zona segura de x 64 a 940 e y 250 a 1440. Em cima fica a barra do app (250 px). Embaixo ficam a legenda e os botões (480 px, a medida do TikTok, que é maior que a do Instagram). À direita, de x 940 em diante, ficam os botões do TikTok. As medidas são a prática de mercado, não número oficial das plataformas; confira com um post de teste.
- **Canal 1280×720:** margem de 48 px. O 16:9 é o formato que o Telegram e o WhatsApp mostram inteiro, sem cortar.
- **Destaques:** o ícone fica dentro de um círculo de 600 px no centro. O Instagram corta a capa num círculo central.
- **Rodapé dos posts:** linha fina e o logo à esquerda, que já diz "ofertaslivros.com.br". Nos posts de oferta, à direita, "Link de afiliado. O preço final é o da loja."

## Que template usar em cada rede

| Rede | Peça | Arquivo |
|---|---|---|
| Instagram (feed) | oferta | `templates/feed-oferta.svg` |
| Instagram (feed) | explicação em passos | `templates/carrossel-capa.svg` + `templates/carrossel-pagina.svg` (o número só quando há sequência real) |
| Instagram (feed) | aviso, institucional | copiar um post de `posts/` (claro: 02, 04, 06, 08; escuro: 01, 05, 07) |
| Instagram (stories), Reels, TikTok | story e capa de vídeo | `templates/story-reels-tiktok.svg` |
| Instagram (destaques) | capa | `destaques/*.png` |
| Telegram e WhatsApp | post manual ou anúncio | `templates/canal-1280x720.svg` |
| Telegram e WhatsApp | mensagem fixada | `canal/telegram-fixada.png` |

As ofertas automáticas do Telegram continuam como na `distribuicao-canais.md`, com a foto do ML ou sem foto. O template de canal é para posts manuais.

**Grade:** um xadrez de escuro e claro, com os ímpares escuros. Cantos: o que é (1), a oferta real (3), a Mavi (7) e o alerta com a tela do site (9). Centro: "Onde seguir" (5). Bordas, claras: histórico (2), curadoria (4), nichos (6) e "Pedir um livro" (8). Para manter o padrão depois dos 9, alterne um escuro e um claro.

**Nomes que aparecem nas artes** (conferidos no site no ar e nas páginas públicas em 2026-11-07): os dois canais se chamam "Só Mais um Livro - Ofertas Livros" (Telegram `t.me/maviOfertaslivros` e Canal do WhatsApp); o bot é o `@ofertaslivros_bot`, com a Mavi de avatar; os botões do site são "Canal no WhatsApp", "Canal no Telegram", "Me avise se baixar" e "Pedir um livro". As artes não mostram print de conversa nem dado de ninguém: o form do post 8 é desenhado, com os campos vazios, e a tela do post 9 é a página pública de um livro, sem conta, conversa ou dado pessoal.

## Como editar os SVG

1. **Fontes:** os SVG chamam a Fraunces e a Outfit de `static/fonts/` por caminho relativo. Isso funciona no Chrome e no Inkscape a partir do repo. No Figma, instale antes os dois `.woff2` de `static/fonts/`, que são OFL e podem ser instalados. Se a fonte faltar, o texto cai para Georgia/system-ui e a medida muda.
2. **Texto:** todo texto é `<text>` vivo, com uma `<tspan>` por linha. Para mudar o título, edite as linhas. Não há quebra automática: título com até 2 linhas no feed e 3 no story.
3. **Guias:** nos templates, as guias ficam no grupo `id="guias"`. Esconda ou apague esse grupo antes de exportar.
4. **Post de oferta:** o post 3 usa uma oferta real: Mindset, de Carol S. Dweck, na Amazon por R$ 25,75 (de R$ 69,90, −63%), conferida em 07/11 às 09h28, a de maior desconto entre as ofertas ativas com preço no prazo no `offers.json` do branch `price-history` (commit 8e95708), lido com o `resolve` do `build.py`. **O preço é o do horário conferido e pode mudar.** Antes de publicar, confira no site; se mudou, troque `OFERTA` no `gerar.py`. O selo é o que o site mostra para o livro: "Menor preço em 90 dias" só com 90 dias de histórico; aqui é "Menor preço desde 20/10". Sem selo no site, sem o grupo `id="selo"`.
5. **Capa:** no post de oferta real, a capa é a imagem que o site já usa (o `image_url` do `offers.json`, servida pelo CDN do Mercado Livre), nunca baixada da Amazon (regra 1). No template, segue o placeholder (cor do nicho + inicial em itálico), como o site faz quando não tem foto. Nunca o logo das lojas.
6. **Exportar:** Figma ou Inkscape, PNG em 1x. Ou rode o gerador.

**Gerador:** `python3 docs/marca/redes/gerar.py` refaz todos os SVG e PNG (o `--svg` refaz só os SVG; o `--tabela` imprime o contraste). Ele usa o Google Chrome headless, porque rsvg-convert, cairosvg e inkscape não estão na máquina. Fora do macOS, aponte o binário com `CHROME=/caminho/do/chrome python3 docs/marca/redes/gerar.py`. O `--captura` baixa de novo a capa e tira de novo a tela do site (`posts/fontes/`); rode junto com a troca de `OFERTA`, para a tela e os números baterem. O recorte usa o `sips` do macOS e um enquadramento fixo do card: confira a imagem se o layout do site mudar. O gerador sai com erro se algum par de cor ficar abaixo do mínimo WCAG. Mudança de texto dos 9 posts e dos stories: edite `posts()` e `stories()` no script, ou edite o SVG direto (o script sobrescreve o SVG se for rodado de novo).

## Contraste (saída do `gerar.py --tabela`)

Texto ≥ 4,5:1; texto grande, carimbo e UI ≥ 3:1. Todos passam.

| Uso | Frente | Fundo | Razão | Mínimo |
|---|---|---|---|---|
| texto sobre noite (posts escuros) | #edf1f5 | #0f1729 | 15.75:1 | 4.5 |
| texto sobre marinho (perfil, fixada) | #edf1f5 | #1c2b4a | 12.39:1 | 4.5 |
| secundário sobre noite | #a9b4c8 | #0f1729 | 8.55:1 | 4.5 |
| secundário sobre marinho | #a9b4c8 | #1c2b4a | 6.73:1 | 4.5 |
| carimbo rosa sobre marinho (perfil) | #f2a3a8 | #1c2b4a | 7.08:1 | 3.0 |
| carimbo/selo coral sobre noite | #ff8a8f | #0f1729 | 7.90:1 | 3.0 |
| texto do selo sobre coral | #0f1729 | #ff8a8f | 7.90:1 | 4.5 |
| título sobre marfim (posts claros) | #1c2b4a | #edf1f5 | 12.39:1 | 4.5 |
| secundário sobre marfim | #4a5670 | #edf1f5 | 6.48:1 | 4.5 |
| carimbo vermelho sobre marfim | #b3262f | #edf1f5 | 5.72:1 | 3.0 |
| texto branco sobre vermelho | #ffffff | #b3262f | 6.49:1 | 4.5 |
| texto do botão WhatsApp | #06210f | #25d366 | 8.59:1 | 4.5 |
| ícone Telegram sobre noite | #2aabee | #0f1729 | 6.94:1 | 3.0 |
| @ do bot em azul Telegram sobre marinho | #2aabee | #1c2b4a | 5.46:1 | 4.5 |
| texto do formulário sobre papel (post 8) | #1c2b4a | #fbfcfd | 13.69:1 | 4.5 |
| rótulo do formulário sobre papel (post 8) | #4a5670 | #fbfcfd | 7.16:1 | 4.5 |
| ink sobre acento (10 nichos) | ex.: #22040f / #e5468f | | 5.07 a 5.34:1 | 4.5 |
| acento sobre noite (10 nichos) | | #0f1729 | 4.73 a 5.08:1 | 3.0 |
| acento sobre marfim (10 nichos) | | #edf1f5 | 3.10 a 3.33:1 | 3.0 |

O menor texto das artes tem 26 px num quadro de 1080, o que dá cerca de 9 pt no celular. Fica só no rodapé e nas guias.

## Pontos para o Elias decidir

1. **Domínio:** o kit agora mostra "ofertaslivros.com.br" no logo: o gerador acrescenta ".br" ao logo B, no traço fino e na cor do ".com". O `static/logo.svg` do site continua dizendo ".com" (e o nome do bot no Telegram é "Mavi · Ofertaslivros.com"). Se o Elias aprovar o ".br", o mesmo desenho vai para o `static/logo*.svg` e para `docs/marca/logos/wordmark-b*.svg`, numa tarefa do `frontend-developer`.
2. **Foto de perfil:** a escura (padrão) ou a clara.
3. **`@` das redes:** o canal do Telegram (`@maviOfertaslivros`) e o bot (`@ofertaslivros_bot`) já existem. O Instagram e o TikTok ainda não (ver `social.md`).
4. **Ícones de Telegram e WhatsApp:** são os desenhos de linha do site (avião de papel e balão), não os logos oficiais, e aparecem só como rótulo de botão. Se preferir, dá para usar só o texto.
5. **Descrição do canal do Telegram no ar:** "Melhor canal do melhor site de ofertas de livros do Brasil! ..." foge do tom (superlativo, exclamação) e não tem o aviso de afiliado. A sugestão está em `social.md`. O nome do bot ("Mavi · Ofertaslivros.com") também tem sugestão lá.
6. **Transparência sem post próprio:** o post "Como a gente ganha" saiu (rodada 2). O aviso de afiliado continua nas bios, na mensagem fixada, nas legendas de oferta e no rodapé de toda arte com preço.
