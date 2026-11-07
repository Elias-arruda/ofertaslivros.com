// Bot de lista de desejos do Telegram (docs/produto/bot-lista-de-desejos.md): webhook POST /telegram e cron de avisos.
// Dado pessoal só no D1 BOT (chat_id e a lista). Nada do usuário vai para o log: só contagens e tipo de erro.
// A regra de oferta fica no build.py: o /bot.json traz o texto pronto (post_text) só para livro em oferta no prazo.
import { PEDIDOS_SCHEMA } from "../cron/rollup.js";

const SITE = "https://ofertaslivros.com.br";
const PRIVACIDADE = `${SITE}/privacidade/`;
const MAX_CORPO = 65536;
const MAX_ITENS = 30;
const MAX_LINHAS = 10;
const ID_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
// Disparo (§7.4), valores decididos pelo Elias em 2026-11-06: mudar o número e abrir PR.
const POR_CHAT_EXEC = 3, POR_CHAT_DIA = 10, POR_EXEC = 40;
const JANELA = [8, 22];         // horas BRT
const BAIXOU_MAIS = 95;         // avisa de novo com preço <= 95% do último aviso
const SAIU_H = 6;               // fora do bot.json por mais que isso: saiu da oferta
const RETENCAO_DIAS = 365;      // chat sem uso por 12 meses é apagado

export const BOT_SCHEMA = [
  `CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY, pausado INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL, visto_em TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS desejos (id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('livro', 'autor')), chave TEXT NOT NULL, criado_em TEXT NOT NULL,
    UNIQUE (chat_id, tipo, chave))`,
  `CREATE TABLE IF NOT EXISTS avisos (chat_id INTEGER NOT NULL, book_id TEXT NOT NULL, price_cents INTEGER NOT NULL,
    avisado_em TEXT NOT NULL, PRIMARY KEY (chat_id, book_id))`,
  `CREATE TABLE IF NOT EXISTS em_oferta (book_id TEXT PRIMARY KEY, visto_em TEXT NOT NULL)`,
];

/** Igual ao build.bot_key: minúsculas, sem acento, só [a-z0-9] separados por espaço. */
export const chave = s => s.toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "").replace(/[^a-z0-9]+/g, " ").trim();
const palavras = s => chave(s).split(" ").filter(Boolean);
const corta = (s, n = 60) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
const emOferta = (l, agora) => !!l?.texto && agora <= Date.parse(l.valido_ate);
const horaBRT = agora => (agora.getUTCHours() + 21) % 24;
const diaBRT = agora => new Date(agora.getTime() - 3 * 3600e3).toISOString().slice(0, 10);

export function telegramApi(env) {
  return async (method, body) => {
    const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    return r.json().catch(() => ({ ok: false, error_code: r.status }));
  };
}

export async function catalogo(env) {
  const r = await env.ASSETS.fetch(new Request(`${SITE}/bot.json`));
  const doc = r.ok ? await r.json() : null;
  if (doc?.version !== 1 || !Array.isArray(doc.livros)) throw new Error("bot.json inválido");
  return { livros: doc.livros, porId: new Map(doc.livros.map(l => [l.id, l])) };
}

let schemaPronto = false;
async function schema(db) {
  if (schemaPronto) return;
  await db.batch(BOT_SCHEMA.map(s => db.prepare(s)));
  schemaPronto = true;
}

// Header do webhook comparado em tempo constante (SHA-256 dos dois lados, sem atalho no primeiro byte diferente).
async function segredoOk(recebido, esperado) {
  if (!recebido || !esperado) return false;
  const h = async s => new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
  const [a, b] = await Promise.all([h(recebido), h(esperado)]);
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a[i] ^ b[i];
  return d === 0;
}

// ---------- webhook ----------

