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
const WEBMAIL = "https://app.titan.email/mail/"; // caixa pedidos@ofertaslivros.com (Titan)
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

/** /r/<id>[/loja|/tg|/wa|/bot] → { id, canal, loja }. */
export function clique(path) {
  const [, , id, suf] = path.split("/");
  const canal = ["tg", "wa", "bot"].includes(suf) ? suf : "site";
  return { id, canal, loja: suf && canal === "site" ? suf : "vencedora" };
}

function tabela(cols, linhas) {
  const head = cols.map(c => `<th>${esc(c)}</th>`).join("");
  const body = linhas.length ? linhas.map(l => `<tr>${l.map(v => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")
    : `<tr><td colspan="${cols.length}">Sem dados.</td></tr>`;
  return `<details><summary>Ver tabela</summary><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></details>`;
}

const dm = d => `${d.slice(8, 10)}/${d.slice(5, 7)}`;
const pct = (a, b) => (b ? `${(100 * a / b).toFixed(1)}%` : "—");

// Gráficos em SVG montado no servidor (sem JS; tooltip pelo <title>, destaque no :hover pelo CSS).
// Os gráficos diários dividem a largura em N fatias iguais, então as datas se alinham entre eles.
const X = (i, N) => ((i + 0.5) / N) * 100;
const nice = v => { const e = 10 ** Math.floor(Math.log10(v || 1)); return Math.ceil(v / e) * e; };
const eixoX = pts => pts.length ? `<div class="eixo"><span>${esc(dm(pts[0].x))}</span><span>${esc(dm(pts.at(-1).x))}${pts.at(-1).parcial ? " · hoje" : ""}</span></div>` : "";
const legenda = itens => `<ul class="legenda">${itens.map(([cls, txt]) => `<li><i class="sw ${cls}"></i>${esc(txt)}</li>`).join("")}</ul>`;
const grade = W => [8, 54, 100].map(y => `<line x1="0" x2="${W}" y1="${y}" y2="${y}"/>`).join("");
const plot = (W, ymax, corpo, pts, rotulo) =>
  `<div class="plot"><span class="ymax">${esc(ymax)}</span><svg viewBox="0 0 ${W} 100" preserveAspectRatio="none" role="img" aria-label="${esc(rotulo)}">${grade(W)}${corpo}</svg>${eixoX(pts)}</div>`;

/** Barras agrupadas por dia: views (série 1) e cliques (série 2), no mesmo eixo de contagem. */
function barrasDia(pts) {
  const N = pts.length || 1, max = nice(Math.max(1, ...pts.map(p => Math.max(p.v, p.c))));
  const h = y => 92 * y / max;
  const g = pts.map((p, i) => `<g class="col${p.parcial ? " parcial" : ""}"><title>${esc(dm(p.x))}${p.parcial ? " (hoje, parcial)" : ""}: ${n(p.v)} views · ${n(p.c)} cliques</title>`
    + `<rect class="hit" x="${i * 12}" y="0" width="12" height="100"/>`
    + `<rect class="s1" x="${i * 12 + 1.5}" y="${(100 - h(p.v)).toFixed(2)}" width="4.25" height="${h(p.v).toFixed(2)}"/>`
    + `<rect class="s2" x="${i * 12 + 6.25}" y="${(100 - h(p.c)).toFixed(2)}" width="4.25" height="${h(p.c).toFixed(2)}"/></g>`).join("");
  return legenda([["s1", "Views"], ["s2", "Cliques de afiliado"]]) + plot(N * 12, n(max), g, pts, "views e cliques por dia");
}

/** Linha de taxa por dia (diária + média móvel de 7 dias), alinhada às barras de cima. */
function linhaDia(pts) {
  const N = pts.length || 1, max = nice(100 * Math.max(0.01, ...pts.map(p => Math.max(p.y ?? 0, p.m ?? 0))));
  const Y = r => (100 - 92 * (100 * r) / max).toFixed(2);
  const linha = (k, cls) => `<polyline class="${cls}" points="${pts.flatMap((p, i) => p[k] == null ? [] : [`${X(i, N).toFixed(2)},${Y(p[k])}`]).join(" ")}"/>`;
  const hits = pts.map((p, i) => `<g class="pt"><title>${esc(dm(p.x))}${p.parcial ? " (hoje, parcial)" : ""}: CTR ${p.y == null ? "—" : `${(100 * p.y).toFixed(1)}%`} · média 7 dias ${p.m == null ? "—" : `${(100 * p.m).toFixed(1)}%`}</title><rect class="hit" x="${(100 * i / N).toFixed(2)}" y="0" width="${(100 / N).toFixed(2)}" height="100"/></g>`).join("");
  return legenda([["ln", "CTR do dia"], ["lm", "Média de 7 dias"]]) + plot(100, `${max}%`, linha("y", "ln") + linha("m", "lm") + hits, pts, "taxa de clique por dia");
}

/** Minigráfico de tendência para os cartões do topo. */
function spark(vals) {
  const v = vals.filter(x => x != null);
  if (v.length < 2) return "";
  const max = Math.max(...v) || 1, min = Math.min(...v), amp = max - min || 1;
  return `<svg class="spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true"><polyline points="${v.map((y, i) => `${(100 * i / (v.length - 1)).toFixed(1)},${(27 - 24 * (y - min) / amp).toFixed(1)}`).join(" ")}"/></svg>`;
}

/** Barras horizontais ranqueadas: rótulo, barra (largura em % do maior) e valor. */
function barras(linhas, vazio = "Sem dados ainda.") {
  if (!linhas.length) return `<p class="vazio">${esc(vazio)}</p>`;
  const max = Math.max(1, ...linhas.map(l => l.v));
  return `<ol class="hbars">${linhas.map(l => `<li><span class="rot" title="${esc(l.rot)}">${esc(l.rot)}</span>`
    + `<svg class="trilho" preserveAspectRatio="none"><title>${esc(l.rot)}: ${n(l.v)}${l.extra ? ` · ${esc(l.extra)}` : ""}</title><rect width="${(100 * l.v / max).toFixed(1)}%" height="100%" rx="3"/></svg>`
    + `<span class="val">${n(l.v)}${l.extra ? `<small>${esc(l.extra)}</small>` : ""}</span></li>`).join("")}</ol>`;
}

/** Funil: cada etapa com a barra proporcional à primeira e a conversão até a próxima. */
function funil(etapas) {
  const topo = Math.max(1, etapas[0].v);
  return `<ol class="funil">${etapas.map((e, i) => {
    const passo = i ? `<li class="passo">↓ ${etapas[i - 1].v ? `${(100 * e.v / etapas[i - 1].v).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%` : "—"} ${esc(e.verbo)}</li>` : "";
    return `${passo}<li><span class="rot">${esc(e.rot)}</span><svg class="trilho" preserveAspectRatio="none"><title>${esc(e.rot)}: ${n(e.v)}</title><rect width="${Math.max(1.5, 100 * e.v / topo).toFixed(1)}%" height="100%" rx="3"/></svg><span class="val">${n(e.v)}</span></li>`;
  }).join("")}</ol>`;
}

/** Participação: barra 100% segmentada (≤ 4 partes), com rótulo direto e espaço entre as cores. */
function segmentos(partes) {
  const total = partes.reduce((a, p) => a + p.v, 0);
  if (!total) return `<p class="vazio">Sem cliques ainda.</p>`;
  let x = 0;
  const rects = partes.filter(p => p.v).map(p => {
    const w = 100 * p.v / total, r = `<rect class="${p.cls}" x="${x.toFixed(2)}" width="${Math.max(0, w - 0.6).toFixed(2)}" height="100%"><title>${esc(p.rot)}: ${n(p.v)} (${pct(p.v, total)})</title></rect>`;
    x += w; return r;
  }).join("");
  return `<svg class="seg" viewBox="0 0 100 10" preserveAspectRatio="none" role="img" aria-label="participação">${rects}</svg>`
    + `<ul class="legenda seg-leg">${partes.map(p => `<li><i class="sw ${p.cls}"></i>${esc(p.rot)} <b>${pct(p.v, total)}</b> <span>${n(p.v)}</span></li>`).join("")}</ul>`;
}

function tile(rotulo, valor, sub = "", cls = "", extra = "") {
  return `<div class="tile ${cls}"><span class="rotulo">${esc(rotulo)}</span><strong>${esc(valor)}</strong>${sub ? `<span class="sub">${esc(sub)}</span>` : ""}${extra}</div>`;
}

/** Variação contra a janela anterior, em texto (não é cor de status). */
function delta(atual, antes) {
  if (!antes) return "sem base anterior";
  const v = 100 * (atual - antes) / antes;
  return `${v >= 0 ? "▲" : "▼"} ${Math.abs(v).toFixed(0)}% vs 7 dias antes`;
}

const card = (titulo, corpo, cls = "", nota = "", acao = "", id = "") =>
  `<section class="card ${cls}"${id ? ` id="${id}"` : ""}><div class="card-topo"><h2>${esc(titulo)}</h2>${acao}</div>${corpo}${nota ? `<p class="nota">${esc(nota)}</p>` : ""}</section>`;

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
  const bot = await botDados(env.BOT, now, hoje);
  const rowsHoje = toRows(await fetchDay(env.CF_ANALYTICS_TOKEN, hoje))
    .map(([path, status, country, bot, requests]) => ({ path, status, bot, requests }));
  return { porDia: porDia.results, livros7: livros7.results, cliques7: cliques7.results, nichos7: nichos7.results,
    ultimoDia: ultimo?.day || null, hoje, rowsHoje, pedidos, vendas, bot, geradoEm: now };
}

// Bot do Telegram (D1 BOT): só contagens. Nenhum chat_id sai do banco; o top é por livro, não por pessoa.
async function botDados(db, now, hoje) {
  if (!db) return null;
  const sete = new Date(now.getTime() - 7 * 86400e3).toISOString();
  const inicioHoje = `${hoje}T03:00:00.000Z`; // 00:00 em Brasília
  try {
    const [n, top] = await Promise.all([
      db.prepare(`SELECT (SELECT COUNT(*) FROM chats) AS chats, (SELECT COUNT(*) FROM chats WHERE criado_em >= ?1) AS novos7,
        (SELECT COUNT(*) FROM chats WHERE visto_em >= ?1) AS ativos7, (SELECT COUNT(*) FROM chats WHERE pausado = 1) AS pausados,
        (SELECT COUNT(*) FROM desejos WHERE tipo = 'livro') AS livros, (SELECT COUNT(*) FROM desejos WHERE tipo = 'autor') AS autores,
        (SELECT COUNT(*) FROM avisos WHERE avisado_em >= ?2) AS avisosHoje, (SELECT COUNT(*) FROM em_oferta) AS emOferta`)
        .bind(sete, inicioHoje).first(),
      db.prepare(`SELECT chave, COUNT(*) AS n FROM desejos WHERE tipo = 'livro' GROUP BY chave ORDER BY n DESC, chave LIMIT 10`).all(),
    ]);
    return { ...n, top: top.results };
  } catch {
    return null; // tabelas nascem no primeiro update do bot
  }
}

export function render(d) {
  const humanos = d.rowsHoje.filter(r => !r.bot);
  const viewsHoje = soma(humanos, r => r.status === 200 && !r.path.startsWith("/r/"));
  const cliquesHoje = soma(humanos, r => r.path.startsWith("/r/"));
  const topHoje = Object.entries(humanos.filter(r => r.path.startsWith("/r/"))
    .reduce((a, r) => ({ ...a, [clique(r.path).id]: (a[clique(r.path).id] || 0) + r.requests }), {}))
    .filter(([, c]) => c > 0).sort((a, b) => b[1] - a[1]).slice(0, 10);

  const viewsLivro = Object.fromEntries(d.livros7.map(r => [r.id, r.views]));
  const porLivro = {}, porCanal = { site: 0, tg: 0, wa: 0, bot: 0 }, porLoja = {};
  for (const r of d.cliques7) {
    const c = clique(r.path);
    porLivro[c.id] = (porLivro[c.id] || 0) + r.requests;
    porCanal[c.canal] += r.requests;
    porLoja[c.loja] = (porLoja[c.loja] || 0) + r.requests;
  }
  const topLivros = Object.entries(porLivro).sort((a, b) => b[1] - a[1]).slice(0, 10);
  const nichos = d.nichos7.filter(r => NICHOS.has(r.path.slice(1, -1))).sort((a, b) => b.views - a.views);
  const brl = c => (Number(c || 0) / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const novos = d.pedidos.filter(p => p.novo).length;
  const v = (store, status) => d.vendas.find(r => r.store === store && r.status === status) || {};
  const qualificadas = (v("amazon", "enviado").itens || 0) - (v("amazon", "devolvido").itens || 0);
  const comissao = (v("amazon", "enviado").comissao || 0) + (v("amazon", "devolvido").comissao || 0);
  const pedidosAmz = v("amazon", "pedido").itens || 0;
  const vendasAte = d.vendas.reduce((m, r) => (r.ate > m ? r.ate : m), "") || "—";
  const hora = d.geradoEm.toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" });

  // Série diária (antiga → nova) + hoje como dia parcial.
  const dias = [...d.porDia].reverse();
  const serie = dias.map(r => ({ x: r.day, v: r.views || 0, c: r.cliques || 0 }))
    .concat([{ x: d.hoje, v: viewsHoje, c: cliquesHoje, parcial: true }]);
  serie.forEach((p, i) => {
    const w = serie.slice(Math.max(0, i - 6), i + 1), sv = w.reduce((a, q) => a + q.v, 0);
    p.y = p.v ? p.c / p.v : null;
    p.m = sv ? w.reduce((a, q) => a + q.c, 0) / sv : null;
  });
  const janela = (k, de, ate) => dias.slice(de, ate).reduce((a, r) => a + (r[k] || 0), 0);
  const v7 = janela("views", -7), v7a = janela("views", -14, -7), c7 = janela("cliques", -7), c7a = janela("cliques", -14, -7);
  const v30 = janela("views", -30), c30 = janela("cliques", -30);
  const ctr7 = v7 ? c7 / v7 : 0, ctr7a = v7a ? c7a / v7a : 0;
  const ult14 = dias.slice(-14);
  // Muita visita, pouco clique: livros com página vista (≥ 10 views) e CTR abaixo da média dos livros, mais vistos primeiro.
  const comPagina = Object.keys(viewsLivro).filter(id => viewsLivro[id] >= 10);
  const vLivros = comPagina.reduce((a, id) => a + viewsLivro[id], 0), cLivros = comPagina.reduce((a, id) => a + (porLivro[id] || 0), 0);
  const ctrLivros = vLivros ? cLivros / vLivros : 0;
  const fracos = comPagina.filter(id => (porLivro[id] || 0) / viewsLivro[id] < ctrLivros)
    .sort((a, b) => viewsLivro[b] - viewsLivro[a]).slice(0, 8);

  const pedidosHtml = d.pedidos.length ? `<ul class="pedidos">${d.pedidos.slice(0, 12).map(p =>
    `<li${p.novo ? ' class="novo"' : ""}><div><strong>${esc(p.titulo)}</strong><span>${esc(p.autor || "autor não informado")}</span></div>`
    + `<time>${esc(p.criado_em)} UTC</time>${p.novo ? '<b class="badge">NOVO</b>' : ""}</li>`).join("")}</ul>`
    : `<p class="vazio">Nenhum pedido nos últimos 30 dias.</p>`;

  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60">
<meta name="robots" content="noindex"><title>Painel · Ofertas Livros</title><link rel="stylesheet" href="/painel/painel.css"></head>
<body><main class="painel">
<header class="topo"><div><p class="kicker">Ofertas Livros</p><h1>Painel</h1></div>
<p class="meta">Atualizado ${esc(hora)} · recarrega a cada 60 s · sem bots<br>histórico até ${esc(d.ultimoDia || "—")} · hoje pelo GraphQL (minutos de atraso) · vendas até ${esc(vendasAte)}</p></header>

<div class="tiles">
${tile("Views 7 dias", n(v7), delta(v7, v7a), "", spark(ult14.map(r => r.views || 0)))}
${tile("Cliques 7 dias", n(c7), delta(c7, c7a), "", spark(ult14.map(r => r.cliques || 0)))}
${tile("CTR 7 dias", pct(c7, v7), ctr7a ? `antes: ${(100 * ctr7a).toFixed(1)}%` : "cliques ÷ views", "", spark(ult14.map(r => (r.views ? r.cliques / r.views : null))))}
${tile("Comissão 30 dias", brl(comissao), c30 ? `${brl(comissao / c30)} por clique` : "Amazon", "destaque")}
${tile("Creators API", `${n(qualificadas)} de ~10`, "vendas qualificadas, 30 dias", "", `<svg class="medidor" preserveAspectRatio="none"><title>${n(qualificadas)} de ~10</title><rect class="fundo" width="100%" height="100%" rx="4"/><rect width="${Math.min(100, 10 * qualificadas)}%" height="100%" rx="4"/></svg>`)}
${d.bot ? tile("Bot do Telegram", n(d.bot.chats), `pessoas com lista · ${n(d.bot.avisosHoje)} avisos hoje`) : ""}
${tile("Pedidos de livro", n(novos), `novos em 24 h · hoje ${n(viewsHoje)} views, ${n(cliquesHoje)} cliques`, novos ? "alerta" : "", `<a class="sub" href="${WEBMAIL}" target="_blank" rel="noopener noreferrer">Abrir e-mail ↗</a>`)}
</div>

<div class="grade">
${card("Tráfego por dia", barrasDia(serie) + tabela(["Dia", "Views", "Cliques", "Bots"], d.porDia.map(r => [r.day, n(r.views), n(r.cliques), n(r.bots)])), "largo", "Views = páginas HTML com status 200; cliques = /r/ que redirecionou para a loja. Sem bots. A última coluna (mais clara) é hoje, parcial.")}
${card("Taxa de clique (CTR) por dia", linhaDia(serie), "largo", "CTR = cliques em /r/ ÷ views. A média de 7 dias tira o ruído de dias fracos; mesmas datas do gráfico acima.")}

${card("Funil (30 dias)", funil([
    { rot: "Views", v: v30 },
    { rot: "Cliques de afiliado", v: c30, verbo: "clicam para a loja" },
    { rot: "Pedidos Amazon", v: pedidosAmz, verbo: "viram pedido" },
  ]) + `<p class="grande">${brl(comissao)} <small>de comissão · ${c30 ? `${brl(comissao / c30)} por clique` : "—"}</small></p>`
  + tabela(["Status", "Itens", "Receita", "Comissão"], ["pedido", "enviado", "devolvido"].map(st => [st, n(v("amazon", st).itens), brl(v("amazon", st).receita), st === "pedido" ? "—" : brl(v("amazon", st).comissao)])),
  "", `Pedidos só da Amazon (o portal do ML não exporta) e com 1 dia de atraso; parte dos cliques vai para o ML, então a conversão real da Amazon é maior. Creators API: ${qualificadas} de ~10 vendas qualificadas (enviadas − devolvidas) em 30 dias; o número que vale é o do painel da Amazon.`)}
${card("De onde vêm e para onde vão os cliques (7 dias)",
  `<h3>Loja de destino</h3>${segmentos([{ rot: "Menor preço (/r/)", v: porLoja.vencedora || 0, cls: "s1" }, { rot: "Amazon (seta)", v: porLoja.amazon || 0, cls: "s2" }, { rot: "Mercado Livre (seta)", v: porLoja.mercadolivre || 0, cls: "s3" }])}`
  + `<h3>Canal de origem</h3>${segmentos([{ rot: "Site", v: porCanal.site, cls: "s1" }, { rot: "Telegram", v: porCanal.tg, cls: "s2" }, { rot: "WhatsApp", v: porCanal.wa, cls: "s3" }, { rot: "Bot", v: porCanal.bot, cls: "s4" }])}`
  + tabela(["Canal", "Cliques"], Object.entries(porCanal).map(([k, c]) => [k, n(c)])),
  "", "Menor preço = /r/<id>, que leva à loja mais barata do dia; a seta é o link da outra loja na página do livro.")}

${card("Muita visita, pouco clique (7 dias)", barras(fracos.map(id => ({ rot: id, v: viewsLivro[id], extra: `CTR ${pct(porLivro[id] || 0, viewsLivro[id])} · ${n(porLivro[id] || 0)} cliques` })), "Nenhum livro abaixo da média."),
  "largo", `Livros com 10 views ou mais na página e CTR abaixo da média deles (${(100 * ctrLivros).toFixed(1)}%), do mais visto para o menos. A barra é a quantidade de views. Vale rever preço, capa ou oferta.`)}

${card("Top livros por cliques (7 dias)", barras(topLivros.map(([id, c]) => ({ rot: id, v: c, extra: viewsLivro[id] ? `CTR ${pct(c, viewsLivro[id])}` : "" })))
  + tabela(["Livro", "Cliques", "Views da página", "CTR"], topLivros.map(([id, c]) => [id, n(c), n(viewsLivro[id]), pct(c, viewsLivro[id])])),
  "largo", "CTR = cliques em /r/<id> ÷ views de /livro/<id>/. Clique vindo do canal não passa pela página, então pode passar de 100%.")}
${card("Nichos mais vistos (7 dias)", barras(nichos.map(r => ({ rot: r.path, v: r.views }))) + tabela(["Página", "Views"], nichos.map(r => [r.path, n(r.views)])))}
${card("Top livros hoje", barras(topHoje.map(([id, c]) => ({ rot: id, v: c })), "Nenhum clique hoje ainda."))}
${d.bot ? card("Bot do Telegram (lista de desejos)",
  tabela(["", "Total"], [["Pessoas com lista", n(d.bot.chats)], ["Novas em 7 dias", n(d.bot.novos7)], ["Ativas em 7 dias", n(d.bot.ativos7)],
    ["Com avisos pausados", n(d.bot.pausados)], ["Livros nas listas", n(d.bot.livros)], ["Autores nas listas", n(d.bot.autores)],
    ["Avisos hoje", n(d.bot.avisosHoje)], ["Livros em oferta agora", n(d.bot.emOferta)]])
  + `<h3>Livros mais desejados</h3>` + barras(d.bot.top.map(r => ({ rot: r.chave, v: r.n })), "Nenhum livro nas listas ainda."),
  "", "Só contagens do D1 do bot, sem nenhum dado de quem usa. Cliques vindos do bot aparecem como \"Bot\" no canal de origem. Ativa = mandou mensagem ou tocou num botão.") : ""}
${card(`Pedidos de livro: ${novos} novo(s) nas últimas 24 h`, pedidosHtml, "largo", "Formulário \"Pedir um livro\" (também vai para pedidos@ofertaslivros.com). Ficam 30 dias.",
  `<a class="botao" href="${WEBMAIL}" target="_blank" rel="noopener noreferrer">Abrir e-mail dos pedidos ↗</a>`, "pedidos")}
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
    return new Response(CSS, { headers: { "Content-Type": "text/css; charset=utf-8", "Cache-Control": "private, no-cache", "X-Content-Type-Options": "nosniff" } });
  }
  try {
    return new Response(render(await dados(env)), { headers: HEADERS });
  } catch (e) {
    console.log(`painel: ${e.message}`); // mensagem do GraphQL/D1, nunca o token
    return new Response("Painel indisponível agora. Veja os logs do Worker.", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });
  }
}
