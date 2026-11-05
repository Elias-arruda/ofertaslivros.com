// Worker do site: os arquivos de dist/ saem direto dos assets; só /pedido e /painel passam por aqui (run_worker_first).
import { EmailMessage } from "cloudflare:email";
import { pedido } from "./pedido.js";
import { painel } from "./painel.js";

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (pathname === "/painel" || pathname.startsWith("/painel/")) return painel(request, env);
    if (pathname === "/pedido")
      return pedido(request, env, (para, raw) =>
        env.PEDIDOS.send(new EmailMessage("pedidos@ofertaslivros.com.br", para, raw)));
    return env.ASSETS.fetch(request);
  },
};
