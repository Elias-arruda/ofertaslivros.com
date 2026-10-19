#!/usr/bin/env python3
"""Curadoria automática do catálogo: docs/produto/curator.md. Só stdlib.

    python3 collector/curator.py probe [--isbn ISBN]     # passo 0: as rotas de descoberta respondem?
    python3 collector/curator.py suggest [--summary MD]  # até 10 candidatos pendentes no catalog.json

Só fala com api.mercadolibre.com, pelo cliente do collect.py (token de app, timeout,
backoff, User-Agent). Nenhuma request para a Amazon: sem a Creators API não há descoberta
lá. Nada de HTML: resposta que não é application/json aborta (collect.ml_request).
O curator nunca escreve ml_url nem asin: o link vem do painel, colado pelo Elias no PR.
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from collector import collect as c  # noqa: E402  (mesmo módulo que os testes mockam)
from build import brl  # noqa: E402

CATEGORY = "MLB437616"  # "Livros Físicos": folha de MLB1196 (o /highlights exige folha)
# BOOK_GENRE do ML -> GENRES (decisão 4). Autoajuda (7538148) fica fora; literatura-brasileira
# não existe no ML e é trocada à mão no PR.
GENRE_MAP = {
    "13061816": "manga",       # Mangás e HQs
    "13061825": "negocios",    # Negócios
    "7538039": "ficcao",       # Literatura
    "13611960": "nao-ficcao",  # Biografias
    "13464376": "nao-ficcao",  # História
    "76624759": "nao-ficcao",  # Ciência
}
WEEK_MAX = 10      # candidatos por execução (decisão 2)
GENRE_MAX = 4      # por nicho, por execução
CATALOG_MAX = 150  # ativos + pendentes
PRICE_MIN, PRICE_MAX = 1500, 40000  # centavos: R$ 15 a R$ 400 (decisão 3)
SEEN_DAYS = 180    # recusado não volta antes disso
DEADLINE_S = 300   # orçamento de rede do suggest (job tem 10 min)
SUMMARY_MAX = 60_000
PROBE_ISBN = "9788535914849"  # só para o probe do /products/search
SEEN = HERE / "curator_seen.json"
PRODUCT_URL = "https://www.mercadolivre.com.br/p/{}"  # só texto no PR; nunca é chamado
# Dentro de code span nada vira link nem menção; estes trocam por equivalentes de largura
# total para não fechar o span, quebrar a tabela nem parecer markdown.
MD_SAFE = str.maketrans("[]()<>|`@\\", "［］（）＜＞｜｀＠＼")


def _highlights_path(genre_id=None):
    p = f"/highlights/MLB/category/{CATEGORY}"
    return p + "?" + urlencode({"attribute": "BOOK_GENRE", "attributeValue": genre_id}) \
        if genre_id else p


def highlights(token, genre_id=None, **kw):
    """-> [(ml_product_id, posição)], só type=PRODUCT (o coletor só lê /products)."""
    body = c.ml_request(_highlights_path(genre_id), token, **kw)
    content = body.get("content") if isinstance(body, dict) else None
    if not isinstance(content, list):
        raise c.MLError("/highlights malformado")
    return [(it["id"], it["position"]) for it in content
            if isinstance(it, dict) and it.get("type") == "PRODUCT"
            and isinstance(it.get("id"), str) and c.MLB_RE.fullmatch(it["id"])
            and type(it.get("position")) is int and it["position"] > 0]


def _attr(prod, aid):
    for a in prod.get("attributes") or []:
        if isinstance(a, dict) and a.get("id") == aid:
            return a
    return {}


def _values(a, key_one, key_list):
    vals = a.get("values")
    return [a.get(key_one)] + [v.get(key_list) for v in vals if isinstance(v, dict)] \
        if isinstance(vals, list) else [a.get(key_one)]


def genre_of(prod, fallback):
    """BOOK_GENRE da ficha mapeado. Gênero presente e fora do mapa: descarta.
    Ficha sem gênero: vale o nicho da lista em que o produto apareceu (se houver)."""
    ids = [str(v) for v in _values(_attr(prod, "BOOK_GENRE"), "value_id", "id") if v]
    for i in ids:
        if i in GENRE_MAP:
            return GENRE_MAP[i]
    return None if ids else fallback


def portugues(prod):
    return any(isinstance(n, str) and n.strip().casefold().startswith("portugu")
               for n in _values(_attr(prod, "LANGUAGE"), "value_name", "name"))


def price_of(prod, pid, token, **kw):
    """-> (price_cents, list_cents) do vencedor (se novo e BRL) ou do menor anúncio novo
    em BRL do /items; None se não houver. sale_price não: dá 403 com token de app."""
    w = c.winner(prod)
    it = w if w and w.get("condition") == "new" and w.get("currency_id") == "BRL" else None
    if it is None:
        body, _ = c.product_items(pid, token, **kw)
        it, _ = c.best_listing(body)
        if it is None:
            return None
    r = c.listing_row(pid, it, datetime.now(timezone.utc))
    return r["price_cents"], r["list_price_cents"]


def candidate(pid, pos, src_genre, token, known_isbns, **kw):
    """-> (candidato, None) ou (None, motivo do descarte)."""
    prod = c.ml_request(f"/products/{pid}", token, **kw)
    if not isinstance(prod, dict) or prod.get("status") != "active":
        return None, "inativo"
    isbns = {g for g in c.product_gtins(prod) if c.isbn_ok(g)}
    if len(isbns) != 1:  # sem ISBN-13 válido ou ficha com mais de um: não arrisca
        return None, "isbn"
    isbn = isbns.pop()
    if isbn in known_isbns:
        return None, "duplicado"
    if not portugues(prod):
        return None, "idioma"
    genre = genre_of(prod, src_genre)
    if genre is None:
        return None, "nicho"
    try:
        title = c._text({"t": _attr(prod, "BOOK_TITLE").get("value_name") or prod.get("name")},
                        "t")
        author = c._text({"t": _attr(prod, "AUTHOR").get("value_name")}, "t")
    except c.Invalid:
        return None, "texto"
    try:
        pr = price_of(prod, pid, token, **kw)
    except c.Invalid:
        return None, "preco"
    if pr is None:
        return None, "sem_novo_brl"
    price, lst = pr
    if not PRICE_MIN <= price <= PRICE_MAX:
        return None, "preco"
    return {"ml_product_id": pid, "pos": pos, "isbn": isbn, "genre": genre, "title": title,
            "author": author, "price": price, "list_price": lst,
            "off": (lst - price) * 100 // lst}, None


def select(cands, n_catalog):
    """Ranking (menor posição; empate: maior desconto) com os tetos de volume."""
    slots = max(0, min(WEEK_MAX, CATALOG_MAX - n_catalog))
    per, out = Counter(), []
    for x in sorted(cands, key=lambda x: (x["pos"], -x["off"], x["ml_product_id"])):
        if len(out) >= slots:
            break
        if per[x["genre"]] < GENRE_MAX:
            per[x["genre"]] += 1
            out.append(x)
    return out


def slug(title, taken):
    s = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:c.ID_MAX - 3].strip("-") or "livro"
    out, n = s, 2
    while out in taken:
        out, n = f"{s}-{n}", n + 1
    taken.add(out)
    return out


def asin_provavel(isbn):
    """ISBN-10 do ISBN-13 (só 978): costuma ser o ASIN do livro físico. Aritmética pura;
    o Elias confere no navegador antes de pôr asin no catálogo."""
    if not isbn.startswith("978"):
        return "-"
    d = isbn[3:12]
    ck = (11 - sum((10 - i) * int(x) for i, x in enumerate(d)) % 11) % 11
    return d + ("X" if ck == 10 else str(ck))


def md(s):
    return "`" + " ".join(s.translate(MD_SAFE).split()) + "`"


def summary(picked, today):
    lines = [f"## Curadoria {today.isoformat()}: {len(picked)} candidatos",
             "",
             f"Fonte: `/highlights` da categoria `{CATEGORY}` (API do ML), filtrada por ISBN, "
             "novo, BRL, R$ 15 a R$ 400, português e nicho. As entradas entram no "
             "`catalog.json` com `\"pendente\": true` e **não vão ao ar** até ganharem o "
             "`ml_url` do painel.",
             "",
             "| # | Título | Autor | Nicho | Preço | Desconto | Posição | ISBN | ASIN provável "
             "| Produto no ML |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for i, x in enumerate(picked, 1):
        lines.append(f"| {i} | {md(x['title'])} | {md(x['author'])} | {x['genre']} | "
                     f"{brl(x['price'])} | {x['off']}% | {x['pos']} | {x['isbn']} | "
                     f"{asin_provavel(x['isbn'])} | {PRODUCT_URL.format(x['ml_product_id'])} |")
    lines += ["", "### URLs para o Gerador de links do painel", "", "```text",
              *(PRODUCT_URL.format(x["ml_product_id"]) for x in picked), "```", "",
              "### Checklist", "",
              "- [ ] Gerei o link de cada livro no painel e troquei `\"pendente\": true` por "
              "`\"ml_url\": \"<link do painel>\"`",
              "- [ ] Abri cada link no navegador (sem comprar) e conferi que é o livro certo",
              "- [ ] Ajustei o `genre` onde precisava (ex.: `literatura-brasileira`)",
              "- [ ] Apaguei as entradas que não quero (ficam no `curator_seen.json` e não "
              f"voltam por {SEEN_DAYS} dias)",
              "- [ ] `asin` só depois de conferir o ASIN provável no navegador", ""]
    text = "\n".join(lines)
    if len(text) > SUMMARY_MAX:
        raise c.Invalid("resumo do PR acima de 60 mil caracteres")
    return text


def load_seen(path, today):
    """{ml_product_id: AAAA-MM-DD da 1ª sugestão}, já podado. Arquivo estranho: Invalid."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except ValueError:
        raise c.Invalid(f"{path.name} ilegível") from None
    if not isinstance(doc, dict):
        raise c.Invalid(f"{path.name} precisa ser objeto")
    out = {}
    for k, v in doc.items():
        try:
            d = date.fromisoformat(v)
        except (TypeError, ValueError):
            raise c.Invalid(f"{path.name}: data inválida para {k!r}") from None
        if not c.MLB_RE.fullmatch(k):
            raise c.Invalid(f"{path.name}: id inválido {k!r}")
        if today - d < timedelta(days=SEEN_DAYS):
            out[k] = v
    return out


