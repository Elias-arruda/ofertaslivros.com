"""Gera o kit de redes sociais (SVG editável + PNG) a partir dos tokens da marca.

    python3 docs/marca/redes/gerar.py          # SVG + PNG (precisa do Google Chrome)
    python3 docs/marca/redes/gerar.py --svg    # só os SVG

Cores, logo e fontes vêm de static/ (style.css, logo*.svg, fonts/). Os SVG saem com texto vivo
(<text>), então dá para editar direto no Figma/Inkscape; este script é só o jeito rápido de
refazer tudo igual. O PNG sai do Chrome headless (rsvg/cairosvg/inkscape não estão na máquina).
"""
import itertools
import os
import re
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

# Tokens (static/style.css, tema escuro e claro). Não invente cor aqui: copie do CSS.
NAVY, NIGHT, BG2_DARK = "#1c2b4a", "#0f1729", "#18233b"
IVORY, BG2, MUTED, MUTED_DARK = "#edf1f5", "#f3f6f9", "#4a5670", "#a9b4c8"
RED, RED_DARK, ROSE, PAPER, PAPER_EDGE = "#b3262f", "#ff8a8f", "#f2a3a8", "#fbfcfd", "#d5dde7"
WA, WA_INK, TG = "#25d366", "#06210f", "#2aabee"
G = {  # nicho: (rótulo do build.py, acento, acento2, ink)
    "literatura-brasileira": ("Literatura brasileira", "#1f9a5a", "#7fd6a4", "#04140b"),
    "ficcao": ("Ficção", "#9468f5", "#c7b2ff", "#0d0626"),
    "romance": ("Romance", "#e3526b", "#eda9b5", "#26070c"),
    "fantasia": ("Fantasia e ficção científica", "#119590", "#2cd1cb", "#041514"),
    "suspense": ("Suspense e policial", "#df5d12", "#e7af8f", "#1e0e05"),
    "mindset": ("Mindset e hábitos", "#689215", "#97cc2b", "#0e1303"),
    "negocios": ("Negócios e finanças", "#b87d00", "#f2c14e", "#1a1000"),
    "politica": ("Política e sociedade", "#6689a3", "#abbecd", "#05131e"),
    "historia": ("História e biografias", "#bd743f", "#dcb496", "#1c0f05"),
    "manga": ("Mangá e HQ", "#e5468f", "#ff9cc6", "#22040f"),
}

# Ícones de linha do site (build.py ICONS, grade 24x24). tg/wa são desenhos nossos, não os logos.
ICON = {
    "seta": '<path d="M7 17 17 7M8 7h9v9"/>',
    "busca": '<circle cx="11" cy="11" r="7"/><path d="m16.5 16.5 4.5 4.5"/>',
    "canal": '<path d="M3 10v4h3l7 4V6l-7 4z"/><path d="M16.5 9.5a3.5 3.5 0 0 1 0 5M19 7a7 7 0 0 1 0 10"/>',
    "sino": '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0"/>',
    "tg": '<path d="M21 4 3 11.2l6 2.3L18 7.5l-7 7.3.3 5.2 3-3.6 4.2 3.1z"/>',
    "wa": '<path d="M4 20l1.3-3.9A8.5 8.5 0 1 1 8.2 19z"/><path d="M9.2 8.6c-.3 2.9 3.2 6.4 6.2 6.2l.6-1.7-2-.9-.9.8a5 5 0 0 1-2.3-2.3l.8-.9-.9-2z"/>',
    "tag": '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    "grafico": '<path d="M3 4v16h18M6 9l4 3 3-2 3 4 4-1"/>',
    "carimbo": '<circle cx="12" cy="12" r="10.5"/><circle cx="12" cy="12" r="7.8" stroke-width="1"/>'
               '<path fill="currentColor" stroke="none" transform="translate(12 12.4) scale(.6) translate(-16 -16.6)" '
               'd="M9.6 12.4C11.6 11.5 13.8 11.6 15.3 12.8V21.6C13.8 20.5 11.6 20.4 9.6 21.2ZM22.4 12.4C20.4 11.5 18.2 11.6 16.7 12.8V21.6C18.2 20.5 20.4 20.4 22.4 21.2Z"/>',
    "g-literatura-brasileira": '<path d="M5 19C5 10 11 5 19 5c0 8-5 14-14 14zM5 19l8-8M9 15h4M11 13V9"/>',
    "g-ficcao": '<path d="M15 4a7.5 7.5 0 1 0 5.5 11.5A6 6 0 0 1 15 4zM6 3v4M4 5h4"/>',
    "g-negocios": '<path d="M4 20h16M6 16l4.5-4.5 3 3L19 9M15 9h4v4"/>',
    "g-romance": '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    "g-fantasia": '<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2zM19 3v4M17 5h4"/>',
    "g-suspense": '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"/><circle cx="12" cy="12" r="2.5"/>',
    "g-mindset": '<path d="M3 20h18M6 20l5-9 3 5 2-3 3 7M11 11V4l5 2-5 2"/>',
    "g-politica": '<path d="M3 9l9-5 9 5M5 9v9M10 9v9M14 9v9M19 9v9M3 20h18"/>',
    "g-historia": '<path d="M6 3h12M6 21h12M7 3c0 5 5 6 5 9s-5 4-5 9M17 3c0 5-5 6-5 9s5 4 5 9"/>',
    "g-manga": '<path d="M4 4h16v12h-9l-4.5 4v-4H4z"/><path d="m13 6.5-3 4h3.5l-2.5 3.5"/>',
}
BOOK = ("M9.6 12.4C11.6 11.5 13.8 11.6 15.3 12.8V21.6C13.8 20.5 11.6 20.4 9.6 21.2Z"
        "M22.4 12.4C20.4 11.5 18.2 11.6 16.7 12.8V21.6C18.2 20.5 20.4 20.4 22.4 21.2Z")

AFILIADO = "Link de afiliado. O preço final é o da loja."
# Nomes conferidos no site no ar e nas páginas públicas em 2026-11-07 (ver social.md).
CANAL_NOME = "Só Mais um Livro - Ofertas Livros"
BOT = "@ofertaslivros_bot"


