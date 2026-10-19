// Dispara o workflow "pipeline" (coleta -> deploy). Sem handler fetch: não há rota pública.
const URL_DISPATCH =
  "https://api.github.com/repos/Elias-arruda/ofertaslivros.com/actions/workflows/pipeline.yml/dispatches";

export default {
  async scheduled(event, env, ctx) {
    if (!env.GH_DISPATCH_TOKEN) {
      console.log("GH_DISPATCH_TOKEN ausente: coleta não disparada");
      return;
    }
    const r = await fetch(URL_DISPATCH, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GH_DISPATCH_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ofertaslivros-cron",
      },
      body: JSON.stringify({ ref: "main" }),
    });
    // 204 = disparado. Só o status vai para o log, nunca o token nem o corpo.
    console.log(`dispatch pipeline: ${r.status}`);
    if (r.status !== 204) throw new Error(`dispatch falhou: ${r.status}`);
  },
};
