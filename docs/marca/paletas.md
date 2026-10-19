# Paletas, contraste e tipografia

Três combinações. Todas passam WCAG AA nos pares obrigatórios (texto ≥ 4,5:1; forma de UI ≥ 3:1), no claro e no escuro. Os números abaixo saem de `marca/contraste.py` (fórmula de luminância relativa do WCAG 2.x, com autoteste: preto/branco = 21:1, #777/#fff = 4,48:1). Para reconferir: `python3 marca/contraste.py --check`.

## Tokens

| Token | 1. Ficha | 2. Marca-texto | 3. Joia |
|---|---|---|---|
| fundo | #e8ecf0 | #f6f7f5 | #f3f1f7 |
| superfície (card) | #ffffff | #ffffff | #ffffff |
| texto | #1c2b4a | #10292a | #1f1633 |
| texto secundário | #4a5670 | #4d6261 | #5b5170 |
| primária / CTA | #1c2b4a (rótulo #ffffff) | #0d5c58 (rótulo #ffffff) | #4b1f7a (rótulo #ffffff) |
| destaque / preço-desconto | #b3262f | #c2361b | #a3123f |
| selo (90 dias) | #b3262f (texto #ffffff) | #f5c542 (texto #10292a) | #e3b341 (texto #1f1633) |
| borda (decorativa) | #b9cbe2 | #c8d5d3 | #d9d2e6 |
| sucesso | #1e6b45 | #2b6a2f | #17694c |

Modo escuro (opcional, via `prefers-color-scheme`):

| Token | 1. Ficha | 2. Marca-texto | 3. Joia |
|---|---|---|---|
| fundo | #0f1729 | #0b1a1b | #130d1f |
| superfície | #18233b | #132626 | #1e1630 |
| texto | #e6ebf3 | #e7f0ef | #efeaf7 |
| texto secundário | #a9b4c8 | #a3b8b6 | #b5abc9 |
| primária / CTA | #e6ebf3 (rótulo #0f1729) | #5cc8bf (rótulo #0b1a1b) | #c9a7f5 (rótulo #130d1f) |
| destaque | #ff8a8f | #ff8a6e | #ff7aa0 |
| selo | #ff8a8f (texto #0f1729) | #f5c542 (texto #10292a) | #e3b341 (texto #1f1633) |
| borda | #34425f | #2a4342 | #3a2f52 |
| sucesso | #6fd39b | #7fd18a | #6fd3a8 |

Observações:
- **Borda é decorativa** (o card não é um controle). Controles com contorno (chips de nicho, `summary`) devem usar `texto secundário` como borda, que passa 3:1 em todas.
- **Selo amarelo** (paletas 2 e 3) não tem 3:1 contra o card branco; quem carrega a informação é o texto dentro dele (≥ 4,5:1). Se o selo precisar se destacar sem texto, use contorno `texto`.
- O preço riscado usa `texto secundário` (não cinza claro): passa 4,5:1.

## Racional (ligado à pesquisa)
1. **Ficha** — evolução da direção atual. Azul-marinho de caneta + vermelho de carimbo + branco de ficha. Já é frio e de alto contraste (achados 1–3) e não é o creme de IA. O vermelho fica reservado para o histórico ("menor preço em 90 dias"), que é a implicação nº 1. Risco: vermelho também lê como "promoção" genérica; por isso só aparece no selo e no preço.
2. **Marca-texto** — branco quase puro (Cloud Dancer, achado 7) com teal (Transformative Teal, achado 8) no botão e o amarelo de marca-texto no selo: o leitor que grifa o livro. É a mais "2026" e a mais distante de Amazon/ML. Risco: teal é cor-tendência e pode datar.
3. **Joia** — tons de joia das capas 2026 (achado 1) e do público de romantasia do BookTok (achados 6 e 9): ameixa no CTA, carmim no preço, dourado no selo. É a mais emocional, boa para o tráfego do TikTok. Risco: puxa para um nicho (fantasia/romance) quando o site é de livros em geral.

## Tipografia

O site não carrega fonte externa (CSP `style-src`/`font-src 'self'`). Duas opções:

**A. Só fontes do sistema (0 KB)** — pilhas de [modernfontstacks.com](https://modernfontstacks.com/) (lido em 2026-10-18):
- Títulos e preço: Transitional `Charter, 'Bitstream Charter', 'Sitka Text', Cambria, serif` (é a que o site já usa; Charter vem no macOS/iOS).
- Texto e botões: `system-ui, sans-serif`.
- Preço sempre com `font-variant-numeric: tabular-nums lining-nums` para os dígitos alinharem.
- Para o conceito Carimbo: Old Style `'Iowan Old Style', 'Palatino Linotype', 'URW Palladio L', P052, serif`.

**B. OFL auto-hospedada** (servida de `/fonts/`, sem CDN; licença SIL OFL 1.1 permite redistribuir). Pesos **medidos** em 2026-10-18 baixando os WOFF2 do subconjunto *latin* (cobre acentos do português) do Fontsource via jsDelivr:

| Fonte | Papel | 400 | 700 |
|---|---|---|---|
| Literata (Fontsource 5.3.0) | títulos e preço | 20,4 KB | 22,0 KB |
| Atkinson Hyperlegible Next (5.3.0) | texto, botões | 12,1 KB | 12,7 KB |
| Source Serif 4 (5.3.1) | alternativa a Literata | 20,1 KB | 21,7 KB |

Combinação sugerida: **Literata 700 + Atkinson Hyperlegible Next 400 e 700 ≈ 46,8 KB** no total (só Literata 700 = 22 KB, com o texto no `system-ui`). Literata foi desenhada para leitura em tela (Google Play Livros); a Atkinson foi feita para legibilidade em baixa visão, o que ajuda no preço e no rótulo do botão. Usar `font-display: swap` e `<link rel="preload">` só da Literata 700, e manter a pilha do sistema como fallback com `size-adjust` se o salto incomodar.

## Tabelas de contraste (saída do script)

#### Ficha (claro)

| Par | Uso | Cores | Razão | Mínimo | OK |
|---|---|---|---|---|---|
| texto / fundo | texto corrido no fundo | #1c2b4a / #e8ecf0 | 11.84:1 | 4.5 | sim |
| texto / superficie | título/texto no card | #1c2b4a / #ffffff | 14.06:1 | 4.5 | sim |
| texto2 / superficie | autor, data, preço riscado | #4a5670 / #ffffff | 7.35:1 | 4.5 | sim |
| texto2 / fundo | status/legenda no fundo | #4a5670 / #e8ecf0 | 6.19:1 | 4.5 | sim |
| on_primaria / primaria | rótulo do botão da loja | #ffffff / #1c2b4a | 14.06:1 | 4.5 | sim |
| primaria / superficie | forma do botão no card (UI) | #1c2b4a / #ffffff | 14.06:1 | 3.0 | sim |
| destaque / superficie | preço/desconto no card | #b3262f / #ffffff | 6.49:1 | 4.5 | sim |
| on_selo / selo | texto do selo 90 dias | #ffffff / #b3262f | 6.49:1 | 4.5 | sim |
| sucesso / superficie | "menor preço" / confirmação | #1e6b45 / #ffffff | 6.47:1 | 4.5 | sim |
| borda / superficie | borda do card (decorativa) | #b9cbe2 / #ffffff | 1.65:1 | — | decorativo |

Par obrigatório mais fraco: **texto2/fundo = 6.19:1**

#### Ficha (escuro)

| Par | Uso | Cores | Razão | Mínimo | OK |
|---|---|---|---|---|---|
| texto / fundo | texto corrido no fundo | #e6ebf3 / #0f1729 | 14.93:1 | 4.5 | sim |
| texto / superficie | título/texto no card | #e6ebf3 / #18233b | 13.07:1 | 4.5 | sim |
| texto2 / superficie | autor, data, preço riscado | #a9b4c8 / #18233b | 7.49:1 | 4.5 | sim |
| texto2 / fundo | status/legenda no fundo | #a9b4c8 / #0f1729 | 8.55:1 | 4.5 | sim |
| on_primaria / primaria | rótulo do botão da loja | #0f1729 / #e6ebf3 | 14.93:1 | 4.5 | sim |
| primaria / superficie | forma do botão no card (UI) | #e6ebf3 / #18233b | 13.07:1 | 3.0 | sim |
| destaque / superficie | preço/desconto no card | #ff8a8f / #18233b | 6.92:1 | 4.5 | sim |
| on_selo / selo | texto do selo 90 dias | #0f1729 / #ff8a8f | 7.90:1 | 4.5 | sim |
| sucesso / superficie | "menor preço" / confirmação | #6fd39b / #18233b | 8.54:1 | 4.5 | sim |
| borda / superficie | borda do card (decorativa) | #34425f / #18233b | 1.56:1 | — | decorativo |

Par obrigatório mais fraco: **destaque/superficie = 6.92:1**

#### Marca-texto (claro)

| Par | Uso | Cores | Razão | Mínimo | OK |
|---|---|---|---|---|---|
| texto / fundo | texto corrido no fundo | #10292a / #f6f7f5 | 14.24:1 | 4.5 | sim |
| texto / superficie | título/texto no card | #10292a / #ffffff | 15.30:1 | 4.5 | sim |
| texto2 / superficie | autor, data, preço riscado | #4d6261 / #ffffff | 6.49:1 | 4.5 | sim |
| texto2 / fundo | status/legenda no fundo | #4d6261 / #f6f7f5 | 6.04:1 | 4.5 | sim |
| on_primaria / primaria | rótulo do botão da loja | #ffffff / #0d5c58 | 7.81:1 | 4.5 | sim |
| primaria / superficie | forma do botão no card (UI) | #0d5c58 / #ffffff | 7.81:1 | 3.0 | sim |
| destaque / superficie | preço/desconto no card | #c2361b / #ffffff | 5.47:1 | 4.5 | sim |
| on_selo / selo | texto do selo 90 dias | #10292a / #f5c542 | 9.43:1 | 4.5 | sim |
| sucesso / superficie | "menor preço" / confirmação | #2b6a2f / #ffffff | 6.55:1 | 4.5 | sim |
| borda / superficie | borda do card (decorativa) | #c8d5d3 / #ffffff | 1.51:1 | — | decorativo |

Par obrigatório mais fraco: **destaque/superficie = 5.47:1**

#### Marca-texto (escuro)

| Par | Uso | Cores | Razão | Mínimo | OK |
|---|---|---|---|---|---|
| texto / fundo | texto corrido no fundo | #e7f0ef / #0b1a1b | 15.37:1 | 4.5 | sim |
| texto / superficie | título/texto no card | #e7f0ef / #132626 | 13.59:1 | 4.5 | sim |
| texto2 / superficie | autor, data, preço riscado | #a3b8b6 / #132626 | 7.57:1 | 4.5 | sim |
| texto2 / fundo | status/legenda no fundo | #a3b8b6 / #0b1a1b | 8.57:1 | 4.5 | sim |
| on_primaria / primaria | rótulo do botão da loja | #0b1a1b / #5cc8bf | 8.89:1 | 4.5 | sim |
| primaria / superficie | forma do botão no card (UI) | #5cc8bf / #132626 | 7.85:1 | 3.0 | sim |
| destaque / superficie | preço/desconto no card | #ff8a6e / #132626 | 6.84:1 | 4.5 | sim |
| on_selo / selo | texto do selo 90 dias | #10292a / #f5c542 | 9.43:1 | 4.5 | sim |
| sucesso / superficie | "menor preço" / confirmação | #7fd18a / #132626 | 8.54:1 | 4.5 | sim |
| borda / superficie | borda do card (decorativa) | #2a4342 / #132626 | 1.49:1 | — | decorativo |

Par obrigatório mais fraco: **destaque/superficie = 6.84:1**

#### Joia (claro)

| Par | Uso | Cores | Razão | Mínimo | OK |
|---|---|---|---|---|---|
| texto / fundo | texto corrido no fundo | #1f1633 / #f3f1f7 | 15.35:1 | 4.5 | sim |
| texto / superficie | título/texto no card | #1f1633 / #ffffff | 17.20:1 | 4.5 | sim |
| texto2 / superficie | autor, data, preço riscado | #5b5170 / #ffffff | 7.35:1 | 4.5 | sim |
| texto2 / fundo | status/legenda no fundo | #5b5170 / #f3f1f7 | 6.56:1 | 4.5 | sim |
| on_primaria / primaria | rótulo do botão da loja | #ffffff / #4b1f7a | 11.82:1 | 4.5 | sim |
| primaria / superficie | forma do botão no card (UI) | #4b1f7a / #ffffff | 11.82:1 | 3.0 | sim |
| destaque / superficie | preço/desconto no card | #a3123f / #ffffff | 7.73:1 | 4.5 | sim |
| on_selo / selo | texto do selo 90 dias | #1f1633 / #e3b341 | 8.84:1 | 4.5 | sim |
| sucesso / superficie | "menor preço" / confirmação | #17694c / #ffffff | 6.64:1 | 4.5 | sim |
| borda / superficie | borda do card (decorativa) | #d9d2e6 / #ffffff | 1.47:1 | — | decorativo |

Par obrigatório mais fraco: **texto2/fundo = 6.56:1**

#### Joia (escuro)

| Par | Uso | Cores | Razão | Mínimo | OK |
|---|---|---|---|---|---|
| texto / fundo | texto corrido no fundo | #efeaf7 / #130d1f | 16.09:1 | 4.5 | sim |
| texto / superficie | título/texto no card | #efeaf7 / #1e1630 | 14.66:1 | 4.5 | sim |
| texto2 / superficie | autor, data, preço riscado | #b5abc9 / #1e1630 | 7.94:1 | 4.5 | sim |
| texto2 / fundo | status/legenda no fundo | #b5abc9 / #130d1f | 8.72:1 | 4.5 | sim |
| on_primaria / primaria | rótulo do botão da loja | #130d1f / #c9a7f5 | 9.35:1 | 4.5 | sim |
| primaria / superficie | forma do botão no card (UI) | #c9a7f5 / #1e1630 | 8.52:1 | 3.0 | sim |
| destaque / superficie | preço/desconto no card | #ff7aa0 / #1e1630 | 7.05:1 | 4.5 | sim |
| on_selo / selo | texto do selo 90 dias | #1f1633 / #e3b341 | 8.84:1 | 4.5 | sim |
| sucesso / superficie | "menor preço" / confirmação | #6fd3a8 / #1e1630 | 9.53:1 | 4.5 | sim |
| borda / superficie | borda do card (decorativa) | #3a2f52 / #1e1630 | 1.41:1 | — | decorativo |

Par obrigatório mais fraco: **destaque/superficie = 7.05:1**

