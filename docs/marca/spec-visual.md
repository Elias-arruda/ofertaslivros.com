# Spec visual do site (v2)

Decisão do Elias em 2026-10-19: o front segue a linguagem visual do ofertasdiscos.com, conforme a spec abaixo, com três trocas:
1. **Paleta:** a do manual da marca (Ficha refinada, `docs/marca/`), no lugar de vinho e creme. Os papéis da spec se mantêm: cor profunda da marca, base clara, acento padrão e acentos por categoria.
2. **Nicho:** livros no lugar de discos. O objeto-metáfora é o livro (páginas ou miolo saindo de trás da capa e marcador de fita na cor da categoria), seguindo a seção 11.1.
3. **Logo:** a variação B ("ofertas" leve, "livros" pesado, carimbo no lugar do "o" de livros).

Isso substitui a orientação anterior do CLAUDE.md de usar o ofertasdiscos "sem copiar a estética".

**Restrições do projeto que continuam valendo** (CLAUDE.md e specs de produto):
- **JavaScript como melhoria progressiva** (decisão do Elias em 2026-10-19, substitui o "sem JS"):
  - **Arquivo:** um só, nosso (`static/app.js`), sem framework, com `defer`, carregado depois do HTML. A CSP passa a ter `script-src 'self'`. Nada de script inline, `eval`, CDN, analytics ou script de terceiros.
  - **Sem JS o site funciona igual,** só sem os extras: o HTML gerado pelo `build.py` é completo, o carrossel passa sozinho em CSS, as categorias levam às páginas `/<nicho>/`, os detalhes ficam na página `/livro/<id>/` e a lista completa em `/ofertas/`.
  - **O que o JS acrescenta:** busca instantânea, ordenação, filtro de categoria sem recarregar (trocando o acento global), botão de tema claro/escuro (salvo em localStorage), setas e arraste no carrossel com a barra de progresso, modal de detalhes com histórico de navegação, "carregar mais" e a faixa de busca do header.
  - **Segurança:** o JS lê só os dados que o próprio HTML traz (atributos `data-*` ou um `<script type="application/json">` com escape de `<`) e escreve só com `textContent`. Nada de `innerHTML` com dado de oferta. Os links continuam sendo `/r/<id>` gerados no build.
- **"Pedir um livro":** abre o bot do Telegram. Não há formulário, porque não temos backend e a CSP mantém `form-action 'none'`.
- **Fontes OFL auto-hospedadas** em `static/fonts/` (`font-src 'self'`). Nada de Google Fonts em tempo de execução.
- **Regras de produto mantidas:**
  - o selo "menor preço em 90 dias" só aparece com histórico real;
  - botão da loja vencedora e acesso à outra loja;
  - "Me avise se baixar (Telegram)" em cada oferta;
  - rodapé com o aviso de associado e "o preço final é o da loja";
  - nada de urgência falsa (estoque e "em alta" só com dado real).
- **Curadores ilustrados:** ficam para quando houver arte. No MVP, um ícone desenhado por nicho no mesmo lugar.

---

## Texto original da spec (19/10/2026)

### 1. Como usar este documento
O objetivo é reproduzir a linguagem visual do ofertasdiscos.com (home analisada em 19/10/2026, desktop 1440px e mobile via CSS) em outro nicho. Layout, espaçamentos, raios, tipografia, comportamento e motion devem ser copiados fielmente; só mudam cores de acento, ícones, ilustrações, textos e o objeto-metáfora do nicho.

Conceito em uma frase: vitrine editorial quente, com cara de loja de discos independente — fundo creme com textura de grão, títulos serifados "macios", tudo em pílulas arredondadas, e cada produto tratado como um objeto físico que se mexe (capa inclinada, disco que desliza e gira).

Os 5 pilares que não podem se perder:
1. Fundo creme quente + manchas de cor desfocadas animadas + ruído (grão) por cima de tudo.
2. Tipografia em dupla: serif display expressiva (títulos, subtítulos em itálico) + sans geométrica (UI).
3. Forma: tudo é pílula (999px) ou cartão com raio grande (22–34px). Quase nada tem canto vivo.
4. Cor por categoria: cada categoria/curador tem um acento próprio que tinge card, botão, sticker, avatar e hover.
5. Objeto físico: o produto nunca é uma imagem chapada; é uma capa com sombra, levemente rotacionada, com o objeto do nicho saindo de trás no hover.

Pode mudar: paleta de acentos, nomes e ilustrações dos curadores, ícones, logo, objeto-metáfora (disco → livro, etc.), copy. Não pode mudar: grid, medidas, raios, pesos tipográficos, sombras, timings de animação, hierarquia e ordem das seções.

### 2. Design tokens
Todos os valores abaixo saem do CSS real do site. Implementar como CSS custom properties no :root, com tema claro e escuro trocando só as variáveis de superfície.