export async function telegram(request, env, api = telegramApi(env), agora = new Date()) {
  if (request.method !== "POST") return new Response(null, { status: 405 });
  if (!(await segredoOk(request.headers.get("X-Telegram-Bot-Api-Secret-Token"), env.TELEGRAM_WEBHOOK_SECRET)))
    return new Response(null, { status: 401 });
  const tam = Number(request.headers.get("Content-Length"));
  if (!tam) return new Response(null, { status: 411 }); // o Telegram sempre manda; sem ele, nem lê o corpo
  if (tam > MAX_CORPO) return new Response(null, { status: 413 });
  const corpo = await request.text();
  if (corpo.length > MAX_CORPO) return new Response(null, { status: 413 });
  try {
    await tratar(JSON.parse(corpo), env, api, agora);
  } catch (e) {
    console.log(`bot: erro no update (${e?.name || "erro"})`); // 200 mesmo assim: o Telegram não reenvia
  }
  return new Response("ok");
}

async function tratar(u, env, api, agora) {
  const chat = u.message?.chat ?? u.callback_query?.message?.chat ?? u.my_chat_member?.chat;
  if (chat?.type !== "private") return; // grupo, supergrupo e canal: ignorados em silêncio
  const db = env.BOT;
  await schema(db);
  if (u.my_chat_member) {
    if (u.my_chat_member.new_chat_member?.status === "kicked") await apagarChat(db, chat.id);
    return;
  }
  if (!env.BOT_LIMITE || !(await env.BOT_LIMITE.limit({ key: String(chat.id) })).success) return; // sem binding: fecha
  await db.prepare("UPDATE chats SET visto_em = ?2 WHERE chat_id = ?1").bind(chat.id, agora.toISOString()).run();
  const c = { db, env, api, agora, chat: chat.id, cat: null };
  c.livros = async () => (c.cat ??= await catalogo(env));
  if (u.callback_query) return callback(c, u.callback_query);
  const m = u.message;
  if (typeof m.text !== "string") return enviar(c, "Por aqui eu só entendo texto: mande o título ou o nome do autor.");
  const cmd = m.text.match(/^\/([a-z_]+)(?:@\w+)?(?:\s+(.*))?$/is);
  if (!cmd) return cadastro(c, m);
  const arg = (cmd[2] || "").trim();
  switch (cmd[1].toLowerCase()) {
    case "start": return arg ? startId(c, arg) : boasVindas(c);
    case "lista": return lista(c);
    case "pausar": return pausar(c, 1);
    case "voltar": return pausar(c, 0);
    case "parar": return enviar(c, "Isso apaga sua lista e tudo o que guardo sobre esta conversa. Quer mesmo?",
      teclado([[["Apagar tudo", "stop:sim"], ["Cancelar", "stop:nao"]]]));
    case "ajuda": return ajuda(c);
    default: return enviar(c, "Não conheço esse comando. Veja /ajuda.");
  }
}

// Sem parse_mode e sem prévia de link em toda mensagem (título vem de dado coletado; a prévia seguiria o /r/).
const enviar = (c, text, extra = {}) =>
  c.api("sendMessage", { chat_id: c.chat, text, link_preview_options: { is_disabled: true }, ...extra });
const teclado = linhas => ({ reply_markup: { inline_keyboard: linhas.map(l => l.map(([t, d]) => ({ text: corta(t), callback_data: d }))) } });
const resposta = (m, extra = {}) => ({ reply_parameters: { message_id: m.message_id, allow_sending_without_reply: true }, ...extra });

const boasVindas = c => enviar(c, "Oi, eu sou a Mavi, do Ofertas Livros.\n"
  + "Me diga um livro ou um autor e eu aviso aqui quando ele entrar em oferta no site.\n"
  + "É só mandar o título ou o nome do autor numa mensagem. Pode mandar vários, um por linha.\n"
  + `Ajuda: /ajuda\n\nGuardo o número desta conversa, a sua lista e quando avisei. Para apagar tudo: /parar. Privacidade: ${PRIVACIDADE}`,
  { reply_markup: { inline_keyboard: [[{ text: "Ver as ofertas de hoje", url: `${SITE}/ofertas/` }]] } });

const ajuda = c => enviar(c, "Como usar:\n"
  + "• Mande o título ou o nome do autor. Pode mandar vários, um por linha. Ex.: Torto Arado — Itamar Vieira Junior\n"
  + "• Eu aviso aqui quando o livro entrar em oferta no site, com o mesmo critério do site e do canal.\n"
  + "• Aviso uma vez por oferta, das 8h às 22h. Se o preço cair mais, aviso de novo.\n"
  + "• /lista mostra e tira itens · /pausar pausa os avisos · /voltar retoma · /parar apaga tudo\n"
  + "• O preço final é o da loja. Os links são de afiliado: ganhamos com compras qualificadas, sem custo para você.\n"
  + `Privacidade: ${PRIVACIDADE}`);

