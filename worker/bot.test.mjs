// node --test worker/bot.test.mjs  (Node 22.5+) — critérios 1 a 29 de docs/produto/bot-lista-de-desejos.md
import test from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { telegram, avisar, buscar, chave, BOT_SCHEMA } from "./bot.js";
import { PEDIDOS_SCHEMA } from "../cron/rollup.js";

const SEGREDO = "s3gredo_do_webhook_com_32_chars_xx";
const CHAT = 987654321;          // sentinela: nunca pode aparecer no log
const AGORA = new Date("2026-11-06T15:00:00Z"); // 12h BRT
const ATE = "2026-11-06T23:00:00+00:00";

function fakeD1() {
  const db = new DatabaseSync(":memory:");
  const stmt = (sql, args = []) => ({
    bind: (...a) => stmt(sql, a),
    run: async () => { const r = db.prepare(sql).run(...args); return { meta: { changes: Number(r.changes), last_row_id: Number(r.lastInsertRowid) } }; },
    all: async () => ({ results: db.prepare(sql).all(...args).map(r => ({ ...r })) }),
    first: async () => { const r = db.prepare(sql).get(...args); return r ? { ...r } : null; },
  });
  const d1 = { db, prepare: sql => stmt(sql), batch: async ss => { const out = []; for (const s of ss) out.push(await s.run()); return out; } };
  for (const s of BOT_SCHEMA) db.exec(s);
  return d1;
}

const livro = (id, titulo, autor, extra = {}) => ({ id, titulo, autor, busca: chave(`${titulo} ${autor}`),
  autores: autor.split(/,|;|&| e /).map(chave).filter(Boolean), preco_cents: 5000, valido_ate: ATE, texto: null, ...extra });
const oferta = (l, preco = l.preco_cents) => ({ ...l, preco_cents: preco,
  texto: `${l.titulo}, de ${l.autor}\nR$ ${preco / 100}\nLink de afiliado: https://ofertaslivros.com.br/r/${l.id}/bot` });

function setup(livros) {
  const calls = [];
  const env = {
    TELEGRAM_WEBHOOK_SECRET: SEGREDO, BOT: fakeD1(), ANALYTICS: fakeD1(),
    ASSETS: { fetch: async () => new Response(JSON.stringify({ version: 1, livros: env.livros })) },
    livros,
  };
  env.ANALYTICS.db.exec(PEDIDOS_SCHEMA);
  let next = 1, resp = () => ({ ok: true });
  const api = async (method, body) => { calls.push({ method, body }); return method === "sendMessage" ? { ok: true, ...resp(body) } : { ok: true }; };
  const q = (sql, ...a) => env.BOT.db.prepare(sql).all(...a).map(r => ({ ...r }));
  const upd = (u, { segredo = SEGREDO, agora = AGORA } = {}) => {
    const body = JSON.stringify({ update_id: next++, ...u });
    return telegram(new Request("https://ofertaslivros.com.br/telegram", { method: "POST", body,
      headers: { "Content-Length": String(Buffer.byteLength(body)), ...(segredo ? { "X-Telegram-Bot-Api-Secret-Token": segredo } : {}) } }),
    env, api, agora);
  };
  const msg = (text, { chat = CHAT, type = "private", id = 10 } = {}) => upd({ message: { message_id: id, chat: { id: chat, type }, text } });
  const cb = (data, { chat = CHAT, message = { message_id: 50, chat: { id: chat, type: "private" }, text: "x" } } = {}) =>
    upd({ callback_query: { id: "q1", data, from: { id: chat }, message: { ...message, chat: { id: chat, type: "private" } } } });
  const enviados = () => calls.filter(c => c.method === "sendMessage");
  const ultimo = () => enviados().at(-1)?.body.text;
  const botoes = () => (enviados().at(-1)?.body.reply_markup?.inline_keyboard || []).flat();
  return { env, api, calls, q, msg, cb, upd, enviados, ultimo, botoes, setResp: f => { resp = f; } };
}

const TORTO = livro("torto-arado", "Torto Arado", "Itamar Vieira Junior");
const SALVAR = livro("salvar-o-fogo", "Salvar o fogo", "Itamar Vieira Junior");
const DOM = livro("dom-casmurro", "Dom Casmurro", "Machado de Assis");
const BOM = livro("good-omens", "Belas maldições", "Neil Gaiman e Terry Pratchett");

