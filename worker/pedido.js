// "Pedir um livro": recebe o POST do form e manda o pedido por e-mail (Email Routing do .com.br).
// Sem armazenamento: o pedido só existe no e-mail. Nada do visitante vai para o log.
const ORIGEM = "https://ofertaslivros.com.br";
const DE = "pedidos@ofertaslivros.com.br"; // remetente precisa ser da zona com Email Routing
const OK = "/#pedido-recebido";
const MAX_CORPO = 4096;

const limpa = (v, max) => {
  if (typeof v !== "string") return "";
  const s = v.replace(/[\u0000-\u001f\u007f]+/g, " ").trim(); // sem quebra de linha nem controle
  return s.length > max ? null : s;
};

const b64 = (s) => btoa(String.fromCharCode(...new TextEncoder().encode(s)));

export function mime(para, titulo, autor, agora = new Date()) {
  const corpo = `Novo pedido de livro no site.\n\nNome do livro: ${titulo}\nAutor do livro: ${autor || "(não informado)"}\n`;
  return [
    `From: Ofertas Livros <${DE}>`,
    `To: <${para}>`,
    `Subject: =?UTF-8?B?${b64("Ofertas Livros: novo pedido de livro")}?=`,
    `Date: ${agora.toUTCString()}`,
    `Message-ID: <${crypto.randomUUID()}@ofertaslivros.com.br>`,
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=utf-8",
    "Content-Transfer-Encoding: base64",
    "",
    b64(corpo).replace(/.{76}/g, "$&\r\n"),
  ].join("\r\n");
}

const volta = (caminho) => new Response(null, { status: 303, headers: { Location: caminho } });
const erro = (status, texto) => new Response(texto, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });

// enviar(para, raw): manda o e-mail; injetado para o teste rodar fora do Worker.
export async function pedido(request, env, enviar) {
  if (request.method !== "POST") return erro(405, "Use o formulário do site.");
  if (request.headers.get("Origin") !== ORIGEM) return erro(403, "Origem não permitida.");
  if (!env.PEDIDOS_PARA) return erro(503, "Pedidos indisponíveis no momento.");
  const ip = request.headers.get("CF-Connecting-IP") || "";
  if (env.LIMITE && !(await env.LIMITE.limit({ key: ip })).success)
    return erro(429, "Muitos pedidos seguidos. Tente de novo em um minuto.");

  const corpo = await request.text();
  if (corpo.length > MAX_CORPO) return erro(413, "Pedido grande demais.");
  const f = new URLSearchParams(corpo);
  if (f.get("site")) return volta(OK); // honeypot: finge que deu certo e não envia
  const titulo = limpa(f.get("titulo"), 150);
  const autor = limpa(f.get("autor") ?? "", 100);
  if (!titulo || autor === null) return erro(400, "Preencha o nome do livro (até 150 letras) e o autor (até 100).");

  try {
    await enviar(env.PEDIDOS_PARA, mime(env.PEDIDOS_PARA, titulo, autor));
  } catch (e) {
    console.log(`pedido: envio falhou (${e?.name || "erro"})`); // sem o conteúdo do pedido
    return erro(502, "Não deu para enviar agora. Tente de novo mais tarde.");
  }
  return volta(OK);
}
