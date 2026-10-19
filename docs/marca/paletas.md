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


## Visual v2 (2026-10-19): papéis da spec com a Ficha refinada

Decisão do Elias (`spec-visual.md`): os papéis da spec do ofertasdiscos com a paleta Ficha. Os valores vivem só no `static/style.css` (`:root` e `:root[data-theme="dark"]`); a tabela abaixo é a saída do `python3 docs/marca/contraste.py`, que lê o CSS e sai com erro se algum par falhar.

| Papel na spec | Token | Claro | Escuro |
|---|---|---|---|
| cor profunda (`--wine`) | `--wine` | #1c2b4a | #1c2b4a |
| base clara (`--ivory`) / fundo | `--bg` | #edf1f5 | #0f1729 |
| cartões grandes, modal | `--bg2` | #f3f6f9 | #18233b |
| tinta | `--tint` | #e6ecf3 | #1d2a45 |
| superfície / pílula / linha | `--surface` / `--surface2` / `--line` | marinho a 5% / 9% / 13% | #e6ebf3 a 4% / 8% / 10% |
| texto / secundário | `--text` / `--muted` | #1c2b4a / #4a5670 | #e6ebf3 / #a9b4c8 |
| acento padrão (`--coral`) e selo | `--coral` (texto `--coral-ink`) | #b3262f (#ffffff) | #ff8a8f (#0f1729) |
| acento secundário (`--rose`) | `--rose` | #f2a3a8 | #f2a3a8 |

O acento padrão muda no escuro porque o vermelho #b3262f fica com 2,75:1 sobre #0f1729 (abaixo dos 3:1 de UI). O #ff8a8f é o destaque escuro da Ficha.

### Acentos por nicho

Saturação alta e luminância relativa entre 0,22 e 0,25: é a faixa em que o texto quase preto passa 4,5:1 sobre o acento **e** o acento passa 3:1 tanto no fundo claro quanto no escuro. Os acentos não mudam com o tema.

| Nicho | `--accent` | `--accent2` | `--accent-ink` |
|---|---|---|---|
| Literatura brasileira | #1f9a5a verde-mata | #7fd6a4 | #04140b |
| Ficção | #9468f5 violeta | #c7b2ff | #0d0626 |
| Negócios e finanças | #b87d00 ocre | #f2c14e | #1a1000 |
| Não ficção | #2b8fd6 azul-céu | #8cc8f2 | #03111f |
| Mangá e HQ | #e5468f pink | #ff9cc6 | #22040f |

O acento como **texto** só aparece em título grande (≥ 24 px, onde o mínimo é 3:1); texto pequeno fica em `--text`.

### Contraste (saída do script)

