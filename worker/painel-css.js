// CSS do /painel, servido pelo próprio Worker em /painel/painel.css (atrás do Access + JWT).
// Arquivo à parte porque a CSP é style-src 'self': nada de <style> nem style="" inline.
// Cor das marcas validada com o dataviz (faixa de luminosidade e contraste ≥ 3:1 na superfície).
export const CSS = `
@font-face { font-family: "Fraunces"; font-weight: 100 900; font-display: swap; src: url(/fonts/fraunces-latin-full-normal.woff2) format("woff2"); }
@font-face { font-family: "Outfit"; font-weight: 100 900; font-display: swap; src: url(/fonts/outfit-latin-wght-normal.woff2) format("woff2"); }
:root {
  --bg: #edf1f5; --card: #ffffff; --line: #1c2b4a1f; --grid: #1c2b4a14;
  --text: #1c2b4a; --muted: #4a5670; --mark: #b3262f; --mark-soft: #b3262f59; --track: #1c2b4a12;
  --hl: #1c2b4a; --hl-text: #edf1f5; --badge: #b3262f; --badge-ink: #fff;
  --c1: #2f5fb3; --c2: #b3262f; --c3: #b87d00; /* categóricas validadas (dataviz) no fundo claro */
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0f1729; --card: #18233b; --line: #e6ebf31a; --grid: #e6ebf312;
    --text: #e6ebf3; --muted: #a9b4c8; --mark: #e85a66; --mark-soft: #e85a6659; --track: #e6ebf314;
    --hl: #ff8a8f; --hl-text: #0f1729; --badge: #ff8a8f; --badge-ink: #0f1729;
    --c1: #5b8def; --c2: #e85a66; --c3: #bd8a14; /* idem no fundo escuro; c2×c3 pede rótulo direto */
    color-scheme: dark;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.45 "Outfit", system-ui, sans-serif; }
.painel { max-width: 1280px; margin: 0 auto; padding: 24px 16px 64px; }
h1, h2 { font-family: "Fraunces", Georgia, serif; margin: 0; font-weight: 600; }
h1 { font-size: 36px; line-height: 1; }
h2 { font-size: 17px; margin-bottom: 14px; }
.topo { display: flex; flex-wrap: wrap; gap: 12px 24px; justify-content: space-between; align-items: end; margin-bottom: 20px; }
.kicker { margin: 0 0 4px; font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.meta { margin: 0; font-size: 13px; color: var(--muted); text-align: right; }

.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 16px; }
.tile { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 14px 16px; display: flex; flex-direction: column; gap: 2px; }
.tile .rotulo { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
.tile strong { font-family: "Fraunces", Georgia, serif; font-size: 30px; font-weight: 600; line-height: 1.15; font-variant-numeric: tabular-nums; }
.tile .sub { font-size: 13px; color: var(--muted); }
.tile.destaque { background: var(--hl); border-color: transparent; color: var(--hl-text); }
.tile.destaque .rotulo, .tile.destaque .sub { color: inherit; opacity: .8; }
.tile.alerta { border: 2px solid var(--badge); }

.grade { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 18px; padding: 18px 18px 14px; min-width: 0; }
.card.largo { grid-column: span 2; }
@media (max-width: 760px) { .grade { grid-template-columns: minmax(0, 1fr); } .card.largo { grid-column: auto; } .meta { text-align: left; } }
.nota { margin: 12px 0 0; font-size: 12.5px; color: var(--muted); }
.vazio { margin: 0; color: var(--muted); }

.plot { position: relative; padding-top: 18px; }
.plot svg { display: block; width: 100%; height: 180px; overflow: visible; }
.plot line { stroke: var(--grid); stroke-width: 1; vector-effect: non-scaling-stroke; }
.plot .ymax { position: absolute; top: 0; left: 0; font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }
.col .hit { fill: transparent; }
.eixo { display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); margin-top: 6px; }

.hbars { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.hbars li { display: grid; grid-template-columns: minmax(90px, 32%) 1fr 76px; gap: 10px; align-items: center; font-size: 13.5px; }
.hbars .rot { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hbars .trilho { width: 100%; height: 12px; display: block; background: var(--track); border-radius: 3px; }
.hbars rect { fill: var(--mark); }
.hbars li:hover rect { fill: var(--text); }
.hbars .val { font-variant-numeric: tabular-nums; text-align: right; min-width: 3ch; }
.hbars .val small { display: block; font-size: 11px; color: var(--muted); }

.grande { font-family: "Fraunces", Georgia, serif; font-size: 44px; font-weight: 600; margin: 0 0 10px; line-height: 1; }
.grande small { font-size: 18px; color: var(--muted); font-weight: 400; }
.medidor { display: block; width: 100%; height: 14px; }
.medidor rect { fill: var(--mark); }
.medidor .fundo { fill: var(--track); }

.pedidos { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px; max-height: 340px; overflow: auto; }
.pedidos li { display: grid; grid-template-columns: 1fr auto; gap: 2px 10px; padding: 10px 12px; border-radius: 12px; background: var(--track); }
.pedidos li.novo { outline: 2px solid var(--badge); outline-offset: -2px; }
.pedidos div { display: flex; flex-direction: column; min-width: 0; }
.pedidos strong { overflow-wrap: anywhere; }
.pedidos span, .pedidos time { font-size: 12.5px; color: var(--muted); }
.pedidos time { grid-column: 1; }
.badge { grid-column: 2; grid-row: 1; align-self: start; background: var(--badge); color: var(--badge-ink); font-size: 11px; letter-spacing: .06em; padding: 2px 8px; border-radius: 999px; }

details { margin-top: 12px; font-size: 13px; }
summary { cursor: pointer; color: var(--muted); }
table { width: 100%; border-collapse: collapse; margin-top: 8px; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--line); }
th { color: var(--muted); font-weight: 500; }
h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); font-weight: 500; margin: 14px 0 8px; }
h3:first-of-type { margin-top: 0; }
.legenda { list-style: none; margin: 0 0 6px; padding: 0; display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 12.5px; color: var(--muted); }
.legenda li { display: flex; align-items: center; gap: 6px; }
.sw { display: inline-block; width: 12px; height: 12px; border-radius: 3px; }
.sw.s1 { background: var(--c1); } .sw.s2 { background: var(--c2); } .sw.s3 { background: var(--c3); }
.sw.ln { height: 3px; background: var(--c2); } .sw.lm { height: 3px; background: var(--muted); }
.col .s1, .seg .s1 { fill: var(--c1); } .col .s2, .seg .s2 { fill: var(--c2); } .seg .s3 { fill: var(--c3); }
.col.parcial .s1, .col.parcial .s2 { opacity: .4; }
.col:hover .s1, .col:hover .s2 { opacity: 1; filter: brightness(1.15); }
.plot polyline { fill: none; vector-effect: non-scaling-stroke; stroke-linejoin: round; stroke-linecap: round; }
.plot .ln { stroke: var(--c2); stroke-width: 2.5; }
.plot .lm { stroke: var(--muted); stroke-width: 2; opacity: .8; }
.pt .hit { fill: transparent; } .pt:hover .hit { fill: var(--track); }
.spark { display: block; width: 100%; height: 30px; margin-top: 8px; }
.spark polyline { fill: none; stroke: var(--c2); stroke-width: 2; vector-effect: non-scaling-stroke; stroke-linejoin: round; }
.tile .medidor { margin-top: 10px; height: 10px; }
.funil { list-style: none; margin: 0 0 14px; padding: 0; display: grid; gap: 4px; }
.funil li { display: grid; grid-template-columns: minmax(90px, 34%) 1fr 64px; gap: 10px; align-items: center; font-size: 13.5px; }
.funil .trilho { width: 100%; height: 22px; display: block; background: var(--track); border-radius: 4px; }
.funil rect { fill: var(--c1); }
.funil .val { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }
.funil .passo { display: block; padding-left: calc(34% + 10px); font-size: 12.5px; color: var(--muted); }
.disp { display: block; width: 100%; height: auto; }
.disp .g { stroke: var(--grid); }
.disp .tick, .disp .eixo-t { fill: var(--muted); font-size: 13px; font-family: "Outfit", system-ui, sans-serif; }
.disp .ref { stroke: var(--muted); stroke-width: 1.5; opacity: .7; }
.disp circle { fill: var(--c1); stroke: var(--card); stroke-width: 2; }
.disp .abaixo circle { fill: var(--c3); }
.disp .dot:hover circle { r: 8; }
.disp .lbl { fill: var(--text); font-size: 13px; paint-order: stroke; stroke: var(--card); stroke-width: 4px; font-family: "Outfit", system-ui, sans-serif; }
.seg { display: block; width: 100%; height: 26px; border-radius: 6px; overflow: hidden; }
.seg-leg { margin-top: 8px; }
.seg-leg b { color: var(--text); font-weight: 600; }
.seg-leg span { font-size: 11.5px; }
.card-topo { display: flex; flex-wrap: wrap; gap: 8px 16px; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.card-topo h2 { margin: 0; }
.botao { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 999px; background: var(--hl); color: var(--hl-text); font-size: 13.5px; font-weight: 600; text-decoration: none; }
.botao:hover, .botao:focus-visible { filter: brightness(1.1); outline: 2px solid var(--text); outline-offset: 2px; }
.tile a { color: inherit; }
`;
