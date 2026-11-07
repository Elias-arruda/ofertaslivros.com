#!/usr/bin/env python3
"""Post diário no Instagram pela API oficial da Meta (Instagram API com login do Instagram). Só stdlib.

    python3 instagram_post.py --render <offers.json> <instagram_posts.csv> <dist/ig>   # no deploy
    python3 instagram_post.py <offers.json> <instagram_posts.csv>                       # no instagram.yml

1 oferta por dia, das 10h às 19:59 BRT: o maior desconto entre as ofertas do site (build.resolve + ofertas, sem preço
vencido), sem repetir o livro por 14 dias. A API exige image_url pública, então o deploy gera o JPEG 1080x1350 do
modelo do kit de redes (docs/marca/redes, post 03) em dist/ig/<id>-<preço>-<conferido>.jpg e o publica junto com o
site. Depois do deploy, este script refaz a mesma escolha, confere que o JPEG está no ar e publica
(POST /<user>/media, espera o container, POST /<user>/media_publish).
O nome do arquivo amarra livro, preço e horário: se o offers.json mudou entre o deploy e o post, o arquivo não
existe, nada sai e o próximo deploy tenta de novo.
Estado: instagram_posts.csv do branch instagram-posts (formato do channel_posts.csv do Telegram).
Lê INSTAGRAM_TOKEN e INSTAGRAM_USER_ID do ambiente. O token vai só no header Authorization, nunca na URL nem no log.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import build
import telegram_post as tp

CHANNEL = "ig"
JANELA = (10, 20)   # horas BRT: posta das 10:00 às 19:59
REPOST_DIAS = 14
DIR = "ig"          # dist/ig/ e https://ofertaslivros.com.br/ig/
# ponytail: versão fixa da Graph API; a Meta desliga cada versão ~2 anos depois do lançamento: subir quando avisar.
API = "https://graph.instagram.com/v24.0"
USER_AGENT = "ofertaslivros-instagram/1.0 (+https://ofertaslivros.com.br)"
USER_ID_RE = re.compile(r"\d{1,25}")
CAPA_MAX = 2_000_000


# ---------- escolha ----------
def pick(offers, log, now):
    """A oferta do dia, ou None (fora da janela, já postou hoje ou nenhuma livre)."""
    h = now.astimezone(build.BRT)
    if not JANELA[0] <= h.hour < JANELA[1]:
        return None
    if any(r["at"].astimezone(build.BRT).date() == h.date() for r in log):
        return None
    recentes = {r["offer_id"] for r in log if now - r["at"] < timedelta(days=REPOST_DIAS)}
    cand = [o for o in build.ofertas(offers) if not o["velho"] and o["id"] not in recentes]
    return min(cand, key=lambda o: (-build.discount(o), o["seal"] != "90d", -o["checked_at"].timestamp()),
               default=None)


def nome(o):
    """id (ID_RE: [a-z0-9-]) + preço + horário conferido: nada vindo do JSON livre vira caminho."""
    if not build.ID_RE.fullmatch(o["id"]):
        raise build.Invalid(f"id inválido: {o['id']!r}")
    return f"{o['id']}-{o['price_cents']}-{o['checked_at'].astimezone(build.BRT):%Y%m%d%H%M}.jpg"


def caption(o):
    """Texto puro. Sem @ nem # vindos do dado coletado: virariam menção ou hashtag."""
    limpo = lambda s: re.sub(r"[@#]", "", s)  # noqa: E731
    d = o["checked_at"].astimezone(build.BRT)
    off = build.discount(o)
    lines = ["Menor preço em 90 dias"] if o["seal"] == "90d" else []
    lines += [f"{limpo(o['title'])}, de {limpo(o['author'])}",
              build.brl(o["price_cents"]) + (f" (de {build.brl(o['list_price_cents'])}, -{off}%)" if off else "")
              + f" {build.na(o['store'])}",
              f"Conferido às {d:%H}h{d:%M} de {d:%d/%m}, o preço pode mudar.",
              "Link na bio.",
              "",
              "Link de afiliado: como associado, ganhamos com compras qualificadas. O preço final é o da loja.",
              "",
              f"#livros #ofertasdelivros #{o['genre'].replace('-', '')}"]
    return "\n".join(lines)


