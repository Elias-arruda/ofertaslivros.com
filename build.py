#!/usr/bin/env python3
"""Gera dist/ a partir de data/offers.json. Só stdlib.

    python3 build.py             # build
    python3 build.py --selftest  # asserts da validação

data/offers.json é tratado como entrada não confiável: tudo é validado aqui,
a URL de afiliado é montada no código e o host é conferido contra a allowlist.
"""
import html
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "offers.json"
STATIC = ROOT / "static"
DIST = ROOT / "dist"

ALLOWED_HOSTS = {
    "amazon.com.br",
    "www.amazon.com.br",
    "mercadolivre.com.br",
    "www.mercadolivre.com.br",
    "mercadolivre.com",
}
STORES = {"amazon": "Amazon", "mercadolivre": "Mercado Livre"}
# Conjunto fechado: o slug vira diretório em dist/, então nunca vem do JSON livre.
GENRES = {
    "literatura-brasileira": "Literatura brasileira",
    "ficcao": "Ficção",
    "negocios": "Negócios e finanças",
    "nao-ficcao": "Não ficção",
    "manga": "Mangá e HQ",
}

# Sempre re.fullmatch: com re.match + "$", "B0ABCDEFGH\n" passaria.
ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
ASIN_RE = re.compile(r"[A-Z0-9]{10}")
MLB_RE = re.compile(r"MLB\d{1,15}")
TAG_RE = re.compile(r"[A-Za-z0-9-]{1,64}")
CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")

COMMON = {"id", "store", "genre", "title", "author", "price_cents", "list_price_cents",
          "lowest_90d_cents", "checked_at", "history_start"}
STORE_KEY = {"amazon": "asin", "mercadolivre": "ml_item_id"}
# O link do ML é opaco (param ref cifrado), então vem do painel e é validado.
STORE_EXTRA = {"amazon": set(), "mercadolivre": {"ml_url"}}

# ponytail: fuso fixo -03:00 (Brasil sem horário de verão desde 2019);
# trocar por zoneinfo("America/Sao_Paulo") se o horário de verão voltar.
BRT = timezone(timedelta(hours=-3))


class Invalid(ValueError):
    pass


def _env_id(name, default):
    v = os.environ.get(name, default)
    if not TAG_RE.fullmatch(v):
        raise Invalid(f"{name} com formato inválido")
    return v


def partner_tag():
    return _env_id("AMAZON_PARTNER_TAG", "exemplo-20")


def ml_affiliate():
    return _env_id("ML_AFFILIATE_ID", "exemplo")


ML_PARAMS = {"matt_word", "matt_tool", "forceInApp", "ref"}