#### 2.1 Cores-base (marca)
| Token | Valor | Uso |
|---|---|---|
| --wine | #62051f | Cor de marca. Blocos escuros (bot, faixa de canais), botão flutuante, bordas de tags de estoque |
| --ivory | #f7e9cf | Creme da marca. Fundo do tema claro, texto sobre vinho |
| --coral | #e45b50 | Acento padrão (sem categoria ativa) |
| --rose | #c98b92 | Acento secundário, kicker sobre fundo vinho |
| --night | #171011 | theme-color do navegador |

#### 2.2 Superfícies e texto
Superfícies são sempre a cor da marca em baixa opacidade, nunca cinza. Isso mantém tudo "quente".

| Token | Tema claro | Tema escuro |
|---|---|---|
| --bg | #f7e9cf | #120b0c |
| --bg2 (cartões grandes, modal) | #f0dcb9 | #1d1214 |
| --surface (fundo de card) | #62051f a 5% (#62051f0d) | #f7e9cf a 4% (#f7e9cf0b) |
| --surface2 (botões ghost, pílulas) | #62051f a 9% (#62051f17) | #f7e9cf a 8% (#f7e9cf14) |
| --line (todas as bordas 1px) | #62051f a 13% (#62051f21) | #f7e9cf a 10% (#f7e9cf1a) |
| --text | #2b0811 | #f7e9cf |
| --muted | #2b0811 a 62% | #f7e9cf a 62% |
| --shadow | 0 30px 60px -34px #62051f73 | 0 30px 60px -30px #000000b3 |

#### 2.3 Acentos por categoria
Cada categoria define 3 variáveis: --accent, --accent2 (segunda cor para gradientes/anéis) e --accent-ink (texto sobre o acento, quase preto tingido). No card, a mesma cor chega como --c e --ink. Trocar estas cores é a principal personalização permitida; manter a saturação alta e luminosidade média para contrastar com o creme.

| Categoria (original) | --accent | --accent2 | --accent-ink |
|---|---|---|---|
| Brasileira | #fdb303 amarelo | #ff6b1a | #1b1203 |
| Rock | #fb514a vermelho | #ffb4a8 | #1a0605 |
| Indie | #be83fa lilás | #7b46c9 | #14061f |
| Pop | #fb4395 pink | #fb81cc | #1f0412 |
| Exploração (jazz/soul) | #1acdce turquesa | #fd7609 | #031a1a |

Cores funcionais fixas: verde WhatsApp #25d366 (texto #06210f), azul Telegram #2aabee / ícone #229ed9, verde "ao vivo/novo" #3ef08a, laranja "em alta" #ff7a1a, erro #b02e26.

#### 2.4 Tipografia
- Display: Fraunces Variable (Google Fonts), pesos 700–800, com font-variation-settings: "SOFT" 100, "WONK" 1 — isso arredonda as serifas e dá o ar "retrô amigável". Sem esses eixos, não fica igual. letter-spacing: -0.02em, line-height: 1.
- Corpo/UI: Outfit, pesos 400/500/600/700, 16px, line-height: 1.45, -webkit-font-smoothing: antialiased.
- Itálico da Fraunces é assinatura: subtítulos de produto, nome do álbum/obra, números do ranking, e palavras destacadas com `<em>` (que ficam na cor de acento).

| Elemento | Fonte | Tamanho | Peso | Extra |
|---|---|---|---|---|
| Título do hero (produto) | Fraunces | clamp(40px, 6.4vw, 96px) | 800 | line-height .98, máx. 3 linhas, text-wrap: balance |
| Subtítulo do hero | Fraunces itálico | clamp(20px, 2.4vw, 32px) | 400 | cor muted, máx. 2 linhas |
| H1 da página | Fraunces | clamp(30px, 4vw, 52px) | 700 | tracking -1px |
| H2 de seção | Fraunces | clamp(26px, 3.2vw, 38px) | 700 | com contador em Outfit 15px/600 muted ao lado |
| H2 de blocos grandes (bot, canais) | Fraunces | clamp(32px, 4.6vw, 60px) | 700 | máx. 18ch |
| Título do card | Fraunces | 21px | 700 | line-height 1.08, máx. 2 linhas |
| Subtítulo do card | Fraunces itálico | 15px | 400 | muted, 1 linha com reticências |
| Preço hero | Outfit | clamp(34px, 4.4vw, 56px) | 700 | tracking -0.03em |
| Preço card | Outfit | 22px | 700 | tracking -0.02em; riscado 13px muted |
| Botão | Outfit | 16px | 600 | — |
| Chips/badges | Outfit | 11–12px | 600–700 | MAIÚSCULAS, tracking .05–.06em |
| Kicker (sobretítulo) | Outfit | 13px | 700 | MAIÚSCULAS, tracking .1em |
| Meta ("enviada há 4h") | Outfit | 12–13px | 400 | muted |