# ---------- contraste (WCAG 2.x) ----------
def _lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


PARES = [  # (uso, frente, fundo, mínimo)
    ("texto sobre noite (posts escuros)", IVORY, NIGHT, 4.5),
    ("texto sobre marinho (perfil, fixada)", IVORY, NAVY, 4.5),
    ("secundário sobre noite", MUTED_DARK, NIGHT, 4.5),
    ("secundário sobre marinho", MUTED_DARK, NAVY, 4.5),
    ("carimbo rosa sobre marinho (perfil)", ROSE, NAVY, 3.0),
    ("carimbo/selo coral sobre noite", RED_DARK, NIGHT, 3.0),
    ("texto do selo sobre coral", NIGHT, RED_DARK, 4.5),
    ("título sobre marfim (posts claros)", NAVY, IVORY, 4.5),
    ("secundário sobre marfim", MUTED, IVORY, 4.5),
    ("carimbo vermelho sobre marfim", RED, IVORY, 3.0),
    ("texto branco sobre vermelho (selo claro)", "#ffffff", RED, 4.5),
    ("texto do botão WhatsApp", WA_INK, WA, 4.5),
    ("ícone Telegram sobre noite", TG, NIGHT, 3.0),
    ("@ do bot em azul Telegram sobre marinho", TG, NAVY, 4.5),
    ("texto do formulário sobre papel (post 10)", NAVY, PAPER, 4.5),
    ("rótulo do formulário sobre papel (post 10)", MUTED, PAPER, 4.5),
] + [(f"{k}: ink sobre acento", v[3], v[1], 4.5) for k, v in G.items()] \
  + [(f"{k}: acento sobre noite", v[1], NIGHT, 3.0) for k, v in G.items()] \
  + [(f"{k}: acento sobre marfim", v[1], IVORY, 3.0) for k, v in G.items()]


def tabela_contraste():
    linhas = ["| Uso | Frente | Fundo | Razão | Mínimo | OK |", "|---|---|---|---|---|---|"]
    ruins = []
    for uso, a, b, m in PARES:
        r = ratio(a, b)
        linhas.append(f"| {uso} | {a} | {b} | {r:.2f}:1 | {m} | {'sim' if r >= m else 'NÃO'} |")
        if r < m:
            ruins.append(uso)
    return "\n".join(linhas), ruins


# ---------- primitivas SVG ----------
def font_css(depth):
    up = "../" * depth
    return (
        "<style>\n"
        f'@font-face{{font-family:"Fraunces";font-weight:100 900;src:url("{up}static/fonts/fraunces-latin-full-normal.woff2")}}\n'
        f'@font-face{{font-family:"Fraunces";font-style:italic;font-weight:100 900;src:url("{up}static/fonts/fraunces-latin-full-italic.woff2")}}\n'
        f'@font-face{{font-family:"Outfit";font-weight:100 900;src:url("{up}static/fonts/outfit-latin-wght-normal.woff2")}}\n'
        '.f{font-family:Fraunces,Charter,Georgia,serif;font-weight:800;font-variation-settings:"SOFT" 100,"WONK" 1;letter-spacing:-.02em}\n'
        '.fi{font-family:Fraunces,Charter,Georgia,serif;font-style:italic;font-weight:400;font-variation-settings:"SOFT" 100,"WONK" 1}\n'
        ".s{font-family:Outfit,system-ui,sans-serif}\n"
        ".up{text-transform:uppercase;letter-spacing:.06em}\n"
        "</style>\n"
    )


def doc(w, h, body, title, depth=4, fonts=True):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{escape(title)}">\n<title>{escape(title)}</title>\n'
            + (font_css(depth) if fonts else "") + body + "\n</svg>\n")


def text(x, y, lines, size, cls="s", fill=IVORY, weight=None, lh=1.15, anchor="start", extra=""):
    if isinstance(lines, str):
        lines = [lines]
    w = f' font-weight="{weight}"' if weight else ""
    spans = "".join(f'<tspan x="{x}" dy="{0 if i == 0 else round(size * lh)}">{escape(l)}</tspan>'
                    for i, l in enumerate(lines))
    return (f'<text class="{cls}" x="{x}" y="{y}" font-size="{size}" fill="{fill}"{w} '
            f'text-anchor="{anchor}"{extra}>{spans}</text>')


def tw(s, size, k=0.56):
    """Largura aproximada de texto em Outfit (para dimensionar pílulas)."""
    return len(s) * size * k


def icon(name, x, y, size, stroke, sw=1.8, fill="none"):
    s = size / 24
    return (f'<g transform="translate({x} {y}) scale({s:.4f})" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" color="{stroke}">{ICON[name]}</g>')


def pill(x, y, label, size, fill, color, ic=None, outline=False, up=True, h=None, ic_color=None):
    h = h or round(size * 2.1)
    pad = round(size * 0.9)
    iw = round(size * 1.35) if ic else 0
    w = round(tw(label, size, 0.62 if up else 0.53) + pad * 2 + iw)
    bg = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" fill="none" stroke="{fill}" stroke-width="3"/>'
          if outline else f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" fill="{fill}"/>')
    ico = icon(ic, x + pad, y + (h - size * 1.1) / 2, size * 1.1, ic_color or color, 2.2) if ic else ""
    t = text(x + pad + iw, y + h / 2 + size * 0.36, label, size, "s up" if up else "s", color, 700)
    return bg + ico + t, w


# ".br" desenhado no traço do ".com" do logo B: ponto, "b" (haste + bojo do "o") e "r" (o mesmo de "ofertas")
BR = ("M 272.6 38.3 h 0.01 M 277.3 11.7 V 38.3 M 277.3 30 A 8.3 8.3 0 1 1 293.9 30 A 8.3 8.3 0 1 1 277.3 30 Z "
      "M 299 21.7 V 38.3 M 299 27.5 C 299 23.8 301.8 21.7 305 21.7 C 306 21.7 306.6 21.9 307 22.1")
