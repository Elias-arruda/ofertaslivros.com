// /painel: KPIs do site só para o Elias (docs/produto/analytics.md, F1b).
// Duas travas: o Cloudflare Access na frente (ofertaslivros.com.br/painel, só o e-mail do Elias) e,
// aqui, a conferência do JWT do Access. Sem JWT válido = 403, mesmo se a regra do Access sumir
// ou se o pedido vier pelo workers.dev. HTML montado no servidor, sem JS, tudo escapado.
import { brDay, fetchDay, toRows } from "../cron/rollup.js";
import { CSS } from "./painel-css.js";

const HOST = "ofertaslivros.com.br";
const TEAM = "https://ofertaslivros.cloudflareaccess.com";
const AUD = "eae97b05c067191b8a26d7e97bfbf575088be98d0e891009127728de1932779b"; // não é segredo
const EMAIL = "mkt.eliasarruda@gmail.com";
const NICHOS = new Set(["literatura-brasileira", "ficcao", "romance", "fantasia", "suspense", "mindset",
  "negocios", "politica", "historia", "manga"]); // GENRES do build.py

const b64url = s => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));
const json64 = s => JSON.parse(new TextDecoder().decode(b64url(s)));

let jwks = null, jwksAt = 0; // ponytail: cache por isolate, 1 h; a Cloudflare gira as chaves com folga
async function keys(fetcher) {
  if (!jwks || Date.now() - jwksAt > 3600e3) {
    const r = await fetcher(`${TEAM}/cdn-cgi/access/certs`);
    if (!r.ok) throw new Error(`certs do Access: ${r.status}`);
    jwks = (await r.json()).keys || []; jwksAt = Date.now();
  }
  return jwks;
}

/** Confere o JWT do Access (RS256, kid conhecido, aud, iss, exp e e-mail). Devolve o e-mail ou null. */
export async function accessEmail(token, { fetcher = fetch, now = Date.now() } = {}) {
  const parts = (token || "").split(".");
  if (parts.length !== 3) return null;
  try {
    const [h, p] = [json64(parts[0]), json64(parts[1])];
    if (h.alg !== "RS256") return null;
    const jwk = (await keys(fetcher)).find(k => k.kid === h.kid);
    if (!jwk) return null;
    const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64url(parts[2]),
      new TextEncoder().encode(`${parts[0]}.${parts[1]}`));
    const aud = Array.isArray(p.aud) ? p.aud : [p.aud];
    if (!ok || !aud.includes(AUD) || p.iss !== TEAM || !(p.exp * 1000 > now) || p.email !== EMAIL) return null;
    return p.email;
  } catch { return null; }
}

const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const n = v => Number(v || 0).toLocaleString("pt-BR");

/** /r/<id>[/loja|/tg|/wa] → { id, canal, loja }. */
export function clique(path) {
  const [, , id, suf] = path.split("/");
  return { id, canal: suf === "tg" || suf === "wa" ? suf : "site", loja: suf && suf !== "tg" && suf !== "wa" ? suf : "vencedora" };
}

