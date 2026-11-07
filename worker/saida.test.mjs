// node worker/saida.test.mjs
import assert from "node:assert/strict";
import { saida, semMeta } from "./saida.js";

const AMZ = "https://www.amazon.com.br/dp/8535914846?tag=ofertas-20";
const FBCLID = "IwAR3xYz_AbC-123DeF";
const REF = `https://ofertaslivros.com.br/negocios/?utm_source=meta&utm_medium=paid&utm_campaign=bf&fbclid=${FBCLID}`;
const SEGREDOS = { META_CAPI_TOKEN: "tok", META_DATASET_ID: "1234567890" };

const assets = (location, status = 302) => ({
  fetch: async () => new Response(null, { status, headers: { Location: location, "X-Teste": "1" } }),
});
const req = ({ ref = REF, ua = "Mozilla/5.0 Teste", method = "GET", extra = {} } = {}) =>
  new Request("https://ofertaslivros.com.br/r/abc123", {
    method, headers: { ...(ref ? { Referer: ref } : {}), ...(ua ? { "User-Agent": ua } : {}), ...extra },
  });

// Roda o /r/ e devolve a resposta, as chamadas à Meta e as promessas do waitUntil.
async function rodar({ request = req(), location = AMZ, status = 302, env = SEGREDOS, meta } = {}) {
  const chamadas = [], esperas = [];
  const f = meta || (async () => new Response("{}"));
  const resp = await saida(request, { ...env, ASSETS: assets(location, status) }, { waitUntil: p => esperas.push(p) },
    async (url, init) => { chamadas.push({ url, init }); return f(url, init); });
  await Promise.all(esperas.map(p => Promise.race([p, new Promise(r => setTimeout(r, 50))])));
  return { resp, chamadas, esperas };
}

// Caso feliz: 1 chamada, só os campos da spec (§3.3), resposta intacta.
{
  const antes = Date.now();
  const { resp, chamadas } = await rodar();
  assert.equal(resp.status, 302);
  assert.equal(resp.headers.get("Location"), AMZ);
  assert.equal(resp.headers.get("X-Teste"), "1");
  assert.equal(chamadas.length, 1);
  assert.equal(chamadas[0].url, "https://graph.facebook.com/v27.0/1234567890/events");
  assert.ok(!chamadas[0].url.includes("tok"));                     // token nunca na URL
  assert.ok(chamadas[0].init.signal instanceof AbortSignal);
  const corpo = JSON.parse(chamadas[0].init.body);
  assert.deepEqual(Object.keys(corpo).sort(), ["access_token", "data"]);
  assert.equal(corpo.access_token, "tok");
  const [ev] = corpo.data;
  assert.deepEqual(Object.keys(ev).sort(), ["action_source", "event_id", "event_name", "event_source_url", "event_time", "user_data"]);
  assert.equal(ev.event_name, "SaidaLoja");
  assert.equal(ev.action_source, "website");
  assert.equal(ev.event_source_url, "https://ofertaslivros.com.br/negocios/"); // sem query
  assert.match(ev.event_id, /^[0-9a-f-]{36}$/);
  assert.ok(Math.abs(ev.event_time - antes / 1000) < 5);
  assert.deepEqual(Object.keys(ev.user_data).sort(), ["client_user_agent", "fbc"]); // sem IP
  assert.equal(ev.user_data.client_user_agent, "Mozilla/5.0 Teste");
  assert.match(ev.user_data.fbc, new RegExp(`^fb\\.1\\.\\d{13}\\.${FBCLID}$`));   // caixa preservada
  assert.ok(!chamadas[0].init.body.includes("abc123"));             // nada do livro
}

// event_source_url: só as 5 páginas de destino; o resto vira a raiz.
for (const [pagina, esperado] of [["/mindset/", "/mindset/"], ["/livro/torto-arado/", "/"], ["/", "/"], ["/negocios", "/"]]) {
  const { chamadas } = await rodar({ request: req({ ref: REF.replace("/negocios/", pagina) }) });
  assert.equal(JSON.parse(chamadas[0].init.body).data[0].event_source_url, "https://ofertaslivros.com.br" + esperado, pagina);
}

// META_TEST_CODE só quando existe.
{
  const { chamadas } = await rodar({ env: { ...SEGREDOS, META_TEST_CODE: "TEST123" } });
  assert.equal(JSON.parse(chamadas[0].init.body).test_event_code, "TEST123");
}