# ---------- imagem (modelo aprovado: docs/marca/redes/gerar.py, oferta(), branch do PR #86) ----------
# ponytail: cópia do trecho do kit que o post de oferta usa; quando o kit entrar na main, o gerar.py pode importar daqui.
NIGHT, IVORY, MUTED_DARK, RED_DARK, PAPER, PAPER_EDGE = "#0f1729", "#edf1f5", "#a9b4c8", "#ff8a8f", "#fbfcfd", "#d5dde7"
G = {  # nicho: (acento, acento2, ink), tokens de static/style.css
    "literatura-brasileira": ("#1f9a5a", "#7fd6a4", "#04140b"), "ficcao": ("#9468f5", "#c7b2ff", "#0d0626"),
    "romance": ("#e3526b", "#eda9b5", "#26070c"), "fantasia": ("#119590", "#2cd1cb", "#041514"),
    "suspense": ("#df5d12", "#e7af8f", "#1e0e05"), "mindset": ("#689215", "#97cc2b", "#0e1303"),
    "negocios": ("#b87d00", "#f2c14e", "#1a1000"), "politica": ("#6689a3", "#abbecd", "#05131e"),
    "historia": ("#bd743f", "#dcb496", "#1c0f05"), "manga": ("#e5468f", "#ff9cc6", "#22040f"),
}
ICON = {
    "literatura-brasileira": '<path d="M5 19C5 10 11 5 19 5c0 8-5 14-14 14zM5 19l8-8M9 15h4M11 13V9"/>',
    "ficcao": '<path d="M15 4a7.5 7.5 0 1 0 5.5 11.5A6 6 0 0 1 15 4zM6 3v4M4 5h4"/>',
    "negocios": '<path d="M4 20h16M6 16l4.5-4.5 3 3L19 9M15 9h4v4"/>',
    "romance": '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    "fantasia": '<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2zM19 3v4M17 5h4"/>',
    "suspense": '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"/><circle cx="12" cy="12" r="2.5"/>',
    "mindset": '<path d="M3 20h18M6 20l5-9 3 5 2-3 3 7M11 11V4l5 2-5 2"/>',
    "politica": '<path d="M3 9l9-5 9 5M5 9v9M10 9v9M14 9v9M19 9v9M3 20h18"/>',
    "historia": '<path d="M6 3h12M6 21h12M7 3c0 5 5 6 5 9s-5 4-5 9M17 3c0 5-5 6-5 9s5 4 5 9"/>',
    "manga": '<path d="M4 4h16v12h-9l-4.5 4v-4H4z"/><path d="m13 6.5-3 4h3.5l-2.5 3.5"/>',
}
BR = ("M 272.6 38.3 h 0.01 M 277.3 11.7 V 38.3 M 277.3 30 A 8.3 8.3 0 1 1 293.9 30 A 8.3 8.3 0 1 1 277.3 30 Z "
      "M 299 21.7 V 38.3 M 299 27.5 C 299 23.8 301.8 21.7 305 21.7 C 306 21.7 306.6 21.9 307 22.1")
VB_W = 311.6


def _b64(path):
    return base64.b64encode(path.read_bytes()).decode()


def font_css():
    """Fontes embutidas (data:): o SVG não depende de arquivo nem de rede para renderizar."""
    f = build.STATIC / "fonts"
    ff = lambda fam, arq, st="": (f'@font-face{{font-family:"{fam}";{st}font-weight:100 900;'  # noqa: E731
                                  f'src:url(data:font/woff2;base64,{_b64(f / arq)})}}\n')
    return ("<style>\n" + ff("Fraunces", "fraunces-latin-full-normal.woff2")
            + ff("Fraunces", "fraunces-latin-full-italic.woff2", "font-style:italic;")
            + ff("Outfit", "outfit-latin-wght-normal.woff2")
            + '.f{font-family:Fraunces,Georgia,serif;font-weight:800;font-variation-settings:"SOFT" 100,"WONK" 1;letter-spacing:-.02em}\n'
            '.fi{font-family:Fraunces,Georgia,serif;font-style:italic;font-weight:400;font-variation-settings:"SOFT" 100,"WONK" 1}\n'
            ".s{font-family:Outfit,system-ui,sans-serif}\n.up{text-transform:uppercase;letter-spacing:.06em}\n</style>\n")


def text(x, y, lines, size, cls="s", fill=IVORY, weight=None, lh=1.15, anchor="start", extra=""):
    lines = [lines] if isinstance(lines, str) else lines
    w = f' font-weight="{weight}"' if weight else ""
    spans = "".join(f'<tspan x="{x}" dy="{0 if i == 0 else round(size * lh)}">{escape(s)}</tspan>'
                    for i, s in enumerate(lines))
    return (f'<text class="{cls}" x="{x}" y="{y}" font-size="{size}" fill="{fill}"{w} '
            f'text-anchor="{anchor}"{extra}>{spans}</text>')