function tabela(cols, linhas) {
  const head = cols.map(c => `<th>${esc(c)}</th>`).join("");
  const body = linhas.length ? linhas.map(l => `<tr>${l.map(v => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")
    : `<tr><td colspan="${cols.length}">Sem dados.</td></tr>`;
  return `<details><summary>Ver tabela</summary><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></details>`;
}

const dm = d => `${d.slice(8, 10)}/${d.slice(5, 7)}`;
const pct = (a, b) => (b ? `${(100 * a / b).toFixed(1)}%` : "—");

/** Colunas por dia em SVG (sem JS: tooltip pelo <title>, destaque no :hover pelo CSS). */
function colunas(pontos, unidade) {
  const max = Math.max(1, ...pontos.map(p => p.y)), W = pontos.length * 10 || 10;
  const cols = pontos.map((p, i) => {
    const h = 92 * p.y / max;
    return `<g class="col${p.parcial ? " parcial" : ""}"><title>${esc(dm(p.x))}${p.parcial ? " (hoje, parcial)" : ""}: ${n(p.y)} ${esc(unidade)}</title>`
      + `<rect class="hit" x="${i * 10}" y="0" width="10" height="100"/><rect class="bar" x="${i * 10 + 1.5}" y="${(100 - h).toFixed(2)}" width="7" height="${h.toFixed(2)}"/></g>`;
  }).join("");
  const grid = [8, 54, 100].map(y => `<line x1="0" x2="${W}" y1="${y}" y2="${y}"/>`).join("");
  const eixo = pontos.length ? `<div class="eixo"><span>${esc(dm(pontos[0].x))}</span><span>${esc(dm(pontos.at(-1).x))}${pontos.at(-1).parcial ? " · hoje" : ""}</span></div>` : "";
  return `<div class="plot"><span class="ymax">${n(max)}</span><svg viewBox="0 0 ${W} 100" preserveAspectRatio="none" role="img" aria-label="${esc(unidade)} por dia">${grid}${cols}</svg>${eixo}</div>`;
}

/** Barras horizontais ranqueadas: rótulo, barra (largura em % do maior) e valor. */
function barras(linhas, vazio = "Sem dados ainda.") {
  if (!linhas.length) return `<p class="vazio">${esc(vazio)}</p>`;
  const max = Math.max(1, ...linhas.map(l => l.v));
  return `<ol class="hbars">${linhas.map(l => `<li><span class="rot" title="${esc(l.rot)}">${esc(l.rot)}</span>`
    + `<svg class="trilho" preserveAspectRatio="none"><title>${esc(l.rot)}: ${n(l.v)}${l.extra ? ` · ${esc(l.extra)}` : ""}</title><rect width="${(100 * l.v / max).toFixed(1)}%" height="100%" rx="3"/></svg>`
    + `<span class="val">${n(l.v)}${l.extra ? `<small>${esc(l.extra)}</small>` : ""}</span></li>`).join("")}</ol>`;
}

function tile(rotulo, valor, sub = "", cls = "") {
  return `<div class="tile ${cls}"><span class="rotulo">${esc(rotulo)}</span><strong>${esc(valor)}</strong>${sub ? `<span class="sub">${esc(sub)}</span>` : ""}</div>`;
}

/** Variação contra a janela anterior, em texto (não é cor de status). */
function delta(atual, antes) {
  if (!antes) return "sem base anterior";
  const v = 100 * (atual - antes) / antes;
  return `${v >= 0 ? "▲" : "▼"} ${Math.abs(v).toFixed(0)}% vs 7 dias antes`;
}

const card = (titulo, corpo, cls = "", nota = "") =>
  `<section class="card ${cls}"><h2>${esc(titulo)}</h2>${corpo}${nota ? `<p class="nota">${esc(nota)}</p>` : ""}</section>`;

const soma = (rows, f) => rows.filter(f).reduce((a, r) => a + r.requests, 0);

export async function dados(env, now = new Date()) {
  const db = env.ANALYTICS;
  const [porDia, livros7, cliques7, nichos7, ultimo] = await Promise.all([
    db.prepare(`SELECT day, SUM(CASE WHEN bot = 0 AND status = 200 AND path NOT LIKE '/r/%' THEN requests END) AS views,
      SUM(CASE WHEN bot = 0 AND path LIKE '/r/%' THEN requests END) AS cliques,
      SUM(CASE WHEN bot = 1 THEN requests END) AS bots
      FROM daily_rollup WHERE day >= date('now', '-3 hours', '-30 days') GROUP BY day ORDER BY day DESC`).all(),
    db.prepare(`SELECT substr(path, 8, length(path) - 8) AS id, SUM(requests) AS views FROM daily_rollup
      WHERE bot = 0 AND path LIKE '/livro/%/' AND day >= date('now', '-3 hours', '-7 days') GROUP BY id`).all(),
    db.prepare(`SELECT path, SUM(requests) AS requests FROM daily_rollup
      WHERE bot = 0 AND path LIKE '/r/%' AND day >= date('now', '-3 hours', '-7 days') GROUP BY path`).all(),
    db.prepare(`SELECT path, SUM(requests) AS views FROM daily_rollup
      WHERE bot = 0 AND status = 200 AND day >= date('now', '-3 hours', '-7 days') GROUP BY path`).all(),
    db.prepare(`SELECT MAX(day) AS day FROM daily_rollup`).first(),
  ]);
  // Tabelas que nascem depois (pedidos no 1º pedido, sales no 1º import): sem tabela = lista vazia.
  const talvez = q => q.all().then(r => r.results, () => []);
  const [pedidos, vendas] = await Promise.all([
    talvez(db.prepare(`SELECT criado_em, titulo, autor, criado_em >= datetime('now', '-1 day') AS novo
      FROM pedidos ORDER BY id DESC LIMIT 100`)),
    talvez(db.prepare(`SELECT store, status, SUM(qty) AS itens, SUM(revenue_cents) AS receita,
      SUM(commission_cents) AS comissao, MAX(order_date) AS ate FROM sales
      WHERE order_date >= date('now', '-3 hours', '-30 days') GROUP BY store, status`)),
  ]);
  // Hoje (desde 00:00 em Brasília) direto do GraphQL: alguns minutos de atraso.
  const hoje = brDay(now, 0);
  const rowsHoje = toRows(await fetchDay(env.CF_ANALYTICS_TOKEN, hoje))
    .map(([path, status, country, bot, requests]) => ({ path, status, bot, requests }));
  return { porDia: porDia.results, livros7: livros7.results, cliques7: cliques7.results, nichos7: nichos7.results,
    ultimoDia: ultimo?.day || null, hoje, rowsHoje, pedidos, vendas, geradoEm: now };
}

export function render(d) {
  const humanos = d.rowsHoje.filter(r => !r.bot);
  const viewsHoje = soma(humanos, r => r.status === 200 && !r.path.startsWith("/r/"));
  const cliquesHoje = soma(humanos, r => r.path.startsWith("/r/"));
  const topHoje = Object.entries(humanos.filter(r => r.path.startsWith("/r/"))
    .reduce((a, r) => ({ ...a, [clique(r.path).id]: (a[clique(r.path).id] || 0) + r.requests }), {}))
    .filter(([, c]) => c > 0).sort((a, b) => b[1] - a[1]).slice(0, 10);

  const viewsLivro = Object.fromEntries(d.livros7.map(r => [r.id, r.views]));
  const porLivro = {}, porCanal = { site: 0, tg: 0, wa: 0 }, porLoja = {};
  for (const r of d.cliques7) {
    const c = clique(r.path);
    porLivro[c.id] = (porLivro[c.id] || 0) + r.requests;
    porCanal[c.canal] += r.requests;
    porLoja[c.loja] = (porLoja[c.loja] || 0) + r.requests;
  }
  const topLivros = Object.entries(porLivro).sort((a, b) => b[1] - a[1]).slice(0, 15);
  const nichos = d.nichos7.filter(r => NICHOS.has(r.path.slice(1, -1))).sort((a, b) => b.views - a.views);
  const brl = c => (Number(c || 0) / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const novos = d.pedidos.filter(p => p.novo).length;
  const v = (store, status) => d.vendas.find(r => r.store === store && r.status === status) || {};
  const qualificadas = (v("amazon", "enviado").itens || 0) - (v("amazon", "devolvido").itens || 0);
  const comissao = (v("amazon", "enviado").comissao || 0) + (v("amazon", "devolvido").comissao || 0);
  const vendasAte = d.vendas.reduce((m, r) => (r.ate > m ? r.ate : m), "") || "—";
  const hora = d.geradoEm.toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" });

  // Série diária (antiga → nova) + hoje como coluna parcial.
  const dias = [...d.porDia].reverse();
  const serieV = dias.map(r => ({ x: r.day, y: r.views || 0 })).concat([{ x: d.hoje, y: viewsHoje, parcial: true }]);
  const serieC = dias.map(r => ({ x: r.day, y: r.cliques || 0 })).concat([{ x: d.hoje, y: cliquesHoje, parcial: true }]);
  const janela = (k, de, ate) => dias.slice(de, ate).reduce((a, r) => a + (r[k] || 0), 0);
  const v7 = janela("views", -7), v7a = janela("views", -14, -7), c7 = janela("cliques", -7), c7a = janela("cliques", -14, -7);
  const meta = Math.min(100, 10 * qualificadas);

  const pedidosHtml = d.pedidos.length ? `<ul class="pedidos">${d.pedidos.slice(0, 12).map(p =>
    `<li${p.novo ? ' class="novo"' : ""}><div><strong>${esc(p.titulo)}</strong><span>${esc(p.autor || "autor não informado")}</span></div>`
    + `<time>${esc(p.criado_em)} UTC</time>${p.novo ? '<b class="badge">NOVO</b>' : ""}</li>`).join("")}</ul>`
    : `<p class="vazio">Nenhum pedido nos últimos 30 dias.</p>`;

  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60">
<meta name="robots" content="noindex"><title>Painel · Ofertas Livros</title><link rel="stylesheet" href="/painel/painel.css"></head>
<body><main class="painel">
<header class="topo"><div><p class="kicker">Ofertas Livros</p><h1>Painel</h1></div>
<p class="meta">Atualizado ${esc(hora)} · recarrega a cada 60 s · sem bots<br>histórico até ${esc(d.ultimoDia || "—")} · hoje pelo GraphQL (minutos de atraso)</p></header>

<div class="tiles">
${tile("Views hoje", n(viewsHoje), `CTR ${pct(cliquesHoje, viewsHoje)}`)}
${tile("Cliques hoje", n(cliquesHoje), "em /r/ (site + canais)")}
${tile("Views 7 dias", n(v7), delta(v7, v7a))}
${tile("Cliques 7 dias", n(c7), delta(c7, c7a))}
${tile("Comissão Amazon 30 dias", brl(comissao), `vendas até ${vendasAte}`, "destaque")}
${tile("Pedidos de livro", n(novos), "novos nas últimas 24 h", novos ? "alerta" : "")}
</div>

<div class="grade">
${card("Views por dia", colunas(serieV, "views") + tabela(["Dia", "Views", "Cliques", "Bots"], d.porDia.map(r => [r.day, n(r.views), n(r.cliques), n(r.bots)])), "largo", "Páginas HTML com status 200, sem bots. A última coluna (mais clara) é hoje, ainda parcial.")}
${card("Cliques de afiliado por dia", colunas(serieC, "cliques"), "largo", "Cada acesso a /r/ que redirecionou para a loja.")}

${card("Creators API", `<p class="grande">${n(qualificadas)} <small>de ~10</small></p><svg class="medidor" preserveAspectRatio="none"><title>${n(qualificadas)} de ~10 vendas qualificadas</title><rect class="fundo" width="100%" height="100%" rx="6"/><rect width="${meta}%" height="100%" rx="6"/></svg>`
  + tabela(["Status", "Itens", "Receita", "Comissão"], ["pedido", "enviado", "devolvido"].map(st => [st, n(v("amazon", st).itens), brl(v("amazon", st).receita), st === "pedido" ? "—" : brl(v("amazon", st).comissao)])),
  "", `Creators API: ${qualificadas} de ~10 vendas qualificadas (enviadas − devolvidas) em 30 dias. Vem do CSV exportado pelo Chrome, D+1; o número que vale é o do painel da Amazon. ML: o portal não tem exportação.`)}
${card(`Pedidos de livro: ${novos} novo(s) nas últimas 24 h`, pedidosHtml, "", "Formulário \"Pedir um livro\" (também vai para pedidos@ofertaslivros.com). Ficam 30 dias.")}

${card("Top livros (7 dias)", barras(topLivros.map(([id, c]) => ({ rot: id, v: c, extra: viewsLivro[id] ? `CTR ${pct(c, viewsLivro[id])}` : "" })))
  + tabela(["Livro", "Cliques", "Views da página", "CTR"], topLivros.map(([id, c]) => [id, n(c), n(viewsLivro[id]), pct(c, viewsLivro[id])])),
  "largo", "CTR = cliques em /r/<id> ÷ views de /livro/<id>/. Clique vindo do canal não passa pela página, então pode passar de 100%.")}
${card("Top livros hoje", barras(topHoje.map(([id, c]) => ({ rot: id, v: c })), "Nenhum clique hoje ainda."))}
${card("Nichos mais vistos (7 dias)", barras(nichos.map(r => ({ rot: r.path, v: r.views }))) + tabela(["Página", "Views"], nichos.map(r => [r.path, n(r.views)])))}
${card("Canal (7 dias)", barras(Object.entries(porCanal).map(([k, c]) => ({ rot: k, v: c }))) + tabela(["Canal", "Cliques"], Object.entries(porCanal).map(([k, c]) => [k, n(c)])))}
${card("Loja (7 dias)", barras(Object.entries(porLoja).sort((a, b) => b[1] - a[1]).map(([k, c]) => ({ rot: k, v: c }))), "", "vencedora = /r/<id> (a loja com menor preço no dia); amazon/mercadolivre = a seta da outra loja.")}
</div>
</main></body></html>`;
}

const HEADERS = {
  "Content-Type": "text/html; charset=utf-8",
  "Cache-Control": "private, no-store",
  "Content-Security-Policy": "default-src 'none'; style-src 'self'; font-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Robots-Tag": "noindex, nofollow",
};
const negado = () => new Response("Acesso negado.", { status: 403, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });

export async function painel(request, env, deps = {}) {
  const url = new URL(request.url);
  if (url.hostname !== HOST || request.method !== "GET") return negado();
  if (!await accessEmail(request.headers.get("Cf-Access-Jwt-Assertion"), deps)) return negado();
  if (url.pathname === "/painel/painel.css") {
    return new Response(CSS, { headers: { "Content-Type": "text/css; charset=utf-8", "Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff" } });
  }
  try {
    return new Response(render(await dados(env)), { headers: HEADERS });
  } catch (e) {
    console.log(`painel: ${e.message}`); // mensagem do GraphQL/D1, nunca o token
    return new Response("Painel indisponível agora. Veja os logs do Worker.", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });
  }
}