def ml_url(raw, aff):
    """Aceita só o link completo do painel, preso à nossa conta (matt_word)."""
    if not isinstance(raw, str) or len(raw) > 1000:  # limite por regra do _redirects
        raise Invalid("ml_url precisa ser texto até 1000 chars")
    _ascii(raw)
    p = urlsplit(raw)
    try:
        params = parse_qsl(p.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        params = None
    keys = [k for k, _ in params or []]
    # Chaves em allowlist, cada uma uma vez só (sem MATT_WORD, matt_word vazio, &go=...).
    # ponytail: matt_tool e ref não são conferidos (ref é cifrado pelo ML);
    # fixar matt_tool via env se aparecer abuso.
    # meli.la fica de fora: é encurtador, o build não consegue conferir a conta.
    if ((p.scheme, p.netloc, p.path) != ("https", "www.mercadolivre.com.br", f"/social/{aff}")
            or p.fragment or params is None or not set(keys) <= ML_PARAMS
            or len({k.lower() for k in keys}) != len(keys)
            or dict(params).get("matt_word") != aff):
        raise Invalid(f"ml_url precisa ser o link completo do painel "
                      f"(/social/{aff}?matt_word={aff}...), não meli.la: {raw!r}")
    return raw


def _ascii(url):
    # Só ASCII imprimível: o urlsplit remove C0/espaço antes de validar, o _redirects não.
    if not re.fullmatch(r"[\x21-\x7e]+", url):
        raise Invalid(f"URL com caractere de controle, espaço ou não ASCII: {url!r}")


def affiliate_url(o, tag, aff):
    if o["store"] == "amazon":
        url = f"https://www.amazon.com.br/dp/{o['asin']}?tag={tag}"
    else:
        url = ml_url(o["ml_url"], aff)
    check_url(url)
    return url


def check_url(url):
    _ascii(url)  # uma linha por regra no _redirects
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS or p.username or p.port:
        raise Invalid(f"host fora da allowlist: {url!r}")


def _text(o, k):
    v = o.get(k)
    if not isinstance(v, str) or not v.strip() or len(v) > 300 or CTRL_RE.search(v):
        raise Invalid(f"{k} precisa ser texto não vazio, até 300 chars, sem controle")
    return v.strip()


def _cents(o, k):
    v = o.get(k)
    if type(v) is not int or v <= 0:  # type() exclui bool e float
        raise Invalid(f"{k} precisa ser inteiro positivo (centavos)")
    return v


def validate_offer(o):
    if not isinstance(o, dict):
        raise Invalid("oferta precisa ser objeto")
    store = o.get("store")
    if store not in STORE_KEY:
        raise Invalid(f"store inválida: {store!r}")
    extra = set(o) - COMMON - {STORE_KEY[store]} - STORE_EXTRA[store]
    if extra:  # rejeita "url", "href", o id da outra loja etc.
        raise Invalid(f"campos não permitidos: {sorted(extra)}")
    if o.get("genre") not in GENRES:
        raise Invalid(f"genre inválido: {o.get('genre')!r} (use um de {sorted(GENRES)})")
    oid = o.get("id")
    if not isinstance(oid, str) or len(oid) > 80 or not ID_RE.fullmatch(oid):
        raise Invalid(f"id inválido: {oid!r}")
    ident = o.get(STORE_KEY[store])
    rx = ASIN_RE if store == "amazon" else MLB_RE
    if not isinstance(ident, str) or not rx.fullmatch(ident):
        raise Invalid(f"{STORE_KEY[store]} inválido: {ident!r}")
    out = {"id": oid, "store": store, STORE_KEY[store]: ident, "genre": o["genre"],
           "title": _text(o, "title"), "author": _text(o, "author")}
    if store == "mercadolivre":
        out["ml_url"] = o.get("ml_url")  # validado em affiliate_url
    for k in ("price_cents", "list_price_cents", "lowest_90d_cents"):
        out[k] = _cents(o, k)
    if out["list_price_cents"] < out["price_cents"]:
        raise Invalid("list_price_cents menor que price_cents")
    ca = o.get("checked_at")
    try:
        dt = datetime.fromisoformat(ca.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise Invalid(f"checked_at não é ISO 8601: {ca!r}") from None
    if dt.tzinfo is None:
        raise Invalid("checked_at precisa ter fuso")
    out["checked_at"] = dt
    # Opcional: data (BRT) do 1º preço no histórico do item. Sem ela, nada de selo (CDC).
    hs = o.get("history_start")
    if hs is not None:
        if not isinstance(hs, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", hs):
            raise Invalid(f"history_start precisa ser data AAAA-MM-DD: {hs!r}")
        try:
            hs = date.fromisoformat(hs)
        except ValueError:
            raise Invalid(f"history_start inválida: {hs!r}") from None
        if hs > dt.astimezone(BRT).date():
            raise Invalid("history_start depois de checked_at")
    out["history_start"] = hs
    return out


def load_offers(doc):
    """Valida o documento inteiro; levanta Invalid na primeira falha."""
    if not isinstance(doc, dict) or not isinstance(doc.get("offers"), list):
        raise Invalid('JSON precisa ser {"offers": [...]}')
    tag, aff = partner_tag(), ml_affiliate()
    offers, seen = [], set()
    for i, raw in enumerate(doc["offers"]):
        try:
            o = validate_offer(raw)
            if o["id"] in seen:
                raise Invalid(f"id duplicado: {o['id']!r}")
            seen.add(o["id"])
            o["url"] = affiliate_url(o, tag, aff)
        except Invalid as e:
            raise Invalid(f"offers[{i}]: {e}") from None
        offers.append(o)
    if not offers:
        raise Invalid("nenhuma oferta")
    return offers


# ---------- render ----------

e = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def brl(cents):
    return f"R$ {cents // 100:,}".replace(",", ".") + f",{cents % 100:02d}"


def when(dt):
    d = dt.astimezone(BRT)
    return f"{d:%d/%m} às {d:%H}h{d:%M}"


def discount(o):
    return (o["list_price_cents"] - o["price_cents"]) * 100 // o["list_price_cents"]  # piso: não exagera


def seal(o):
    """"90d" só com 90 dias reais de histórico (CDC); "since" com histórico curto; senão None."""
    hs = o["history_start"]
    if hs is None or o["price_cents"] > o["lowest_90d_cents"]:
        return None
    return "90d" if (o["checked_at"].astimezone(BRT).date() - hs).days >= 90 else "since"


def card(o, i):
    off = discount(o)
    store = STORES[o["store"]]
    t, a = e(o["title"]), e(o["author"])
    old = (f'<s class="old"><span class="sr">De </span>{brl(o["list_price_cents"])}</s>'
           if off else "")
    disc = f'<span class="off">−{off}%</span>' if off else ""
    kind = seal(o)
    stamp = ('<p class="stamp">Menor preço em 90 dias</p>' if kind == "90d" else
             f'<p class="stamp stamp--since">Menor preço desde {o["history_start"]:%d/%m}</p>'
             if kind == "since" else "")
    prep = "no" if o["store"] == "mercadolivre" else "na"
    return f"""<li class="card">
  <div class="top">
    <div class="cover cover--{i % 6}">
      <img src="/capa.svg" alt="Capa ilustrativa de {t}" width="120" height="180" loading="lazy" decoding="async">
      <span class="cover-t" aria-hidden="true">{t}</span>
      <span class="cover-a" aria-hidden="true">{a}</span>
    </div>
    <div class="head">
      <h2 class="title">{t}</h2>
      <p class="author">{a}</p>
    </div>
  </div>
  {stamp}
  <p class="price"><span class="sr">Por </span><strong>{brl(o["price_cents"])}</strong> {old} {disc}</p>
  <p class="meta"><span class="store">{store}</span>, verificado em <time datetime="{e(o["checked_at"].isoformat())}">{when(o["checked_at"])}</time></p>
  <p class="acts"><a class="go" href="/r/{e(o["id"])}" rel="sponsored noopener noreferrer" target="_blank">Ver {prep} {store}<span class="sr">: {t} (abre em nova aba)</span></a></p>
</li>"""


def nav(offers, current):
    present = [g for g in GENRES if any(o["genre"] == g for o in offers)]
    items = [("/", "Todos", current is None)] + [(f"/{g}/", GENRES[g], g == current) for g in present]
    current_attr = ' aria-current="page"'
    links = "".join(
        f'<li><a href="{href}"{current_attr if cur else ""}>{e(label)}</a></li>'
        for href, label, cur in items)
    return f'<nav class="nichos" aria-label="Nichos"><ul>{links}</ul></nav>'


FOOT = """<footer class="foot">
  <p>Como associado da Amazon, ganhamos com compras qualificadas. Também participamos do programa de afiliados do Mercado Livre. Preços verificados no horário indicado; o preço final é o da loja.</p>
</footer>"""


def shell(title, desc, mast, body):
    """Esqueleto comum. title/desc/mast/body já chegam escapados."""
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="theme-color" content="#e8ecf0">
<meta name="color-scheme" content="light">
<link rel="stylesheet" href="/style.css">
</head>
<body>
<a class="skip" href="#conteudo">Pular para o conteúdo</a>
<header class="mast">
{mast}
</header>
<main id="conteudo">
{body}
</main>
{FOOT}
</body>
</html>
"""


def page(all_offers, genre=None):
    offers = [o for o in all_offers if genre is None or o["genre"] == genre]
    latest = max(o["checked_at"] for o in offers)
    cards = "\n".join(card(o, i) for i, o in enumerate(offers))
    n = len(offers)
    head = (f'<p class="brand"><a href="/">Ofertas Livros</a></p>\n<h1>{e(GENRES[genre])}</h1>' if genre
            else '<h1><a href="/">Ofertas Livros</a></h1>')
    mast = f"""{head}
<p class="lede">Só entra aqui livro que baixou de preço de verdade. Conferimos cada um na loja e comparamos com o histórico de preço.</p>
<p class="status">Atualizado em {when(latest)}, {n} {"oferta" if n == 1 else "ofertas"}.</p>
{nav(all_offers, genre)}"""
    title = (f"{e(GENRES[genre])}: ofertas de livros" if genre
             else "Ofertas Livros: descontos de livros conferidos na loja")
    desc = "Ofertas de livros na Amazon e no Mercado Livre, conferidas uma a uma e comparadas com o histórico de preço."
    return shell(title, desc, mast, f'<ol class="grid">\n{cards}\n</ol>')


HEADERS = """/*
  Content-Security-Policy: default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Strict-Transport-Security: max-age=31536000
"""


def require_prod(doc):
    """Fail-closed: sem --dev, nada de tag de exemplo nem dado de exemplo no ar."""
    for name in ("AMAZON_PARTNER_TAG", "ML_AFFILIATE_ID"):
        v = os.environ.get(name, "")
        if not v or "exemplo" in v:
            raise Invalid(f"{name} ausente ou de exemplo (build local: python3 build.py --dev)")
    if doc.get("_exemplo"):
        raise Invalid("offers.json marcado como _exemplo (build local: python3 build.py --dev)")


def build(dev=False):
    doc = json.loads(DATA.read_text(encoding="utf-8"))
    if not dev:
        require_prod(doc)
    offers = load_offers(doc)
    # tudo validado e renderizado antes de tocar no dist/
    pages = {"index.html": page(offers)}
    for g in {o["genre"] for o in offers}:
        pages[f"{g}/index.html"] = page(offers, g)
    redirects = "".join(f"/r/{o['id']} {o['url']} 302\n" for o in offers)
    shutil.rmtree(DIST, ignore_errors=True)
    shutil.copytree(STATIC, DIST)
    for path, body in pages.items():
        (DIST / path).parent.mkdir(exist_ok=True)
        (DIST / path).write_text(body, encoding="utf-8")
    (DIST / "_redirects").write_text(redirects, encoding="utf-8")
    (DIST / "_headers").write_text(HEADERS, encoding="utf-8")
    print(f"ok: {len(offers)} ofertas, {len(pages)} páginas -> {DIST}")


def selftest():
    aff = ml_affiliate()
    ml_link = (f"https://www.mercadolivre.com.br/social/{aff}?matt_word={aff}"
               "&matt_tool=123&forceInApp=true&ref=AbC%2Fd%3D%3D")
    good = {"id": "livro-1", "store": "amazon", "asin": "B0ABCDEFGH", "genre": "manga",
            "title": "T", "author": "A", "price_cents": 1990, "list_price_cents": 3990,
            "lowest_90d_cents": 1990, "checked_at": "2026-10-18T08:00:00-03:00"}
    ml = {**good, "store": "mercadolivre", "id": "livro-2", "ml_item_id": "MLB123",
          "genre": "ficcao", "ml_url": ml_link}
    del ml["asin"]

    def rejects(*offers):
        try:
            load_offers({"offers": list(offers)})
        except Invalid:
            return True
        return False

    o = load_offers({"offers": [good, ml]})
    assert o[0]["url"] == "https://www.amazon.com.br/dp/B0ABCDEFGH?tag=" + partner_tag()
    assert o[1]["url"] == ml_link
    # link do ML: só o completo do painel, preso ao nosso matt_word
    for bad in ("https://meli.la/2NDbdvz",
                ml_link.replace("https://", "http://"),
                ml_link.replace(f"matt_word={aff}", "matt_word=evil"),
                ml_link + "&matt_word=evil",
                ml_link.replace(f"/social/{aff}", "/social/evil"),
                ml_link.replace("www.mercadolivre.com.br", "evil.com@www.mercadolivre.com.br"),
                ml_link.replace("www.mercadolivre.com.br", "www.mercadolivre.com.br:8443"),
                ml_link + "\n/r/x https://evil.com 302",
                ml_link + "x" * 1000, None,
                # achados do security-auditor
                ml_link + "&MATT_WORD=evil", ml_link + "&matt_word%00=evil",
                ml_link + "&matt_word=", ml_link + "&go=https://evil.com",
                ml_link.replace("matt_tool=123", "matt_tool=123&matt_tool=9"),
                "\x00" + ml_link, ml_link + "&ref=\x00", ml_link + "&ref=á",
                ml_link + "&&"):
        assert rejects({**ml, "ml_url": bad}), bad
    assert rejects({k: v for k, v in ml.items() if k != "ml_url"})
    # fail-closed fora do --dev
    saved = {k: os.environ.pop(k, None) for k in ("AMAZON_PARTNER_TAG", "ML_AFFILIATE_ID")}
    for env, doc in (({}, {}), ({"AMAZON_PARTNER_TAG": "minha-20", "ML_AFFILIATE_ID": "exemplo"}, {}),
                     ({"AMAZON_PARTNER_TAG": "minha-20", "ML_AFFILIATE_ID": "eu"}, {"_exemplo": True})):
        os.environ.update(env)
        try:
            require_prod(doc)
            raise AssertionError((env, doc))
        except Invalid:
            pass
    require_prod({})  # env real e dado real: passa
    for k, v in saved.items():
        os.environ.pop(k, None)
        if v is not None:
            os.environ[k] = v
    assert rejects({**good, "ml_url": ml_link})  # ml_url em oferta da Amazon
    # nicho: conjunto fechado (vira diretório)
    for bad in ("../evil", "Manga", "", None):
        assert rejects({**good, "genre": bad}), bad
    assert rejects({k: v for k, v in good.items() if k != "genre"})
    p = page(o, "manga")
    assert "B0ABCDEFGH" not in p and 'href="/r/livro-1"' in p and 'href="/r/livro-2"' not in p
    assert 'href="/manga/" aria-current="page"' in p
    # ASIN inválido / com URL injetada
    for bad in ("B0ABC", "b0abcdefgh", "B0ABCDEFGH\n", "B0ABCDEFGH?tag=evil-20",
                "../../evil", "x@evil.com/"):
        assert rejects({**good, "asin": bad}), bad
    assert rejects({**ml, "ml_item_id": "MLB1.evil.com"})
    # id usado no _redirects: injeção de linha / path
    for bad in ("x\n/r/y https://evil.com 302", "A", "a/b", "a b", "", "-a"):
        assert rejects({**good, "id": bad}), bad
    # campos extras (URL no JSON) e id da outra loja
    assert rejects({**good, "url": "https://evil.com"})
    assert rejects({**good, "ml_item_id": "MLB1"})
    # duplicado, dinheiro em float/bool, data, store
    assert rejects(good, good)
    assert rejects({**good, "price_cents": 19.9})
    assert rejects({**good, "price_cents": True})
    assert rejects({**good, "list_price_cents": 100})
    assert rejects({**good, "checked_at": "ontem"})
    assert rejects({**good, "checked_at": "2026-10-18T08:00:00"})
    assert rejects({**good, "store": "evil"})
    assert rejects({**good, "title": "<b>\x00</b>"})
    # allowlist de host
    for bad in ("https://evil.com/dp/X", "https://amazon.com.br.evil.com/",
                "https://www.amazon.com.br@evil.com/", "http://www.amazon.com.br/",
                "https://www.amazon.com.br/a b"):
        try:
            check_url(bad)
            raise AssertionError(bad)
        except Invalid:
            pass
    # tag via env
    saved = os.environ.get("AMAZON_PARTNER_TAG")
    os.environ["AMAZON_PARTNER_TAG"] = "x&evil=1"
    assert rejects(good)
    os.environ.pop("AMAZON_PARTNER_TAG")
    if saved is not None:
        os.environ["AMAZON_PARTNER_TAG"] = saved
    # escape no HTML
    xss = load_offers({"offers": [{**good, "title": '<script>alert(1)</script>"'}]})
    assert "<script>" not in page(xss) and "&lt;script&gt;" in page(xss)
    assert brl(123456) == "R$ 1.234,56" and brl(5) == "R$ 0,05"
    # selo de 90 dias: só com history_start cobrindo 90 dias (checked_at 18/10 BRT)
    def stamp(**kw):
        return page(load_offers({"offers": [{**good, **kw}]}))
    assert 'class="stamp' not in stamp()                                   # sem histórico
    assert "Menor preço desde 21/07" in stamp(history_start="2026-07-21")  # 89 dias
    assert "Menor preço em 90 dias" not in stamp(history_start="2026-07-21")
    assert "Menor preço em 90 dias" in stamp(history_start="2026-07-20")   # 90 dias
    assert 'class="stamp' not in stamp(history_start="2026-07-20", lowest_90d_cents=1000)
    for bad in ("2026-10-19", "20260720", "2026-02-30", "2026-07-20T00:00", 20260720):
        assert rejects({**good, "history_start": bad}), bad
    print("selftest ok")


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--selftest"]:
            selftest()
        else:
            build(dev=sys.argv[1:] == ["--dev"])
    except Invalid as err:
        sys.exit(f"build falhou: {err}")