def write_catalog(path, doc):
    """Um livro por linha: o PR do curator mostra só linhas novas no diff."""
    head = "".join(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},\n"
                   for k, v in doc.items() if k != "books")
    books = ",\n".join("  " + json.dumps(b, ensure_ascii=False) for b in doc["books"])
    text = "{\n" + head + ' "books": [\n' + books + "\n ]\n}\n"
    assert json.loads(text) == doc
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def suggest(catalog=None, seen_path=None, summary_path=None, today=None,
            clock=time.monotonic):
    catalog, seen_path = catalog or c.CATALOG, seen_path or SEEN
    today = today or datetime.now(timezone.utc).date()
    doc = json.loads(catalog.read_text(encoding="utf-8"))
    books = c.load_catalog(doc, include_pending=True)  # catálogo quebrado: nem começa
    seen = load_seen(seen_path, today)
    if CATALOG_MAX - len(books) <= 0:
        print(f"curator: catálogo no teto ({len(books)}/{CATALOG_MAX}); nada a sugerir")
        return 0
    known_pids = {b["ml_product_id"] for b in books if "ml_product_id" in b} | set(seen)
    known_isbns = {b["isbn"] for b in books if "isbn" in b}
    deadline = clock() + DEADLINE_S
    kw = {"deadline": deadline, "clock": clock}
    try:
        token = c.ml_token(deadline, clock)
    except c.MLError as e:
        print(f"::error::curator: token falhou ({e})")
        return 1
    if token is None:
        print("::error::curator: ML_CLIENT_ID/ML_CLIENT_SECRET ausentes no ambiente")
        return 1

    ranks, ok = {}, 0  # pid -> [melhor posição, nicho da lista]
    for gid in (None, *GENRE_MAP):
        try:
            found = highlights(token, gid, **kw)
        except c.MLError as e:
            print(f"curator: /highlights {gid or 'geral'}: {e}")
            continue
        ok += 1
        for pid, pos in found:
            if pid in known_pids:
                continue
            r = ranks.setdefault(pid, [pos, None])
            r[0] = min(r[0], pos)
            r[1] = r[1] or GENRE_MAP.get(gid)
    if not ok:
        print("::error::curator: nenhuma lista do /highlights respondeu (ver o probe)")
        return 1

    why, cands, isbns = Counter(), [], set(known_isbns)
    order = sorted(ranks.items(), key=lambda kv: (kv[1][0], kv[0]))
    for n, (pid, (pos, g)) in enumerate(order):
        try:
            x, reason = candidate(pid, pos, g, token, isbns, **kw)
        except c.Deadline:
            why["adiado"] += len(order) - n
            break
        except (c.MLError, c.Invalid) as e:
            print(f"curator: {pid}: {e}")
            why["erro"] += 1
            continue
        if x is None:
            why[reason] += 1
            continue
        isbns.add(x["isbn"])  # dois produtos com o mesmo ISBN: fica o primeiro
        cands.append(x)
    picked = select(cands, len(books))
    print(f"curator: {len(ranks)} produtos novos nas listas, {len(cands)} passaram nos "
          f"filtros, {len(picked)} sugeridos; descartes: "
          + (", ".join(f"{v} {k}" for k, v in sorted(why.items())) or "nenhum"))
    if not picked:
        return 1 if why["erro"] and not cands else 0

    taken = {b["id"] for b in books}
    new = [{"id": slug(x["title"], taken), "isbn": x["isbn"], "genre": x["genre"],
            "title": x["title"], "author": x["author"], "ml_product_id": x["ml_product_id"],
            "pendente": True} for x in picked]
    doc = {**doc, "books": doc["books"] + new}
    c.load_catalog(doc, include_pending=True)  # valida antes de gravar
    text = summary(picked, today)
    write_catalog(catalog, doc)
    seen.update({x["ml_product_id"]: today.isoformat() for x in picked})
    seen_path.write_text(json.dumps(dict(sorted(seen.items())), indent=1) + "\n",
                         encoding="utf-8")
    if summary_path:
        summary_path.write_text(text, encoding="utf-8")
    return 0