#### 2.5 Raios
| Uso | Raio |
|---|---|
| Botões, chips, pílulas, inputs, faixa "strip" | 999px |
| Avatares, botão de compra, sticker de desconto, setas | 50% |
| Card de produto, banners inline, ranking | 22px (--radius) |
| Hero, bloco do bot, seção de canais | 34px |
| Modal | 30px; faixa de canais 24px; FAQ item 18px |
| Capa do produto dentro do card | 14px (hero 16px) |

#### 2.6 Sombras
Sombras são longas, difusas e com spread negativo (ficam "embaixo" do objeto, não em volta). Botões e stickers coloridos usam a própria cor como sombra.
- Capa no card: 0 16px 30px -18px #000c
- Capa no hero: 0 40px 70px -25px #000c
- Disco: inset 0 0 0 2px #000, 0 20px 40px -18px #000000e6
- Botão de acento: 0 12px 30px -12px var(--accent)
- Sticker de desconto: 0 10px 22px -8px var(--c)
- Card em hover: 0 24px 50px -28px var(--c)
- Botão flutuante: 0 16px 34px -12px #000000a6

#### 2.7 Motion
- Easing único: --ease: cubic-bezier(.2, .8, .2, 1) (rápido no começo, assenta suave).
- Durações: hover de botão .2s; cores e bordas .3s; capas e discos .6s; troca de cor do hero .7s; troca de tema .5s.
- Hover de botão: translateY(-2px); active: scale(.97).
- Respeitar prefers-reduced-motion zerando todas as animações.

#### 2.8 Fundo e textura
1. body com --bg sólido.
2. Camada fixa .bg-blobs com 3 círculos de 55vmax, blur(110px), opacidade .16 (.22 no claro): um no acento (canto sup. esquerdo), um no acento2 (canto inf. direito), um vinho de 35vmax no meio. Animação drift 28s alternada (translate 8vmax/6vmax, scale 1.15). Como o acento muda conforme a categoria, o fundo inteiro muda de clima.
3. Grão: body::after fixo, z-index: 100, opacity: .06, mix-blend-mode: overlay, com SVG feTurbulence fractalNoise (baseFrequency .85, 3 octaves) de 160×160 em repetição. É sutil mas é o que dá o aspecto de papel/impressão.

### 3. Layout global e ritmo
Página única, coluna central de no máximo 1440px, com gutter lateral fluido --pad: clamp(16px, 4vw, 40px). main tem padding: 0 var(--pad) 120px (os 120px finais deixam espaço para o botão flutuante). Não há sidebar: tudo empilha verticalmente, e a densidade vem do grid de cards.

Ordem das seções da home (de cima para baixo) e espaço antes de cada uma:
1. Header sticky (85px de altura no desktop) — seção 4.
2. Intro: H1 + parágrafo lado a lado — margin-top: 26px.
3. Hero carrossel (5 slides) — margin-top: 18px.
4. "Destaques da curadoria" + grid de 10 cards — margin-top: 30px.
5. "Filtrar por categoria" (avatares redondos) — margin-top: 26px.
6. "Ofertas ativas" + ordenação + grid infinito — margin-top: 30px. Dentro do grid entram, intercalados: faixa de canais, ranking "Em alta agora", banner inline do bot e a faixa "Primeiro …? Veja nossos guias".
7. Bloco grande do bot (vinho) — margin-top: 70px.
8. Seção "A curadoria inteira no seu celular" (canais) — margin-top: 70px.
9. FAQ (máx. 860px de largura, alinhado à esquerda) — margin-top: 70px.
10. Rodapé — padding: 50px var(--pad) 120px, borda superior 1px --line.

Regra de ritmo: 18–30px entre um título e seu conteúdo ou entre blocos relacionados; 70px entre blocos "de capítulo" (bot, canais, FAQ). Cabeçalhos de seção têm padding: 0 4px para alinhar opticamente com o raio dos cards abaixo.

Grid de produtos: grid-template-columns: repeat(auto-fill, minmax(214px, 1fr)), gap: clamp(14px, 2vw, 26px), margin-top: 24px. No desktop de 1440px isso dá 5 colunas de ~251px com 26px de gap. Itens especiais ocupam grid-column: span 2 (banner inline) ou 1 / -1 (ranking, faixa de canais).

