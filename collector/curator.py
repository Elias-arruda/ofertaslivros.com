#!/usr/bin/env python3
"""Curadoria automática do catálogo: docs/produto/curator.md. Só stdlib.

    python3 collector/curator.py probe [--isbn ISBN]     # passo 0: as rotas de descoberta respondem?
    python3 collector/curator.py suggest [--summary MD]  # até 10 candidatos pendentes no catalog.json

Fontes: /highlights geral da categoria e, em segundo, os termos do /trends resolvidos pelo
/products/search?q=. O /highlights filtrado por BOOK_GENRE dá 400 (probe 39258219518):
o nicho sai só do BOOK_GENRE da ficha do produto.

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
TRENDS_MAX = 5      # termos do /trends usados por execução (1 busca cada)
SEARCH_LIMIT = 10   # produtos por termo
TREND_POS = 100     # produto vindo do /trends ranqueia depois de todo o /highlights
LOOKUP_MAX = 60     # fichas lidas por execução (1 a 3 requests cada); o resto fica adiado
SEEN = HERE / "curator_seen.json"
PRODUCT_URL = "https://www.mercadolivre.com.br/p/{}"  # só texto no PR; nunca é chamado
# Dentro de code span nada vira link nem menção; estes trocam por equivalentes de largura
# total para não fechar o span, quebrar a tabela nem parecer markdown.
MD_SAFE = str.maketrans("[]()<>|`@\\", "［］（）＜＞｜｀＠＼")


HIGHLIGHTS = f"/highlights/MLB/category/{CATEGORY}"
TRENDS = f"/trends/MLB/{CATEGORY}"


def _search_path(q):
    return "/products/search?" + urlencode({"site_id": "MLB", "status": "active",
                                            "domain_id": "MLB-BOOKS", "q": q,
                                            "limit": SEARCH_LIMIT})


def highlights(token, **kw):
    """-> [(ml_product_id, posição)], só type=PRODUCT (o coletor só lê /products)."""
    body = c.ml_request(HIGHLIGHTS, token, **kw)
    content = body.get("content") if isinstance(body, dict) else None
    if not isinstance(content, list):
        raise c.MLError("/highlights malformado")
    return [(it["id"], it["position"]) for it in content
            if isinstance(it, dict) and it.get("type") == "PRODUCT"
            and isinstance(it.get("id"), str) and c.MLB_RE.fullmatch(it["id"])
            and type(it.get("position")) is int and it["position"] > 0]


def trends(token, **kw):
    """-> [(ml_product_id, posição)] dos primeiros TRENDS_MAX termos do /trends, cada um
    resolvido pelo /products/search?q= (API; a URL de lista.mercadolivre do termo é HTML e
    nunca é seguida). Posição = TREND_POS + ordem do termo e do resultado."""
    body = c.ml_request(TRENDS, token, **kw)
    if not isinstance(body, list):
        raise c.MLError("/trends malformado")
    kws = [t["keyword"].strip()[:100] for t in body if isinstance(t, dict)
           and isinstance(t.get("keyword"), str) and t["keyword"].strip()][:TRENDS_MAX]
    out = []
    for i, q in enumerate(kws):
        res = c.ml_request(_search_path(q), token, **kw)
        res = res.get("results") if isinstance(res, dict) else None
        if not isinstance(res, list):
            raise c.MLError("/products/search malformado")
        ids = [r["id"] for r in res if isinstance(r, dict) and isinstance(r.get("id"), str)
               and c.MLB_RE.fullmatch(r["id"])][:SEARCH_LIMIT]
        out += [(pid, TREND_POS + i * SEARCH_LIMIT + j) for j, pid in enumerate(ids, 1)]
    return out


def _attr(prod, aid):
    for a in prod.get("attributes") or []:
        if isinstance(a, dict) and a.get("id") == aid:
            return a
    return {}


def _values(a, key_one, key_list):
    vals = a.get("values")
    return [a.get(key_one)] + [v.get(key_list) for v in vals if isinstance(v, dict)] \
        if isinstance(vals, list) else [a.get(key_one)]


def genre_of(prod):
    """BOOK_GENRE da ficha mapeado. Sem gênero ou fora do mapa: None (descarta)."""
    for i in (str(v) for v in _values(_attr(prod, "BOOK_GENRE"), "value_id", "id") if v):
        if i in GENRE_MAP:
            return GENRE_MAP[i]
    return None


def isbn_of(prod):
    """-> (ISBN-13 ou None, motivo ou None). ISBN é opcional (probe 39259800320: a ficha
    com token de app não traz GTIN). Sem código: (None, None). Com código, fail-closed:
    exatamente um ISBN-13 válido (978/979, checksum) ou descarte."""
    codes = c.product_gtins(prod)
    isbns = {g for g in codes if c.isbn_ok(g)}
    if len(isbns) == 1:
        return isbns.pop(), None
    if isbns:
        return None, "isbn_multiplo"
    if codes:
        return None, "isbn_invalido"  # há código, mas nenhum vira ISBN-13 válido
    return None, None


def _name(prod, aid):
    """1º texto não vazio do atributo (value_name ou values[].name); "" se não houver."""
    return next((v.strip() for v in _values(_attr(prod, aid), "value_name", "name")
                 if isinstance(v, str) and v.strip()), "")


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


def candidate(pid, pos, token, known_isbns, **kw):
    """-> (candidato, None) ou (None, motivo do descarte). Os itens das listas não trazem
    a ficha: título, autor, ISBN, gênero e idioma vêm sempre do /products/{id} completo.
    Prova de que é livro: BOOK_TITLE e AUTHOR não vazios (papelaria vem com BRAND etc.)."""
    prod = c.ml_request(f"/products/{pid}", token, **kw)
    if not isinstance(prod, dict) or prod.get("status") != "active":
        return None, "inativo"
    title, author = _name(prod, "BOOK_TITLE"), _name(prod, "AUTHOR")
    if not title or not author:
        return None, "nao_livro"
    isbn, why = isbn_of(prod)
    if why:
        return None, why
    if isbn and isbn in known_isbns:
        return None, "duplicado"
    if not portugues(prod):
        return None, "idioma"
    genre = genre_of(prod)
    if genre is None:
        return None, "nicho"
    try:
        title, author = c._text({"t": title}, "t"), c._text({"t": author}, "t")
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
    if not isbn or not isbn.startswith("978"):
        return "-"
    d = isbn[3:12]
    ck = (11 - sum((10 - i) * int(x) for i, x in enumerate(d)) % 11) % 11
    return d + ("X" if ck == 10 else str(ck))


def md(s):
    return "`" + " ".join(s.translate(MD_SAFE).split()) + "`"


def summary(picked, today):
    lines = [f"## Curadoria {today.isoformat()}: {len(picked)} candidatos",
             "",
             f"Fonte: `/highlights` da categoria `{CATEGORY}` e termos do `/trends` "
             f"(posição acima de {TREND_POS}), via API do ML, filtrada por ficha de livro "
             "(`BOOK_TITLE` e `AUTHOR`), ISBN válido quando houver, novo, BRL, "
             "R$ 15 a R$ 400, português e nicho. As entradas entram no "
             "`catalog.json` com `\"pendente\": true` e **não vão ao ar** até ganharem o "
             "`ml_url` do painel.",
             "",
             "| # | Título | Autor | Nicho | Preço | Desconto | Posição | ISBN | ASIN provável "
             "| Produto no ML |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for i, x in enumerate(picked, 1):
        lines.append(f"| {i} | {md(x['title'])} | {md(x['author'])} | {x['genre']} | "
                     f"{brl(x['price'])} | {x['off']}% | {x['pos']} | {x['isbn'] or '-'} | "
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
              "- [ ] `asin` só depois de conferir o ASIN provável no navegador; sem ISBN "
              "(`-`), preencha o `isbn` à mão antes, porque livro nas duas lojas exige isbn",
              ""]
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

    ranks, ok = {}, 0  # pid -> melhor posição
    for name, src in (("highlights", highlights), ("trends", trends)):
        try:
            found = src(token, **kw)
        except c.MLError as e:
            print(f"curator: /{name}: {e}")
            continue
        ok += 1
        new = {pid for pid, _ in found if pid not in known_pids}
        print(f"curator: /{name}: {len(found)} produtos, {len(new)} novos")
        for pid, pos in found:
            if pid in new:
                ranks[pid] = min(ranks.get(pid, pos), pos)
    if not ok:
        print("::error::curator: nem /highlights nem /trends responderam (ver o probe)")
        return 1

    why, cands, isbns = Counter(), [], set(known_isbns)
    order = sorted(ranks.items(), key=lambda kv: (kv[1], kv[0]))
    if len(order) > LOOKUP_MAX:
        why["adiado"] += len(order) - LOOKUP_MAX
        order = order[:LOOKUP_MAX]
    for n, (pid, pos) in enumerate(order):
        try:
            x, reason = candidate(pid, pos, token, isbns, **kw)
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
        if x["isbn"]:
            isbns.add(x["isbn"])  # dois produtos com o mesmo ISBN: fica o primeiro
        cands.append(x)
    picked = select(cands, len(books))
    print(f"curator: {len(ranks)} produtos novos nas listas, {len(cands)} passaram nos "
          f"filtros, {len(picked)} sugeridos; descartes: "
          + (", ".join(f"{v} {k}" for k, v in sorted(why.items())) or "nenhum"))
    if not picked:
        return 1 if why["erro"] and not cands else 0

    taken = {b["id"] for b in books}
    new = [{"id": slug(x["title"], taken), **({"isbn": x["isbn"]} if x["isbn"] else {}),
            "genre": x["genre"], "title": x["title"], "author": x["author"],
            "ml_product_id": x["ml_product_id"], "pendente": True} for x in picked]
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


def _fmt(v):
    """Formato de um valor de atributo sem o valor: comprimento, hífen, espaço, nº de partes."""
    if not isinstance(v, str):
        return type(v).__name__
    return (f"len={len(v)} hifen={'sim' if '-' in v else 'nao'} "
            f"espaco={'sim' if ' ' in v.strip() else 'nao'} "
            f"valores={len([x for x in re.split(r'[,;/|]', v) if x.strip()])}")


def _probe_product(pid, item, token):
    """Ficha de um PRODUCT do highlights: só ids de atributo e o formato dos de GTIN/ISBN."""
    st, prod = c._probe_get(f"/products/{pid}", token)
    print(f"  produto #{item.get('position')}: chaves do item={c._keys(item)} "
          f"/products -> {st}")
    if not isinstance(prod, dict):
        return
    attrs = [a for a in prod.get("attributes") or [] if isinstance(a, dict)]
    kids = prod.get("children_ids")
    print(f"    status={prod.get('status')!r} children_ids="
          f"{len(kids) if isinstance(kids, list) else '-'} atributos="
          + ",".join(sorted(str(a.get("id")) for a in attrs)))
    for a in attrs:
        aid = str(a.get("id"))
        if "GTIN" not in aid and "ISBN" not in aid:
            continue
        vals = a.get("values") if isinstance(a.get("values"), list) else []
        print(f"    {aid}: value_name {_fmt(a.get('value_name'))}; values={len(vals)}"
              + "".join(f"; values[{i}].name {_fmt(v.get('name'))}"
                        for i, v in enumerate(vals[:3]) if isinstance(v, dict)))
    isbn, why = isbn_of(prod)
    print(f"    isbn: {why or ('ok' if isbn else 'ausente')} "
          f"livro: {'sim' if _name(prod, 'BOOK_TITLE') and _name(prod, 'AUTHOR') else 'nao'}")


def probe(isbn=PROBE_ISBN):
    """Passo 0: status HTTP, chaves de topo e contagens de cada rota de descoberta e, para
    os 3 primeiros PRODUCT do highlights, o formato dos atributos (nunca título, vendedor,
    preço nem token)."""
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
    st, body = c._probe_get(HIGHLIGHTS, token)
    print(f"highlights geral: {HIGHLIGHTS} -> {st} chaves={c._keys(body)} {_count(body)}")
    content = body.get("content") if isinstance(body, dict) else None
    prods = [it for it in content if isinstance(it, dict) and it.get("type") == "PRODUCT"
             and isinstance(it.get("id"), str) and c.MLB_RE.fullmatch(it["id"])] \
        if isinstance(content, list) else []
    for it in prods[:3]:
        _probe_product(it["id"], it, token)
    st, body = c._probe_get(TRENDS, token)
    print(f"trends: {TRENDS} -> {st} chaves={c._keys(body)} {_count(body)}")
    kw = next((t["keyword"].strip()[:100] for t in body if isinstance(t, dict)
               and isinstance(t.get("keyword"), str) and t["keyword"].strip()), None) \
        if isinstance(body, list) else None
    routes = [("products/search isbn", "/products/search?" + urlencode(
        {"site_id": "MLB", "status": "active", "product_identifier": isbn}))]
    if kw:
        routes.append(("products/search q (1º termo do trends)", _search_path(kw)))
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