VB_W = 311.6  # 274.07 do logo B + o ".br"


def wordmark(x, y, width, negativo=True):
    """O logo B (static/logo*.svg) com ".br" no fim. width é a largura da parte ofertaslivros.com,
    para as letras ficarem do mesmo tamanho de antes."""
    src = (ROOT / "static" / ("logo-negativo.svg" if negativo else "logo.svg")).read_text()
    inner = re.search(r"</title>(.*)</svg>", src, re.S).group(1).strip()
    inner = re.sub(r'<rect[^>]*/>', "", inner)  # o negativo do static já vem sem fundo
    cor = re.findall(r'stroke="(#[0-9a-fA-F]+)"', inner)[-1]  # a cor do ".com"
    inner += (f'<path d="{BR}" fill="none" stroke="{cor}" stroke-width="2.3" stroke-linecap="round" '
              f'stroke-linejoin="round"/>')
    w = width * VB_W / 274.07
    h = w * 32.4 / VB_W
    return (f'<svg x="{x}" y="{y}" width="{w:.1f}" height="{h:.1f}" viewBox="-3.4 8.8 {VB_W} 32.4" '
            f'aria-label="ofertaslivros.com.br">{inner}</svg>')


_MAVI_ID = itertools.count(1)


def mavi(cx, cy, d, halo=IVORY):
    """A Mavi (static/mavi.svg) sem alteração, cortada no círculo como o avatar do bot, com o halo do site."""
    src = (ROOT / "static" / "mavi.svg").read_text()
    inner = re.search(r"</title>(.*)</svg>", src, re.S).group(1).strip()
    n = next(_MAVI_ID)
    return (f'<circle cx="{cx}" cy="{cy}" r="{d / 2 + d * .05:.1f}" fill="{halo}" fill-opacity=".08"/>'
            f'<svg x="{cx - d / 2:.1f}" y="{cy - d / 2:.1f}" width="{d}" height="{d}" viewBox="0 0 640 640" '
            f'aria-label="Mavi"><defs><clipPath id="mavi{n}"><circle cx="320" cy="320" r="320"/></clipPath></defs>'
            f'<g clip-path="url(#mavi{n})">{inner}</g></svg>')


def carimbo(cx, cy, d, color, rot=-10, thin=1.0):
    """O símbolo do carimbo (docs/marca/logos/carimbo-simbolo.svg) numa cor só, com diâmetro d."""
    s = d / 32
    return (f'<g transform="translate({cx - d / 2:.1f} {cy - d / 2:.1f}) scale({s:.4f}) rotate({rot} 16 16)">'
            f'<circle cx="16" cy="16" r="14" fill="none" stroke="{color}" stroke-width="2.4"/>'
            f'<circle cx="16" cy="16" r="10.6" fill="none" stroke="{color}" stroke-width="{thin}"/>'
            f'<path fill="{color}" d="{BOOK}"/></g>')


def carimbo_conferido(cx, cy, r, color, linha1="conferido", linha2="DD/MM", linha3="às HHhMM"):
    """O carimbo "conferido" do topo do site: anel duplo girado, data em serifa."""
    return (f'<g transform="rotate(-10 {cx} {cy})">'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{r * .07:.1f}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r * .82:.1f}" fill="none" stroke="{color}" stroke-width="{r * .025:.1f}"/>'
            + text(cx, cy - r * .3, linha1, round(r * .26), "s", color, 600, anchor="middle")
            + text(cx, cy + r * .14, linha2, round(r * .42), "f", color, anchor="middle")
            + text(cx, cy + r * .48, linha3, round(r * .24), "s", color, 600, anchor="middle")
            + "</g>")


def aneis(cx, cy, color, n=7, r0=120, step=70, op=0.07):
    """Anéis de carimbo concêntricos: a textura dos blocos marinho do site."""
    return "".join(f'<circle cx="{cx}" cy="{cy}" r="{r0 + i * step}" fill="none" stroke="{color}" '
                   f'stroke-opacity="{op}" stroke-width="2"/>' for i in range(n))


def livro(x, y, w, accent, ink, inicial, rot=-3, ribbon=None):
    """O objeto da marca: capa com miolo saindo por trás e fita marcadora na cor do nicho.
    A capa é o placeholder do site (cor do nicho + inicial em itálico): não finge ser a capa real."""
    h = w * 1.5
    ribbon = ribbon or accent
    pg = w * 0.16
    pages = (f'<rect x="{x + pg}" y="{y + h * .03}" width="{w}" height="{h * .95}" rx="{w * .03}" fill="{PAPER}" stroke="{PAPER_EDGE}" stroke-width="2"/>'
             + "".join(f'<line x1="{x + w * .2}" y1="{y + h * (.12 + i * .045):.1f}" x2="{x + pg + w * .93}" y2="{y + h * (.12 + i * .045):.1f}" stroke="{PAPER_EDGE}" stroke-width="1.5"/>'
                       for i in range(18)))
    fita_x = x + pg + w * .74
    fita = (f'<path d="M{fita_x} {y + h * .9} h{w * .1} v{h * .16} l{-w * .05} {-h * .04} l{-w * .05} {h * .04}z" fill="{ribbon}"/>')
    sombra = f'<rect x="{x + 10}" y="{y + 24}" width="{w}" height="{h}" rx="{w * .05}" fill="#000" fill-opacity=".35"/>'
    capa = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{w * .05}" fill="{accent}"/>'
            f'<rect x="{x + w * .045}" y="{y}" width="{w * .02}" height="{h}" fill="#000" fill-opacity=".12"/>'
            + text(x + w * .5, y + h * .6, inicial, round(w * .62), "fi", ink, 800, anchor="middle",
                   extra=' fill-opacity=".72"'))
    cx, cy = x + w / 2, y + h / 2
    return f'<g transform="rotate({rot} {cx} {cy})">{fita}{pages}{sombra}{capa}</g>'