### 4. Header
Barra sticky de vidro fosco, logo à esquerda e ações em pílulas à direita.
- Container: position: sticky; top: 0; z-index: 30, flex, gap: 16px, padding: 6px var(--pad). Fundo color-mix(in srgb, var(--bg) 72%, transparent) + backdrop-filter: blur(18px) saturate(1.4), borda inferior 1px --line. Altura resultante ~85px.
- Logo: imagem com 72px de altura (56px ≤640px, 46px ≤400px). O logo original é um lettering script vermelho com contorno escuro e um disco atrás — o novo logo deve ter o mesmo peso: colorido, ilustrado, levemente "sticker".
- Pílula "Ao vivo": ao lado do logo. Fundo --surface2, 999px, padding: 6px 12px, 13px/600 MAIÚSCULAS tracking .06em. Contém: bolinha verde #3ef08a de 8px com animação pulse 1.8s (anel que expande 9px e some) + texto + contador em mini-pílula com fundo --accent e texto --accent-ink (padding: 1px 8px). Some no mobile.
- Nav à direita (margin-left: auto; gap: 8px), todos 42px de altura, 999px, 14px/600, fundo --surface2 + borda 1px --line:
  - "Buscar" com ícone de lupa (padding: 0 14px). Ao clicar, abre uma faixa de busca de vidro logo abaixo do header, input centralizado de até 640px × 48px.
  - Botão de tema (só ícone de sol/lua, 42×42).
  - "Telegram" com ícone azul #229ed9; no hover o fundo ganha 14% de azul.
  - CTA principal verde WhatsApp #25d366, texto #06210f 700, padding: 0 18px, sombra 0 10px 24px -14px #25d366e6, sem borda. Hover: brightness(1.06).
- Hover de qualquer pílula: sobe 2px.

### 5. Intro e hero carrossel
#### 5.1 Intro
Linha flex com align-items: baseline, gap: 6px clamp(16px, 3vw, 36px), quebrando em telas menores: à esquerda o H1 ("Ofertas de …", Fraunces 52px/700), à direita um parágrafo muted de 16px, max-width: 62ch, flex: 340px. Ou seja, título e explicação dividem a mesma linha, não empilham.

#### 5.2 Hero — a peça mais importante do site
Carrossel de 5 ofertas em destaque, avanço automático, em um cartão grande.
- Cartão: border-radius: 34px, borda 1px --line, min-height: 460px, overflow: hidden, isolation: isolate. Fundo = cor da oferta atual misturada: color-mix(in srgb, var(--hc) 14%, var(--bg2)), com transição de .7s quando o slide muda. --hc é o acento da categoria daquele produto.
- Brilho: div .hero-glow em inset: -20%, z-index: -1, radial-gradient(circle at 75% 45%, --hc a 55%, transparente 55%), animação breathe 7s (escala 1.08 e opacidade .8 no meio). Fica atrás da capa, como uma luz.
- Grid interno: 1.1fr .9fr, gap: 24px, padding: clamp(24px, 4.5vw, 64px), itens centralizados verticalmente.

Coluna esquerda (texto), de cima para baixo:
1. Linha de chips (gap: 8px, margin-bottom: 18px): chip principal preenchido com --hc e ícone de raio ("MAIS RECENTE"), depois chips de contexto ("SÓ 2 EM ESTOQUE" em creme com borda vinho; "DESCONTO" em --surface2). Chips: 12px/600, MAIÚSCULAS, tracking .06em, padding: 6px 12px, 999px.
2. Título do produto (artista/autor) — Fraunces 800, até 96px, 3 linhas no máximo. Títulos longos ganham classe que reduz para clamp(34px, 4.6vw, 68px).
3. Subtítulo (nome da obra) em Fraunces itálico muted, até 32px, margin-top: 10px.
4. Bloco de preço (margin: 26px 0, flex baseline, gap: 12px): preço em Outfit 700 até 56px; pílula de desconto preenchida com --hc, 20px/800, padding: 4px 12px, rotacionada -4deg; texto "verificado às 06:47" 13px muted.
5. Botões (gap: 10px): primário "Ver preço na [loja]" com ícone de seta diagonal ↗, fundo --hc, texto #120606, sombra na própria cor; secundário "Ver detalhes" ghost. Ambos 48px de altura, padding: 0 22px, 999px, 600.
6. Assinatura do curador (margin-top: 24px): avatar redondo 30px + "Nome · Categoria" 13px muted.

Coluna direita (objeto): quadrado de até 460px, centralizado.
- Capa: 78% de largura, top: 11%, left: 0, fundo branco, raio 16px, transform: rotate(-4deg), sombra 0 40px 70px -25px #000c.
- Disco atrás da capa: 72% de largura, top: 14%, left: 27% — ou seja, aparece saindo pela direita. Feito 100% em CSS: repeating-radial-gradient de #121212/#1d1d1d (sulcos de 3,5px) + um anel sutil a 29%, conic-gradient por cima simulando reflexo de luz, rótulo central de 34% na cor --hc com furo central na cor do fundo. Gira continuamente (spin 2.4s linear infinite).
- Hover: capa vai para rotate(-1deg) translate(-6%) em .6s, revelando mais do disco.

