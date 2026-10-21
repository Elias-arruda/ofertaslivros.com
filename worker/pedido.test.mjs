// node worker/pedido.test.mjs
import assert from "node:assert/strict";
import { pedido } from "./pedido.js";

const env = { PEDIDOS_PARA: "destino@example.com", LIMITE: { limit: async () => ({ success: true }) } };
const req = (body, { origin = "https://ofertaslivros.com.br", method = "POST" } = {}) =>
  new Request("https://ofertaslivros.com.br/pedido", {
    method, headers: { Origin: origin, "Content-Type": "application/x-www-form-urlencoded" },
    body: method === "POST" ? body : undefined,
  });
let enviados = [];
const enviar = async (para, raw) => enviados.push({ para, raw });

let r = await pedido(req("titulo=Dom+Casmurro&autor=Machado%0D%0ABcc:+x@y.com&site="), env, enviar);
assert.equal(r.status, 303);
assert.equal(r.headers.get("Location"), "/#pedido-recebido");
assert.equal(enviados.length, 1);
const corpo = Buffer.from(enviados[0].raw.split("\r\n\r\n")[1].replace(/\r\n/g, ""), "base64").toString();
assert.match(corpo, /Nome do livro: Dom Casmurro\nAutor do livro: Machado Bcc: x@y.com\n/); // quebra de linha vira espaço
assert.ok(!/\r\nBcc:/i.test(enviados[0].raw));

enviados = [];
assert.equal((await pedido(req("titulo=X&site=bot"), env, enviar)).status, 303);           // honeypot
assert.equal(enviados.length, 0);
assert.equal((await pedido(req("titulo=X", { origin: "https://evil.example" }), env, enviar)).status, 403);
assert.equal((await pedido(req("", { method: "GET" }), env, enviar)).status, 405);
assert.equal((await pedido(req("titulo=+&autor=a"), env, enviar)).status, 400);           // título vazio
assert.equal((await pedido(req("titulo=" + "a".repeat(151)), env, enviar)).status, 400);
assert.equal((await pedido(req("titulo=a&autor=" + "b".repeat(101)), env, enviar)).status, 400);
assert.equal((await pedido(req("titulo=" + "a".repeat(5000)), env, enviar)).status, 413);
assert.equal((await pedido(req("titulo=X"), { ...env, LIMITE: { limit: async () => ({ success: false }) } }, enviar)).status, 429);
assert.equal((await pedido(req("titulo=X"), { LIMITE: env.LIMITE }, enviar)).status, 503);
assert.equal((await pedido(req("titulo=X"), env, async () => { throw new Error("x"); })).status, 502);
assert.equal(enviados.length, 0);
console.log("ok");
