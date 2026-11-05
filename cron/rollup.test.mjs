// node --test cron/rollup.test.mjs  (Node 22.5+: usa node:sqlite como D1 falso, para testar o SQL de verdade)
import test from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { rollup, toRows, brDay } from "./rollup.js";

function fakeD1() {
  const db = new DatabaseSync(":memory:");
  const stmt = (sql, args = []) => ({
    bind: (...a) => stmt(sql, a),
    run: async () => db.prepare(sql).run(...args),
    all: async () => ({ results: db.prepare(sql).all(...args) }),
  });
  const batch = async stmts => {
    db.exec("BEGIN");
    try { for (const st of stmts) await st.run(); db.exec("COMMIT"); } catch (e) { db.exec("ROLLBACK"); throw e; }
  };
  return { db, prepare: sql => stmt(sql), batch };
}

const g = (path, status, country, ua, count) =>
  ({ count, dimensions: { clientRequestPath: path, edgeResponseStatus: status, clientCountryName: country, userAgentBrowser: ua } });

test("brDay usa o fuso de Brasília", () => {
  assert.equal(brDay(new Date("2026-11-05T03:15:00Z"), 1), "2026-11-04"); // 00:15 BRT do dia 5
  assert.equal(brDay(new Date("2026-11-05T02:00:00Z"), 1), "2026-11-03"); // ainda é dia 4 em BRT
});

test("toRows marca bot, soma a mesma chave e descarta caminho inválido", () => {
  const rows = toRows([
    g("/r/livro-1", 302, "BR", "MobileSafari", 2),
    g("/r/livro-1", 302, "BR", "MobileSafari", 3),
    g("/r/livro-1", 302, "US", "GoogleBot", 4),
    g("/", 200, "BR", "Unknown", 5),
    g("x", 200, "BR", "Chrome", 1),
  ]);
  assert.deepEqual(rows.sort(), [
    ["/", 200, "BR", 1, 5], ["/r/livro-1", 302, "BR", 0, 5], ["/r/livro-1", 302, "US", 1, 4],
  ].sort());
});

test("rollup grava ontem e os dias que faltam, sem duplicar ao rodar de novo", async () => {
  const d1 = fakeD1(), days = [];
  globalThis.fetch = async (_url, init) => {
    const { variables } = JSON.parse(init.body);
    assert.ok(!init.body.includes("tok-secreto"));
    days.push(variables.s.slice(0, 10));
    return { ok: true, status: 200, json: async () => ({ data: { viewer: { zones: [{ httpRequestsAdaptiveGroups: [
      g("/r/livro-1", 302, "BR", "Chrome", 3), g("/livro/livro-1/", 200, "BR", "Chrome", 7)] }] } } }) };
  };
  const env = { CF_ANALYTICS_TOKEN: "tok-secreto", ANALYTICS: d1 };
  const now = new Date("2026-11-05T03:15:00Z");
  await rollup(env, now);
  assert.equal(days.length, 7);
  assert.equal(days[0], "2026-11-04");
  assert.equal(d1.db.prepare("SELECT COUNT(*) n FROM daily_rollup").get().n, 14);
  days.length = 0;
  await rollup(env, now); // segunda vez: só regrava ontem
  assert.deepEqual(days, ["2026-11-04"]);
  assert.equal(d1.db.prepare("SELECT SUM(requests) n FROM daily_rollup WHERE day = '2026-11-04'").get().n, 10);
  const r = d1.db.prepare("SELECT * FROM daily_rollup WHERE day = '2026-11-04' AND status = 302").get();
  assert.deepEqual({ ...r }, { day: "2026-11-04", path: "/r/livro-1", status: 302, country: "BR", bot: 0, requests: 3 });
});

test("regravar ontem apaga a linha que sumiu do GraphQL", async () => {
  const d1 = fakeD1(), now = new Date("2026-11-05T03:15:00Z");
  let groups = [g("/r/livro-1", 302, "BR", "Chrome", 3), g("/livro/livro-1/", 200, "BR", "Chrome", 7)];
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ data: { viewer: { zones: [{ httpRequestsAdaptiveGroups: groups }] } } }) });
  const env = { CF_ANALYTICS_TOKEN: "t", ANALYTICS: d1 };
  await rollup(env, now);
  groups = [g("/livro/livro-1/", 200, "BR", "Chrome", 8)];
  await rollup(env, now);
  assert.deepEqual(d1.db.prepare("SELECT path, requests FROM daily_rollup WHERE day = '2026-11-04'").all().map(r => ({ ...r })),
    [{ path: "/livro/livro-1/", requests: 8 }]);
});

test("dia no limite do GraphQL falha em vez de gravar truncado", async () => {
  const d1 = fakeD1();
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ data: { viewer: { zones: [{
    httpRequestsAdaptiveGroups: Array.from({ length: 10000 }, (_, i) => g(`/p${i}/`, 200, "BR", "Chrome", 1)) }] } } }) });
  await assert.rejects(rollup({ CF_ANALYTICS_TOKEN: "t", ANALYTICS: d1 }, new Date("2026-11-05T03:15:00Z")), /no limite/);
  assert.equal(d1.db.prepare("SELECT COUNT(*) n FROM daily_rollup").get().n, 0);
});

test("rollup sem token falha visível", async () => {
  await assert.rejects(rollup({ ANALYTICS: fakeD1() }), /CF_ANALYTICS_TOKEN ausente/);
});

test("erro do GraphQL vira exceção sem vazar o token", async () => {
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ errors: [{ message: "authz" }] }) });
  await assert.rejects(rollup({ CF_ANALYTICS_TOKEN: "tok-secreto", ANALYTICS: fakeD1() }, new Date()),
    e => /authz/.test(e.message) && !e.message.includes("tok-secreto"));
});