def sticker(cx, cy, r, accent, ink, label):
    return (f'<g transform="rotate(-8 {cx} {cy})"><circle cx="{cx}" cy="{cy}" r="{r}" fill="{accent}"/>'
            + text(cx, cy + r * .2, label, round(r * .58), "f", ink, anchor="middle") + "</g>")


def glow(w, h, color, cx, cy, r, op=0.55, gid="g"):
    return (f'<defs><radialGradient id="{gid}" cx="{cx}" cy="{cy}" r="{r}" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{color}" stop-opacity="{op}"/>'
            f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient></defs>'
            f'<rect width="{w}" height="{h}" fill="{NIGHT}"/><rect width="{w}" height="{h}" fill="url(#{gid})"/>')


def guia(x, y, w, h, label, color="#00b3ff"):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{color}" stroke-width="3" stroke-dasharray="14 10"/>'
            + text(x + 10, y + 34 if y < 40 else y - 10, label, 26, "s", color, 600))


def guias(items):
    """Camada de guias: apague o grupo id="guias" (ou esconda) antes de exportar."""
    return '<g id="guias">' + "".join(items) + "</g>"


# ---------- peças ----------
def perfil(fundo=NAVY, cor=ROSE, size=720, fonts=False):
    """Foto de perfil: o carimbo, girado -10°, com 60% do lado (cabe no corte circular com folga)."""
    return doc(size, size, f'<rect width="{size}" height="{size}" fill="{fundo}"/>'
               + carimbo(size / 2, size / 2, size * .6, cor, thin=1.3), "Ofertas Livros", fonts=fonts)


def destaque(nome, ic, cor_anel):
    W, H = 1080, 1920
    body = (f'<rect width="{W}" height="{H}" fill="{NAVY}"/>'
            f'<circle cx="540" cy="960" r="300" fill="none" stroke="{cor_anel}" stroke-width="22"/>'
            + icon(ic, 540 - 190, 960 - 190, 380, IVORY, 1.7))
    return doc(W, H, body, f"Destaque: {nome}", fonts=False)


def oferta(d, template=False, depth=4):
    """Post de feed 1080x1350 de oferta (escuro, glow do nicho, como o hero do site)."""
    W, H = 1080, 1350
    nome, acc, acc2, ink = G[d["g"]]
    b = glow(W, H, acc, 860, 260, 820, .6)
    b += aneis(1080, 0, IVORY, 6, 180, 90, .05)
    p, pw = pill(72, 72, nome, 26, acc, ink, "g-" + d["g"])
    b += p
    # montado de baixo para cima: a linha da loja fica fixa e o livro ocupa o que sobra
    de_y = 1124 if d.get("ilustrativo") or template else 1160
    preco_y = de_y - 54
    topo_preco = preco_y - 92
    sy = topo_preco - 70 if d.get("selo") else topo_preco
    autor_y = sy - 40
    n = len(d["titulo"])
    t1 = autor_y - 62 - 90 * (n - 1)
    lw = min(380, (t1 - 80 - 60 - 150) / 1.62)
    b += livro(545 - lw * 1.16 / 2, 150, lw, acc, ink, d["inicial"], ribbon=acc2)
    b += text(72, t1, d["titulo"], 88, "f", IVORY, lh=1.02)
    b += text(72, autor_y, d["autor"], 42, "fi", MUTED_DARK)
    if d.get("selo"):
        s, _ = pill(72, sy, "Menor preço em 90 dias", 24, RED_DARK, NIGHT)
        b += f'<g id="selo">{s}</g>'
    b += text(72, preco_y, d["preco"], 100, "s", IVORY, 700)
    b += text(72, de_y, d["de"], 36, "s", MUTED_DARK, 500, extra=' text-decoration="line-through"')
    b += text(72 + tw(d["de"], 36, .55) + 28, de_y, d["loja"], 36, "s", IVORY, 600)
    b += sticker(545 + lw * .58, 150 + lw * .1, 74, acc, ink, d["desconto"])
    b += '<g id="carimbo-conferido">' + carimbo_conferido(905, preco_y - 30, 92, RED_DARK, linha2=d["data"], linha3=d["hora"]) + "</g>"
    if d.get("ilustrativo"):
        b += '<g id="ilustrativo">' + text(72, de_y + 52, "Preço ilustrativo: troque pelo conferido no dia", 28, "s", RED_DARK, 600) + "</g>"
    b += f'<line x1="72" y1="1212" x2="1008" y2="1212" stroke="{IVORY}" stroke-opacity=".14" stroke-width="2"/>'
    b += wordmark(72, 1248, 330)
    b += text(1008, 1268, ["Link de afiliado.", "O preço final é o da loja."], 26, "s", MUTED_DARK, 500, 1.25, "end")
    if template:
        b += guias([
            guia(34, 0, 1012, 1350, "corte 3:4 da grade do perfil (1012 px)", "#ffcc00"),
            guia(72, 72, 936, 1206, "margem 72 px"),
            guia(300, 140, 480, t1 - 220, "capa: placeholder do nicho (troque a inicial)"),
            guia(66, t1 - 80, 760, autor_y - t1 + 100, "título (Fraunces 800, até 2 linhas) e autor"),
            guia(66, sy - 10, 760, de_y - sy + 30, "selo só com histórico real; preço de/por; loja"),
        ])
    return doc(W, H, b, f"Oferta: {' '.join(d['titulo'])}", depth=depth)


def claro(titulo, corpo, extra="", depth=4, tsize=104, selo=True):
    """Post informativo claro (marfim), título em Fraunces e corpo em Outfit."""
    W, H = 1080, 1350
    b = f'<rect width="{W}" height="{H}" fill="{IVORY}"/>'
    if selo:
        b += carimbo(966, 132, 120, RED)
    b += text(72, 250, titulo, tsize, "f", NAVY, lh=1.0)
    ty = 250 + round(tsize * 1.0) * (len(titulo) - 1) + 90
    b += text(72, ty, corpo, 40, "s", MUTED, 400, 1.4)
    b += extra
    b += f'<line x1="72" y1="1212" x2="1008" y2="1212" stroke="{NAVY}" stroke-opacity=".14" stroke-width="2"/>'
    b += wordmark(72, 1248, 330, negativo=False)
    return doc(W, H, b, " ".join(titulo), depth=depth)


