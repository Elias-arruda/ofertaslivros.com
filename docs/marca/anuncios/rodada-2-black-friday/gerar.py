"""Gera os HTML da rodada 2 a partir da tabela abaixo (o render.sh chama este script).
Os títulos vêm das páginas do site no ar em 07/11/2026. Antes de subir ou renovar o anúncio:
    python3 gerar.py --conferir"""
import re
import sys
import urllib.request
from html import escape, unescape
from pathlib import Path

G = {  # cores de nicho do static/style.css (tema escuro): acento e tinta
    "romance": ("#e3526b", "#26070c"), "fantasia": ("#119590", "#041514"),
    "negocios": ("#b87d00", "#1a1000"), "mindset": ("#689215", "#0e1303"),
    "ficcao": ("#9468f5", "#0d0626"), "literatura-brasileira": ("#1f9a5a", "#04140b"),
}
CORAL = "#ff8a8f"
BF = ("Black Friday", "de livros")

# (arquivo, h1, sub, selo, cor do fundo 2, nicho fixo ou None, livros [(título, autor, nicho)], o 6º só nos Stories)
PECAS = [
    ("1-black-friday", "Black Friday de livros sem desconto falso.", "Comparamos cada preço com o nosso histórico.",
     ("30% off", "ou mais"), "#9468f5", None,
     [("Mindset", "Carol S. Dweck", "mindset"), ("É assim que acaba", "Colleen Hoover", "romance"),
      ("Harry Potter e a pedra filosofal", "J. K. Rowling", "fantasia"),
      ("O homem mais rico da Babilônia", "George S. Clason", "negocios"),
      ("O pequeno príncipe", "Antoine de Saint-Exupéry", "ficcao"),
      ("Torto arado", "Itamar Vieira Junior", "literatura-brasileira")]),
    ("2-negocios", "Finanças com desconto de verdade.", "Dinheiro e negócios, comparados com o nosso histórico.",
     BF, G["negocios"][0], "negocios",
     [("Do mil ao milhão", "Thiago Nigro"), ("Pai rico, pai pobre", "Robert T. Kiyosaki"),
      ("O homem mais rico da Babilônia", "George S. Clason"), ("A psicologia financeira", "Morgan Housel"),
      ("De zero a um", "Peter Thiel"), ("O investidor inteligente", "Benjamin Graham")]),
    ("2b-mindset", "Mindset com desconto de verdade.", "Hábitos e psicologia, comparados com o nosso histórico.",
     BF, G["mindset"][0], "mindset",
     [("Mindset", "Carol S. Dweck"), ("Hábitos atômicos", "James Clear"), ("O poder do hábito", "Charles Duhigg"),
      ("Rápido e devagar", "Daniel Kahneman"), ("Em busca de sentido", "Viktor E. Frankl"),
      ("Essencialismo", "Greg McKeown")]),
    ("3-romance", "Colleen Hoover com desconto de verdade.", "E outros romances, comparados com o nosso histórico.",
     BF, G["romance"][0], "romance",
     [("Um dia", "David Nicholls"), ("É assim que acaba", "Colleen Hoover"), ("É assim que começa", "Colleen Hoover"),
      ("Os sete maridos de Evelyn Hugo", "Taylor Jenkins Reid"), ("Como eu era antes de você", "Jojo Moyes"),
      ("Uma segunda chance", "Colleen Hoover")]),
    ("4-fantasia", "Fantasia com desconto de verdade.", "Sagas e clássicos, comparados com o nosso histórico.",
     BF, G["fantasia"][0], "fantasia",
     [("O Hobbit", "J.R.R. Tolkien"), ("Quarta asa", "Rebecca Yarros"),
      ("Harry Potter e a pedra filosofal", "J. K. Rowling"), ("Corte de espinhos e rosas", "Sarah J. Maas"),
      ("Duna", "Frank Herbert"), ("O nome do vento", "Patrick Rothfuss")]),
]
DESTINO = {"1-black-friday": "/black-friday/", "2-negocios": "/negocios/", "2b-mindset": "/mindset/",
           "3-romance": "/romance/", "4-fantasia": "/fantasia/"}
OFFSET = [0, 40, 0, 12, 8, 36]
ROT = [-1.2, .8, -.5, 1.1, -.9, .6]


def lombada(k, livro, nicho):
    titulo, autor = livro[0], livro[1]
    a, ink = G[nicho or livro[2]]
    # Nicho: alterna acento, papel e noite (sem o acento 2: o amarelo de negócios sobre o azul lembraria loja).
    # Geral: cada livro no acento do seu nicho.
    cls, c = [("", a), ("papel", None), ("noite", None)][k % 3] if nicho else ("", a)
    style = f"--a:{a};margin-left:{OFFSET[k]}px;rotate:{ROT[k]}deg" + (f";--c:{c};--ink:{ink}" if c else "")
    return f'    <div class="{"lomb " + cls if cls else "lomb"}" style="{style}"><b>{escape(titulo)}</b><span>{escape(autor)}</span></div>'


def pagina(p, fmt):
    nome, h1, sub, selo, b2, nicho, livros = p
    story = fmt == "stories"
    n = 6 if story else 5
    lomb = "\n".join(lombada(k, l, nicho) for k, l in enumerate(livros[:n]))
    w, h = (1080, 1920) if story else (1080, 1350)
    return f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>{escape(nome)}, {fmt}</title>
<link rel="stylesheet" href="../rodada-1/anuncio.css"><link rel="stylesheet" href="bf.css"></head>
<body>
<main class="peca {'story' if story else 'feed'}" style="--b1:{CORAL};--b2:{b2}">
  <img class="logo" src="../rodada-1/logo-negativo.svg" alt="ofertaslivros.com">
  <h1>{escape(h1)}</h1>
  <p class="sub">{escape(sub)}</p>
  <div class="pilha" aria-label="Livros em oferta">
    <div class="selo"><strong>{escape(selo[0])}</strong><span>{escape(selo[1])}</span></div>
{lomb}
  </div>
</main>
</body>
</html>
""", f"{nome}-{fmt}-{w}x{h}.html"


def conferir():
    """Confere no site no ar se cada título ainda é oferta ativa na página de destino. Sai com 1 se algum saiu.
    Na peça black-friday, cujo selo promete "30% off ou mais", cada título também precisa ter data-off >= 30."""
    falta = 0
    for nome, *_, livros in PECAS:
        url = "https://ofertaslivros.com.br" + DESTINO[nome]
        req = urllib.request.Request(url, headers={"User-Agent": "ofertaslivros-anuncios"})
        page = urllib.request.urlopen(req, timeout=30).read().decode()
        ativos = []
        for tag, t in re.findall(r'(<li class="card"[^>]*data-tipo="oferta">).*?card-title"><a[^>]*>(.*?)</a>', page, re.S):
            off = re.search(r'data-off="(\d+)"', tag)
            ativos.append((unescape(t), int(off.group(1)) if off else 0))
        minimo = 30 if nome == "1-black-friday" else 0
        for livro in livros:
            offs = [off for t, off in ativos if livro[0] in t]
            if not offs:
                status = "SAIU "
            elif max(offs) < minimo:
                status = f"<{minimo}%"
            else:
                status = "ok   "
            falta += status != "ok   "
            print(f"{status} {DESTINO[nome]:16} {livro[0]}" + (f" ({max(offs)}%)" if offs else ""))
    sys.exit(1 if falta else 0)


if "--conferir" in sys.argv:
    conferir()
here = Path(__file__).parent
for p in PECAS:
    for fmt in ("feed", "stories"):
        html, arq = pagina(p, fmt)
        (here / arq).write_text(html)
