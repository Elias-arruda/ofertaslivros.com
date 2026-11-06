// node --test worker/painel.test.mjs  (Node 22.5+)
import test from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { accessEmail, painel, render, dados, clique } from "./painel.js";
import { SCHEMA, PEDIDOS_SCHEMA } from "../cron/rollup.js";
import { execFileSync } from "node:child_process";

const TEAM = "https://ofertaslivros.cloudflareaccess.com";
const AUD = "eae97b05c067191b8a26d7e97bfbf575088be98d0e891009127728de1932779b";
const alg = { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" };
const real = await crypto.subtle.generateKey(alg, true, ["sign", "verify"]);
const intruso = await crypto.subtle.generateKey(alg, true, ["sign", "verify"]);
const jwk = { ...(await crypto.subtle.exportKey("jwk", real.publicKey)), kid: "k1" };
const fetcher = async () => ({ ok: true, json: async () => ({ keys: [jwk] }) });

const b64 = x => Buffer.from(typeof x === "string" ? x : JSON.stringify(x)).toString("base64url");
async function jwt(payload, { key = real.privateKey, header = { alg: "RS256", kid: "k1" } } = {}) {
  const data = `${b64(header)}.${b64(payload)}`;
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(data));
  return `${data}.${Buffer.from(sig).toString("base64url")}`;
}
const ok = { aud: [AUD], iss: TEAM, email: "mkt.eliasarruda@gmail.com", exp: Math.floor(Date.now() / 1000) + 600 };

test("JWT do Access válido passa", async () => {
  assert.equal(await accessEmail(await jwt(ok), { fetcher }), "mkt.eliasarruda@gmail.com");
});

test("JWT inválido é recusado", async () => {
  const casos = [
    await jwt({ ...ok, aud: ["outra-app"] }),
    await jwt({ ...ok, iss: "https://evil.cloudflareaccess.com" }),
    await jwt({ ...ok, exp: Math.floor(Date.now() / 1000) - 1 }),
    await jwt({ ...ok, email: "outra@pessoa.com" }),
    await jwt(ok, { key: intruso.privateKey }),                         // assinatura de outra chave
    await jwt(ok, { header: { alg: "RS256", kid: "desconhecido" } }),
    `${b64({ alg: "none", kid: "k1" })}.${b64(ok)}.`,                   // alg none
    "", "a.b", "lixo.lixo.lixo",
  ];
  for (const t of casos) assert.equal(await accessEmail(t, { fetcher }), null, t.slice(0, 40));
});

test("painel recusa host errado, método errado e pedido sem JWT", async () => {
  const env = {};
  for (const req of [
    new Request("https://ofertaslivros.mkt-eliasarruda.workers.dev/painel", { headers: { "Cf-Access-Jwt-Assertion": await jwt(ok) } }),
    new Request("https://ofertaslivros.com.br/painel", { method: "POST", headers: { "Cf-Access-Jwt-Assertion": await jwt(ok) } }),
    new Request("https://ofertaslivros.com.br/painel"),
  ]) assert.equal((await painel(req, env, { fetcher })).status, 403);
});

test("clique separa livro, canal e loja", () => {
  assert.deepEqual(clique("/r/livro-1"), { id: "livro-1", canal: "site", loja: "vencedora" });
  assert.deepEqual(clique("/r/livro-1/tg"), { id: "livro-1", canal: "tg", loja: "vencedora" });
  assert.deepEqual(clique("/r/livro-1/mercadolivre"), { id: "livro-1", canal: "site", loja: "mercadolivre" });
});

function fakeD1() {
  const db = new DatabaseSync(":memory:");
  const stmt = (sql, args = []) => ({
    bind: (...a) => stmt(sql, a),
    run: async () => db.prepare(sql).run(...args),
    all: async () => ({ results: db.prepare(sql).all(...args).map(r => ({ ...r })) }),
    first: async () => ({ ...db.prepare(sql).get(...args) }),
  });
  return { db, prepare: sql => stmt(sql) };
}

