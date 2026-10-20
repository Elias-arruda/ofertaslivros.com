#!/usr/bin/env python3
"""Coletor de preços: etapa 1 de docs/produto/alerta-de-preco.md e contrato v2 de
docs/produto/comparacao-lojas.md. Só stdlib.

    python3 collector/collect.py run --history DIR   # manual da Amazon + ML + offers.json v2
    python3 collector/collect.py export OUT.json     # valida o catálogo e exporta a parte pública
    python3 collector/collect.py probe [MLB...]      # confere as rotas do ML (sem gravar nada)

Amazon: NENHUMA request HTTP. Até a Creators API ser liberada, o preço entra só pelo
CSV manual (source=manual). A fila (DIR/amazon_queue.csv) diz o que o humano confere.
Foto da Amazon também não: image_url só vem do ML.

Mercado Livre: o link do painel aponta para PRODUTO de catálogo (/p/MLB...). Por produto:
  1. GET /products/{ml_product_id} -> buy_box_winner.item_id, pictures (image_url) e o
     atributo GTIN (doc "Buscador de produtos", 29/12/2025). A doc mostra produto
     status=active com buy_box_winner null: sem vencedor não quer dizer sem anúncio.
     GTIN diferente do ISBN do catálogo: o preço do ML daquele livro é descartado.
  1b. Sem buy_box_winner: GET /products/{id}/items (anúncios que competem no produto).
     Elegível: condition=new, BRL, status ausente/active, item_id válido. O de menor
     price vale, com price/original_price do próprio resultado (sale_price dá 403 com
     token de app, run 39178554200). Nenhum elegível (ou 404) = "inativo".
  2. Só no buy_box: GET /items/{item_id}/sale_price?context=channel_marketplace ->
     amount/regular_amount (doc "Preços de produtos", 14/10/2026). 403: cai para
     price/original_price do buy_box_winner.
Token de app via client_credentials (ML_CLIENT_ID/ML_CLIENT_SECRET), nunca logado.

Saída em DIR (branch price-history):
  price_history/AAAA-MM.csv  append-only, nunca reescreve linha
  offers.json                contrato v2: um livro com stores[]; o build escolhe a vencedora
                             (median_90d_cents por loja: mediana dos dias 8 a 90, §10.8)
  state.json                 history_since, image_url e as datas da retirada (curadoria)
                             por livro (metadado, sobrescrito)
  amazon_queue.csv           ordem de conferência manual
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from http.client import HTTPException
from pathlib import Path
from statistics import median_low
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
# build.py só define constantes e funções (o build roda sob __main__): importar é seguro.
import build  # noqa: E402
from build import (ASIN_RE, BRT, GENRES, ID_RE, MLB_RE, STORE_COMMON, Invalid, _text,  # noqa: E402
                   check_url, ml_affiliate, ml_url)

CATALOG = HERE / "catalog.json"
MANUAL_CSV = HERE / "amazon_prices.csv"

ID_MAX = 57  # deep link do Telegram aceita 64; folga para prefixo futuro
STORES = ("amazon", "mercadolivre")
BOOK_FIELDS = {"id", "isbn", "genre", "title", "author", "asin", "ml_product_id", "ml_url",
               "pendente", "genre_source"}
# genre_source: só o curator grava. Com ele, o livro é automático e pode sair por 30 dias sem
# oferta (curadoria-automatica.md §10.8, item 6); sem ele, é manual e fica isento.
GENRE_SOURCES = {"ml_book_genre", "padrao_lgbtqia"}
PUBLIC_FIELDS = ("id", "title", "author", "genre")  # export: sem ids de loja nem URL
ISBN_RE = re.compile(r"97[89][0-9]{10}")
# Só o CDN de imagem do ML (é o que a CSP libera em img-src); sem query, aspas ou espaço.
IMG_RE = re.compile(r"https://http2\.mlstatic\.com/[A-Za-z0-9_./-]{1,400}")
HISTORY_COLS = ["book_id", "store", "price_cents", "list_price_cents", "checked_at", "source"]
MANUAL_COLS = ["asin", "price_cents", "list_price_cents", "checked_at"]
CENTS_RE = re.compile(r"[1-9][0-9]{0,8}")  # inteiro positivo, sem sinal/ponto/expoente
MAX_CENTS = 1_000_000  # R$ 10.000: acima disso é erro de digitação ou dado quebrado
MANUAL_MAX_AGE = timedelta(days=7)
WINDOW = timedelta(days=90)
MEDIAN_DAYS = (8, 90)  # dias BRT antes da coleta: alta recente não infla a mediana (§10.8, item 3)
AMAZON_COVERAGE_MIN = 0.8  # provisório (curator.md 5.7): série manual esparsa não dá mediana
# O build rejeita campo de loja desconhecido: só emite a mediana quando ele já a aceita.
# ponytail: tirar o teste quando o build com median_90d_cents estiver na main.
EMIT_MEDIAN = "median_90d_cents" in STORE_COMMON

ML_HOST = "api.mercadolibre.com"  # único host que o coletor chama
UA = "ofertaslivros-coletor/0.1 (+https://ofertaslivros.com)"
TIMEOUT = 10
RETRIES = 3
MAX_BYTES = 5_000_000
ML_DEADLINE_S = 40  # orçamento do ML inteiro (token incluso): job abaixo de 1 min
ITEMS_PAGE_SIZE = 50
ITEMS_MAX_TOTAL = 1000  # falha fechada se um produto exceder o teto de coleta
_urlopen = urlopen  # ponto de mock dos testes


class MLError(Exception):
    code = None  # status HTTP, quando houver


class Deadline(MLError):
    pass


# ---------- catálogo (uma entrada por livro, ids das duas lojas) ----------

def isbn_ok(s):
    return (isinstance(s, str) and bool(ISBN_RE.fullmatch(s))
            and sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(s)) % 10 == 0)


def load_catalog(doc, include_pending=False):
    """Valida o catálogo inteiro (pendentes inclusos: id/isbn/produto únicos entre todos).
    Pendente ("pendente": true, sugerido pelo curator) não tem ml_url nem asin e fica fora
    da coleta e do ar; só volta na lista com include_pending=True (uso do curator)."""
    if not isinstance(doc, dict) or not isinstance(doc.get("books"), list) or not doc["books"]:
        raise Invalid('catálogo precisa ser {"books": [...]} não vazio')
    gone = doc.get("retirados", {})  # gate 9: id retirado nunca volta, nem à mão
    if not isinstance(gone, dict) or not all(isinstance(k, str) and ID_RE.fullmatch(k)
                                             and _day(v) for k, v in gone.items()):
        raise Invalid("retirados precisa ser {id: AAAA-MM-DD}")
    aff = ml_affiliate()
    books, seen = [], set()
    for i, b in enumerate(doc["books"]):
        try:
            if not isinstance(b, dict):
                raise Invalid("livro precisa ser objeto")
            extra = set(b) - BOOK_FIELDS
            if extra:
                raise Invalid(f"campos não permitidos: {sorted(extra)}")
            bid = b.get("id")
            if not isinstance(bid, str) or len(bid) > ID_MAX or not ID_RE.fullmatch(bid):
                raise Invalid(f"id inválido (slug até {ID_MAX} chars): {bid!r}")
            if bid in gone:
                raise Invalid(f"id {bid!r} foi retirado e não pode ser reaproveitado")
            if b.get("genre") not in GENRES:
                raise Invalid(f"genre inválido: {b.get('genre')!r} (use um de {sorted(GENRES)})")
            out = {"id": bid, "genre": b["genre"],
                   "title": _text(b, "title"), "author": _text(b, "author")}
            if "genre_source" in b:
                if b["genre_source"] not in GENRE_SOURCES:
                    raise Invalid(f"genre_source inválido: {b['genre_source']!r}")
                out["genre_source"] = b["genre_source"]
            if "isbn" in b:
                if not isbn_ok(b["isbn"]):
                    raise Invalid(f"isbn precisa ser ISBN-13 válido, só dígitos: {b['isbn']!r}")
                out["isbn"] = b["isbn"]
            if "asin" in b:
                if not isinstance(b["asin"], str) or not ASIN_RE.fullmatch(b["asin"]):
                    raise Invalid(f"asin inválido: {b['asin']!r}")
                out["asin"] = b["asin"]
            pend = "pendente" in b
            if pend:
                if b["pendente"] is not True:
                    raise Invalid("pendente só aceita true (para publicar, apague o campo)")
                if "ml_url" in b or "asin" in b:
                    raise Invalid("pendente não pode ter ml_url nem asin: troque "
                                  '"pendente": true pelo ml_url do painel')
                if "ml_product_id" not in b:
                    raise Invalid("pendente precisa de ml_product_id")
                out["pendente"] = True
            elif ("ml_product_id" in b) != ("ml_url" in b):
                raise Invalid("ml_product_id e ml_url andam juntos")
            if "ml_product_id" in b:
                pid = b["ml_product_id"]
                if not isinstance(pid, str) or not MLB_RE.fullmatch(pid):
                    raise Invalid(f"ml_product_id inválido: {pid!r}")
                out["ml_product_id"] = pid
                if not pend:
                    out["ml_url"] = ml_url(b["ml_url"], aff)
            if "asin" not in out and "ml_product_id" not in out:
                raise Invalid("livro precisa de asin e/ou ml_product_id")
            if "asin" in out and "ml_product_id" in out and "isbn" not in out:
                raise Invalid("livro nas duas lojas precisa de isbn (é o que casa as duas)")
            for k in (bid, out.get("isbn"), out.get("asin"), out.get("ml_product_id")):
                if k is None:
                    continue
                if k in seen:
                    raise Invalid(f"duplicado: {k!r}")
                seen.add(k)
        except Invalid as e:
            raise Invalid(f"books[{i}]: {e}") from None
        books.append(out)
    if include_pending:
        return books
    for b in books:
        if b.get("pendente"):
            print(f"catálogo: {b['id']} pendente (sem ml_url), fora da coleta e do ar")
    return [b for b in books if not b.get("pendente")]


def read_catalog(path=None):
    return load_catalog(json.loads((path or CATALOG).read_text(encoding="utf-8")))


def _write_json(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def export_catalog(books, out):
    _write_json(out, {"books": [
        {**{k: b[k] for k in PUBLIC_FIELDS},
         "stores": [s for s in STORES if (s == "amazon" and "asin" in b)
                    or (s == "mercadolivre" and "ml_product_id" in b)]}
        for b in books]})


# ---------- dinheiro e datas ----------

def to_cents(amount):
    """Decimal/int em reais -> centavos inteiros. float nunca entra (JSON lido com Decimal)."""
    if type(amount) is int:
        amount = Decimal(amount)
    if not isinstance(amount, Decimal) or not amount.is_finite():
        raise Invalid(f"valor inválido: {amount!r}")
    c = amount * 100
    if c != c.to_integral_value() or not 0 < c <= MAX_CENTS:
        raise Invalid(f"valor precisa ser positivo, até R$ 10.000, com até 2 casas: {amount!r}")
    return int(c)


def utc_iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def row(book_id, store, price, list_price, checked_at, source):
    return {"book_id": book_id, "store": store, "price_cents": price,
            "list_price_cents": list_price, "checked_at": utc_iso(checked_at), "source": source}


# ---------- price_history (append-only) ----------

def shard(hist_dir, checked_at):
    return Path(hist_dir) / "price_history" / f"{checked_at[:7]}.csv"  # AAAA-MM em UTC


def append_history(hist_dir, rows):
    by = {}
    for r in rows:
        by.setdefault(shard(hist_dir, r["checked_at"]), []).append(r)
    for path, rs in sorted(by.items()):
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:  # "a": nunca reescreve
            w = csv.DictWriter(f, HISTORY_COLS, lineterminator="\n")
            if new:
                w.writeheader()
            w.writerows(rs)


def read_history(hist_dir, months):
    for m in sorted(set(months)):
        p = Path(hist_dir) / "price_history" / f"{m}.csv"
        if p.exists():
            with p.open(newline="", encoding="utf-8") as f:
                yield from csv.DictReader(f)


def recent_months(now, n=4):
    """Meses (UTC) que cobrem a janela de 90 dias."""
    out, d = [], now.astimezone(timezone.utc).replace(day=1)
    for _ in range(n):
        out.append(f"{d:%Y-%m}")
        d = (d - timedelta(days=1)).replace(day=1)
    return out


# ---------- Amazon: entrada manual (sem nenhuma request) ----------

def _cents_field(v):
    if not isinstance(v, str) or not CENTS_RE.fullmatch(v.strip()):
        raise Invalid(f"centavos precisam ser inteiro positivo (ex.: 3990): {v!r}")
    c = int(v.strip())
    if c > MAX_CENTS:
        raise Invalid(f"acima de R$ 10.000: {v!r}")
    return c


def parse_manual(text, books, now):
    """Tudo ou nada: qualquer linha inválida levanta Invalid e nada é gravado."""
    if not text.strip():
        return []
    by_asin = {b["asin"]: b for b in books if "asin" in b}
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != MANUAL_COLS:
        raise Invalid(f"{MANUAL_CSV.name}: cabeçalho precisa ser {','.join(MANUAL_COLS)}")
    rows = []
    for n, r in enumerate(reader, start=2):
        try:
            if None in r or None in r.values():
                raise Invalid("número de colunas errado")
            asin = r["asin"].strip()
            if not ASIN_RE.fullmatch(asin):
                raise Invalid(f"ASIN inválido: {asin!r}")
            if asin not in by_asin:
                raise Invalid(f"ASIN fora do catálogo: {asin}")
            price, lst = _cents_field(r["price_cents"]), _cents_field(r["list_price_cents"])
            if lst < price:
                raise Invalid("list_price_cents menor que price_cents")
            raw = r["checked_at"].strip()
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                raise Invalid(f"checked_at não é ISO 8601: {raw!r}") from None
            if dt.tzinfo is None:
                raise Invalid(f"checked_at precisa ter fuso (ex.: -03:00): {raw!r}")
            if dt > now + timedelta(minutes=5):
                raise Invalid(f"checked_at no futuro: {raw!r}")
            if dt < now - MANUAL_MAX_AGE:
                raise Invalid(f"checked_at com mais de 7 dias: {raw!r}")
        except Invalid as e:
            raise Invalid(f"{MANUAL_CSV.name} linha {n}: {e}") from None
        rows.append(row(by_asin[asin]["id"], "amazon", price, lst, dt, "manual"))
    return rows


def only_new_manual(hist_dir, rows):
    """O CSV é relido a cada run: só entra (livro, checked_at) que ainda não está no histórico."""
    seen = {(h["book_id"], h["checked_at"])
            for h in read_history(hist_dir, (r["checked_at"][:7] for r in rows))
            if h["source"] == "manual"}
    out = []
    for r in rows:
        k = (r["book_id"], r["checked_at"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def amazon_queue(books, last_checked):
    """Ordem de conferência: nunca conferido primeiro, depois o mais antigo.
    Etapa 2: ordenar por número de alertas ativos antes da data (só mudar esta chave)."""
    am = [b for b in books if "asin" in b]
    return sorted(am, key=lambda b: (last_checked.get(b["id"], ""), b["id"]))


def write_queue(hist_dir, books, latest):
    path = Path(hist_dir) / "amazon_queue.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    last = {bid: r["checked_at"] for (bid, s), r in latest.items() if s == "amazon"}
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "asin", "title", "last_checked_at", "conferir_em"])
        for b in amazon_queue(books, last):
            # link sem tag de propósito: clique do próprio associado não pode levar a tag
            w.writerow([b["id"], b["asin"], b["title"], last.get(b["id"], ""),
                        f"https://www.amazon.com.br/dp/{b['asin']}"])


# ---------- Mercado Livre ----------

def _headers(token):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def ml_request(path, token=None, form=None, deadline=None, clock=time.monotonic,
               sleep=None):
    """GET/POST em api.mercadolibre.com com timeout e backoff exponencial em 429/5xx/rede.
    deadline (clock() absoluto): não começa tentativa nem espera que passe dele.
    Mensagens de erro levam só o caminho sem query: nunca token, corpo ou segredo."""
    url = f"https://{ML_HOST}{path}"
    where = path.split("?")[0]
    data = urlencode(form).encode() if form else None
    for attempt in range(RETRIES + 1):
        left = None if deadline is None else deadline - clock()
        if left is not None and left <= 0:
            raise Deadline(f"sem tempo para {where}")
        timeout = TIMEOUT if left is None else min(TIMEOUT, left)
        try:
            with _urlopen(Request(url, data=data, headers=_headers(token)), timeout=timeout) as r:
                h = getattr(r, "headers", None)  # resposta real sempre tem; o BytesIO dos testes não
                if h is not None and not (h.get("Content-Type") or "").startswith(
                        "application/json"):
                    raise MLError(f"resposta não é JSON em {where}")  # HTML nunca é lido
                return json.loads(r.read(MAX_BYTES), parse_float=Decimal)
        except HTTPError as e:
            if (e.code != 429 and e.code < 500) or attempt == RETRIES:
                err = MLError(f"HTTP {e.code} em {where}")
                err.code = e.code
                raise err from None
            ra = (e.headers or {}).get("Retry-After", "") or ""
            wait = int(ra) if ra.isascii() and ra.isdigit() else 2 ** attempt
        except (URLError, HTTPException, OSError) as e:
            if attempt == RETRIES:
                raise MLError(f"rede em {where}: {type(e).__name__}") from None
            wait = 2 ** attempt
        except ValueError:
            raise MLError(f"JSON inválido em {where}") from None
        wait = min(wait, 30)
        if deadline is not None and clock() + wait >= deadline:
            raise Deadline(f"sem tempo para repetir {where}")
        (sleep or time.sleep)(wait)


def ml_token(deadline=None, clock=time.monotonic):
    cid, secret = os.environ.get("ML_CLIENT_ID"), os.environ.get("ML_CLIENT_SECRET")
    if not cid or not secret:
        return None
    r = ml_request("/oauth/token", form={"grant_type": "client_credentials",
                                         "client_id": cid, "client_secret": secret},
                   deadline=deadline, clock=clock)
    tok = r.get("access_token") if isinstance(r, dict) else None
    if not isinstance(tok, str) or not tok:
        raise MLError("resposta do /oauth/token sem access_token")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{tok}")  # o log é público: mascara caso algo o imprima
    return tok


def winner(prod):
    """buy_box_winner do produto, ou None se não houver (aí vale o /items).
    Sem checar status: a doc mostra inactive sempre com buy_box_winner null, e active
    também pode vir com null."""
    if not isinstance(prod, dict):
        raise MLError("produto malformado")
    if prod.get("buy_box_winner") is None:
        return None
    w = prod["buy_box_winner"]
    if not isinstance(w, dict) or not isinstance(w.get("item_id"), str) \
            or not MLB_RE.fullmatch(w["item_id"]):
        raise MLError("buy_box_winner malformado")
    return w


def best_listing(body):
    """De /products/{id}/items -> (anúncio elegível de menor price ou None, nº de elegíveis).
    Elegível: condition == "new" (ausente = descarta: livro usado não entra), BRL, status
    ausente ou "active", item_id no MLB_RE, price válido."""
    res = body.get("results") if isinstance(body, dict) else None
    if not isinstance(res, list):
        raise MLError("/items malformado")
    best, n = None, 0
    for it in res:
        if not isinstance(it, dict) or it.get("condition") != "new" \
                or it.get("currency_id") != "BRL" \
                or it.get("status", "active") != "active" \
                or not isinstance(it.get("item_id"), str) or not MLB_RE.fullmatch(it["item_id"]):
            continue
        try:
            c = to_cents(it.get("price"))
        except Invalid:
            continue
        n += 1
        if best is None or c < best[0]:
            best = (c, it)
    return (best and best[1]), n


def listing_row(book_id, it, now):
    """price/original_price de um anúncio (/items ou buy_box_winner). original_price só
    vale como "de" se for numérico e maior que o price; senão list = price."""
    if not isinstance(it, dict):
        raise MLError("anúncio malformado")
    if it.get("currency_id") != "BRL":
        raise Invalid(f"moeda não é BRL: {it.get('currency_id')!r}")
    price = to_cents(it.get("price"))
    try:
        lst = to_cents(it.get("original_price"))
    except Invalid:
        lst = price
    return row(book_id, "mercadolivre", price, max(lst, price), now, "ml_api")


def product_items(pid, token, **kw):
    """-> (resposta agregada, nº de anúncios). Pagina para não perder o menor preço.
    404 = nenhum anúncio. Falha fechada se a resposta não permitir paginação segura."""
    try:
        body = ml_request(f"/products/{pid}/items?limit={ITEMS_PAGE_SIZE}&offset=0", token, **kw)
    except MLError as e:
        if e.code == 404:
            return {"results": []}, 0
        raise
    res = body.get("results") if isinstance(body, dict) else None
    if not isinstance(res, list):
        raise MLError("/items malformado")
    paging = body.get("paging")
    if paging is None:
        return body, len(res)
    if not isinstance(paging, dict):
        raise MLError("/items paging malformado")
    total, limit, offset = paging.get("total"), paging.get("limit"), paging.get("offset")
    if any(type(v) is not int or v < 0 for v in (total, limit, offset)) or limit == 0:
        raise MLError("/items paging inválido")
    if total > ITEMS_MAX_TOTAL:
        raise MLError(f"/items tem {total} anúncios; limite seguro é {ITEMS_MAX_TOTAL}")
    if offset != 0 or len(res) > limit or len(res) > total:
        raise MLError("/items paging inconsistente")
    all_results = list(res)
    while len(all_results) < total:
        next_offset = len(all_results)
        page = ml_request(
            f"/products/{pid}/items?{urlencode({'limit': limit, 'offset': next_offset})}",
            token, **kw)
        page_results = page.get("results") if isinstance(page, dict) else None
        page_paging = page.get("paging") if isinstance(page, dict) else None
        if not isinstance(page_results, list) or not isinstance(page_paging, dict) \
                or page_paging.get("total") != total or page_paging.get("limit") != limit \
                or page_paging.get("offset") != next_offset or not page_results \
                or len(all_results) + len(page_results) > total:
            raise MLError("/items pagina inconsistente")
        all_results.extend(page_results)
    body["results"] = all_results
    return body, len(all_results)


def product_image(prod):
    """Primeira foto do produto, só se for do CDN do ML. Qualquer coisa estranha: sem foto."""
    pics = prod.get("pictures") if isinstance(prod, dict) else None
    if not isinstance(pics, list) or not pics or not isinstance(pics[0], dict):
        return None
    u = pics[0].get("secure_url") or pics[0].get("url")
    return u if isinstance(u, str) and IMG_RE.fullmatch(u) else None


# Ids de atributo que podem trazer o ISBN na ficha do produto (o ML usa GTIN; os outros
# são variações plausíveis, aceitas para não descartar livro por nome de atributo).
CODE_ATTR_RE = re.compile(r"(GTIN|EAN|ISBN)(_?1[03])?")
CODE_RE = re.compile(r"[0-9]{8,14}|[0-9]{9}[0-9X]")


def isbn10_to_13(s):
    """ISBN-10 com dígito verificador válido -> ISBN-13 (978). Senão None."""
    if not re.fullmatch(r"[0-9]{9}[0-9X]", s):
        return None
    if sum((10 - i) * (10 if d == "X" else int(d)) for i, d in enumerate(s)) % 11:
        return None
    core = "978" + s[:9]
    return core + str((10 - sum(int(d) * (3 if i % 2 else 1)
                                for i, d in enumerate(core)) % 10) % 10)


def _codes(text):
    """"978-85-359-1484-9, 85 359 1484 6" -> códigos só com dígitos (e X do ISBN-10).
    Vírgula, ponto e vírgula, barra e | separam valores; hífen e espaço dentro de um valor
    são formatação. Se o valor sem eles não fecha um código, tenta cada pedaço por espaço."""
    for part in re.split(r"[,;/|]", text.upper()):
        part = re.sub(r"ISBN(-?1[03])?:?", " ", part)
        whole = re.sub(r"[\s.-]", "", part)
        yield from [whole] if CODE_RE.fullmatch(whole) else \
            [t for t in (re.sub(r"[.-]", "", x) for x in part.split()) if CODE_RE.fullmatch(t)]


def product_gtins(prod):
    """Códigos dos atributos GTIN/EAN/ISBN da ficha (value_name e values[].name; pode vir
    vários). ISBN-10 válido volta como ISBN-13; o resto volta como veio, só dígitos."""
    out = set()
    attrs = prod.get("attributes") if isinstance(prod, dict) else None
    for a in attrs if isinstance(attrs, list) else []:
        if not isinstance(a, dict) or not isinstance(a.get("id"), str) \
                or not CODE_ATTR_RE.fullmatch(a["id"]):
            continue
        vals = a.get("values") if isinstance(a.get("values"), list) else []
        for v in [a.get("value_name")] + [v.get("name") for v in vals if isinstance(v, dict)]:
            if isinstance(v, str):
                out |= {isbn10_to_13(x) or x for x in _codes(v)}
    return out


def sale_row(book_id, sp, now):
    if not isinstance(sp, dict):
        raise MLError("sale_price malformado")
    if sp.get("currency_id") != "BRL":
        raise Invalid(f"moeda não é BRL: {sp.get('currency_id')!r}")
    price = to_cents(sp.get("amount"))
    reg = sp.get("regular_amount")
    lst = to_cents(reg) if reg is not None else price
    return row(book_id, "mercadolivre", price, max(lst, price), now, "ml_api")


def _sale_path(item_id):
    return f"/items/{item_id}/sale_price?context=channel_marketplace"


def collect_ml(books, token, now, deadline, start=0, clock=time.monotonic, sleep=None):
    """-> (linhas do price_history, contagens, {book_id: image_url})."""
    ml = [b for b in books if "ml_product_id" in b]
    if ml:  # gira o início para nenhum item ficar "adiado" para sempre
        k = start % len(ml)
        ml = ml[k:] + ml[:k]
    rows, images = [], {}
    n = {"ok": 0, "inativo": 0, "gtin_divergente": 0, "erro": 0, "adiado": 0}
    kw = {"deadline": deadline, "clock": clock, "sleep": sleep}
    for i, b in enumerate(ml):
        # diagnóstico (log público): só id do livro, status HTTP, contagens e caminho
        d = {"http": "-", "buy_box": "não", "items": "-", "novos_brl": "-", "caminho": "erro"}
        try:
            try:
                prod = ml_request(f"/products/{b['ml_product_id']}", token, **kw)
            except MLError as e:
                d["http"] = e.code or "-"
                raise
            d["http"] = 200
            w = winner(prod)
            d["buy_box"] = "sim" if w else "não"
            gtins = product_gtins(prod)
            if "isbn" in b and gtins and b["isbn"] not in gtins:
                print(f"::warning::ML: {b['id']}: GTIN do produto não bate com o isbn do "
                      f"catálogo; preço do ML descartado")
                n["gtin_divergente"] += 1
                d["caminho"] = "gtin_divergente"
                continue
            img = product_image(prod)
            if img:
                images[b["id"]] = img
            if w:
                d["caminho"] = "buy_box"
                try:
                    r = sale_row(b["id"], ml_request(_sale_path(w["item_id"]), token, **kw), now)
                except MLError as e:
                    if e.code != 403:
                        raise
                    d["caminho"] = "buy_box_preco_winner"
                    r = listing_row(b["id"], w, now)  # sem price: Invalid, conta como erro
            else:
                body, d["items"] = product_items(b["ml_product_id"], token, **kw)
                it, d["novos_brl"] = best_listing(body)
                if it is None:
                    n["inativo"] += 1
                    d["caminho"] = "inativo"
                    continue
                d["caminho"] = "items"
                r = listing_row(b["id"], it, now)
            rows.append(r)
            n["ok"] += 1
        except Deadline:
            n["adiado"] += len(ml) - i
            d["caminho"] = "adiado"
            break
        except (MLError, Invalid) as e:
            print(f"ML: {b['id']}: {e}")
            n["erro"] += 1
        finally:
            print(f"ML diag: {b['id']} /products={d['http']} buy_box={d['buy_box']} "
                  f"/items={d['items']} novos_brl={d['novos_brl']} caminho={d['caminho']}")
    return rows, n, images


def run_number():
    v = os.environ.get("GITHUB_RUN_NUMBER", "")
    return int(v) if v.isascii() and v.isdigit() else 0


# ---------- offers.json v2 (o build escolhe a vencedora; aqui só fatos por loja) ----------

def load_state(hist_dir):
    p = Path(hist_dir) / "state.json"
    try:
        s = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        s = {}
    except ValueError:
        print("::warning::state.json ilegível; recomeçando history_since/image_url")
        s = {}
    hs = s.get("history_since") if isinstance(s, dict) else None
    im = s.get("image_url") if isinstance(s, dict) else None
    cu = s.get("curadoria") if isinstance(s, dict) else None
    return {"history_since": {k: v for k, v in (hs or {}).items()
                              if isinstance(k, str) and isinstance(v, str)},
            "image_url": {k: v for k, v in (im or {}).items()
                          if isinstance(v, str) and IMG_RE.fullmatch(v)},
            "curadoria": {k: v for k, v in (cu or {}).items()
                          if isinstance(v, dict) and set(v) == CURADORIA_KEYS
                          and _day(v["publicado"]) and _day(v["ultimo_anuncio"])
                          and (v["ultima_oferta"] is None or _day(v["ultima_oferta"]))},
            "curadoria_ok": ok if isinstance(s, dict) and _day(ok := s.get("curadoria_ok"))
            else None}


CURADORIA_KEYS = {"publicado", "ultimo_anuncio", "ultima_oferta"}


def _day(v):
    """AAAA-MM-DD válido (entrada estranha no state.json é descartada, nunca derruba)."""
    try:
        return isinstance(v, str) and len(v) == 10 and bool(date.fromisoformat(v))
    except ValueError:
        return False


def track_curadoria(state, books, latest, offers, now, ml_ok=False):
    """Datas (BRT) que a retirada do curator lê (§10.8, item 6), a cada execução do coletor:
    publicado (1ª vez no catálogo publicado), ultimo_anuncio (último preço gravado, ou seja,
    anúncio ativo, em qualquer loja) e ultima_oferta (pelo resolve do build: o mesmo critério
    "em oferta" do site). Fica no price-history, e não num PR, para não perder dia.
    curadoria_ok: último dia em que a coleta do ML rodou inteira; sem ele fresco, o curator
    não retira (ML fora do ar não pode parecer "sem anúncio")."""
    today = now.astimezone(BRT).date().isoformat()
    if ml_ok:
        state["curadoria_ok"] = today
    try:
        em_oferta = {o["id"] for o in build.load_offers(offers, now) if o["oferta"]}
    except Invalid:  # nenhuma loja fresca agora (ou offers que o build recusaria)
        em_oferta = set()
    cur = state["curadoria"]
    for k in [k for k, v in cur.items() if max(x or "" for x in v.values()) > today]:
        del cur[k]  # data no futuro prenderia o max para sempre: recomeça o relógio
    for b in books:
        st = cur.setdefault(b["id"], {"publicado": today, "ultimo_anuncio": today,
                                      "ultima_oferta": None})
        seen = [datetime.fromisoformat(r["checked_at"]).astimezone(BRT).date().isoformat()
                for (bid, _), r in latest.items() if bid == b["id"]]
        st["ultimo_anuncio"] = max([st["ultimo_anuncio"], *seen])
        if b["id"] in em_oferta:
            st["ultima_oferta"] = today
    for k in set(cur) - {b["id"] for b in books}:
        del cur[k]  # saiu do catálogo (ou voltou a pendente)


def summarize(hist_dir, now):
    """Por (livro, loja): última linha, menor preço em 90 dias, primeira data vista e o
    menor preço de cada dia BRT da janela da mediana ({date: cents})."""
    since = utc_iso(now - WINDOW)
    today = now.astimezone(BRT).date()
    lo, hi = (today - timedelta(days=n) for n in reversed(MEDIAN_DAYS))
    latest, low, first, daily = {}, {}, {}, {}
    # 5 meses UTC: 4 não cobrem o dia 90 BRT em todo começo de mês (ex.: 1º/05)
    for h in read_history(hist_dir, recent_months(now, 5)):
        k = (h["book_id"], h["store"])
        p = int(h["price_cents"])
        if k not in latest or h["checked_at"] >= latest[k]["checked_at"]:  # empate: a última gravada
            latest[k] = h
        if h["checked_at"] >= since:
            low[k] = min(low.get(k, p), p)
        first[k] = min(first.get(k, h["checked_at"]), h["checked_at"])
        d = datetime.fromisoformat(h["checked_at"]).astimezone(BRT).date()
        if lo <= d <= hi:
            days = daily.setdefault(k, {})
            days[d] = min(days.get(d, p), p)
    return latest, low, first, daily


def median_90d(days, history_since, today, store):
    """Mediana (median_low: inteira e conservadora) do menor preço diário nos dias 8 a 90
    antes de hoje (BRT), limitada ao history_since. None sem amostra ou, na Amazon, com
    amostra em menos de AMAZON_COVERAGE_MIN dos dias da janela: aí o build cai no "de/por"."""
    lo = max(today - timedelta(days=MEDIAN_DAYS[1]), date.fromisoformat(history_since))
    hi = today - timedelta(days=MEDIAN_DAYS[0])
    vals = [p for d, p in days.items() if lo <= d <= hi]
    if not vals or (store == "amazon"
                    and len(vals) < AMAZON_COVERAGE_MIN * ((hi - lo).days + 1)):
        return None
    return median_low(vals)


def build_offers(books, latest, low, state, daily, today):
    hs = state["history_since"]
    offers = []
    for b in books:
        stores = []
        for store, ident in (("amazon", "asin"), ("mercadolivre", "ml_product_id")):
            r = latest.get((b["id"], store))
            if ident not in b or r is None:
                continue
            k = (b["id"], store)
            s = {"store": store, ident: b[ident]}
            if store == "mercadolivre":
                s["ml_url"] = b["ml_url"]
            price = int(r["price_cents"])
            s.update(price_cents=price, list_price_cents=int(r["list_price_cents"]),
                     lowest_90d_cents=min(low.get(k, price), price),
                     history_since=hs[f"{b['id']}|{store}"],
                     checked_at=r["checked_at"])
            med = median_90d(daily.get(k, {}), s["history_since"], today, store) \
                if EMIT_MEDIAN else None
            if med is not None:
                s["median_90d_cents"] = med
            stores.append(s)
        if stores:
            o = {"id": b["id"]}
            if "isbn" in b:
                o["isbn"] = b["isbn"]
            o.update(genre=b["genre"], title=b["title"], author=b["author"])
            if b["id"] in state["image_url"]:
                o["image_url"] = state["image_url"][b["id"]]
            o["stores"] = stores
            offers.append(o)
    return {"version": 2, "offers": offers}


def _dt(v, k):
    try:
        d = datetime.fromisoformat(v)
    except (TypeError, ValueError):
        raise Invalid(f"{k} não é ISO 8601: {v!r}") from None
    if d.tzinfo is None:
        raise Invalid(f"{k} sem fuso")
    return d


def _int_cents(s, k):
    v = s.get(k)
    if type(v) is not int or not 0 < v <= MAX_CENTS:
        raise Invalid(f"{k} precisa ser inteiro em (0, {MAX_CENTS}]")
    return v


STORE_OUT = {"amazon": {"store", "asin"}, "mercadolivre": {"store", "ml_product_id", "ml_url"}}
STORE_NUM = {"price_cents", "list_price_cents", "lowest_90d_cents", "history_since", "checked_at"}
STORE_OPT = {"median_90d_cents"}
OFFER_KEYS = {"id", "isbn", "genre", "title", "author", "image_url", "stores"}


def validate_offers(doc):
    """Schema do contrato v2. Falhou: Invalid, e o offers.json não é gravado."""
    if not isinstance(doc, dict) or set(doc) != {"version", "offers"} or doc["version"] != 2 \
            or not isinstance(doc["offers"], list):
        raise Invalid('offers.json precisa ser {"version": 2, "offers": [...]}')
    aff, ids = ml_affiliate(), set()
    for i, o in enumerate(doc["offers"]):
        try:
            if not isinstance(o, dict) or not set(o) <= OFFER_KEYS \
                    or not {"id", "genre", "title", "author", "stores"} <= set(o):
                raise Invalid("campos da oferta fora do contrato")
            if not isinstance(o["id"], str) or len(o["id"]) > ID_MAX \
                    or not ID_RE.fullmatch(o["id"]) or o["id"] in ids:
                raise Invalid(f"id inválido ou duplicado: {o['id']!r}")
            ids.add(o["id"])
            if "isbn" in o and not isbn_ok(o["isbn"]):
                raise Invalid("isbn inválido")
            if o["genre"] not in GENRES:
                raise Invalid("genre fora de GENRES")
            _text(o, "title"), _text(o, "author")
            if "image_url" in o and not (isinstance(o["image_url"], str)
                                         and IMG_RE.fullmatch(o["image_url"])):
                raise Invalid("image_url fora do CDN do ML")
            st = o["stores"]
            if not isinstance(st, list) or not 1 <= len(st) <= 2 \
                    or len({s.get("store") for s in st if isinstance(s, dict)}) != len(st):
                raise Invalid("stores precisa ter 1 ou 2 lojas distintas")
            for s in st:
                if not isinstance(s, dict) or s.get("store") not in STORE_OUT \
                        or not STORE_OUT[s["store"]] | STORE_NUM <= set(s) \
                        <= STORE_OUT[s["store"]] | STORE_NUM | STORE_OPT:
                    raise Invalid(f"campos da loja fora do contrato: {sorted(s)}")
                if s["store"] == "amazon":
                    if not isinstance(s["asin"], str) or not ASIN_RE.fullmatch(s["asin"]):
                        raise Invalid("asin inválido")
                else:
                    if not isinstance(s["ml_product_id"], str) \
                            or not MLB_RE.fullmatch(s["ml_product_id"]):
                        raise Invalid("ml_product_id inválido")
                    check_url(ml_url(s["ml_url"], aff))
                p, lst, lo = (_int_cents(s, k) for k in
                              ("price_cents", "list_price_cents", "lowest_90d_cents"))
                if lst < p or lo > p:
                    raise Invalid("precisa list >= price >= lowest_90d")
                if "median_90d_cents" in s:
                    _int_cents(s, "median_90d_cents")
                ca = _dt(s["checked_at"], "checked_at")
                try:
                    since = date.fromisoformat(s["history_since"])
                except (TypeError, ValueError):
                    raise Invalid("history_since precisa ser AAAA-MM-DD") from None
                if since > ca.astimezone(timezone.utc).date():
                    raise Invalid("history_since depois do checked_at")
        except Invalid as e:
            raise Invalid(f"offers[{i}]: {e}") from None
    return doc


# ---------- probe (diagnóstico manual das rotas) ----------

def _probe_get(path, token):
    try:
        with _urlopen(Request(f"https://{ML_HOST}{path}", headers=_headers(token)),
                      timeout=TIMEOUT) as r:
            return getattr(r, "status", 200), json.loads(r.read(MAX_BYTES), parse_float=Decimal)
    except HTTPError as e:
        return e.code, None
    except (URLError, HTTPException, OSError, ValueError) as e:
        return type(e).__name__, None


def _keys(body):
    return sorted(body) if isinstance(body, dict) else type(body).__name__


def probe(ids):
    """Só status HTTP, chaves de topo e o que foi interpretado. Nunca token nem secret."""
    try:
        token = ml_token()
    except MLError as e:
        print(f"token: falhou ({e})")
        return 1
    if token is None:
        print("token: ML_CLIENT_ID/ML_CLIENT_SECRET ausentes no ambiente")
        return 1
    print("token: ok")
    for pid in ids:
        if not MLB_RE.fullmatch(pid):
            print(f"{pid!r}: ignorado, fora do MLB_RE")
            continue
        st, prod = _probe_get(f"/products/{pid}", token)
        print(f"{pid} /products -> {st} chaves={_keys(prod)}")
        if not isinstance(prod, dict):
            continue
        w = prod.get("buy_box_winner")
        print(f"  status={prod.get('status')!r} buy_box_winner="
              + (f"item_id={w.get('item_id')!r} price={w.get('price')} "
                 f"original_price={w.get('original_price')} currency={w.get('currency_id')!r}"
                 if isinstance(w, dict) else repr(w)))
        print(f"  gtin={sorted(product_gtins(prod))} image_url={product_image(prod)!r}")
        try:
            w = winner(prod)
        except MLError as e:
            print(f"  vencedor: {e}")
            continue
        if w is None:
            st, body = _probe_get(f"/products/{pid}/items", token)
            res = body.get("results") if isinstance(body, dict) else None
            print(f"  sem buy_box_winner; /items -> {st} itens="
                  f"{len(res) if isinstance(res, list) else '-'}")
            try:
                it, ne = best_listing(body) if st != 404 else (None, 0)
                print(f"  novos_brl={ne}")
                if it is None:
                    print("  resultado: inativo (nenhum anúncio novo em BRL)")
                    continue
                r = listing_row("probe", it, datetime.now(timezone.utc))
                print(f"  resultado: price_cents={r['price_cents']} "
                      f"list_price_cents={r['list_price_cents']}")
            except (MLError, Invalid) as e:
                print(f"  /items: {e}")
            continue
        item_id = w["item_id"]
        st, sp = _probe_get(_sale_path(item_id), token)
        print(f"  {item_id} /sale_price -> {st} chaves={_keys(sp)}")
        if isinstance(sp, dict):
            print(f"  amount={sp.get('amount')} regular_amount={sp.get('regular_amount')} "
                  f"currency={sp.get('currency_id')!r}")
            try:
                r = sale_row("probe", sp, datetime.now(timezone.utc))
                print(f"  resultado: price_cents={r['price_cents']} "
                      f"list_price_cents={r['list_price_cents']}")
            except (MLError, Invalid) as e:
                print(f"  resultado: erro ({e})")
    return 0


# ---------- orquestração ----------

def run(hist_dir, now=None, catalog=None, manual=None, clock=time.monotonic):
    now = now or datetime.now(timezone.utc)
    manual = manual or MANUAL_CSV
    books = read_catalog(catalog)
    # 1) valida a entrada manual inteira antes de qualquer request ou escrita
    text = manual.read_text(encoding="utf-8-sig") if manual.exists() else ""  # BOM do Excel
    manual_rows = only_new_manual(hist_dir, parse_manual(text, books, now))
    # 2) ML: qualquer erro (ou ML sem coleta) deixa o job vermelho
    has_ml = any("ml_product_id" in b for b in books)
    status, ml_rows, images, ml_ok = 0, [], {}, False
    deadline = clock() + ML_DEADLINE_S
    try:
        token = ml_token(deadline, clock)
    except MLError as e:
        print(f"::error::ML: token falhou ({e}); coleta do ML pulada")
        token, status = None, 1
    else:
        if token is None and has_ml:
            print("::error::ML_CLIENT_ID/ML_CLIENT_SECRET ausentes; coleta do ML pulada")
            status = 1
    if token and has_ml:
        ml_rows, n, images = collect_ml(books, token, now, deadline, start=run_number(),
                                        clock=clock)
        print("ML: " + ", ".join(f"{v} {k}" for k, v in n.items()))
        if n["erro"]:
            status = 1
        ml_ok = bool(ml_rows) and not n["erro"]
    append_history(hist_dir, manual_rows + ml_rows)
    # 3) offers.json v2: monta, valida e só então grava (dado quebrado não sai)
    latest, low, first, daily = summarize(hist_dir, now)
    state = load_state(hist_dir)
    for (bid, store), ts in first.items():
        state["history_since"].setdefault(f"{bid}|{store}", ts[:10])  # fixa na 1ª vez vista
    state["image_url"].update(images)
    offers = validate_offers(build_offers(books, latest, low, state, daily,
                                          now.astimezone(BRT).date()))
    track_curadoria(state, books, latest, offers, now, ml_ok)
    _write_json(Path(hist_dir) / "state.json", state)
    _write_json(Path(hist_dir) / "offers.json", offers)
    write_queue(hist_dir, books, latest)
    print(f"ok: {len(manual_rows)} manuais novos, {len(ml_rows)} do ML gravados, "
          f"{len(offers['offers'])} livros no offers.json")
    return status


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--history", type=Path, required=True)
    x = sub.add_parser("export")
    x.add_argument("out", type=Path)
    p = sub.add_parser("probe")
    p.add_argument("ids", nargs="*", help="ml_product_id; vazio = os do catálogo")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "run":
            return run(a.history)
        if a.cmd == "probe":
            return probe(a.ids or [b["ml_product_id"] for b in read_catalog()
                                   if "ml_product_id" in b])
        export_catalog(read_catalog(), a.out)
        print(f"ok: catálogo exportado -> {a.out}")
        return 0
    except Invalid as e:
        sys.exit(f"coletor falhou: {e}")


if __name__ == "__main__":
    sys.exit(main())
