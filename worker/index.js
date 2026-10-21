// Worker do site: os arquivos de dist/ saem direto dos assets; só /pedido passa por aqui (run_worker_first).
import { EmailMessage } from "cloudflare:email";
import { pedido } from "./pedido.js";

export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname === "/pedido")
      return pedido(request, env, (para, raw) =>
        env.PEDIDOS.send(new EmailMessage("pedidos@ofertaslivros.com.br", para, raw)));
    return env.ASSETS.fetch(request);
  },
};