async function pausar(c, valor) {
  await c.db.prepare("UPDATE chats SET pausado = ?2 WHERE chat_id = ?1").bind(c.chat, valor).run();
  return enviar(c, valor ? "Avisos pausados. Sua lista continua guardada. Para voltar: /voltar."
    : "Voltei a avisar. Sua lista: /lista");
}

export async function apagarChat(db, chat) {
  await db.batch(["chats", "desejos", "avisos"].map(t => db.prepare(`DELETE FROM ${t} WHERE chat_id = ?1`).bind(chat)));
}

/** Grava um item: "cheia" | "repetido" | { id, novo } (novo = primeira linha do chat, leva a nota de privacidade). */
async function adicionar(c, tipo, ch) {
  const ts = c.agora.toISOString();
  const n = await c.db.prepare("SELECT COUNT(*) AS n FROM desejos WHERE chat_id = ?1").bind(c.chat).first();
  if (n.n >= MAX_ITENS) return "cheia";
  const [novo, ins] = await c.db.batch([
    c.db.prepare("INSERT OR IGNORE INTO chats (chat_id, criado_em, visto_em) VALUES (?1, ?2, ?2)").bind(c.chat, ts),
    c.db.prepare("INSERT OR IGNORE INTO desejos (chat_id, tipo, chave, criado_em) VALUES (?1, ?2, ?3, ?4)").bind(c.chat, tipo, ch, ts),
  ]);
  if (!ins.meta.changes) return "repetido";
  return { id: ins.meta.last_row_id, novo: novo.meta.changes > 0 };
}

const NOTA = `\n\nGuardo o número desta conversa, a sua lista e quando avisei. Para apagar tudo: /parar. Privacidade: ${PRIVACIDADE}`;
const CHEIA = `Sua lista já tem ${MAX_ITENS} itens, o máximo. Tire algum em /lista e tente de novo.`;

/** Adiciona um livro e confirma; se ele já está em oferta, manda o aviso na hora (e grava, para o cron não repetir). */
async function addLivro(c, l, desfazer = false) {
  const r = await adicionar(c, "livro", l.id);
  if (r === "cheia") return enviar(c, CHEIA);
  if (r === "repetido") return enviar(c, `${l.titulo} já está na sua lista. Sua lista: /lista`);
  await enviar(c, `Pronto: ${l.titulo}, de ${l.autor}, está na sua lista.\nAviso aqui quando ele entrar em oferta.\nSua lista: /lista${r.novo ? NOTA : ""}`,
    desfazer ? teclado([[["Desfazer", `rm:${r.id}`]]]) : {});
  if (emOferta(l, c.agora)) await aviso(c, l, "Ele já está em oferta agora:");
}

async function addAutor(c, l, k) {
  const r = await adicionar(c, "autor", l.autores[k]);
  const nome = autorNome(l, k);
  if (r === "cheia") return enviar(c, CHEIA);
  if (r === "repetido") return enviar(c, `${nome} já está na sua lista. Sua lista: /lista`);
  return enviar(c, `Pronto: aviso quando sair oferta de livro de ${nome}.\nSua lista: /lista${r.novo ? NOTA : ""}`);
}

const autorNome = (l, k) => (l.autores.length === 1 ? l.autor : l.autores[k]);

async function aviso(c, l, cabecalho) {
  const r = await enviar(c, `${cabecalho}\n\n${l.texto}\n\nTirar da lista: /lista`);
  if (r?.ok) await c.db.prepare(`INSERT INTO avisos (chat_id, book_id, price_cents, avisado_em) VALUES (?1, ?2, ?3, ?4)
    ON CONFLICT (chat_id, book_id) DO UPDATE SET price_cents = ?3, avisado_em = ?4`)
    .bind(c.chat, l.id, l.preco_cents, c.agora.toISOString()).run();
  return r;
}

