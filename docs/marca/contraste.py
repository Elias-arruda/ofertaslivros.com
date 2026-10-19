#!/usr/bin/env python3
"""Confere o contraste WCAG 2.x dos tokens do static/style.css (só stdlib).

    python3 docs/marca/contraste.py          # tabela em Markdown; sai com erro se algum par falhar

Lê do CSS, então não há segunda fonte de verdade: o bloco `:root {` (tema claro) e o
`:root[data-theme="dark"] {` (tema escuro). Pares conferidos:
- texto do acento (--g-<nicho>-ink) sobre o acento: >= 4,5 (texto);
- acento sobre --bg e --bg2, nos dois temas: >= 3 (forma de UI, WCAG 1.4.11);
- o mesmo para o acento padrão (--coral / --coral-ink) de cada tema;
- texto e texto secundário sobre --bg e --bg2; marfim e rosado sobre o marinho dos blocos.
"""
import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "static" / "style.css"


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + .05) / (lb + .05)


def block(css, head):
    i = css.index(head)
    return css[i:css.index("}", i)]


def tokens(text):
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})\b", text))


def pairs(css):
    light = tokens(block(css, ":root {"))
    dark = {**light, **tokens(block(css, ':root[data-theme="dark"] {'))}
    genres = sorted(k[2:] for k in light if k.startswith("g-") and f"{k}-ink" in light)
    out = []
    for theme, t in (("claro", light), ("escuro", dark)):
        accents = [(g, t[f"g-{g}"], t[f"g-{g}-ink"]) for g in genres] + [("padrão", t["coral"], t["coral-ink"])]
        for name, acc, ink in accents:
            if theme == "claro" or name == "padrão":  # o ink sobre o acento não muda com o tema
                out.append((theme, f"{name}: texto sobre o acento", ink, acc, 4.5))
            out += [(theme, f"{name}: acento sobre {bg}", acc, t[bg], 3.0) for bg in ("bg", "bg2")]
        out += [(theme, f"{fg} sobre {bg}", t[fg], t[bg], 4.5) for fg in ("text", "muted") for bg in ("bg", "bg2")]
    out += [("blocos", "marfim sobre o marinho", light["ivory"], light["wine"], 4.5),
            ("blocos", "rosado sobre o marinho", light["rose"], light["wine"], 4.5)]
    return out


def selftest():
    assert round(ratio("#000000", "#ffffff"), 2) == 21.0
    assert round(ratio("#777777", "#ffffff"), 2) == 4.48


def main():
    selftest()
    rows = pairs(CSS.read_text(encoding="utf-8"))
    print("| Tema | Par | Cores | Razão | Mínimo | OK |\n|---|---|---|---|---|---|")
    bad = 0
    for theme, label, fg, bg, need in rows:
        r = ratio(fg, bg)
        bad += r < need
        print(f"| {theme} | {label} | {fg} / {bg} | {r:.2f}:1 | {need} | {'sim' if r >= need else 'NÃO'} |")
    if bad:
        sys.exit(f"{bad} par(es) abaixo do mínimo")


if __name__ == "__main__":
    main()