def escuro(titulo, corpo, extra="", depth=4, tsize=110, ty0=520):
    W, H = 1080, 1350
    b = f'<rect width="{W}" height="{H}" fill="{NAVY}"/>' + aneis(0, 1350, IVORY, 8, 160, 90, .06)
    b += text(72, ty0, titulo, tsize, "f", IVORY, lh=1.0)
    ty = ty0 + round(tsize) * (len(titulo) - 1) + 96
    b += text(72, ty, corpo, 40, "s", MUTED_DARK, 400, 1.4)
    b += extra
    b += f'<line x1="72" y1="1212" x2="1008" y2="1212" stroke="{IVORY}" stroke-opacity=".14" stroke-width="2"/>'
    b += wordmark(72, 1248, 330)
    return doc(W, H, b, " ".join(titulo), depth=depth)


def grafico(x, y, w, h):
    """Mini histórico de 90 dias (ilustrativo), como o gráfico do site: ponto vermelho no preço de hoje."""
    pts = [0, .25, .2, .35, .3, .15, .3, .45, .4, .55, .5, .62, .58, .7, 1.0]
    n = len(pts) - 1
    xy = [(x + w * i / n, y + h * (.1 + .8 * v)) for i, v in enumerate(pts)]
    path = "M" + " L".join(f"{a:.0f} {b:.0f}" for a, b in xy)
    lx, ly = xy[-1]
    g = (f'<rect x="{x - 36}" y="{y - 70}" width="{w + 72}" height="{h + 190}" rx="28" fill="{BG2}" stroke="{NAVY}" stroke-opacity=".13" stroke-width="2"/>'
         + text(x, y - 22, "90 dias", 28, "s", MUTED, 600)
         + text(x + w, y - 22, "gráfico ilustrativo", 26, "s", MUTED, 500, anchor="end")
         + f'<line x1="{x}" y1="{ly:.0f}" x2="{x + w}" y2="{ly:.0f}" stroke="{RED}" stroke-width="2" stroke-dasharray="8 8"/>'
         + f'<path d="{path}" fill="none" stroke="{NAVY}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>'
         + f'<circle cx="{lx:.0f}" cy="{ly:.0f}" r="15" fill="{RED}" stroke="{BG2}" stroke-width="5"/>'
         + text(lx - 26, ly + 52, "hoje", 28, "s", RED, 700, anchor="end")
         + text(x, y + h + 80, "Hoje é o menor preço dos últimos 90 dias.", 32, "s", NAVY, 600))
    return g


def lista_check(x, y, itens, cor_carimbo, cor_texto, gap=118):
    out = ""
    for i, t in enumerate(itens):
        yy = y + i * gap
        out += carimbo(x + 30, yy - 12, 64, cor_carimbo, thin=1.4)
        out += text(x + 92, yy, t, 40, "s", cor_texto, 600)
    return out


def chips(x, y, w_max, chave_lista, size=30):
    out, cx, cy = "", x, y
    for k in chave_lista:
        nome, acc, _, ink = G[k]
        h = round(size * 2.3)
        w = round(tw(nome, size, .55) + size * 1.8 + size * 1.4)
        if cx + w > x + w_max:
            cx, cy = x, cy + h + 22
        out += f'<rect x="{cx}" y="{cy}" width="{w}" height="{h}" rx="{h / 2}" fill="{acc}"/>'
        out += icon("g-" + k, cx + size * .8, cy + (h - size * 1.2) / 2, size * 1.2, ink, 2.2)
        out += text(cx + size * 2.4, cy + h / 2 + size * .36, nome, size, "s", ink, 600)
        cx += w + 18
    return out


def botoes_canais(x, y, size=34):
    """Os dois botões do site: WhatsApp verde cheio, Telegram em contorno (ícones desenhados por nós)."""
    h = round(size * 2.6)
    p1, w1 = pill(x, y, "Canal no WhatsApp", size, WA, WA_INK, "wa", up=False, h=h)
    p2, w2 = pill(x, y + h + 24, "Canal no Telegram", size, IVORY, IVORY, "tg", outline=True, up=False, h=h,
                  ic_color=TG)
    return p1 + p2


def linha_bot(x, y, d=120, cor=IVORY, cor2=TG, pergunta="Quer um livro só?"):
    """A Mavi pequena + o @ do bot: a ponte dos canais para o alerta."""
    return (mavi(x + d / 2, y, d)
            + text(x + d + 32, y - 8, pergunta, 40, "s", cor, 600)
            + text(x + d + 32, y + 44, f"A Mavi avisa: {BOT}", 36, "s", cor2, 600))


def form_pedido(x, y, w):
    """Desenho do form "Pedir um livro" do site (build.py fab), com os campos vazios: não é print."""
    h = 520
    campo = lambda yy: (f'<rect x="{x + 48}" y="{yy}" width="{w - 96}" height="76" rx="14" fill="{IVORY}" '
                        f'stroke="{NAVY}" stroke-opacity=".25" stroke-width="2"/>')
    b = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="28" fill="{PAPER}" stroke="{NAVY}" '
         f'stroke-opacity=".13" stroke-width="2"/>'
         + text(x + 48, y + 84, "Qual livro você quer ver aqui?", 40, "f", NAVY)
         + text(x + 48, y + 150, "Nome do livro", 30, "s", NAVY, 600) + campo(y + 168)
         + f'<line x1="{x + 72}" y1="{y + 188}" x2="{x + 72}" y2="{y + 224}" stroke="{NAVY}" stroke-width="3"/>'
         + text(x + 48, y + 300, "Autor do livro", 30, "s", NAVY, 600)
         + text(x + 48 + tw("Autor do livro", 30, .5) + 4, y + 300, "(opcional)", 30, "s", MUTED, 500)
         + campo(y + 318))
    btn, _ = pill(x + 48, y + 428, "Enviar pedido", 30, NAVY, IVORY, up=False, h=68)
    fab, fw = pill(0, 0, "Pedir um livro", 30, NAVY, IVORY, "busca", up=False, h=72)
    return b + btn + f'<g transform="translate({x + w - fw - 24} {y - 36})">{fab}</g>'