Navegação do carrossel (abaixo do grid, padding: 0 64px 22px): uma barra de progresso segmentada (5 segmentos, gap: 6px, trilho de 4px em --line, preenchimento em --text animado linearmente durante o tempo do slide; segmentos já vistos ficam cheios) + contador "4/5" (14px/700, tabular-nums) + duas setas circulares de 44px (--surface2, borda --line; hover tinge com 30% de --hc). Swipe horizontal no touch.

Comportamento-chave: ao trocar o slide, fundo, brilho, chip, pílula de desconto, botão primário e rótulo do disco mudam todos para a cor da categoria do novo produto, com transição suave. Isso faz o hero "mudar de humor" a cada 5–7 segundos.

### 6. Card de oferta
O card é um cartão translúcido de 251×440px (desktop) com a capa quadrada no topo e o preço ancorado no rodapé. Cada card carrega a cor da sua categoria em --c / --ink.

Contêiner (article.card): display: flex; flex-direction: column, padding: 12px, border-radius: 22px, fundo --surface, borda 1px --line, position: relative. Transição .3s em borda, fundo e sombra.

Anatomia, de cima para baixo:
1. Área da capa (.sleeve, quadrada, aspect-ratio: 1, ~225px):
   - Objeto do nicho (disco) atrás, position: absolute; inset: 5%, parado.
   - Capa por cima, inset: 0, fundo branco, raio 14px, object-fit: contain (capas não são cortadas), sombra 0 16px 30px -18px #000c.
   - Badge de status no canto superior esquerdo (top/left: 10px): pílula 11px/700 MAIÚSCULAS, tracking .05em, padding: 5px 10px, sombra 0 6px 16px -6px #0009. Variações: "NOVO" verde #3ef08a (texto #052012); "EM ALTA" laranja #ff7a1a (texto #200c00); "EDIÇÃO ESPECIAL"/"LANÇAMENTO" na cor da categoria.
   - Sticker de desconto no canto superior direito, vazando para fora do card (top: -8px; right: -8px): círculo 58px na cor da categoria, "−30%" 16px/800, rotacionado 12deg, sombra na própria cor. Só aparece quando há preço de referência.
2. Corpo (padding: 14px 4px 2px, flex coluna, flex: 1):
   - Linha meta (gap: 8px, 12px muted): mini-avatar do curador 24px com anel de 2px na cor da categoria + "enviada há 4h".
   - Tag opcional "Só 2 em estoque": 11.5px/800, fundo creme --ivory, texto e borda 1px --wine, 999px, padding: 3px 9px, margin-top: 8px.
   - Título (artista/autor): Fraunces 21px/700, margin-top: 10px, máx. 2 linhas. É link; sublinhado só aparece no hover.
   - Subtítulo (obra): Fraunces itálico 15px muted, 1 linha com reticências, margin-top: 4px.
3. Rodapé (margin-top: auto; padding-top: 14px, flex space-between, align-items: flex-end): à esquerda o preço (22px/700; preço antigo riscado 13px muted logo abaixo); à direita o botão de compra: círculo 44px na cor da categoria com seta diagonal ↗ na cor --ink.

Hover do card (o momento "uau", tudo em .6s com --ease):
- Capa: translate(-8%) rotate(-3deg) — desliza para a esquerda e inclina.
- Disco: translate(22%) — sai pela direita e começa a girar (2.4s linear infinite).
- Sticker: rotate(-8deg) scale(1.1) (gira para o outro lado).
- Card: borda vira --c a 60%, fundo ganha 8% de --c, sombra colorida 0 24px 50px -28px var(--c).
- Botão de compra (hover próprio): rotate(45deg) scale(1.1) em .3s — a seta passa a apontar para a direita.

Estados extras:
- Card novo que entra no topo do feed: anel de 3px na cor da categoria que esmaece em 2.4s (fresh-in).
- Oferta encerrada: capa, disco e avatar em escala de cinza; botão de compra vira ghost; badge "ENCERRADA" em --text sobre --bg; disco não gira.
- Sem imagem: placeholder com gradiente radial --c2 → --c e a inicial em Fraunces itálico 800 com 72% de preto.

### 7. Filtro por categoria (curadores)
Em vez de abas ou dropdown, as categorias são personagens ilustrados em círculos, como "stories". Cada categoria tem um curador com nome próprio (Aurora, Valentina, Íris, Mel, Cora) e esse personagem reaparece nos cards, no hero e no modal.
- Cabeçalho: H2 Fraunces clamp(20px, 2.2vw, 26px), menor que os outros H2.
- Trilho: flex com scroll horizontal (scrollbar oculta, scroll-snap-type: x proximity), gap: 14px, padding-top: 14px. Quando há overflow, as bordas ganham máscara de fade de 56px e aparecem setas circulares de 44px.
- Item (136px de largura, centralizado, coluna, gap: 4px):
  - Anel de 88×88px com padding: 4px e fundo --line; dentro, o avatar ilustrado redondo.
  - Nome da categoria 14px/700; descrição 12.5px (ex. "Samba, rock nacional e mais") com text-wrap: balance; contagem de ofertas 12px muted.
  - Primeiro item "Todos": no lugar do avatar, um disco feito com conic-gradient passando por todas as cores de categoria, com furo central de 24%.
