# Layout: técnicas para um site fluido, sem JS e mobile first

Pesquisa em 2026-10-18. Cada técnica tem fonte, o que ela resolve aqui e o trecho de CSS mínimo. Restrições: sem JS; mobile first; rodapé com aviso de associado e "o preço final é o da loja"; botão da loja mais barata com seta (`details/summary`) para a outra loja; botão "Me avise se baixar (Telegram)".

## 1. Escala tipográfica e espaçamento fluidos com `clamp()`
- **O quê:** define mínimo e máximo em duas larguras de viewport e o navegador interpola; não precisa de breakpoint. Fonte: [Utopia, "Designing with fluid type scales"](https://utopia.fyi/blog/clamp/) e o pacote [utopia-core](https://npmjs.com/utopia-core) (gera `--step-0…5` e `--space-*`).
- **Aqui:** escala de razão 1,2 em 360 px → 1,25 em 1280 px. O site já usa `clamp()` para gutter e gap; estender para todos os tamanhos.
```css
:root{
  --step--1: clamp(.83rem, .8rem + .15vw, .9rem);   /* meta: autor, data */
  --step-0:  clamp(1rem, .96rem + .2vw, 1.125rem);   /* texto */
  --step-1:  clamp(1.2rem, 1.1rem + .45vw, 1.4rem);  /* título do card */
  --step-2:  clamp(1.44rem, 1.3rem + .7vw, 1.75rem); /* preço */
  --step-4:  clamp(2.07rem, 1.7rem + 1.8vw, 3.05rem);/* h1 */
  --space-s: clamp(.75rem, .7rem + .25vw, 1rem);
  --space-m: clamp(1rem, .9rem + .5vw, 1.5rem);
  --space-l: clamp(1.5rem, 1.3rem + 1vw, 2.25rem);
}
```
- Cuidado WCAG 1.4.4: usar `rem + vw` (nunca só `vw`) para o zoom continuar funcionando.

## 2. Grid intrínseco (sem media query)
- **O quê:** `repeat(auto-fill, minmax(min(100%, X), 1fr))` cria quantas colunas couberem. Fonte: [Every Layout — Grid, Switcher, Cluster, Stack](https://every-layout.dev/layouts).
- **Aqui:** já em uso (`18rem`). Proposta: 1 coluna até ~600 px (card horizontal, capa à esquerda), 2–4 colunas acima. Baymard aponta a tensão no mobile entre miniatura grande e lista condensada ([Baymard, mobile search results](https://baymard.com/mcommerce-usability/benchmark/mobile-page-types/search-results)); com capa de livro (2:3) e preço, 1 coluna horizontal mostra ~3 ofertas por tela sem esconder atributo.

## 3. Container queries no card
- **O quê:** o card muda de forma pela largura **dele**, não da tela. `@container` de tamanho é Baseline desde 2023 (Chrome/Edge 106, Safari 16, Firefox 110). Fontes: [web.dev Baseline 2023](https://web.dev/blog/baseline2023?hl=en), [caniuse](https://caniuse.com/css-container-queries).
- **Aqui:** o mesmo card serve a vitrine (estreito) e o destaque (largo).
```css
.grid > li{ container-type:inline-size }
.card{ display:grid; grid-template-columns: 6.5rem 1fr; gap: var(--space-s) }
@container (min-width: 22rem){ .card{ grid-template-columns: 1fr } .capa{ aspect-ratio:2/3 } }
```

## 4. Primitivas: Stack, Cluster, Switcher
- **Stack** (ritmo vertical): `.stack > * + * { margin-block-start: var(--space, 1em) }`. Um espaço só por nível, em vez de margem em cada elemento.
- **Cluster** (chips de nicho, selos): `display:flex; flex-wrap:wrap; gap:.5rem`. Já em uso nos nichos.
- **Switcher** (os dois botões do card lado a lado quando cabem, empilhados quando não): `flex-wrap:wrap` + `flex-basis: calc((30rem - 100%) * 999)`.
- Fonte: [Every Layout](https://every-layout.dev/layouts).

## 5. Ritmo vertical
- Linha-base de 1.5 no texto, 1.1–1.2 nos títulos; espaços do card sempre múltiplos de `--space-s`. Medida de linha < 80 caracteres no texto corrido (`max-inline-size: 65ch`), como pede a skill de design e a tradição de Bringhurst.
- `text-wrap: balance` nos títulos de livro (Baseline 2024) e `pretty` como melhoria progressiva (não é Baseline; sem suporte cai no quebrar normal). Fontes: [MDN text-wrap](https://developer.mozilla.org/docs/Web/CSS/text-wrap), [LogRocket](https://blog.logrocket.com/css-text-wrap-balance-vs-text-wrap-pretty/) (2025-09).

## 6. Hierarquia do preço (dentro do card)
Baseado em [Baymard, price discounts](https://baymard.com/blog/product-page-price-discounts) (2022-05-25):
1. **Preço atual** grande (`--step-2`), negrito, `tabular-nums`, cor `texto` (o vermelho fica para o selo, para não haver dois elementos fortes).
2. **Selo "menor preço em 90 dias"** colado ao preço, só com histórico real.
3. **Preço anterior riscado** na mesma linha, `texto secundário`, só quando a origem é o nosso histórico.
4. **Desconto** em uma forma só: % abaixo de R$ 100, valor acima (regra do 100).
5. **Loja por extenso** dentro do botão: "Comprar na Amazon". Nunca só "Ver oferta".
6. **Mini-histórico** (sparkline em SVG inline, 90 dias): o diferencial, com `<title>` e texto alternativo ("variou de R$ 39,90 a R$ 64,90").

## 7. Botões sem JS
- **Loja mais barata + seta para a outra:** `<details>` cujo `<summary>` é a seta; o botão principal é um `<a>` irmão. Fontes: [modern-css, accordion sem JS](https://modern-css.com/accordion-without-javascript/), `::details-content` para estilizar só o painel.
```html
<div class="buy">
  <a class="btn" href="/r/abc">Comprar na Amazon <b>R$ 39,90</b></a>
  <details class="other">
    <summary aria-label="Ver na outra loja"></summary>
    <a href="/r/abc-ml">Mercado Livre <b>R$ 42,50</b></a>
  </details>
</div>
```
- Não usar `name` (acordeão exclusivo): há divergência sobre acessibilidade e não é necessário.
- **"Me avise se baixar (Telegram)"**: link secundário (contorno), link profundo para o bot com o ID do livro. Sem logo do Telegram; ícone de sino genérico ou nenhum.
- **Alvo de toque:** WCAG 2.2 AA pede 24×24 px ([2.5.8](https://dequeuniversity.com/rules/axe/4.8/target-size)); usar 44 px de altura como padrão (AAA 2.5.5), como o site já faz nos nichos.

## 8. Densidade mobile (390 px)
- Gutter `clamp(1rem, …)` = 16 px em 390 px; card horizontal de 104 px de capa; 3 ofertas por dobra.
- Cabeçalho curto: marca + 1 linha de proposta + chips de nicho. O destaque ("Menor preço do dia") vem antes da grade.
- Rodapé fixo em conteúdo (não `position:fixed`): aviso de associado + "o preço final é o da loja" + data/hora da última coleta.

## Escolhas para as pranchetas
Escala Utopia 1,2→1,25; grid intrínseco + container query no card; Stack/Cluster/Switcher; preço com hierarquia Baymard e selo colado; `details/summary` para a outra loja; alvos de 44 px; rodapé de transparência.