def passos(x, y, itens, gap=150):
    """Lista numerada: só para sequência real (os passos do alerta, os mesmos do site)."""
    return "".join(text(x, y + i * gap, str(i + 1), 96, "fi", RED, 800)
                   + text(x + 92, y + i * gap - 8, t, 40, "s", NAVY, 600) for i, t in enumerate(itens))


def story(fundo, titulo, corpo, extra="", template=False, depth=4, ty0=760, tsize=124, cor=None):
    W, H = 1080, 1920
    escuro_ = fundo != IVORY
    tc = IVORY if escuro_ else NAVY
    mc = MUTED_DARK if escuro_ else MUTED
    b = f'<rect width="{W}" height="{H}" fill="{fundo}"/>'
    if escuro_:
        b += aneis(1080, 1920, IVORY, 9, 200, 100, .06)
    b += wordmark(72, 270, 420, negativo=escuro_)
    b += text(72, ty0, titulo, tsize, "f", cor or tc, lh=1.0)
    ty = ty0 + tsize * (len(titulo) - 1) + 100
    b += text(72, ty, corpo, 44, "s", mc, 400, 1.4)
    b += extra
    b += text(72, 1430, "ofertaslivros.com.br", 36, "s", tc, 600)
    if template:
        b += guias([
            guia(0, 0, 1080, 250, "topo: barra do app (250 px)", "#ff3b6b"),
            guia(0, 1440, 1080, 480, "base: legenda e botões (480 px, TikTok)", "#ff3b6b"),
            guia(940, 250, 140, 1190, "TikTok: botões", "#ff3b6b"),
            guia(64, 250, 876, 1190, "zona segura 876 x 1190"),
        ])
    return doc(W, H, b, " ".join(titulo), depth=depth)


def canal_1280(d=None, template=False, depth=4):
    """Imagem de post para Telegram/WhatsApp, 1280x720 (16:9, a prévia não corta)."""
    W, H = 1280, 720
    if d is None:  # mensagem fixada
        b = f'<rect width="{W}" height="{H}" fill="{NAVY}"/>' + aneis(1280, 720, IVORY, 7, 140, 80, .06)
        b += wordmark(80, 80, 460)
        b += text(80, 290, ["Ofertas de livros", "conferidas na loja."], 76, "f", IVORY, lh=1.02)
        b += text(80, 460, ["Poucas por dia, com o preço e o horário da conferência.",
                            f"Quer um livro só? A Mavi avisa: {BOT}"], 32, "s", MUTED_DARK, 400, 1.45)
        b += text(80, 640, "Link de afiliado: ganhamos com compras qualificadas. O preço final é o da loja.",
                  26, "s", IVORY, 500)
        b += carimbo(1090, 250, 250, ROSE)
        return doc(W, H, b, "Mensagem fixada do canal", depth=depth)
    nome, acc, acc2, ink = G[d["g"]]
    b = glow(W, H, acc, 250, 300, 620, .6)
    b += livro(120, 90, 300, acc, ink, d["inicial"], ribbon=acc2)
    p, _ = pill(560, 80, nome, 24, acc, ink, "g-" + d["g"])
    b += p
    b += text(560, 230, d["titulo"], 68, "f", IVORY, lh=1.02)
    ny = 230 + 70 * (len(d["titulo"]) - 1)
    b += text(560, ny + 52, d["autor"], 34, "fi", MUTED_DARK)
    py = ny + 90
    if d.get("selo"):
        s, _ = pill(560, py, "Menor preço em 90 dias", 22, RED_DARK, NIGHT)
        b += s
        py += 64
    b += text(560, py + 80, d["preco"], 84, "s", IVORY, 700)
    b += text(560, py + 128, f'{d["de"]}', 30, "s", MUTED_DARK, 500, extra=' text-decoration="line-through"')
    b += text(560 + tw(d["de"], 30, .55) + 24, py + 128, d["loja"], 30, "s", IVORY, 600)
    b += sticker(1150, 140, 62, acc, ink, d["desconto"])
    b += wordmark(110, 636, 260)
    b += text(1200, 660, AFILIADO, 22, "s", MUTED_DARK, 500, anchor="end")
    if template:
        b += guias([guia(48, 48, 1184, 624, "margem 48 px"),
                    guia(90, 70, 420, 560, "capa: placeholder do nicho"),
                    guia(548, 180, 680, 380, "título, autor, selo (só com histórico real), preço, loja")])
    return doc(W, H, b, "Post do canal", depth=depth)


def carrossel(capa, template=False, depth=4, n="1/5"):
    W, H = 1080, 1350
    if capa:
        b = f'<rect width="{W}" height="{H}" fill="{NAVY}"/>' + aneis(1080, 1350, IVORY, 8, 160, 90, .06)
        b += text(1008, 112, n, 30, "s", MUTED_DARK, 600, anchor="end")
        b += text(72, 560, ["Título do", "carrossel em", "até 3 linhas"], 112, "f", IVORY, lh=1.0)
        b += text(72, 900, ["Subtítulo curto em Outfit, até duas", "linhas de 40 px."], 40, "s", MUTED_DARK, 400, 1.4)
        b += livro(760, 980, 120, G["fantasia"][1], G["fantasia"][3], "A", rot=8, ribbon=G["fantasia"][2])
        b += wordmark(72, 1248, 330)
        g = [guia(34, 0, 1012, 1350, "corte 3:4 da grade", "#ffcc00"), guia(66, 440, 900, 520, "título + subtítulo")]
    else:
        b = f'<rect width="{W}" height="{H}" fill="{IVORY}"/>'
        b += text(1008, 112, "2/5", 30, "s", MUTED, 600, anchor="end")
        b += text(72, 300, "2", 220, "fi", RED, 800)
        b += text(72, 520, ["Título do passo", "em até 2 linhas"], 88, "f", NAVY, lh=1.02)
        b += text(72, 720, ["Texto do passo em Outfit 40 px, com até", "seis linhas de cerca de 38 caracteres.",
                            "Uma ideia por página."], 40, "s", MUTED, 400, 1.4)
        b += wordmark(72, 1248, 330, negativo=False)
        g = [guia(34, 0, 1012, 1350, "corte 3:4 da grade", "#ffcc00"),
             guia(66, 120, 300, 220, "número do passo (só em sequência real)"),
             guia(66, 420, 936, 520, "título + texto")]
    if template:
        b += guias(g)
    return doc(W, H, b, "Carrossel " + ("capa" if capa else "página"), depth=depth)