- Hover: anel sobe 4px e gira -6deg.
- Ativo: anel vira conic-gradient(--c, --c2, --c) girando continuamente (4s), com a imagem girando ao contrário para ficar parada; escala 1.06; nome sublinhado (2px) na cor da categoria.
- Efeito global: ao ativar uma categoria, o :root recebe data-style="rock" (etc.), o que troca --accent no site inteiro — manchas de fundo, botões, contador "ao vivo" e destaques mudam de cor.

Ilustrações dos curadores: retratos de meio-corpo em estilo cartoon flat, traço grosso, fundo circular na cor da categoria. Para o novo nicho, manter um personagem por categoria no mesmo estilo.

### 8. Feed e blocos intercalados
#### 8.1 Cabeçalho do feed
Padrão usado em "Destaques da curadoria" e "Ofertas ativas": linha flex align-items: baseline, gap: 6px 16px, com H2 (Fraunces até 38px) + contador colado ("45 no momento", Outfit 15px/600 muted, margin-left: 8px) + frase curta muted 14px que ocupa o resto da linha.

Abaixo (margin-top: 16px): "Ordenar por" 14px muted + select em pílula de 46px (fundo --surface, borda --line, chevron SVG à direita, 15px). Busca, quando visível, é pílula de 46px até 480px com borda que vira --accent no foco.

"Destaques" mostra 10 cards (2 linhas de 5); "Ofertas ativas" tem rolagem infinita com indicador "Carregando mais ofertas…" — mini-disco de 18px girando + texto 14px muted, centralizados. Quando chegam ofertas novas, uma pílula fixa no topo (top: 100px, centralizada, fundo --accent, 700, sombra na cor) avisa.

#### 8.2 Faixa de canais (dentro do grid, largura total)
Barra horizontal vinho, raio 24px, padding: 16px 30px, grid auto 1fr auto:
- Fundo: radial-gradient(circle at 0% 50%, coral a 38%, transparente 45%) sobre --wine, texto creme, --shadow.
- Esquerda: ícone "radar" de 56px (círculos concêntricos + varredura cônica girando 4s + ponto coral no centro).
- Centro: H2 Fraunces 26px "Receba as próximas ofertas de graça" (o itálico em coral) + linha 14px creme a 82%.
- Direita: botão WhatsApp verde 52px (ícone dentro de círculo de 36px, 15.5px/700) + botão Telegram contorno creme a 38%.
- Decoração: sulcos de disco (repeating-radial-gradient creme 6%) de 340px vazando pela direita, girando em 24s.

#### 8.3 Ranking "Em alta agora" (largura total)
Cartão raio 22px, padding: 22px, fundo linear-gradient(120deg, acento a 20% sobre --bg2, --bg2). Cabeçalho com ícone de raio + H3 Fraunces 26px e setas de 38px à direita. Trilho horizontal com scroll-snap: mandatory, gap: 12px, itens de 280px:
- Item: pílula retangular raio 16px, fundo --surface, borda --line, padding: 10px 10px 10px 14px.
- Número da posição em Fraunces itálico 800, 46px, na cor da categoria — é o elemento visual dominante.
- Nome 700 + obra em Fraunces itálico muted, ambos com reticências.
- Botão de compra circular 44px na cor da categoria.
- Hover: sobe 3px.

#### 8.4 Banner inline do bot (ocupa 2 colunas)
Cartão vinho de span 2, raio 22px, min-height: 260px, padding: 28px, conteúdo alinhado embaixo (justify-content: flex-end). Mascote circular (92–132px) flutuando no canto superior direito (float 5s: sobe 14px e gira 3deg) com halo de 6px creme a 10%. Kicker em pílula translúcida ("AGENTE NO TELEGRAM · GRÁTIS", 11px/700, tracking .12em), H3 Fraunces até 38px máx. 16ch, linha de apoio a 80% de opacidade e CTA pílula coral "Ativar alertas ↗". Sulcos de disco girando no canto (240px, 14s). Hover: translateY(-4px) rotate(-.5deg).

#### 8.5 Faixa de guias
Pílula horizontal de largura total (999px), padding: 18px 26px, fundo creme claro, 600: "Primeiro …? Veja nossos guias" à esquerda e "Ler guias ↗" à direita. Hover: scale(1.01).