| Tema | Par | Cores | Razão | Mínimo | OK |
|---|---|---|---|---|---|
| claro | ficcao: texto sobre o acento | #0d0626 / #9468f5 | 5.19:1 | 4.5 | sim |
| claro | ficcao: acento sobre bg | #9468f5 / #edf1f5 | 3.33:1 | 3.0 | sim |
| claro | ficcao: acento sobre bg2 | #9468f5 / #f3f6f9 | 3.48:1 | 3.0 | sim |
| claro | literatura-brasileira: texto sobre o acento | #04140b / #1f9a5a | 5.25:1 | 4.5 | sim |
| claro | literatura-brasileira: acento sobre bg | #1f9a5a / #edf1f5 | 3.17:1 | 3.0 | sim |
| claro | literatura-brasileira: acento sobre bg2 | #1f9a5a / #f3f6f9 | 3.32:1 | 3.0 | sim |
| claro | manga: texto sobre o acento | #22040f / #e5468f | 5.13:1 | 4.5 | sim |
| claro | manga: acento sobre bg | #e5468f / #edf1f5 | 3.30:1 | 3.0 | sim |
| claro | manga: acento sobre bg2 | #e5468f / #f3f6f9 | 3.45:1 | 3.0 | sim |
| claro | nao-ficcao: texto sobre o acento | #03111f / #2b8fd6 | 5.44:1 | 4.5 | sim |
| claro | nao-ficcao: acento sobre bg | #2b8fd6 / #edf1f5 | 3.08:1 | 3.0 | sim |
| claro | nao-ficcao: acento sobre bg2 | #2b8fd6 / #f3f6f9 | 3.23:1 | 3.0 | sim |
| claro | negocios: texto sobre o acento | #1a1000 / #b87d00 | 5.34:1 | 4.5 | sim |
| claro | negocios: acento sobre bg | #b87d00 / #edf1f5 | 3.10:1 | 3.0 | sim |
| claro | negocios: acento sobre bg2 | #b87d00 / #f3f6f9 | 3.24:1 | 3.0 | sim |
| claro | padrão: texto sobre o acento | #ffffff / #b3262f | 6.49:1 | 4.5 | sim |
| claro | padrão: acento sobre bg | #b3262f / #edf1f5 | 5.72:1 | 3.0 | sim |
| claro | padrão: acento sobre bg2 | #b3262f / #f3f6f9 | 5.98:1 | 3.0 | sim |
| claro | text sobre bg | #1c2b4a / #edf1f5 | 12.39:1 | 4.5 | sim |
| claro | text sobre bg2 | #1c2b4a / #f3f6f9 | 12.96:1 | 4.5 | sim |
| claro | muted sobre bg | #4a5670 / #edf1f5 | 6.48:1 | 4.5 | sim |
| claro | muted sobre bg2 | #4a5670 / #f3f6f9 | 6.78:1 | 4.5 | sim |
| escuro | ficcao: acento sobre bg | #9468f5 / #0f1729 | 4.73:1 | 3.0 | sim |
| escuro | ficcao: acento sobre bg2 | #9468f5 / #18233b | 4.14:1 | 3.0 | sim |
| escuro | literatura-brasileira: acento sobre bg | #1f9a5a / #0f1729 | 4.96:1 | 3.0 | sim |
| escuro | literatura-brasileira: acento sobre bg2 | #1f9a5a / #18233b | 4.34:1 | 3.0 | sim |
| escuro | manga: acento sobre bg | #e5468f / #0f1729 | 4.77:1 | 3.0 | sim |
| escuro | manga: acento sobre bg2 | #e5468f / #18233b | 4.17:1 | 3.0 | sim |
| escuro | nao-ficcao: acento sobre bg | #2b8fd6 / #0f1729 | 5.11:1 | 3.0 | sim |
| escuro | nao-ficcao: acento sobre bg2 | #2b8fd6 / #18233b | 4.47:1 | 3.0 | sim |
| escuro | negocios: acento sobre bg | #b87d00 / #0f1729 | 5.08:1 | 3.0 | sim |
| escuro | negocios: acento sobre bg2 | #b87d00 / #18233b | 4.45:1 | 3.0 | sim |
| escuro | padrão: texto sobre o acento | #0f1729 / #ff8a8f | 7.90:1 | 4.5 | sim |
| escuro | padrão: acento sobre bg | #ff8a8f / #0f1729 | 7.90:1 | 3.0 | sim |
| escuro | padrão: acento sobre bg2 | #ff8a8f / #18233b | 6.92:1 | 3.0 | sim |
| escuro | text sobre bg | #e6ebf3 / #0f1729 | 14.93:1 | 4.5 | sim |
| escuro | text sobre bg2 | #e6ebf3 / #18233b | 13.07:1 | 4.5 | sim |
| escuro | muted sobre bg | #a9b4c8 / #0f1729 | 8.55:1 | 4.5 | sim |
| escuro | muted sobre bg2 | #a9b4c8 / #18233b | 7.49:1 | 4.5 | sim |
| blocos | marfim sobre o marinho | #edf1f5 / #1c2b4a | 12.39:1 | 4.5 | sim |
| blocos | rosado sobre o marinho | #f2a3a8 / #1c2b4a | 7.08:1 | 4.5 | sim |
