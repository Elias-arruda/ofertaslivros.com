// Rollup diário do analytics (docs/produto/analytics.md, F1): views de página e cliques em /r/ do dia
// anterior (horário de Brasília), lidos do GraphQL da zona e gravados no D1. O Free guarda 31 dias;
// o D1 guarda o histórico. Só leitura na Cloudflare: o token CF_ANALYTICS_TOKEN é Account/Zone Analytics Read.
const GRAPHQL = "https://api.cloudflare.com/client/v4/graphql";
const ZONE = "ffabf11913bbbc37dfed21270064d5b5"; // ofertaslivros.com.br (não é segredo)
const BACKFILL_DAYS = 7; // por execução; dias que faltarem entram nas próximas
const BOT_RE = /bot|crawl|spider|slurp|curl|wget|headless|python|java|go-http|unknown/i;

// Página HTML com 200 ou /r/ com 302. Asset, 404 e scanner ficam de fora.
const LIMIT = 10000; // máximo do GraphQL por consulta
const QUERY = `query($z:String!,$s:Time!,$e:Time!){viewer{zones(filter:{zoneTag:$z}){
  httpRequestsAdaptiveGroups(limit:${LIMIT},filter:{datetime_geq:$s,datetime_lt:$e,
    OR:[{edgeResponseContentTypeName:"html",edgeResponseStatus:200},{clientRequestPath_like:"/r/%",edgeResponseStatus:302}]}){
    count dimensions{clientRequestPath edgeResponseStatus clientCountryName userAgentBrowser}}}}}`;

export const SCHEMA = `CREATE TABLE IF NOT EXISTS daily_rollup (
  day TEXT NOT NULL, path TEXT NOT NULL, status INTEGER NOT NULL, country TEXT NOT NULL,
  bot INTEGER NOT NULL, requests INTEGER NOT NULL,
  PRIMARY KEY (day, path, status, country, bot))`;

// Um único statement por dia: os dados vão como um parâmetro JSON (o D1 limita parâmetros por query).
const INSERT = `INSERT OR REPLACE INTO daily_rollup (day, path, status, country, bot, requests)
  SELECT ?1, j.value->>0, j.value->>1, j.value->>2, j.value->>3, j.value->>4 FROM json_each(?2) AS j`;

/** Dia (AAAA-MM-DD) em Brasília, n dias antes de `now`. Brasília é -03:00 fixo desde 2019. */
export function brDay(now, n) {
  return new Date(now.getTime() - 3 * 3600e3 - n * 86400e3).toISOString().slice(0, 10);
}

/** Grupos do GraphQL → linhas [path, status, country, bot, requests], somando o que cai na mesma chave. */
export function toRows(groups) {
  const acc = new Map();
  for (const { count, dimensions: d } of groups) {
    const path = String(d.clientRequestPath || "").slice(0, 200);
    if (!path.startsWith("/")) continue;
    const key = JSON.stringify([path, d.edgeResponseStatus, d.clientCountryName || "XX", BOT_RE.test(d.userAgentBrowser || "unknown") ? 1 : 0]);
    acc.set(key, (acc.get(key) || 0) + count);
  }
  return [...acc].map(([k, n]) => [...JSON.parse(k), n]);
}

async function fetchDay(token, day) {
  const r = await fetch(GRAPHQL, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ query: QUERY, variables: { z: ZONE, s: `${day}T00:00:00-03:00`, e: `${brDay(new Date(`${day}T12:00:00-03:00`), -1)}T00:00:00-03:00` } }),
  });
  const j = await r.json();
  // Só o status e a mensagem do GraphQL vão para o log, nunca o token.
  if (!r.ok || j.errors?.length) throw new Error(`GraphQL ${day}: ${r.status} ${JSON.stringify(j.errors || []).slice(0, 300)}`);
  const groups = j.data.viewer.zones[0]?.httpRequestsAdaptiveGroups || [];
  // ponytail: sem paginação; hoje são ~150-550 grupos por dia. Se bater o limite, falha em vez de gravar um dia truncado.
  if (groups.length >= LIMIT) throw new Error(`GraphQL ${day}: ${groups.length} grupos, no limite; dividir a consulta por hora`);
  return groups;
}

export async function rollup(env, now = new Date()) {
  if (!env.CF_ANALYTICS_TOKEN) throw new Error("CF_ANALYTICS_TOKEN ausente: rollup não rodou");
  await env.ANALYTICS.prepare(SCHEMA).run();
  const days = Array.from({ length: BACKFILL_DAYS }, (_, i) => brDay(now, i + 1));
  const { results } = await env.ANALYTICS.prepare(
    `SELECT DISTINCT day FROM daily_rollup WHERE day >= ?1`).bind(days.at(-1)).all();
  const done = new Set(results.map(r => r.day));
  done.delete(days[0]); // ontem sempre é regravado (o GraphQL pode ter chegado incompleto na primeira leitura)
  for (const day of days.filter(d => !done.has(d))) {
    const rows = toRows(await fetchDay(env.CF_ANALYTICS_TOKEN, day));
    await env.ANALYTICS.prepare(INSERT).bind(day, JSON.stringify(rows)).run();
    console.log(`rollup ${day}: ${rows.length} linhas`);
  }
}
