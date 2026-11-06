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
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0f1729; --card: #18233b; --line: #e6ebf31a; --grid: #e6ebf312;
    --text: #e6ebf3; --muted: #a9b4c8; --mark: #e85a66; --mark-soft: #e85a6659; --track: #e6ebf314;
    --hl: #ff8a8f; --hl-text: #0f1729; --badge: #ff8a8f; --badge-ink: #0f1729;
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
.col .bar { fill: var(--mark); }
.col.parcial .bar { fill: var(--mark-soft); }
.col:hover .bar { fill: var(--text); }
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

.pedidos { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; max-height: 340px; overflow: auto; }
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
`;
