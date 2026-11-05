#!/usr/bin/env python3
"""Capa provisória dos livros só da Amazon (sem foto do ML): static/capas/<isbn>.jpg. Só stdlib.

    python3 collector/capas.py            # baixa as que faltam e lista as não achadas

Fontes, pelo ISBN exato, nesta ordem: Open Library e o catálogo público (VTEX) de duas
livrarias, conferindo o EAN do item. Nenhuma request para a Amazon (regra 1).
Rodar na carga de catálogo, conferir cada imagem nova (mockup 3D, selo, edição errada)
antes do PR; a que não servir sai e o ISBN entra em RECUSADAS. Sai quando a Creators API der a foto da Amazon.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPAS = HERE.parent / "static" / "capas"
UA = {"User-Agent": "ofertaslivros-capas/1.0"}
VTEX = ("www.livrariascuritiba.com.br", "www.martinsfontespaulista.com.br")  # a 1ª costuma ter a capa plana
JPEG = b"\xff\xd8\xff"
# Conferidas e recusadas (só foto de brinde ou mockup com selo): ficam no placeholder.
RECUSADAS = {"9788501303950", "9788582358894"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read()


def jpeg(data):
    return data if data[:3] == JPEG and len(data) > 2000 else None


def open_library(isbn):
    try:
        return jpeg(get(f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg?default=false"))
    except OSError:  # 404 = sem capa
        return None


def vtex_url(host, isbn, products):
    """URL da 1ª imagem do item com o EAN exato, em 400x600, só no CDN da própria loja."""
    for p in products:
        for it in p.get("items", []):
            if it.get("ean") == isbn and it.get("images"):
                u = it["images"][0]["imageUrl"].split("?")[0]
                if re.fullmatch(rf"https://{host.split('.')[1]}\.vteximg\.com\.br/arquivos/ids/\d+/[\w.-]+\.jpg", u):
                    return re.sub(r"/ids/(\d+)/", r"/ids/\1-400-600/", u)
    return None


def vtex(isbn):
    for host in VTEX:
        try:
            q = get(f"https://{host}/api/catalog_system/pub/products/search?fq=alternateIds_Ean:{isbn}")
            u = vtex_url(host, isbn, json.loads(q))
            if u and (d := jpeg(get(u))):
                return d
        except (OSError, ValueError):
            pass
        time.sleep(1)
    return None


def main():
    books = json.loads((HERE / "catalog.json").read_text(encoding="utf-8"))
    books = books["books"] if isinstance(books, dict) else books
    falta = []
    for b in books:
        isbn = b.get("isbn")
        if b.get("ml_url") or not isbn or isbn in RECUSADAS or (CAPAS / f"{isbn}.jpg").exists():
            continue
        d = open_library(isbn) or vtex(isbn)
        if d:
            (CAPAS / f"{isbn}.jpg").write_bytes(d)
            print(f"ok {isbn} {b['title']}")
        else:
            falta.append(f"{isbn} {b['title']}")
        time.sleep(1)
    print(f"não achadas: {len(falta)}", *falta, sep="\n  ")


def demo():
    p = [{"items": [{"ean": "1", "images": [{"imageUrl": "https://livrariascuritiba.vteximg.com.br/arquivos/ids/9/a.jpg?v=1"}]}]}]
    assert vtex_url(VTEX[0], "1", p) == "https://livrariascuritiba.vteximg.com.br/arquivos/ids/9-400-600/a.jpg"
    assert vtex_url(VTEX[0], "2", p) is None                               # EAN diferente
    assert vtex_url(VTEX[1], "1", p) is None                               # CDN de outra loja
    evil = [{"items": [{"ean": "1", "images": [{"imageUrl": "https://evil.com/arquivos/ids/9/a.jpg"}]}]}]
    assert vtex_url(VTEX[0], "1", evil) is None
    assert jpeg(JPEG + b"x" * 3000) and not jpeg(b"\x89PNG" + b"x" * 3000) and not jpeg(JPEG)


if __name__ == "__main__":
    demo() if sys.argv[1:] == ["--demo"] else main()