# ---------- conteúdo ----------
OFERTAS = {  # livros reais do collector/catalog.json; preço sempre placeholder/ilustrativo
    "torto": dict(g="literatura-brasileira", titulo=["Torto arado"], autor="Itamar Vieira Junior", inicial="T",
                  preco="R$ 00,00", de="R$ 00,00", loja="na Amazon", desconto="−00%", data="DD/MM",
                  hora="às HHhMM", ilustrativo=True),
    "onepiece": dict(g="manga", titulo=["One Piece", "vol. 1"], autor="Eiichiro Oda", inicial="O",
                     preco="R$ 00,00", de="R$ 00,00", loja="na Amazon", desconto="−00%", data="DD/MM",
                     hora="às HHhMM", ilustrativo=True),
    "hobbit": dict(g="fantasia", titulo=["O Hobbit"], autor="J.R.R. Tolkien", inicial="H", selo=True,
                   preco="R$ 00,00", de="R$ 00,00", loja="no Mercado Livre", desconto="−00%", data="DD/MM",
                   hora="às HHhMM", ilustrativo=True),
}
TEMPLATE_OFERTA = dict(g="fantasia", titulo=["Título do livro", "em até 2 linhas"], autor="Nome do autor",
                       inicial="A", selo=True, preco="R$ 00,00", de="R$ 00,00", loja="na loja", desconto="−00%",
                       data="DD/MM", hora="às HHhMM")


def posts():
    """Os 12 posts na ordem de publicação (4 linhas de 3). O 1 fica no canto inferior direito, o 12 no superior esquerdo."""
    nichos = ["manga", "romance", "fantasia", "suspense", "literatura-brasileira", "ficcao", "mindset",
              "negocios", "historia", "politica"]
    return [
        ("01-o-que-e", escuro(["Livros que", "baixaram de", "verdade."],
                              ["Conferimos o preço de cada livro na loja", "e comparamos com o histórico.",
                               "Se não baixou, não entra."],
                              extra=carimbo(860, 230, 260, ROSE), ty0=470, tsize=120)),
        ("02-historico", claro(["Desconto de", "verdade se vê", "no histórico."],
                               ["Guardamos o preço de cada livro todo dia.", "Desconto sobre preço inflado não conta."],
                               extra=grafico(108, 820, 864, 190), tsize=100)),
        ("03-oferta-torto-arado", oferta(OFERTAS["torto"])),
        ("04-curadoria", claro(["Curadoria,", "não despejo."],
                               ["Poucas ofertas por dia. Cada uma passa", "por três conferências:"],
                               extra=lista_check(72, 760, ["O preço foi visto na loja, com horário.",
                                                           "Ele é comparado com os últimos 90 dias.",
                                                           "Oferta vencida sai da lista."], RED, NAVY))),
        ("05-onde-seguir", escuro(["As ofertas", "no seu celular."],
                                  ["Os dois canais se chamam", CANAL_NOME + "."],
                                  extra=botoes_canais(72, 640)
                                  + text(540, 694, "um resumo por dia", 30, "s", MUTED_DARK, 500)
                                  + text(540, 806, "até 8 por dia, das 8h às 22h", 30, "s", MUTED_DARK, 500)
                                  + f'<line x1="72" y1="930" x2="1008" y2="930" stroke="{IVORY}" stroke-opacity=".14" stroke-width="2"/>'
                                  + linha_bot(72, 1050)
                                  + text(72, 1170, "Grátis, só de leitura e sem cadastro. Os links estão na bio.",
                                         30, "s", MUTED_DARK, 400),
                                  ty0=300)),
        ("06-nichos", claro(["Do mangá", "ao Machado."],
                            ["Uma página por nicho no site. Siga o seu."],
                            extra=chips(72, 620, 936, nichos))),
        ("07-oferta-one-piece", oferta(OFERTAS["onepiece"])),
        ("08-transparencia", claro(["Como a gente", "ganha."],
                                   ["Os links são de afiliado. Como associados", "da Amazon e afiliados do Mercado Livre,",
                                    "ganhamos com compras qualificadas.", "", "O preço final é o da loja: mostramos o",
                                    "horário em que conferimos, e ele pode", "mudar depois disso."])),
        ("09-oferta-o-hobbit", oferta(OFERTAS["hobbit"])),
        ("10-pedir-um-livro", claro(["Não achou", "o seu livro?"],
                                    ["Toque em Pedir um livro no site e escreva o",
                                     "nome e o autor. O pedido vai para a curadoria",
                                     "e não leva nenhum dado seu."],
                                    extra=form_pedido(72, 650, 936))),
        ("11-mavi-alerta", escuro(["Escolha o livro.", "A Mavi avisa."],
                                  ["Quando o livro entrar em oferta, ela manda",
                                   "uma mensagem no Telegram. Vale para um",
                                   "autor também. Grátis, das 8h às 22h."],
                                  extra=mavi(770, 330, 400)
                                  + pill(72, 300, "Me avise se baixar", 30, IVORY, IVORY, "sino", outline=True,
                                         up=False, h=80)[0]
                                  + text(72, 1150, BOT, 44, "s", TG, 700),
                                  ty0=760, tsize=100)),
        ("12-alerta-passos", claro(["Alerta em", "três passos."], [], selo=False,
                                   extra=mavi(930, 150, 170, NAVY)
                                   + passos(72, 620, ["No site, toque no sino do livro.",
                                                      "No Telegram, toque em Iniciar.",
                                                      "Quando entrar em oferta, a Mavi avisa."])
                                   + text(72, 1040, ["Também dá para mandar o título ou o autor",
                                                    f"direto ao {BOT}. Em /lista você vê",
                                                    "e tira livros; /parar apaga tudo."], 36, "s", MUTED, 400, 1.4))),
    ]