async function startId(c, id) {
  const l = ID_RE.test(id) && id.length <= 60 ? (await c.livros()).porId.get(id) : null;
  if (!l) return enviar(c, "Não achei esse livro no catálogo agora. Mande o título que eu procuro.");
  return addLivro(c, l);
}

// ---------- busca e cadastro por texto ----------

// ponytail: título com " - " no nome ("Harry Potter - A Pedra Filosofal") vira título + autor; mandar sem o traço resolve
const SEP = /\s+[—–-]\s+/;

/** Linha -> { livros (ordenados), autor: { l, k, n } | null }. */
export function buscar(livros, linha) {
  const [t, a] = linha.split(SEP, 2);
  const pt = palavras(t), pa = a ? palavras(a) : [];
  const tem = (campo, ws) => { const cs = palavras(campo); return ws.every(w => cs.some(x => x.startsWith(w))); };
  const achados = !pt.length || (a && !pa.length) ? [] // "@#$" ou emoji: sem palavra, sem resultado
    : livros.filter(l => (a ? tem(l.titulo, pt) && tem(l.autor, pa) : tem(`${l.titulo} ${l.autor}`, pt)));
  const q = chave(t);
  const rank = l => { const ct = chave(l.titulo); return ct === q ? 0 : ct.startsWith(q) ? 1 : 2; };
  achados.sort((x, y) => rank(x) - rank(y) || x.titulo.localeCompare(y.titulo, "pt-BR"));
  let autor = null;
  if (!a) for (const l of livros) {
    const k = l.autores.indexOf(q);
    if (k >= 0 && k < 10) { autor = { l, k, n: livros.filter(x => x.autores.includes(q)).length }; break; } // k de 1 dígito no callback
  }
  return { livros: achados, autor };
}