test("webhook: segredo, tamanho, tipo de chat e rate limit (1-4)", async () => {
  const t = setup([TORTO]);
  assert.equal((await t.upd({ message: { chat: { id: 1, type: "private" }, text: "/start" } }, { segredo: null })).status, 401);
  assert.equal((await t.upd({ message: { chat: { id: 1, type: "private" }, text: "/start" } }, { segredo: "errado" })).status, 401);
  const antes = t.calls.length;
  const big = "x".repeat(70000);
  const r = await telegram(new Request("https://x/telegram", { method: "POST", body: big,
    headers: { "X-Telegram-Bot-Api-Secret-Token": SEGREDO, "Content-Length": String(big.length) } }), t.env, t.api);
  assert.equal(r.status, 413);
  assert.equal((await telegram(new Request("https://x/telegram"), t.env, t.api)).status, 405);
  for (const type of ["group", "supergroup", "channel"]) assert.equal((await t.msg("/start torto-arado", { type })).status, 200);
  assert.equal(t.calls.length, antes);
  assert.equal(t.q("SELECT * FROM chats").length, 0);
  let n = 0;
  t.env.BOT_LIMITE = { limit: async () => ({ success: ++n <= 20 }) };
  for (let i = 0; i < 21; i++) await t.msg("/ajuda");
  assert.equal(t.enviados().length, 20);
});

test("log sem chat_id, texto nem token; saída sem parse_mode e sem prévia (5-6)", async () => {
  const t = setup([livro("x", "<b>x</b>", "Autor")]);
  const logs = [];
  const orig = console.log;
  console.log = (...a) => logs.push(a.join(" "));
  try {
    t.env.TELEGRAM_BOT_TOKEN = "123:TOKENSENTINELA";
    await t.msg("<b>x</b>");
    await t.msg("textosentinela-xyz");
    t.env.ASSETS = { fetch: async () => new Response("quebrado") };
    await t.msg("outro");
  } finally { console.log = orig; }
  assert.ok(logs.length > 0 && logs.every(l => !l.includes(String(CHAT)) && !l.includes("sentinela") && !l.includes("TOKEN")));
  for (const c of t.calls.filter(c => c.method !== "answerCallbackQuery")) {
    assert.equal(c.body.parse_mode, undefined);
    assert.deepEqual(c.body.link_preview_options, { is_disabled: true });
  }
  assert.match(t.enviados()[0].body.text, /Pronto: <b>x<\/b>, de Autor/);
});

test("callbacks presos ao chat e validados (7)", async () => {
  const t = setup([TORTO]);
  await t.msg("/start torto-arado");
  const [{ id }] = t.q("SELECT id FROM desejos");
  await t.cb(`rm:${id}`, { chat: 111 });
  assert.equal(t.q("SELECT * FROM desejos").length, 1);
  for (const d of ["add:nao-existe", "add:../x", "add:" + "a".repeat(70), "au:torto-arado:9", "lixo"]) await t.cb(d);
  assert.equal(t.q("SELECT * FROM desejos").length, 1);
});