// Casos sem envio: 0 chamadas e a mesma resposta.
const semEnvio = {
  "sem fbclid": { request: req({ ref: "https://ofertaslivros.com.br/negocios/?utm_medium=paid" }) },
  "sem utm_medium=paid": { request: req({ ref: `https://ofertaslivros.com.br/negocios/?fbclid=${FBCLID}` }) },
  "utm_medium=social": { request: req({ ref: REF.replace("paid", "social") }) },
  "Referer de outra origem": { request: req({ ref: REF.replace("ofertaslivros.com.br", "evil.example") }) },
  "Referer http": { request: req({ ref: REF.replace("https:", "http:") }) },
  "Referer .com": { request: req({ ref: REF.replace(".com.br", ".com") }) },
  "sem Referer": { request: req({ ref: null }) },
  "Referer malformado": { request: req({ ref: "::::" }) },
  "sem User-Agent": { request: req({ ua: null }) },
  "Sec-GPC: 1": { request: req({ extra: { "Sec-GPC": "1" } }) },
  "cookie sem_meta=1": { request: req({ extra: { Cookie: "a=b; sem_meta=1" } }) },
  "HEAD": { request: req({ method: "HEAD" }) },
  "curinga para a home": { location: "/" },
  "host fora da allowlist": { location: "https://evil.example/x" },
  "amazon.com.br.evil": { location: "https://amazon.com.br.evil.example/x" },
  "loja em http": { location: "http://www.amazon.com.br/dp/1" },
  "status 200": { status: 200 },
  "sem segredos": { env: {} },
  "sem token": { env: { META_DATASET_ID: "123" } },
  "dataset não numérico": { env: { META_CAPI_TOKEN: "t", META_DATASET_ID: "../me" } },
  "fbclid curto": { request: req({ ref: REF.replace(FBCLID, "abc") }) },
  "fbclid longo": { request: req({ ref: REF.replace(FBCLID, "a".repeat(501)) }) },
  "fbclid com ponto": { request: req({ ref: REF.replace(FBCLID, "IwAR3xYz.AbC123") }) },
  "fbclid com %": { request: req({ ref: REF.replace(FBCLID, "IwAR3xYz%3CAbC123") }) },
};
for (const [nome, caso] of Object.entries(semEnvio)) {
  const location = caso.location || AMZ;
  const { resp, chamadas, esperas } = await rodar(caso);
  assert.equal(chamadas.length, 0, nome);
  assert.equal(esperas.length, 0, nome);
  assert.equal(resp.status, caso.status || 302, nome);
  assert.equal(resp.headers.get("Location"), location, nome);
}
assert.equal((await rodar({ request: req({ ref: REF.replace(FBCLID, "a".repeat(500)) }) })).chamadas.length, 1); // 500 cabe

// Meta lenta, com 500 ou lançando erro: a resposta sai na hora e o envio fica no waitUntil.
for (const [nome, meta] of Object.entries({
  lenta: () => new Promise(() => {}),
  "500": async () => new Response("x", { status: 500 }),
  erro: async () => { throw new Error("rede"); },
})) {
  const t = Date.now();
  const { resp, chamadas, esperas } = await rodar({ meta });
  assert.ok(Date.now() - t < 500, nome);
  assert.equal(resp.status, 302, nome);
  assert.equal(resp.headers.get("Location"), AMZ, nome);
  assert.equal(chamadas.length, 1, nome);
  assert.equal(esperas.length, 1, nome);
}

// Timeout de 3 s: a Meta que só responde ao abort encerra o waitUntil sem lançar.
{
  const esperas = [];
  const t = Date.now();
  await saida(req(), { ...SEGREDOS, ASSETS: assets(AMZ) }, { waitUntil: p => esperas.push(p) },
    (url, init) => new Promise((_, rej) => init.signal.addEventListener("abort", () => rej(init.signal.reason))));
  const vivo = setInterval(() => {}, 1000); // no Node o timer do AbortSignal.timeout não segura o processo
  await esperas[0]; // não lança
  clearInterval(vivo);
  const dt = Date.now() - t;
  assert.ok(dt >= 2900 && dt < 4000, `timeout em ${dt} ms`);
}

// Opt-out.
{
  const r = semMeta(new Request("https://ofertaslivros.com.br/privacidade/sem-meta", { method: "POST" }));
  assert.equal(r.status, 303);
  assert.equal(r.headers.get("Location"), "/privacidade/#sem-meta-ok");
  assert.equal(r.headers.get("Set-Cookie"), "sem_meta=1; Max-Age=31536000; Path=/r/; Secure; HttpOnly; SameSite=Lax");
  const g = semMeta(new Request("https://ofertaslivros.com.br/privacidade/sem-meta"));
  assert.equal(g.status, 405);
  assert.equal(g.headers.get("Set-Cookie"), null);
}

console.log("ok");