async function cadastro(c, m) {
  const linhas = m.text.split("\n").map(s => s.trim().replace(/^["'“”‘’.,;:!?]+|["'“”‘’.,;:!?]+$/g, "")).filter(Boolean);
  if (!linhas.length) return;
  if (linhas.length > MAX_LINHAS || linhas.some(s => s.length > 120)) return enviar(c, "Mande até 10 nomes por mensagem, um por linha.");
  const { livros } = await c.livros();
  if (linhas.length === 1) return umaLinha(c, m, linhas[0], buscar(livros, linhas[0]));
  const add = [], varios = [], nada = [];
  let cheia = false, novo = false;
  for (const s of linhas) {
    const r = s.length < 3 ? { livros: [], autor: null } : buscar(livros, s);
    if (r.livros.length === 1 && !r.autor) {
      const x = await adicionar(c, "livro", r.livros[0].id);
      if (x === "cheia") cheia = true;
      else if (x !== "repetido") { add.push(r.livros[0].titulo); novo ||= x.novo; }
    } else (r.livros.length || r.autor ? varios : nada).push(s);
  }
  return enviar(c, [add.length && `Adicionei: ${add.join("; ")}.`, cheia && CHEIA,
    varios.length && `Achei mais de um para: ${varios.join("; ")}. Mande sozinho para eu mostrar as opções.`,
    nada.length && `Não achei: ${nada.join("; ")}. Mande sozinho para pedir à curadoria.`, "Sua lista: /lista"].filter(Boolean).join("\n")
    + (novo ? NOTA : ""));
}

const PERGUNTA_PEDIDO = s => `Não achei “${s}” no nosso catálogo. Quer que eu peça para a curadoria incluir?`;
const BOTOES_PEDIDO = [[["Pedir este livro", "pd"], ["Não, obrigado", "no"]]];
const opcao = l => [`${l.titulo} — ${l.autor}`, `add:${l.id}`];

function umaLinha(c, m, s, r) {
  if (s.length < 3) return enviar(c, "Mande pelo menos 3 letras do título ou do autor.");
  if (r.autor) {
    const { l, k, n } = r.autor;
    return enviar(c, "Quer aviso de qual?", resposta(m, teclado([[[`Todos de ${autorNome(l, k)} (${n} no catálogo)`, `au${k}:${l.id}`]],
      ...r.livros.slice(0, 4).map(x => [opcao(x)])])));
  }
  if (r.livros.length === 1) return addLivro(c, r.livros[0], true);
  if (!r.livros.length) return enviar(c, PERGUNTA_PEDIDO(s), resposta(m, teclado(BOTOES_PEDIDO)));
  const txt = r.livros.length > 5 ? `Achei ${r.livros.length}. Mostro os 5 primeiros; se não for nenhum, mande o título mais completo.`
    : "Achei mais de um. Qual deles?";
  return enviar(c, txt, resposta(m, teclado([...r.livros.slice(0, 5).map(x => [opcao(x)]), [["Nenhum desses", "nd"]]])));
}

// ---------- /lista ----------

async function textoLista(c) {
  const [{ results: itens }, chat] = await Promise.all([
    c.db.prepare("SELECT id, tipo, chave FROM desejos WHERE chat_id = ?1 ORDER BY id").bind(c.chat).all(),
    c.db.prepare("SELECT pausado FROM chats WHERE chat_id = ?1").bind(c.chat).first(),
  ]);
  if (!itens.length) return { text: "Sua lista está vazia. Mande o título ou o autor de um livro para começar." };
  const { livros, porId } = await c.livros();
  const linhas = [], botoes = [];
  for (const i of itens) {
    if (i.tipo === "livro") {
      const l = porId.get(i.chave);
      linhas.push(l ? `• ${l.titulo}, de ${l.autor}${emOferta(l, c.agora) ? " (em oferta agora)" : ""}` : `• ${i.chave} (fora do catálogo agora)`);
      botoes.push([[`Tirar: ${l ? l.titulo : i.chave}`, `rm:${i.id}`]]);
    } else {
      const doAutor = livros.filter(l => l.autores.includes(i.chave));
      const nome = doAutor.length ? autorNome(doAutor[0], doAutor[0].autores.indexOf(i.chave)) : i.chave;
      linhas.push(`• Autor: ${nome} (${doAutor.length} livros no catálogo)`);
      botoes.push([[`Tirar: ${nome}`, `rm:${i.id}`]]);
    }
  }
  return { text: `Sua lista (${itens.length} de ${MAX_ITENS}):\n${linhas.join("\n")}\nPara tirar um item, toque nele abaixo.`
    + (chat?.pausado ? "\nAvisos pausados. Para voltar: /voltar." : ""), extra: teclado(botoes) };
}

async function lista(c) {
  const { text, extra } = await textoLista(c);
  return enviar(c, text, extra);
}

// ---------- callbacks (callback_data é dado do cliente: validado e preso ao chat de quem tocou) ----------

async function callback(c, q) {
  const r = { aviso: "" };
  try {
    await acao(c, q, r);
  } finally { // botão nunca fica girando, nem se a ação falhar
    await c.api("answerCallbackQuery", { callback_query_id: q.id, ...(r.aviso ? { text: r.aviso } : {}) });
  }
}

async function acao(c, q, r_) {
  const d = typeof q.data === "string" ? q.data : "";
  const msg = q.message;
  let m;
  if ((m = d.match(/^add:([a-z0-9-]{1,60})$/))) {
    const l = (await c.livros()).porId.get(m[1]);
    if (l) await addLivro(c, l);
  } else if ((m = d.match(/^au(\d):([a-z0-9-]{1,60})$/))) {
    const l = (await c.livros()).porId.get(m[2]);
    if (l && Number(m[1]) < l.autores.length) await addAutor(c, l, Number(m[1]));
  } else if ((m = d.match(/^rm:(\d{1,15})$/))) {
    const r = await c.db.prepare("DELETE FROM desejos WHERE id = ?1 AND chat_id = ?2").bind(Number(m[1]), c.chat).run();
    r_.aviso = r.meta.changes ? "Tirei da lista." : "";
    if (msg?.text?.startsWith("Sua lista")) {
      const { text, extra } = await textoLista(c);
      const e = await c.api("editMessageText", { chat_id: c.chat, message_id: msg.message_id, text,
        link_preview_options: { is_disabled: true }, ...(extra || {}) });
      if (!e?.ok) await enviar(c, text, extra);
    } else if (r.meta.changes && msg) {
      await c.api("editMessageText", { chat_id: c.chat, message_id: msg.message_id, text: "Desfeito: tirei da lista.",
        link_preview_options: { is_disabled: true } });
    }
  } else if (d === "nd") {
    const orig = msg?.reply_to_message;
    if (orig?.text) await enviar(c, PERGUNTA_PEDIDO(orig.text.trim()), resposta(orig, teclado(BOTOES_PEDIDO)));
  } else if (d === "pd") {
    await pedir(c, msg?.reply_to_message?.text);
  } else if (d === "no") {
    r_.aviso = "Tudo bem.";
  } else if (d === "stop:sim") {
    await apagarChat(c.db, c.chat);
    await enviar(c, "Pronto, apaguei tudo. Se quiser voltar, é só mandar /start.");
  } else if (d === "stop:nao") {
    await enviar(c, "Nada foi apagado.");
  }
}

// Pedido de livro pelo bot: vai para a tabela pedidos (D1 ANALYTICS, 30 dias) sem nenhum dado do chat e sem e-mail.
async function pedir(c, texto) {
  const s = typeof texto === "string" ? texto.replace(/[\u0000-\u001f\u007f]+/g, " ").trim() : "";
  if (!s || s.length > 150) return;
  if (!c.env.BOT_PEDIDOS || !(await c.env.BOT_PEDIDOS.limit({ key: String(c.chat) })).success)
    return enviar(c, "Calma, acabei de anotar um pedido seu. Tente de novo em um minuto.");
  const [titulo, autor = ""] = s.split(SEP, 2);
  const db = c.env.ANALYTICS;
  await db.batch([db.prepare(PEDIDOS_SCHEMA), db.prepare(
    "INSERT INTO pedidos (criado_em, titulo, autor) VALUES (datetime('now'), ?1, ?2)").bind(titulo.slice(0, 150), autor.slice(0, 100))]);
  return enviar(c, "Pedido enviado para a curadoria. Se o livro entrar no catálogo, ele aparece no site e no canal. "
    + "Eu não aviso sozinha: quando ele aparecer, é só me mandar o título de novo.");
}

// ---------- cron: avisos (§7.3 e §7.4) ----------

export async function avisar(env, agora = new Date(), api = telegramApi(env)) {
  const db = env.BOT;
  await schema(db);
  const { livros, porId } = await catalogo(env); // bot.json inválido: lança e não manda nada
  const O = livros.filter(l => emOferta(l, agora));
  const ts = agora.toISOString();
  const saiu = new Date(agora.getTime() - SAIU_H * 3600e3).toISOString();
  const velho = new Date(agora.getTime() - RETENCAO_DIAS * 86400e3).toISOString();
  // Livro que sai da oferta: o preço do último aviso vira 0 (a próxima entrada avisa de novo) e a linha fica até o
  // fim do dia BRT, só para contar o limite diário (um aviso por livro por dia; avisos do dia = linhas do dia).
  const inicioDia = `${diaBRT(agora)}T03:00:00.000Z`;
  await db.batch([ // saída antes da renovação: livro que volta depois de 6 h fora conta como nova entrada
    db.prepare("UPDATE avisos SET price_cents = 0 WHERE book_id IN (SELECT book_id FROM em_oferta WHERE visto_em < ?1)").bind(saiu),
    db.prepare("DELETE FROM em_oferta WHERE visto_em < ?1").bind(saiu),
    db.prepare(`INSERT INTO em_oferta (book_id, visto_em) SELECT value, ?2 FROM json_each(?1) WHERE true
      ON CONFLICT (book_id) DO UPDATE SET visto_em = excluded.visto_em`).bind(JSON.stringify(O.map(l => l.id)), ts),
    // aviso do /start de livro que saiu antes do cron (ou saiu do catálogo): nunca entrou em em_oferta
    db.prepare("UPDATE avisos SET price_cents = 0 WHERE book_id NOT IN (SELECT book_id FROM em_oferta)"),
    db.prepare("DELETE FROM avisos WHERE price_cents = 0 AND avisado_em < ?1").bind(inicioDia),
    ...["desejos", "avisos", "chats"].map(t => db.prepare(
      `DELETE FROM ${t} WHERE chat_id IN (SELECT chat_id FROM chats WHERE visto_em < ?1)`).bind(velho)),
  ]);
  const cont = { oferta: O.length, enviados: 0, bloqueados: 0, erros: 0 };
  const h = horaBRT(agora);
  if (h < JANELA[0] || h >= JANELA[1] || !O.length) return log(cont);

  const [{ results: desejos }, { results: avisos }] = await Promise.all([
    db.prepare("SELECT d.chat_id, d.tipo, d.chave FROM desejos d JOIN chats c USING (chat_id) WHERE c.pausado = 0").all(),
    db.prepare("SELECT chat_id, book_id, price_cents, avisado_em FROM avisos").all(),
  ]);
  const hoje = diaBRT(agora);
  const ultimo = new Map(avisos.map(a => [`${a.chat_id}|${a.book_id}`, a]));
  const noDia = new Map();
  for (const a of avisos) if (diaBRT(new Date(a.avisado_em)) === hoje) noDia.set(a.chat_id, (noDia.get(a.chat_id) || 0) + 1);
  const porAutor = new Map();
  for (const l of O) for (const k of l.autores) porAutor.set(k, [...(porAutor.get(k) || []), l]);
  const emO = new Set(O.map(l => l.id));

  const porChat = new Map(); // chat -> Map(book_id -> {l, cab})
  const quer = (chat, l, cab) => {
    const m = porChat.get(chat) || new Map();
    if (!m.has(l.id) || cab.livro) m.set(l.id, { l, cab }); // livro na lista vence o autor (um aviso só)
    porChat.set(chat, m);
  };
  for (const d of desejos) {
    if (d.tipo === "livro" && emO.has(d.chave)) quer(d.chat_id, porId.get(d.chave), { livro: true });
    if (d.tipo === "autor") for (const l of porAutor.get(d.chave) || []) quer(d.chat_id, l, { autor: autorNome(l, l.autores.indexOf(d.chave)) });
  }
  const fila = [];
  for (const [chat, m] of porChat) {
    const cands = [];
    for (const { l, cab } of m.values()) {
      const a = ultimo.get(`${chat}|${l.id}`);
      if (a && diaBRT(new Date(a.avisado_em)) === hoje) continue; // um aviso por livro por dia
      const baixou = a?.price_cents > 0;                          // 0 = saiu da oferta: nova entrada
      if (baixou && l.preco_cents * 100 > a.price_cents * BAIXOU_MAIS) continue;
      cands.push({ l, cabecalho: baixou ? "Baixou mais (está na sua lista):"
        : cab.autor ? `Entrou em oferta, de ${cab.autor} (autor na sua lista):` : "Entrou em oferta (está na sua lista):" });
    }
    const selo = x => (x.l.texto.startsWith("Menor preço em 90 dias") ? 0 : 1);
    // §7.4: selo de 90 dias primeiro, depois o maior desconto (campo desconto do bot.json)
    cands.sort((x, y) => selo(x) - selo(y) || (y.l.desconto || 0) - (x.l.desconto || 0));
    const vagas = Math.min(POR_CHAT_EXEC, POR_CHAT_DIA - (noDia.get(chat) || 0));
    if (vagas > 0) fila.push({ chat, n: noDia.get(chat) || 0, itens: cands.slice(0, vagas) });
  }
  fila.sort((x, y) => x.n - y.n);
  const c = { db, api, agora };
  envio: for (const f of fila) for (const { l, cabecalho } of f.itens) {
    if (cont.enviados + cont.bloqueados + cont.erros >= POR_EXEC) break envio; // toda tentativa é subrequest
    const r = await aviso({ ...c, chat: f.chat }, l, cabecalho);
    if (r?.ok) cont.enviados++;
    else if (r?.error_code === 403) { await apagarChat(db, f.chat); cont.bloqueados++; continue envio; }
    else if (r?.error_code === 429) break envio;
    else cont.erros++;
  }
  return log(cont);
}

function log(c) {
  console.log(`bot-cron: ${c.oferta} em oferta, ${c.enviados} enviados, ${c.bloqueados} bloqueado, ${c.erros} erro`);
  return c;
}
