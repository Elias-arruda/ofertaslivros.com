// /painel: KPIs do site só para o Elias (docs/produto/analytics.md, F1b).
// Duas travas: o Cloudflare Access na frente (ofertaslivros.com.br/painel, só o e-mail do Elias) e,
// aqui, a conferência do JWT do Access. Sem JWT válido = 403, mesmo se a regra do Access sumir
// ou se o pedido vier pelo workers.dev. HTML montado no servidor, sem JS, tudo escapado.
import { brDay, fetchDay, toRows } from "../cron/rollup.js";

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

function tabela(titulo, cols, linhas, nota = "") {
  const head = cols.map(c => `<th>${esc(c)}</th>`).join("");
  const body = linhas.length ? linhas.map(l => `<tr>${l.map(v => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")
    : `<tr><td colspan="${cols.length}">Sem dados.</td></tr>`;
  return `<section><h2>${esc(titulo)}</h2>${nota ? `<p>${esc(nota)}</p>` : ""}<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></section>`;
}

const soma = (rows, f) => rows.filter(f).reduce((a, r) => a + r.requests, 0);

export async function dados(env, now = new Date()) {
  const db = env.ANALYTICS;
  const [porDia, livros7, cliques7, nichos7, ultimo] = await Promise.all([
    db.prepare(`SELECT day, SUM(CASE WHEN bot = 0 AND path NOT LIKE '/r/%' THEN requests END) AS views,
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
  // Hoje (desde 00:00 em Brasília) direto do GraphQL: alguns minutos de atraso.
  const hoje = brDay(now, 0);
  const rowsHoje = toRows(await fetchDay(env.CF_ANALYTICS_TOKEN, hoje))
    .map(([path, status, country, bot, requests]) => ({ path, status, bot, requests }));
  return { porDia: porDia.results, livros7: livros7.results, cliques7: cliques7.results, nichos7: nichos7.results,
    ultimoDia: ultimo?.day || null, hoje, rowsHoje, geradoEm: now };
}

export function render(d) {
  const humanos = d.rowsHoje.filter(r => !r.bot);
  const viewsHoje = soma(humanos, r => r.status === 200), cliquesHoje = soma(humanos, r => r.path.startsWith("/r/"));
  const topHoje = Object.entries(humanos.filter(r => r.path.startsWith("/r/"))
    .reduce((a, r) => ({ ...a, [clique(r.path).id]: (a[clique(r.path).id] || 0) + r.requests }), {}))
    .sort((a, b) => b[1] - a[1]).slice(0, 10);

  const viewsLivro = Object.fromEntries(d.livros7.map(r => [r.id, r.views]));
  const porLivro = {}, porCanal = { site: 0, tg: 0, wa: 0 }, porLoja = {};
  for (const r of d.cliques7) {
    const c = clique(r.path);
    porLivro[c.id] = (porLivro[c.id] || 0) + r.requests;
    porCanal[c.canal] += r.requests;
    porLoja[c.loja] = (porLoja[c.loja] || 0) + r.requests;
  }
  const topLivros = Object.entries(porLivro).sort((a, b) => b[1] - a[1]).slice(0, 20)
    .map(([id, c]) => [id, n(c), n(viewsLivro[id]), viewsLivro[id] ? `${(100 * c / viewsLivro[id]).toFixed(1)}%` : "—"]);
  const nichos = d.nichos7.filter(r => NICHOS.has(r.path.slice(1, -1))).sort((a, b) => b.views - a.views)
    .map(r => [r.path, n(r.views)]);
  const hora = d.geradoEm.toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" });

  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60">
<meta name="robots" content="noindex"><title>Painel · Ofertas Livros</title><link rel="stylesheet" href="/style.css"></head>
<body><main class="painel"><h1>Painel</h1><p>Gerado em ${esc(hora)} (atualiza a cada 60 s). Sem bots. Histórico até ${esc(d.ultimoDia || "—")}; hoje vem do GraphQL com alguns minutos de atraso.</p>
${tabela(`Hoje (${d.hoje})`, ["Views", "Cliques em /r/"], [[n(viewsHoje), n(cliquesHoje)]])}
${tabela("Top livros hoje", ["Livro", "Cliques"], topHoje.map(([id, c]) => [id, n(c)]))}
${tabela("Por dia (30 dias)", ["Dia", "Views", "Cliques", "Bots"], d.porDia.map(r => [r.day, n(r.views), n(r.cliques), n(r.bots)]))}
${tabela("Top livros (7 dias)", ["Livro", "Cliques", "Views da página", "CTR"], topLivros, "CTR = cliques em /r/<id> ÷ views de /livro/<id>/. Clique vindo do canal não passa pela página, então o CTR pode passar de 100%.")}
${tabela("Canal (7 dias)", ["Canal", "Cliques"], Object.entries(porCanal).map(([k, v]) => [k, n(v)]))}
${tabela("Loja (7 dias)", ["Destino", "Cliques"], Object.entries(porLoja).map(([k, v]) => [k, n(v)]), "vencedora = /r/<id> (a loja com menor preço no dia); amazon/mercadolivre = a seta da outra loja.")}
${tabela("Nichos mais vistos (7 dias)", ["Página", "Views"], nichos)}
${tabela("Vendas e comissões", ["Status"], [["Entra na F3 (CSV dos painéis pelo Chrome)."]])}
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
  try {
    return new Response(render(await dados(env)), { headers: HEADERS });
  } catch (e) {
    console.log(`painel: ${e.message}`); // mensagem do GraphQL/D1, nunca o token
    return new Response("Painel indisponível agora. Veja os logs do Worker.", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });
  }
}
