// Worker do site: os arquivos de dist/ saem direto dos assets; só /pedido, /painel, /telegram, /r/* e
// /privacidade/sem-meta passam por aqui (run_worker_first). O cron (20 e 50 de cada hora) manda os avisos do bot do Telegram.
import { EmailMessage } from "cloudflare:email";
import { pedido } from "./pedido.js";
import { painel } from "./painel.js";
import { telegram, avisar } from "./bot.js";
import { saida, semMeta } from "./saida.js";

export default {
  async fetch(request, env, ctx) {
    const { pathname } = new URL(request.url);
    if (pathname === "/painel" || pathname.startsWith("/painel/")) return painel(request, env);
    if (pathname.startsWith("/r/")) return saida(request, env, ctx);
    if (pathname === "/privacidade/sem-meta") return semMeta(request);
    if (pathname === "/telegram") return telegram(request, env);
    if (pathname === "/pedido")
      return pedido(request, env, (para, raw) =>
        env.PEDIDOS.send(new EmailMessage("pedidos@ofertaslivros.com.br", para, raw)));
    return env.ASSETS.fetch(request);
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil(avisar(env));
  },
};