def tw(s, size, k=0.56):
    return len(s) * size * k


def pill(x, y, label, size, fill, color, ic=None):
    h, pad = round(size * 2.1), round(size * 0.9)
    iw = round(size * 1.35) if ic else 0
    w = round(tw(label, size, 0.62) + pad * 2 + iw)
    out = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" fill="{fill}"/>'
    if ic:
        s = size * 1.1 / 24
        out += (f'<g transform="translate({x + pad} {y + (h - size * 1.1) / 2}) scale({s:.4f})" fill="none" '
                f'stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">{ic}</g>')
    return out + text(x + pad + iw, y + h / 2 + size * 0.36, label, size, "s up", color, 700)


def livro(x, y, w, accent, ink, inicial, ribbon, img):
    """Capa (real, ou o placeholder do nicho com a inicial) com o miolo e a fita, girada -3°."""
    h, pg = w * 1.5, w * 0.16
    pages = (f'<rect x="{x + pg}" y="{y + h * .03}" width="{w}" height="{h * .95}" rx="{w * .03}" fill="{PAPER}" '
             f'stroke="{PAPER_EDGE}" stroke-width="2"/>'
             + "".join(f'<line x1="{x + w * .2}" y1="{y + h * (.12 + i * .045):.1f}" x2="{x + pg + w * .93}" '
                       f'y2="{y + h * (.12 + i * .045):.1f}" stroke="{PAPER_EDGE}" stroke-width="1.5"/>' for i in range(18)))
    fx = x + pg + w * .74
    fita = f'<path d="M{fx} {y + h * .9} h{w * .1} v{h * .16} l{-w * .05} {-h * .04} l{-w * .05} {h * .04}z" fill="{ribbon}"/>'
    sombra = f'<rect x="{x + 10}" y="{y + 24}" width="{w}" height="{h}" rx="{w * .05}" fill="#000" fill-opacity=".35"/>'
    if img:
        capa = (f'<defs><clipPath id="capa"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{w * .05}"/></clipPath></defs>'
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{w * .05}" fill="{PAPER}"/>'
                f'<image href="{img}" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice" '
                f'clip-path="url(#capa)"/>')
    else:
        capa = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{w * .05}" fill="{accent}"/>'
                + text(x + w * .5, y + h * .6, inicial, round(w * .62), "fi", ink, 800, anchor="middle",
                       extra=' fill-opacity=".72"'))
    return f'<g transform="rotate(-3 {x + w / 2} {y + h / 2})">{fita}{pages}{sombra}{capa}</g>'


def carimbo_conferido(cx, cy, r, color, data, hora):
    return (f'<g transform="rotate(-10 {cx} {cy})">'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{r * .07:.1f}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * .82:.1f}" fill="none" stroke="{color}" stroke-width="{r * .025:.1f}"/>'
            + text(cx, cy - r * .3, "conferido", round(r * .26), "s", color, 600, anchor="middle")
            + text(cx, cy + r * .14, data, round(r * .42), "f", color, anchor="middle")
            + text(cx, cy + r * .48, hora, round(r * .24), "s", color, 600, anchor="middle") + "</g>")


def wordmark(x, y, width):
    src = (build.STATIC / "logo-negativo.svg").read_text(encoding="utf-8")
    inner = re.sub(r"<rect[^>]*/>", "", re.search(r"</title>(.*)</svg>", src, re.S).group(1).strip())
    cor = re.findall(r'stroke="(#[0-9a-fA-F]+)"', inner)[-1]
    inner += f'<path d="{BR}" fill="none" stroke="{cor}" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/>'
    w = width * VB_W / 274.07
    return (f'<svg x="{x}" y="{y}" width="{w:.1f}" height="{w * 32.4 / VB_W:.1f}" viewBox="-3.4 8.8 {VB_W} 32.4">'
            f'{inner}</svg>')


def quebra(titulo):
    """Título em até 2 linhas: 88 px, senão 70 px, senão 70 px cortado com reticências."""
    for size, n in ((88, 20), (70, 25)):
        lines = textwrap.wrap(titulo, n)
        if len(lines) <= 2:
            return lines, size
    return [lines[0], lines[1][:24].rstrip(" ,;:") + "…"], 70