def stories():
    W = 1080
    return [
        ("s1-chegamos", story(NAVY, ["Chegou o", "Ofertas Livros."],
                              ["Livros que baixaram de preço de verdade,", "conferidos na loja e no histórico."],
                              extra=carimbo(540, 1120, 300, ROSE), ty0=640)),
        ("s2-capa-historico", story(IVORY, ["Esse desconto", "é de verdade?"],
                                    ["Em 30 segundos: como o histórico de", "90 dias mostra a resposta."],
                                    extra=carimbo(880, 560, 200, RED), ty0=720, tsize=120)),
        ("s3-canais", story(NAVY, ["Siga o canal."],
                            [CANAL_NOME + ",", "no Telegram ou no WhatsApp. Sem cadastro."],
                            extra=botoes_canais(72, 1000, 38), ty0=720)),
        ("s4-mavi", story(NAVY, ["Me avise", "se baixar."],
                          ["Toque no sino de um livro no site.", "Quando ele entrar em oferta, a Mavi",
                           f"avisa no Telegram: {BOT}."],
                          extra=mavi(540, 590, 420), ty0=960, tsize=110)),
    ]


# ---------- saída ----------
def write(rel, svg):
    p = HERE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(svg)
    return p


def png(svg_path, out, w, h):
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                    "--force-device-scale-factor=1", f"--window-size={w},{h}", f"--screenshot={out}",
                    svg_path.as_uri()], check=True, capture_output=True, timeout=60)


def main(only_svg=False):
    jobs = []  # (svg, png, w, h)

    # 1. perfil: mestre em 720 e cópias com width/height trocados (mesmo viewBox) para cada tamanho
    mestre = write("perfil/perfil.svg", perfil())
    write("perfil/perfil-claro.svg", perfil(IVORY, RED))
    for nome, s in [("instagram-320", 320), ("tiktok-200", 200), ("tiktok-720", 720),
                    ("telegram-640", 640), ("whatsapp-640", 640)]:
        tmp = write(f"perfil/.tmp-{s}.svg", mestre.read_text().replace('width="720" height="720"',
                                                                         f'width="{s}" height="{s}"', 1))
        jobs.append((tmp, HERE / f"perfil/{nome}.png", s, s))
    claro_ = HERE / "perfil/perfil-claro.svg"
    tmp = write("perfil/.tmp-claro.svg", claro_.read_text().replace('width="720" height="720"', 'width="640" height="640"', 1))
    jobs.append((tmp, HERE / "perfil/perfil-claro-640.png", 640, 640))

    # 2. destaques do Instagram
    for nome, ic, cor in [("ofertas", "tag", RED_DARK), ("manga", "g-manga", G["manga"][1]),
                          ("curadoria", "carimbo", ROSE), ("como-funciona", "grafico", RED_DARK),
                          ("canais", "canal", WA), ("alerta", "sino", TG), ("pedir", "busca", ROSE)]:
        p = write(f"destaques/{nome}.svg", destaque(nome, ic, cor))
        jobs.append((p, p.with_suffix(".png"), 1080, 1920))
    p = write("canal/telegram-fixada.svg", canal_1280(None, depth=4))
    jobs.append((p, p.with_suffix(".png"), 1280, 720))

    # 3. templates (com a camada de guias ligada)
    for nome, svg, w, h in [
        ("feed-oferta", oferta(TEMPLATE_OFERTA, template=True), 1080, 1350),
        ("carrossel-capa", carrossel(True, template=True), 1080, 1350),
        ("carrossel-pagina", carrossel(False, template=True), 1080, 1350),
        ("story-reels-tiktok", story(NAVY, ["Título em até", "três linhas", "curtas."],
                                     ["Texto de apoio em Outfit 44 px,", "até três linhas."], template=True),
         1080, 1920),
        ("canal-1280x720", canal_1280(TEMPLATE_OFERTA | {"titulo": ["Título do livro"]}, template=True), 1280, 720),
    ]:
        p = write(f"templates/{nome}.svg", svg)
        jobs.append((p, p.with_suffix(".png"), w, h))

    # 4. primeiras postagens
    for nome, svg in posts():
        p = write(f"posts/{nome}.svg", svg)
        jobs.append((p, p.with_suffix(".png"), 1080, 1350))
    for nome, svg in stories():
        p = write(f"stories/{nome}.svg", svg)
        jobs.append((p, p.with_suffix(".png"), 1080, 1920))

    tabela, ruins = tabela_contraste()
    if ruins:
        raise SystemExit("contraste abaixo do mínimo: " + ", ".join(ruins))
    if "--tabela" in sys.argv:
        print(tabela)
    if only_svg:
        return
    for svg, out, w, h in jobs:
        png(svg, out, w, h)
    for t in HERE.glob("perfil/.tmp-*.svg"):
        t.unlink()

    # grade como aparece no perfil (o post mais novo no canto superior esquerdo): as 9 mais novas e a completa
    ordem = [n for n, _ in posts()][::-1]
    for nome, lista in [("grade-3x3", ordem[:9]), ("grade-completa", ordem)]:
        cells = "".join(f'<img src="{(HERE / "posts" / (n + ".png")).as_uri()}">' for n in lista)
        html = write("posts/.grade.html", "<style>body{margin:0;background:#fff;display:grid;grid-template-columns:"
                     "repeat(3,360px);gap:4px}img{width:360px;height:450px;display:block}</style>" + cells)
        linhas = len(lista) // 3
        png(html, HERE / f"posts/{nome}.png", 1088, linhas * 454 - 4)
        html.unlink()


if __name__ == "__main__":
    main(only_svg="--svg" in sys.argv)