test("dados roda o SQL de verdade e render escapa o que vem dos caminhos", async () => {
  const d1 = fakeD1();
  d1.db.exec(SCHEMA);
  const ontem = new Date(Date.now() - 3 * 3600e3 - 86400e3).toISOString().slice(0, 10);
  const ins = d1.db.prepare("INSERT INTO daily_rollup VALUES (?, ?, ?, 'BR', ?, ?)");
  ins.run(ontem, "/r/livro-1", 302, 0, 4); ins.run(ontem, "/r/livro-1/tg", 302, 0, 2);
  ins.run(ontem, "/livro/livro-1/", 200, 0, 3); ins.run(ontem, "/manga/", 200, 0, 9); ins.run(ontem, "/", 200, 1, 50);
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ data: { viewer: { zones: [{ httpRequestsAdaptiveGroups: [
    { count: 5, dimensions: { clientRequestPath: "/r/<script>x</script>", edgeResponseStatus: 302, clientCountryName: "BR", userAgentBrowser: "Chrome" } },
    { count: 7, dimensions: { clientRequestPath: "/", edgeResponseStatus: 200, clientCountryName: "BR", userAgentBrowser: "Chrome" } },
  ] }] } } }) });
  const html = render(await dados({ ANALYTICS: d1, CF_ANALYTICS_TOKEN: "t" }));
  assert.ok(!html.includes("<script>") && html.includes("&lt;script&gt;"));
  assert.match(html, /<td>livro-1<\/td><td>6<\/td><td>3<\/td><td>200\.0%<\/td>/); // 6 cliques ÷ 3 views
  assert.match(html, /<td>\/manga\/<\/td><td>9<\/td>/);
  assert.match(html, /<td>tg<\/td><td>2<\/td>/);
  assert.match(html, /Pedidos de livro: 0 novo/);       // tabela pedidos ainda não existe: lista vazia
  assert.match(html, /Creators API: 0 de ~10/);          // sales ainda não existe
});

test("pedidos (texto do visitante) saem escapados e marcados como novos; vendas somam por status", async () => {
  const d1 = fakeD1();
  d1.db.exec(SCHEMA); d1.db.exec(PEDIDOS_SCHEMA);
  d1.db.prepare("INSERT INTO pedidos (criado_em, titulo, autor) VALUES (datetime('now'), ?, ?)").run('<img src=x onerror=alert(1)>', "Autor");
  d1.db.prepare("INSERT INTO pedidos (criado_em, titulo, autor) VALUES (datetime('now', '-3 days'), 'Antigo', '')").run();
  const schema = execFileSync("python3", ["-c", "import sys; sys.path.insert(0, 'analytics'); import vendas; print(vendas.SCHEMA)"]).toString();
  d1.db.exec(schema);
  const hoje = new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10);
  const ins = d1.db.prepare("INSERT INTO sales VALUES ('amazon', ?, '', ?, 't', ?, ?, ?, ?, 'f', 'x')");
  ins.run(hoje, "A1", 3, 9000, null, "pedido"); ins.run(hoje, "A1", 3, 9000, 450, "enviado"); ins.run(hoje, "A1", 1, 3000, -150, "devolvido");
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ data: { viewer: { zones: [{ httpRequestsAdaptiveGroups: [] }] } } }) });
  const html = render(await dados({ ANALYTICS: d1, CF_ANALYTICS_TOKEN: "t" }));
  assert.ok(!html.includes("<img") && html.includes("&lt;img src=x onerror=alert(1)&gt;"));
  assert.match(html, /Pedidos de livro: 1 novo/);
  assert.match(html, /<td>enviado<\/td><td>3<\/td><td>R\$\s?90,00<\/td><td>R\$\s?4,50<\/td>/);
  assert.match(html, /Creators API: 2 de ~10/);
});

test("CSS do painel só sai com JWT válido; gráficos viram SVG sem style inline", async () => {
  assert.equal((await painel(new Request("https://ofertaslivros.com.br/painel/painel.css"), {}, { fetcher })).status, 403);
  const ok200 = await painel(new Request("https://ofertaslivros.com.br/painel/painel.css", { headers: { "Cf-Access-Jwt-Assertion": await jwt(ok) } }), {}, { fetcher });
  assert.equal(ok200.status, 200);
  assert.match(ok200.headers.get("Content-Type"), /text\/css/);

  const d1 = fakeD1(); d1.db.exec(SCHEMA);
  const ins = d1.db.prepare("INSERT INTO daily_rollup VALUES (date('now', '-3 hours', ?), '/', 200, 'BR', 0, ?)");
  for (let i = 1; i <= 14; i++) ins.run(`-${i} days`, i * 10);
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ data: { viewer: { zones: [{ httpRequestsAdaptiveGroups: [] }] } } }) });
  const html = render(await dados({ ANALYTICS: d1, CF_ANALYTICS_TOKEN: "t" }));
  assert.equal((html.match(/<g class="col/g) || []).length, 30);      // 14 dias + hoje, nos dois gráficos
  assert.match(html, /class="col parcial"/);
  assert.match(html, /▼ 64% vs 7 dias antes/);                         // 280 contra 770 (série decrescente)
  assert.ok(!/style="|<style|<script/.test(html));                    // a CSP bloquearia
});