def svg_post(o, capa):
    """O post 03 do kit com os dados da oferta. capa: data: URI ou None (placeholder do nicho)."""
    W, H = 1080, 1350
    acc, acc2, ink = G[o["genre"]]
    d = o["checked_at"].astimezone(build.BRT)
    off = build.discount(o)
    b = (f'<defs><radialGradient id="g" cx="860" cy="260" r="820" gradientUnits="userSpaceOnUse">'
         f'<stop offset="0" stop-color="{acc}" stop-opacity="0.6"/><stop offset="1" stop-color="{acc}" stop-opacity="0"/>'
         f'</radialGradient></defs><rect width="{W}" height="{H}" fill="{NIGHT}"/><rect width="{W}" height="{H}" fill="url(#g)"/>')
    b += "".join(f'<circle cx="1080" cy="0" r="{180 + i * 90}" fill="none" stroke="{IVORY}" stroke-opacity="0.05" '
                 f'stroke-width="2"/>' for i in range(6))
    b += pill(72, 72, build.GENRES[o["genre"]], 26, acc, ink, ICON[o["genre"]])
    selo = ("Menor preço em 90 dias" if o["seal"] == "90d" else
            f"Menor preço desde {o['since']:%d/%m}" if o["seal"] == "since" else None)
    de_y = 1160
    preco_y = de_y - 54
    sy = preco_y - 92 - (70 if selo else 0)
    autor_y = sy - 40
    titulo, ts = quebra(o["title"])
    autor = o["author"] if len(o["author"]) <= 40 else o["author"][:39].rstrip() + "…"
    t1 = autor_y - 62 - round(ts * 1.02) * (len(titulo) - 1)
    lw = min(380, (t1 - 80 - 60 - 150) / 1.62)
    b += livro(545 - lw * 1.16 / 2, 150, lw, acc, ink, o["title"][:1].upper(), acc2, capa)
    b += text(72, t1, titulo, ts, "f", IVORY, lh=1.02)
    b += text(72, autor_y, autor, 42, "fi", MUTED_DARK)
    if selo:
        b += pill(72, sy, selo, 24, RED_DARK, NIGHT)
    b += text(72, preco_y, build.brl(o["price_cents"]), 100, "s", IVORY, 700)
    de = build.brl(o["list_price_cents"]) if off else ""
    if de:
        b += text(72, de_y, de, 36, "s", MUTED_DARK, 500, extra=' text-decoration="line-through"')
    b += text(72 + (tw(de, 36, .55) + 28 if de else 0), de_y, build.na(o["store"]), 36, "s", IVORY, 600)
    if off:
        cx, cy = 545 + lw * .58, 150 + lw * .1
        b += (f'<g transform="rotate(-8 {cx} {cy})"><circle cx="{cx}" cy="{cy}" r="74" fill="{acc}"/>'
              + text(cx, cy + 74 * .2, f"−{off}%", round(74 * .58), "f", ink, anchor="middle") + "</g>")
    b += carimbo_conferido(905, preco_y - 30, 92, RED_DARK, f"{d:%d/%m}", f"às {d:%H}h{d:%M}")
    b += f'<line x1="72" y1="1212" x2="1008" y2="1212" stroke="{IVORY}" stroke-opacity=".14" stroke-width="2"/>'
    b += wordmark(72, 1248, 330)
    b += text(1008, 1268, ["Link de afiliado.", "O preço final é o da loja."], 26, "s", MUTED_DARK, 500, 1.25, "end")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n'
            + font_css() + b + "\n</svg>\n")


MAGIC = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png", b"RIFF": "image/webp"}


