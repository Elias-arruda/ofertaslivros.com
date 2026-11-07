// /r/*: o redirecionamento continua sendo o _redirects estático (env.ASSETS.fetch, resposta devolvida intacta).
// Para quem veio de anúncio pago da Meta (fbclid + utm_medium=paid no Referer), manda o evento SaidaLoja
// à Conversions API depois de responder (docs/produto/meta-conversions-api.md). Sem IP, sem livro, nada guardado.
// Segredos META_CAPI_TOKEN, META_DATASET_ID e META_TEST_CODE (opcional) no Worker; sem eles, nada sai.
// Ordem: este código entra inerte, depois da spec (PR #143) e junto do PR da /privacidade/ (texto + botão de
// opt-out, do frontend-developer). Os segredos só são gravados com a /privacidade/ já descrevendo o envio.

const GRAPH = "https://graph.facebook.com/v27.0";
const ORIGEM = "https://ofertaslivros.com.br";
// Os mesmos hosts do ALLOWED_HOSTS do build.py. Só decide se dispara; o destino nunca sai daqui.
const LOJAS = new Set(["amazon.com.br", "www.amazon.com.br", "mercadolivre.com.br", "www.mercadolivre.com.br", "mercadolivre.com"]);
const FBCLID = /^[A-Za-z0-9_-]{10,500}$/;
// As 5 páginas de destino dos anúncios; qualquer outra página vai como a raiz (não revela qual livro foi visto).
const DESTINOS = new Set(["/black-friday/", "/negocios/", "/mindset/", "/romance/", "/fantasia/"]);

/** Corpo do evento, ou null se não for clique de anúncio pago para uma loja. */
export function evento(request, resposta, env, agora = Date.now()) {
  if (request.method !== "GET" || resposta.status !== 302) return null;
  if (!env.META_CAPI_TOKEN || !/^\d+$/.test(env.META_DATASET_ID || "")) return null;
  if (request.headers.get("Sec-GPC") === "1") return null;
  if (/(?:^|;\s*)sem_meta=1(?:;|$)/.test(request.headers.get("Cookie") || "")) return null;
  const destino = new URL(resposta.headers.get("Location") || "/", ORIGEM);
  if (destino.protocol !== "https:" || !LOJAS.has(destino.hostname)) return null;
  const ref = new URL(request.headers.get("Referer") || "/", "http://invalido");
  if (ref.origin !== ORIGEM) return null;
  const fbclid = ref.searchParams.get("fbclid") || "";
  if (!FBCLID.test(fbclid) || ref.searchParams.get("utm_medium") !== "paid") return null;
  const ua = request.headers.get("User-Agent");
  if (!ua) return null; // a Meta exige client_user_agent em evento de site
  const corpo = {
    data: [{
      event_name: "SaidaLoja",
      event_time: Math.floor(agora / 1000),
      event_id: crypto.randomUUID(),
      action_source: "website",
      event_source_url: ORIGEM + (DESTINOS.has(ref.pathname) ? ref.pathname : "/"),
      user_data: { fbc: `fb.1.${agora}.${fbclid}`, client_user_agent: ua },
    }],
  };
  if (env.META_TEST_CODE) corpo.test_event_code = env.META_TEST_CODE;
  return corpo;
}

async function enviar(corpo, env, f) {
  try {
    const r = await f(`${GRAPH}/${env.META_DATASET_ID}/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...corpo, access_token: env.META_CAPI_TOKEN }), // token no corpo, nunca na URL
      signal: AbortSignal.timeout(3000),
    });
    if (!r.ok) console.log("meta capi", r.status); // só o status: nada de fbclid, Referer, UA ou corpo
  } catch {
    console.log("meta capi falhou");
  }
}

export async function saida(request, env, ctx, f = fetch) {
  const resposta = await env.ASSETS.fetch(request);
  try {
    const corpo = evento(request, resposta, env);
    if (corpo) ctx.waitUntil(enviar(corpo, env, f)); // sem retry; o 302 nunca espera a Meta
  } catch {} // Referer malformado etc.: o redirecionamento segue igual
  return resposta;
}

/** POST /privacidade/sem-meta: opt-out do envio. O cookie só viaja para o /r/. */
export function semMeta(request) {
  if (request.method !== "POST") return new Response("Método não permitido", { status: 405, headers: { Allow: "POST" } });
  return new Response(null, {
    status: 303,
    headers: {
      Location: "/privacidade/#sem-meta-ok",
      "Set-Cookie": "sem_meta=1; Max-Age=31536000; Path=/r/; Secure; HttpOnly; SameSite=Lax",
    },
  });
}