def _count(body):
    """Contagem sem conteúdo: nenhum título, preço, vendedor ou URL vai para o log."""
    if isinstance(body, list):
        return f"itens={len(body)}"
    if not isinstance(body, dict):
        return "itens=-"
    for k in ("content", "results"):
        if isinstance(body.get(k), list):
            types = Counter(it.get("type") for it in body[k] if isinstance(it, dict))
            total = (body.get("paging") or {}).get("total") \
                if isinstance(body.get("paging"), dict) else None
            return (f"{k}={len(body[k])}" + (f" total={total}" if type(total) is int else "")
                    + (" tipos=" + ",".join(f"{t}:{n}" for t, n in sorted(types.items())
                                            if isinstance(t, str)) if any(types) else ""))
    return "itens=-"


def probe(isbn=PROBE_ISBN):
    """Passo 0: status HTTP, chaves de topo e contagens de cada rota de descoberta."""
    try:
        token = c.ml_token()
    except c.MLError as e:
        print(f"token: falhou ({e})")
        return 1
    if token is None:
        print("token: ML_CLIENT_ID/ML_CLIENT_SECRET ausentes no ambiente")
        return 1
    print("token: ok")
    if not c.isbn_ok(isbn):
        print(f"isbn {isbn!r} inválido; usando {PROBE_ISBN}")
        isbn = PROBE_ISBN
    gid = next(iter(GENRE_MAP))
    routes = [
        ("highlights geral", _highlights_path()),
        (f"highlights BOOK_GENRE={gid}", _highlights_path(gid)),
        ("trends", f"/trends/MLB/{CATEGORY}"),
        ("products/search isbn", "/products/search?" + urlencode(
            {"site_id": "MLB", "status": "active", "product_identifier": isbn})),
    ]
    for name, path in routes:
        st, body = c._probe_get(path, token)
        print(f"{name}: {path.split('?')[0]} -> {st} chaves={c._keys(body)} {_count(body)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe")
    p.add_argument("--isbn", default=PROBE_ISBN)
    s = sub.add_parser("suggest")
    s.add_argument("--summary", type=Path, help="markdown para o corpo do PR")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "probe":
            return probe(a.isbn)
        return suggest(summary_path=a.summary)
    except c.Invalid as e:
        sys.exit(f"curator falhou: {e}")


if __name__ == "__main__":
    sys.exit(main())