def capa(o):
    """A capa que o site mostra, embutida como data: URI. Falhou: None (vai o placeholder do nicho)."""
    url = o.get("image_url")
    try:
        if url and re.fullmatch(r"/capas/[0-9X]{10,13}\.jpg", url):
            raw = (build.STATIC / url[1:]).read_bytes()
        elif url and build.image_url(url, o["id"]):  # só https://http2.mlstatic.com
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            # sem seguir redirect: só o host da allowlist responde (3xx vira HTTPError e cai no placeholder)
            with urllib.request.build_opener(tp._NoRedirect).open(req, timeout=15) as r:
                raw = r.read(CAPA_MAX + 1)
        else:
            return None
    except (OSError, ValueError) as err:
        print(f"ig: capa indisponível, vai o placeholder ({type(err).__name__})")
        return None
    mime = next((m for k, m in MAGIC.items() if raw.startswith(k)), None)
    if not mime or len(raw) > CAPA_MAX:
        print("ig: capa em formato inesperado, vai o placeholder")
        return None
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def chrome():
    exe = os.environ.get("CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
    if not exe:
        raise RuntimeError("Chrome não encontrado (defina CHROME)")
    return exe


def render(o, out_dir):
    """SVG -> JPEG pelo Chrome headless (o runner do Actions já tem o Chrome). Rede bloqueada: tudo está embutido."""
    out = out_dir / nome(o)
    with tempfile.TemporaryDirectory() as tmp:
        svg, jpg = Path(tmp) / "post.svg", Path(tmp) / "post.jpg"  # a extensão .jpg faz o Chrome sair em JPEG
        svg.write_text(svg_post(o, capa(o)), encoding="utf-8")
        subprocess.run([chrome(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                        f"--user-data-dir={tmp}/perfil", "--host-resolver-rules=MAP * ~NOTFOUND",
                        "--force-device-scale-factor=1", "--window-size=1080,1350", f"--screenshot={jpg}",
                        svg.as_uri()], check=True, capture_output=True, timeout=120)
        if not jpg.is_file() or not jpg.read_bytes().startswith(b"\xff\xd8\xff"):
            raise RuntimeError("o Chrome não gerou JPEG")
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(jpg, out)  # só arquivo completo chega ao dist/
    return out


# ---------- publicação ----------
def no_ar(url):
    """O JPEG já está publicado no site?"""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200 and r.headers.get("Content-Type", "").startswith("image/jpeg")
    except (urllib.error.URLError, OSError):
        return False


def graph(token, path, data=None):
    """Chamada à Graph API. Token só no header; o erro mostra código e mensagem da Meta, nunca a URL nem o token."""
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(f"{API}/{path}", data=body, method="POST" if data is not None else "GET",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                          "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e).get("error", {})
        except ValueError:
            err = {}
        msg = str(err.get("message", "")).replace(token, "***")[:200]
        raise RuntimeError(f"Instagram {path.split('/')[-1].split('?')[0]}: {e.code} {err.get('code', '')} {msg}") from None


def publicar(token, user, image_url, text, espera=5, tentativas=12, gravar=lambda: None):
    """Container -> espera FINISHED -> grava o estado -> media_publish. Gravar antes do publish: falha no meio
    perde o dia, mas nunca gera post duplicado (mesma regra do resumo do WhatsApp no telegram_post)."""
    cid = graph(token, f"{user}/media", {"image_url": image_url, "caption": text})["id"]
    if not USER_ID_RE.fullmatch(str(cid)):
        raise RuntimeError("Instagram media: id de container inesperado")
    for _ in range(tentativas):
        st = graph(token, f"{cid}?fields=status_code").get("status_code")
        if st == "FINISHED":
            break
        if st in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram container: {st}")
        time.sleep(espera)
    else:
        raise RuntimeError("Instagram container: não ficou pronto a tempo")
    gravar()
    graph(token, f"{user}/media_publish", {"creation_id": cid})


def carregar(offers_path, now):
    return build.resolve(build.load_books(json.loads(Path(offers_path).read_text(encoding="utf-8"))), now)


def main_render(offers_path, log_path, out_dir, now=None):
    now = now or datetime.now(timezone.utc)
    o = pick(carregar(offers_path, now), tp.read_log(log_path, CHANNEL), now)
    if o is None:
        print("ig: nada a gerar agora")
        return
    print(f"ig: imagem gerada: {render(o, out_dir).name}")


def main(offers_path, log_path, now=None):
    token = os.environ.get("INSTAGRAM_TOKEN", "")
    user = os.environ.get("INSTAGRAM_USER_ID", "")
    if not token or not user:
        print("::warning::ig: INSTAGRAM_TOKEN ou INSTAGRAM_USER_ID ausente; nada postado")
        return
    if not USER_ID_RE.fullmatch(user):
        raise build.Invalid("INSTAGRAM_USER_ID precisa ser o id numérico da conta")
    now = now or datetime.now(timezone.utc)
    o = pick(carregar(offers_path, now), tp.read_log(log_path, CHANNEL), now)
    if o is None:
        print("ig: nada a postar agora")
        return
    url = f"{build.SITE}/{DIR}/{nome(o)}"
    if not no_ar(url):
        print("ig: a imagem desta oferta não está no site (o offers.json mudou depois do deploy); fica para o próximo")
        return
    publicar(token, user, url, caption(o), gravar=lambda: tp.gravar(log_path, now, CHANNEL, o))
    print(f"ig: postado {o['id']}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--render"] and len(a) == 4:
        main_render(a[1], Path(a[2]), Path(a[3]))
    elif len(a) == 2:
        main(a[0], Path(a[1]))
    else:
        raise SystemExit(__doc__)