test("/start <id>: adiciona com nota de privacidade, repetido, oferta na hora, inválido (8-10)", async () => {
  const t = setup([TORTO, oferta(DOM, 3000)]);
  await t.msg("/start torto-arado");
  assert.match(t.ultimo(), /^Pronto: Torto Arado, de Itamar Vieira Junior, está na sua lista\.[\s\S]*Privacidade: https:\/\/ofertaslivros\.com\.br\/privacidade\//);
  assert.equal(t.q("SELECT * FROM chats").length, 1);
  await t.msg("/start torto-arado");
  assert.equal(t.ultimo(), "Torto Arado já está na sua lista. Sua lista: /lista");
  assert.equal(t.q("SELECT * FROM desejos").length, 1);
  await t.msg("/start dom-casmurro");
  assert.ok(!/Privacidade/.test(t.enviados().at(-2).body.text));               // nota só na primeira vez
  assert.match(t.ultimo(), /^Ele já está em oferta agora:\n\nDom Casmurro/);
  assert.equal(t.q("SELECT price_cents FROM avisos WHERE book_id = 'dom-casmurro'")[0].price_cents, 3000);
  const n = t.enviados().length;
  await avisar(t.env, AGORA, t.api);
  assert.equal(t.enviados().length, n);                                        // o cron não repete
  for (const bad of ["/start id-que-nao-existe", "/start ../x", "/start " + "a".repeat(65)]) {
    await t.msg(bad);
    assert.equal(t.ultimo(), "Não achei esse livro no catálogo agora. Mande o título que eu procuro.");
  }
  assert.equal(t.q("SELECT * FROM desejos").length, 2);
});

test("busca: único, autor, muitos, nenhum, título — autor e acento (11-12)", async () => {
  const muitos = Array.from({ length: 7 }, (_, i) => livro(`harry-${i}`, `Harry Potter ${i}`, "J.K. Rowling"));
  const t = setup([TORTO, SALVAR, DOM, livro("acao", "Ação e Mangá", "Fulano"), ...muitos]);
  await t.msg("torto arado");
  assert.match(t.ultimo(), /^Pronto: Torto Arado/);
  assert.deepEqual(t.botoes().map(b => b.text), ["Desfazer"]);
  await t.msg("itamar vieira junior");
  assert.equal(t.ultimo(), "Quer aviso de qual?");
  assert.equal(t.botoes()[0].text, "Todos de Itamar Vieira Junior (2 no catálogo)");
  assert.equal(t.enviados().at(-1).body.reply_parameters.message_id, 10);
  await t.msg("harry potter");
  assert.match(t.ultimo(), /^Achei 7\./);
  assert.equal(t.botoes().length, 6);
  await t.msg("xyzxyz");
  assert.match(t.ultimo(), /^Não achei “xyzxyz”/);
  assert.deepEqual(t.botoes().map(b => b.callback_data), ["pd", "no"]);
  const L = [TORTO, SALVAR, DOM];
  assert.deepEqual(buscar(L, "Torto Arado — Itamar Vieira Junior").livros.map(l => l.id), ["torto-arado"]);
  assert.deepEqual(buscar(L, "torto arado - itamar").livros.map(l => l.id), ["torto-arado"]);
  assert.equal(chave("Ação"), "acao");
  assert.equal(chave("Mangá"), "manga");
  assert.deepEqual(buscar([livro("acao", "Ação e Mangá", "Fulano")], "acao manga").livros.length, 1);
});

test("várias linhas, limite de linhas e lista cheia (13-14)", async () => {
  const t = setup([TORTO, SALVAR, DOM]);
  await t.msg("dom casmurro\nitamar\nxyzxyz");
  assert.equal(t.ultimo(), "Adicionei: Dom Casmurro.\nAchei mais de um para: itamar. Mande sozinho para eu mostrar as opções.\n"
    + "Não achei: xyzxyz. Mande sozinho para pedir à curadoria.\nSua lista: /lista");
  assert.equal(t.q("SELECT * FROM desejos").length, 1);
  await t.msg(Array(11).fill("dom casmurro").join("\n"));
  assert.equal(t.ultimo(), "Mande até 10 nomes por mensagem, um por linha.");
  const ts = AGORA.toISOString();
  for (let i = 0; i < 29; i++) t.env.BOT.db.prepare("INSERT INTO desejos (chat_id, tipo, chave, criado_em) VALUES (?, 'livro', ?, ?)").run(CHAT, `x-${i}`, ts);
  await t.msg("/start torto-arado");
  assert.match(t.ultimo(), /^Sua lista já tem 30 itens/);
  assert.equal(t.q("SELECT COUNT(*) n FROM desejos")[0].n, 30);
});

test("pedido de livro: grava sem chat e com limite por minuto (15)", async () => {
  const t = setup([TORTO]);
  let n = 0;
  t.env.BOT_PEDIDOS = { limit: async () => ({ success: ++n <= 1 }) };
  const message = { message_id: 51, text: "x", reply_to_message: { message_id: 10, text: "O Avesso da Pele — Jeferson Tenório" } };
  await t.cb("pd", { message });
  const ped = t.env.ANALYTICS.db.prepare("SELECT * FROM pedidos").all().map(r => ({ ...r }));
  assert.equal(ped.length, 1);
  assert.deepEqual([ped[0].titulo, ped[0].autor], ["O Avesso da Pele", "Jeferson Tenório"]);
  assert.ok(!Object.values(ped[0]).includes(CHAT));
  await t.cb("pd", { message });
  assert.match(t.ultimo(), /^Calma/);
  assert.equal(t.env.ANALYTICS.db.prepare("SELECT COUNT(*) n FROM pedidos").get().n, 1);
});

test("/lista, Tirar, pausar/voltar, parar e bloqueio (16-19)", async () => {
  const t = setup([oferta(TORTO), DOM, SALVAR]);
  await t.msg("/start dom-casmurro");
  await t.cb("au:salvar-o-fogo:0");
  await t.msg("/start torto-arado");
  await t.msg("/lista");
  assert.equal(t.ultimo(), "Sua lista (3 de 30):\n• Dom Casmurro, de Machado de Assis\n• Autor: Itamar Vieira Junior (2 livros no catálogo)\n"
    + "• Torto Arado, de Itamar Vieira Junior (em oferta agora)\nPara tirar um item, toque nele abaixo.");
  const rm = t.botoes()[0];
  assert.equal(rm.text, "Tirar: Dom Casmurro");
  await t.cb(rm.callback_data, { message: { message_id: 77, text: t.ultimo() } });
  const ed = t.calls.filter(c => c.method === "editMessageText").at(-1);
  assert.match(ed.body.text, /^Sua lista \(2 de 30\)/);
  assert.equal(t.calls.at(-1).body.text, "Tirei da lista.");
  await t.msg("/pausar");
  assert.equal(t.q("SELECT pausado FROM chats")[0].pausado, 1);
  await t.msg("/parar");
  assert.deepEqual(t.botoes().map(b => b.callback_data), ["stop:sim", "stop:nao"]);
  await t.cb("stop:nao");
  assert.equal(t.q("SELECT * FROM desejos").length, 2);
  await t.cb("stop:sim");
  for (const tb of ["chats", "desejos", "avisos"]) assert.equal(t.q(`SELECT * FROM ${tb}`).length, 0);
  await t.msg("/start dom-casmurro");
  await t.upd({ my_chat_member: { chat: { id: CHAT, type: "private" }, new_chat_member: { status: "kicked" } } });
  assert.equal(t.q("SELECT * FROM chats").length + t.q("SELECT * FROM desejos").length, 0);
});

const noDia = h => new Date(Date.UTC(2026, 10, 6, h + 3, 20)); // hora BRT -> Date

test("cron: uma vez por entrada, carência de 6 h, baixou mais, prazo, janela (20-24, 28)", async () => {
  const t = setup([TORTO]);
  await t.msg("/start torto-arado");
  const base = t.enviados().length;
  t.env.livros = [oferta(TORTO, 4000)];
  await avisar(t.env, noDia(12), t.api);
  await avisar(t.env, noDia(12), t.api);
  assert.equal(t.enviados().length, base + 1);
  assert.match(t.ultimo(), /^Entrou em oferta \(está na sua lista\):\n\nTorto Arado[\s\S]*\n\nTirar da lista: \/lista$/);
  t.env.livros = [TORTO];                                    // some por 5 h e volta: nada
  await avisar(t.env, noDia(15), t.api);
  t.env.livros = [oferta(TORTO, 4000)];
  await avisar(t.env, noDia(17), t.api);
  assert.equal(t.enviados().length, base + 1);
  t.env.livros = [oferta(TORTO, 3880)];                      // -3%: nada
  await avisar(t.env, noDia(17), t.api);
  assert.equal(t.enviados().length, base + 1);
  t.env.livros = [oferta(TORTO, 3800)];                      // -5%: baixou mais
  await avisar(t.env, noDia(18), t.api);
  assert.match(t.ultimo(), /^Baixou mais/);
  t.env.livros = [TORTO];                                    // some por mais de 6 h e volta: avisa
  await avisar(t.env, noDia(19), t.api);
  t.env.livros = [{ ...oferta(TORTO, 3800), valido_ate: "2026-11-08T00:00:00Z" }];
  await avisar(t.env, new Date(Date.UTC(2026, 10, 7, 5, 20)), t.api); // 02h20 BRT: fora da janela, só em_oferta
  assert.equal(t.enviados().length, base + 2);
  assert.equal(t.q("SELECT * FROM em_oferta").length, 1);
  await avisar(t.env, new Date(Date.UTC(2026, 10, 7, 11, 20)), t.api); // 08h20: sai o pendente
  assert.equal(t.enviados().length, base + 3);
  assert.match(t.ultimo(), /^Entrou em oferta/);
  t.env.livros = [{ ...oferta(TORTO, 3000), valido_ate: "2026-11-06T00:00:00Z" }]; // vencido
  await avisar(t.env, new Date(Date.UTC(2026, 10, 7, 12, 20)), t.api);
  assert.equal(t.enviados().length, base + 3);
  t.env.livros = { version: 2 };
  t.env.ASSETS = { fetch: async () => new Response(JSON.stringify({ version: 2, livros: [] })) };
  await assert.rejects(avisar(t.env, noDia(12), t.api));
});

test("cron: pausa, limites, livro + autor = 1 aviso, 403 e 429 (17, 25-27)", async () => {
  const ls = Array.from({ length: 5 }, (_, i) => livro(`l-${i}`, `Livro ${i}`, "Autora X"));
  const t = setup(ls);
  for (const l of ls) await t.msg(`/start ${l.id}`);
  await t.cb("au:l-0:0");
  await t.msg("/pausar");
  t.env.livros = ls.map(l => oferta(l));
  const base = t.enviados().length;
  await avisar(t.env, noDia(12), t.api);
  assert.equal(t.enviados().length, base);
  await t.msg("/voltar");
  const b2 = t.enviados().length;
  await avisar(t.env, noDia(12), t.api);
  assert.equal(t.enviados().length - b2, 3);                 // 3 por execução, livro + autor contam uma vez
  assert.ok(t.enviados().slice(-3).every(c => c.body.text.startsWith("Entrou em oferta (está")));
  await avisar(t.env, noDia(13), t.api);
  assert.equal(t.enviados().length - b2, 5);
  // 60 chats elegíveis: saem 40
  const u = setup([livro("a", "A", "B")]);
  for (let i = 0; i < 60; i++) await u.msg("/start a", { chat: 1000 + i });
  u.env.livros = [oferta(livro("a", "A", "B"))];
  const b3 = u.enviados().length;
  await avisar(u.env, noDia(12), u.api);
  assert.equal(u.enviados().length - b3, 40);
  // 403 apaga o chat; 429 para sem gravar
  for (const [codigo, chatsFicam, avisosGravados] of [[403, [2], 1], [429, [2, CHAT].sort(), 0]]) {
    const v = setup([livro("a", "A", "B")]);
    await v.msg("/start a"); await v.msg("/start a", { chat: 2 });
    v.env.livros = [oferta(livro("a", "A", "B"))];
    v.setResp(b => (codigo === 429 || b.chat_id === CHAT ? { ok: false, error_code: codigo } : {}));
    await avisar(v.env, noDia(12), v.api);
    assert.deepEqual(v.q("SELECT chat_id FROM chats ORDER BY chat_id").map(r => r.chat_id), chatsFicam);
    assert.equal(v.q("SELECT * FROM avisos").length, avisosGravados);
  }
});

test("cron: retenção de 12 meses (29)", async () => {
  const t = setup([TORTO]);
  const ins = (chat, dias) => {
    const ts = new Date(AGORA.getTime() - dias * 86400e3).toISOString();
    t.env.BOT.db.prepare("INSERT INTO chats (chat_id, criado_em, visto_em) VALUES (?, ?, ?)").run(chat, ts, ts);
    t.env.BOT.db.prepare("INSERT INTO desejos (chat_id, tipo, chave, criado_em) VALUES (?, 'livro', 'torto-arado', ?)").run(chat, ts);
  };
  ins(1, 366); ins(2, 330);
  await avisar(t.env, AGORA, t.api);
  assert.deepEqual(t.q("SELECT chat_id FROM chats").map(r => r.chat_id), [2]);
  assert.deepEqual(t.q("SELECT chat_id FROM desejos").map(r => r.chat_id), [2]);
});