### 9. Blocos finais, rodapé e camadas flutuantes
#### 9.1 Bloco do bot (capítulo vinho)
O maior bloco escuro da página; quebra o ritmo creme e vende o alerta personalizado.
- Cartão raio 34px, padding: clamp(24px, 5vw, 64px), grid auto 1fr, gap: clamp(20px, 4vw, 60px), margin-top: 70px.
- Fundo: radial-gradient(circle at 15% 50%, acento a 35%, transparente 50%) sobre --wine; texto --ivory.
- Esquerda: mascote redondo de 150–260px flutuando (float 5s), com dois halos (8px creme 8% e 16px creme 4%) e drop-shadow(0 30px 40px #00000080). Atrás dele, um radar de 150% de largura com varredura girando.
- Direita: kicker rosa --rose 13px/700 MAIÚSCULAS com ícone de sino ("BIS · SEU AGENTE NO TELEGRAM"); H2 Fraunces clamp(32px, 4.6vw, 60px), máx. 18ch, onde a segunda frase vem em `<em>` itálico coral; passos em pílulas horizontais (fundo creme 8%, padding: 8px 16px 8px 8px, número dentro de círculo de 28px na cor de acento); botões "Ativar" (acento) + "Montar minha lista" (ghost creme 10%); nota de rodapé 13.5px creme a 75%, máx. 54ch.
- Decoração: sulcos de disco de 380px girando em 22s, vazando pelo canto inferior direito.

#### 9.2 Seção de canais
Cartão claro (fundo --surface, borda --line, raio 34px, padding: clamp(24px, 4.5vw, 56px)): kicker muted ("CANAIS GRATUITOS"), H2 Fraunces clamp(30px, 4vw, 52px) com final em itálico de acento ("A curadoria inteira, no seu celular."), parágrafo 17px muted máx. 56ch, botões grandes de 56px (17px, padding: 0 26px) WhatsApp verde + Telegram, e link sublinhado "Como funcionam os canais ↗" com sublinhado na cor de acento a 60%.

#### 9.3 FAQ
Largura máxima 860px, alinhado à esquerda. Kicker muted + H2 Fraunces clamp(28px, 3.6vw, 46px). Lista com gap: 10px de `<details>`:
- Item: fundo --surface, borda --line, raio 18px. Pergunta (summary) 16.5px/600, min-height: 56px, padding: 12px 18px, chevron à direita rotacionado 90deg (aberto: -90deg). Hover: texto na cor de acento.
- Aberto: borda com 45% de acento e fundo com 5% de acento. Resposta padding: 0 18px 16px, line-height 1.6, máx. 68ch, links internos sublinhados com seta ↗ na cor de acento.

#### 9.4 Rodapé
Grid minmax(200px, .8fr) 3fr, gap: 28px clamp(24px, 4vw, 56px), 13.5px muted.
- Coluna da marca: logo de 80px de altura, frase curta, pílula social ("@perfil no Instagram", 44px, --surface2).
- 4 colunas de links (Ofertas, Guias, Receber ofertas, Sobre): título em Outfit 12px/700 MAIÚSCULAS tracking .12em muted; links 600 em --text, 36px de altura, sublinhado só no hover.
- Linha final com divisória 1px: aviso de afiliado 12.5px ocupando a largura toda.
- ≤900px: 1 coluna e links em 2 colunas.

#### 9.5 Botão flutuante "Pedir um [item]"
Fixo bottom/right: 20px, z-index: 38. Pílula vinho 52px, texto creme 14.5px/700, ícone de lupa, borda 1px creme a 20%, sombra 0 16px 34px -12px #000000a6. Hover sobe 2px. Abre um painel creme de 360px, raio 24px, com formulário (inputs de 46px, raio 14px, fundo #fffaf0, borda vinho a 25%). No mobile vira círculo de 48px só com ícone. Some suavemente quando colide com outro CTA.

#### 9.6 Modal de detalhes
Abre em "Ver detalhes"/clique no card. Fundo #080405b8 + blur(8px). Caixa --bg2, até 980px, raio 30px. Grid .9fr 1.1fr: à esquerda a mesma composição capa inclinada (-3deg) + disco girando; à direita título Fraunces até 52px, subtítulo itálico 22px, edição em 700 na cor da categoria, nota do curador em Fraunces 18px com borda esquerda de 3px na cor, bloco de datas. Rodapé fixo do modal com preço 40px + botões, fundo tingido com 6% da cor da categoria. Setas anterior/próximo e contador "3/45" no topo. No mobile vira bottom sheet (raio 26px só em cima).

### 10. Tema escuro, responsivo e acessibilidade
#### 10.1 Tema escuro
O padrão do CSS é escuro (--bg #120b0c); o claro creme entra via prefers-color-scheme: light ou data-theme="light". O botão de sol/lua no header força um dos dois. Só mudam as variáveis de superfície/texto da seção 2.2; acentos, vinho e componentes permanecem. No escuro, banners de WhatsApp/Telegram ganham gradientes próprios (verde-petróleo #13473a → #0b2b24, azul #143e5c → #0a2235). Troca de tema com transição de .5s em fundo e texto.

#### 10.2 Breakpoints
| Largura | O que muda |
|---|---|
| ≤ 1100px | Some texto auxiliar da nav |
| ≤ 900px | Hero vira 1 coluna com a capa em cima (order: -1, até 300px); modal em 1 coluna; bloco do bot empilha; filtros empilham; rodapé 1 coluna |
| 641–900px | Botão Telegram vira só ícone |
| ≤ 640px | Corpo 15px; logo 56px; some "Ao vivo"; Buscar/Telegram viram ícones 42×42; hero raio 26px, capa 184px, título clamp(32px, 10vw, 48px), preço 32px, some o curador, só 2 chips; grid de 2 colunas com gap 10px; card raio 18px e padding 8px; título do card 17px; preço 18px; botão de compra 38px; sticker 46px; badge 9.5px; Destaques limitado a 8 cards; modal vira bottom sheet; FAB vira círculo de 48px |
| ≤ 400px | Logo 46px |
| ≤ 350px | Botão WhatsApp vira só ícone |

#### 10.3 Acessibilidade e detalhes
- Foco: outline: 3px solid var(--accent); outline-offset: 3px; border-radius: 10px.
- Alvos de toque de no mínimo 44px em links e botões (inclusive links do FAQ e rodapé).
- Labels de ícones escondidos com .sr-only, nunca removidos.
- prefers-reduced-motion: todas as animações e transições a .001ms.
- scroll-behavior: smooth; âncoras com scroll-margin-top ~100px por causa do header sticky.

### 11. Adaptação para o novo nicho e checklist de aceite
#### 11.1 Mapa de troca
O único elemento que exige redesenho é o objeto-metáfora (o disco). Ele aparece em 6 lugares e precisa de um equivalente com a mesma função: algo que sai de trás da capa no hover e tem uma animação contínua.

| Elemento original | Função visual | Exemplo para nicho de livros |
|---|---|---|
| Disco atrás da capa (card e hero) | Revela "o produto real" no hover, gira | Bloco de páginas/miolo saindo pela lateral; no hover as páginas "folheiam" em loop curto |
| Rótulo central do disco na cor da categoria | Ponto de cor da categoria no objeto | Marcador de página (fita) na cor da categoria |
| Sulcos girando nos cantos (bot, banners, faixa) | Textura decorativa em movimento | Linhas pautadas ou anéis de carimbo girando devagar |
| Disco "Todos" em gradiente cônico | Ícone multicolor do filtro geral | Pilha de lombadas com as cores das categorias |
| Mini-disco girando no loading | Indicador de carregamento | Página virando |
| Radar (canal/bot) | "Estamos vigiando ofertas" | Pode ser mantido igual |

Trocar também: logo (lettering ilustrado no mesmo peso), curadores ilustrados (um por categoria), paleta de 5 acentos (seção 2.3, mesma saturação), copy, nome do bot e ícones de seta/loja. Manter: vinho + creme como base neutra da marca, ou substituí-los por um par equivalente (cor profunda + creme claro), nunca por branco puro e cinza.

#### 11.2 Checklist de aceite
- [ ] Fraunces com eixos SOFT 100 e WONK 1 aplicados em todos os títulos; Outfit na UI
- [ ] Grão SVG visível (opacidade .06) e 3 manchas desfocadas animadas no fundo
- [ ] Nenhum branco puro de fundo nem cinza neutro; superfícies sempre da cor da marca em baixa opacidade
- [ ] Todos os botões, chips e inputs em pílula (999px); cards 22px; blocos grandes 34px
- [ ] Hero muda fundo, brilho, chips, desconto, botão e rótulo para a cor do produto a cada slide
- [ ] Capa do hero inclinada -4deg, objeto saindo pela direita e girando; barra de progresso segmentada
- [ ] Grid 5 colunas a 1440px (minmax(214px, 1fr), gap 26px) e 2 colunas no mobile
- [ ] Hover do card: capa -8%/-3deg, objeto +22% e animado, sticker gira, borda e sombra coloridas
- [ ] Sticker de desconto redondo, rotacionado 12deg, vazando 8px para fora do card
- [ ] Filtro por personagens circulares com anel cônico animado no ativo, trocando o acento global
- [ ] Ranking com números em Fraunces itálico 46px na cor da categoria
- [ ] Blocos vinho (faixa, banner 2 colunas, bot) com sulcos girando e mascote flutuando
- [ ] Header de vidro sticky com CTA verde de WhatsApp em destaque
- [ ] Tema claro e escuro funcionando; breakpoints da seção 10.2 conferidos
- [ ] prefers-reduced-motion respeitado; foco visível; alvos ≥ 44px

Referência: ofertasdiscos.com, analisado em 19/10/2026 (valores extraídos do CSS publicado e de medições no navegador a 1440px).
