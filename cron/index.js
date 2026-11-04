// Dispara workflows no GitHub pelo Cron Trigger. Sem handler fetch: não há rota pública.
// O schedule do GitHub atrasa ou perde execuções; o Cron Trigger da Cloudflare não.
const REPO = "https://api.github.com/repos/Elias-arruda/ofertaslivros.com/actions/workflows";
const POR_CRON = {
  "*/30 * * * *": { workflow: "pipeline.yml", body: { ref: "main" } },
  "0 12 * * *": { workflow: "curator.yml", body: { ref: "main", inputs: { mode: "suggest" } } },
};

export default {
  async scheduled(event, env, ctx) {
    const alvo = POR_CRON[event.cron];
    if (!alvo) throw new Error(`cron sem workflow: ${event.cron}`);
    // Sem token, falha visível (Workers Logs e métricas de erro), em vez de só um log.
    if (!env.GH_DISPATCH_TOKEN) throw new Error(`GH_DISPATCH_TOKEN ausente: ${alvo.workflow} não disparado`);
    const r = await fetch(`${REPO}/${alvo.workflow}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GH_DISPATCH_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ofertaslivros-cron",
      },
      body: JSON.stringify(alvo.body),
    });
    // 204 = disparado. Só o status vai para o log, nunca o token nem o corpo.
    console.log(`dispatch ${alvo.workflow}: ${r.status}`);
    if (r.status !== 204) throw new Error(`dispatch ${alvo.workflow} falhou: ${r.status}`);
  },
};
