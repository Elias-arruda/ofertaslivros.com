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

ISBN_RE = re.compile(r"\d{9}[\dX]|\d{13}")
IMG_HOST = "http2.mlstatic.com"  # único host de foto liberado no img-src da CSP

BOOK_KEYS = {"id", "isbn", "genre", "title", "author", "image_url", "stores", "featured", "trending_rank"}
STORE_COMMON = {"store", "price_cents", "list_price_cents", "lowest_90d_cents", "history_since", "checked_at"}
# O link do ML é opaco (param ref cifrado), então vem do painel e é validado.
STORE_KEYS = {"amazon": {"asin"}, "mercadolivre": {"ml_url", "ml_product_id"}}

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


# Username de bot do Telegram: 5 a 32 chars, começa com letra, termina em "bot".
TG_BOT_RE = re.compile(r"[a-z][a-z0-9_]{1,28}bot", re.I)
TG_START_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")  # limite do ?start= do deep link


def tg_bot():
    """Opcional: sem TELEGRAM_BOT_USERNAME o site sai sem o botão de alerta."""
    v = os.environ.get("TELEGRAM_BOT_USERNAME", "").removeprefix("@")
    if v and not TG_BOT_RE.fullmatch(v):
        raise Invalid("TELEGRAM_BOT_USERNAME com formato inválido")
    return v or None


def tg_alert_url(bot, oid):
    if not TG_START_RE.fullmatch(oid):  # id até 80 no offers.json; o start aceita 64
        raise Invalid(f"id não cabe no deep link do Telegram: {oid!r}")
    return f"https://t.me/{bot}?start={oid}"


TG_CHANNEL_RE = re.compile(r"[a-z][a-z0-9_]{4,31}", re.I)  # @username público do canal
# ponytail: formato observado do id de Canal do WhatsApp (~24 alfanuméricos), sem spec oficial;
# ajustar a faixa se um id real falhar.
WA_CHANNEL_RE = re.compile(r"[A-Za-z0-9]{16,40}")


def channels():
    """[(nome, url)] dos canais definidos por env. Sem a env, o canal não aparece."""
    out = []
    tg = os.environ.get("TELEGRAM_CHANNEL_ID", "").removeprefix("@")
    if tg:
        if not TG_CHANNEL_RE.fullmatch(tg):
            raise Invalid("TELEGRAM_CHANNEL_ID precisa ser o @username público do canal")
        out.append(("Telegram", f"https://t.me/{tg}"))
    wa = os.environ.get("WHATSAPP_CHANNEL_ID", "")
    if wa:
        if not WA_CHANNEL_RE.fullmatch(wa):
            raise Invalid("WHATSAPP_CHANNEL_ID com formato inválido")
        out.append(("WhatsApp", f"https://whatsapp.com/channel/{wa}"))
    return out


def partner_tag():
    return _env_id("AMAZON_PARTNER_TAG", "exemplo-20")


def channel_tags():
    """Tag da Amazon por caminho do /r/. Sem AMAZON_TAG_TG/WA (ou vazias), usa a tag do site."""
    site = partner_tag()
    return {"": site, **{f"/{c}": _env_id(f"AMAZON_TAG_{c.upper()}", site)
                         if os.environ.get(f"AMAZON_TAG_{c.upper()}") else site
                         for c in ("tg", "wa")}}


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


def _date(v, k, dt):
    """Data AAAA-MM-DD opcional, não posterior ao dia (BRT) de dt."""
    if v is None:
        return None
    if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise Invalid(f"{k} precisa ser data AAAA-MM-DD: {v!r}")
    try:
        d = date.fromisoformat(v)
    except ValueError:
        raise Invalid(f"{k} inválida: {v!r}") from None
    if d > dt.astimezone(BRT).date():
        raise Invalid(f"{k} depois de checked_at")
    return d


def validate_store(s, tag, aff):
    if not isinstance(s, dict):
        raise Invalid("loja precisa ser objeto")
    store = s.get("store")
    if store not in STORE_KEYS:
        raise Invalid(f"store inválida: {store!r}")
    extra = set(s) - STORE_COMMON - STORE_KEYS[store]
    if extra:  # rejeita "url", "href", o id da outra loja etc.
        raise Invalid(f"{store}: campos não permitidos: {sorted(extra)}")
    out = {"store": store}
    if store == "amazon":
        asin = s.get("asin")
        if not isinstance(asin, str) or not ASIN_RE.fullmatch(asin):
            raise Invalid(f"asin inválido: {asin!r}")
        out["asin"] = asin
    else:
        pid = s.get("ml_product_id")  # opcional: o link vem do ml_url
        if pid is not None and (not isinstance(pid, str) or not MLB_RE.fullmatch(pid)):
            raise Invalid(f"ml_product_id inválido: {pid!r}")
        out["ml_product_id"] = pid
        out["ml_url"] = s.get("ml_url")  # validado em affiliate_url
    for k in ("price_cents", "list_price_cents", "lowest_90d_cents"):
        out[k] = _cents(s, k)
    if out["list_price_cents"] < out["price_cents"]:
        raise Invalid(f"{store}: list_price_cents menor que price_cents")
    ca = s.get("checked_at")
    try:
        dt = datetime.fromisoformat(ca.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise Invalid(f"checked_at não é ISO 8601: {ca!r}") from None
    if dt.tzinfo is None:
        raise Invalid("checked_at precisa ter fuso")
    out["checked_at"] = dt
    # Opcional: data (BRT) do 1º preço desta loja no histórico. Sem ela, nada de selo (CDC).
    out["history_since"] = _date(s.get("history_since"), "history_since", dt)
    out["url"] = affiliate_url(out, tag, aff)
    return out


def image_url(v, oid):
    """Foto opcional. Fora de https://http2.mlstatic.com, descarta com aviso (o card usa /capa.svg)."""
    if v is None:
        return None
    try:
        # Caracteres de URL do RFC 3986, sem aspas: vai num atributo src.
        ok = isinstance(v, str) and len(v) <= 1000 and re.fullmatch(r"[A-Za-z0-9\-._~:/?#\[\]@!$&()*+,;=%]+", v)
        p = urlsplit(v) if ok else None
    except ValueError:  # ex.: "https://[x"
        p = None
    if p and p.scheme == "https" and p.netloc == IMG_HOST and not p.fragment:
        return v
    print(f"aviso: {oid}: image_url descartada (só https://{IMG_HOST}): {v!r}", file=sys.stderr)
    return None


def validate_offer(o, tag, aff):
    """Um livro com 1 ou 2 lojas (contrato v2, docs/produto/comparacao-lojas.md)."""
    if not isinstance(o, dict):
        raise Invalid("oferta precisa ser objeto")
    extra = set(o) - BOOK_KEYS
    if extra:
        raise Invalid(f"campos não permitidos: {sorted(extra)}")
    if o.get("genre") not in GENRES:
        raise Invalid(f"genre inválido: {o.get('genre')!r} (use um de {sorted(GENRES)})")
    oid = o.get("id")
    if not isinstance(oid, str) or len(oid) > 80 or not ID_RE.fullmatch(oid):
        raise Invalid(f"id inválido: {oid!r}")
    isbn = o.get("isbn")
    if isbn is not None and (not isinstance(isbn, str) or not ISBN_RE.fullmatch(isbn)):
        raise Invalid(f"isbn precisa ter 10 ou 13 dígitos (X final no ISBN-10): {isbn!r}")
    stores = o.get("stores")
    if not isinstance(stores, list) or not 1 <= len(stores) <= 2:
        raise Invalid("stores precisa ter 1 ou 2 lojas")
    stores = [validate_store(s, tag, aff) for s in stores]
    if len({s["store"] for s in stores}) != len(stores):
        raise Invalid("stores com loja repetida")
    out = {"id": oid, "isbn": isbn, "genre": o["genre"], "title": _text(o, "title"),
           "author": _text(o, "author"), "image_url": image_url(o.get("image_url"), oid), "stores": stores}
    # Opcionais propostos ao back: curadoria manual e ranking de popularidade real.
    ft = o.get("featured", False)
    if type(ft) is not bool:
        raise Invalid(f"featured precisa ser true/false: {ft!r}")
    out["featured"] = ft
    tr = o.get("trending_rank")
    if tr is not None and (type(tr) is not int or tr < 1):  # type() exclui bool e float
        raise Invalid(f"trending_rank precisa ser inteiro >= 1: {tr!r}")
    out["trending_rank"] = tr
    return out


def load_books(doc):
    """Valida o documento inteiro; levanta Invalid na primeira falha."""
    if not isinstance(doc, dict) or type(doc.get("version")) is not int or doc["version"] != 2:
        raise Invalid('offers.json precisa ter "version": 2 (docs/produto/comparacao-lojas.md)')
    if not isinstance(doc.get("offers"), list):
        raise Invalid('JSON precisa ser {"version": 2, "offers": [...]}')
    tag, aff = partner_tag(), ml_affiliate()
    books, seen = [], set()
    for i, raw in enumerate(doc["offers"]):
        try:
            b = validate_offer(raw, tag, aff)
            if b["id"] in seen:
                raise Invalid(f"id duplicado: {b['id']!r}")
            seen.add(b["id"])
        except Invalid as e:
            raise Invalid(f"offers[{i}]: {e}") from None
        books.append(b)
    if not books:
        raise Invalid("nenhuma oferta")
    return books


# Prazo de frescor do preço (distribuicao-canais.md): loja mais velha sai da comparação.
FRESH = {"mercadolivre": timedelta(hours=2), "amazon": timedelta(hours=12)}
SKEW = timedelta(minutes=5)  # checked_at um pouco no futuro: relógio do coletor adiantado


def fresh(s, now):
    return -SKEW <= now - s["checked_at"] <= FRESH[s["store"]]


def seal_of(win, el):
    """("90d" | "since" | None, data do "desde"). Leitura estrita do contrato: o preço da
    vencedora precisa ser <= o mínimo de 90 dias de TODAS as lojas elegíveis, e todas
    precisam de 90 dias de histórico; sem isso não sabemos o mínimo da outra loja."""
    hs = [s["history_since"] for s in el]
    if None in hs or any(win["price_cents"] > s["lowest_90d_cents"] for s in el):
        return None, None
    if all((s["checked_at"].astimezone(BRT).date() - s["history_since"]).days >= 90 for s in el):
        return "90d", None
    return "since", max(hs)


def resolve(books, now):
    """Livro -> oferta exibida: campos do livro + os da loja vencedora, só com lojas no prazo.
    Vencedora: menor price_cents; no empate, a verificada mais recentemente."""
    out = []
    for b in books:
        el = [s for s in b["stores"] if fresh(s, now)]
        if not el:
            continue  # nenhuma loja no prazo: o livro sai da lista
        win = min(el, key=lambda s: (s["price_cents"], -s["checked_at"].timestamp()))
        seal, since = seal_of(win, el)
        out.append({**b, **win, "stores": el, "alt": next((s for s in el if s is not win), None),
                    "seal": seal, "since": since})
    if not out:
        raise Invalid("nenhuma oferta com preço dentro do prazo de frescor")
    return out


def load_offers(doc, now):
    return resolve(load_books(doc), now)


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
    return o["seal"]


def post_text(o, url):
    """Texto puro do post nos canais (sem parse_mode). url = nosso /r/<id>[/tg|/wa], nunca a da loja."""
    p = urlsplit(url)
    if (p.scheme != "https" or not p.hostname or p.hostname in ALLOWED_HOSTS
            or p.path not in {f"/r/{o['id']}", f"/r/{o['id']}/tg", f"/r/{o['id']}/wa"}
            or p.query or p.fragment):
        raise Invalid(f"post_text só aceita o /r/ do nosso domínio: {url!r}")
    _ascii(url)
    off = discount(o)
    price = brl(o["price_cents"]) + (f" (de {brl(o['list_price_cents'])}, -{off}%)" if off else "")
    lines = ["Menor preço em 90 dias"] if seal(o) == "90d" else []
    lines += [f"{o['title']}, de {o['author']}", price,
              f"{STORES[o['store']]} · preço verificado em {when(o['checked_at'])}. O preço final é o da loja.",
              f"Link de afiliado: {url}"]
    return "\n".join(lines)


def cover(o, i, text=True):
    """Capa tipográfica. A cor vem do índice da oferta, igual em todas as seções."""
    t = e(o["title"])
    spans = (f'\n      <span class="cover-t" aria-hidden="true">{t}</span>'
             f'\n      <span class="cover-a" aria-hidden="true">{e(o["author"])}</span>' if text else "")
    return (f'<div class="cover cover--{i % 6}{"" if text else " cover--sm"}">\n'
            f'      <img src="/capa.svg" alt="Capa ilustrativa de {t}" width="120" height="180" '
            f'loading="lazy" decoding="async">{spans}\n    </div>')


def price_html(o):
    off = discount(o)
    old = (f' <s class="old"><span class="sr">De </span>{brl(o["list_price_cents"])}</s>'
           f' <span class="off">−{off}%</span>' if off else "")
    return f'<span class="sr">Por </span><strong>{brl(o["price_cents"])}</strong>{old}'


def stamp_html(o):
    kind = seal(o)
    return ('<p class="stamp">Menor preço em 90 dias</p>' if kind == "90d" else
            f'<p class="stamp stamp--since">Menor preço desde {o["since"]:%d/%m}</p>'
            if kind == "since" else "")


def meta_html(o):
    return (f'<span class="store">{STORES[o["store"]]}</span>, verificado em '
            f'<time datetime="{e(o["checked_at"].isoformat())}">{when(o["checked_at"])}</time>')


def go(o, cls="go"):
    """Link de afiliado: sempre o nosso /r/<id>, nunca a URL da loja."""
    prep = "no" if o["store"] == "mercadolivre" else "na"
    return (f'<a class="{cls}" href="/r/{e(o["id"])}" rel="sponsored noopener noreferrer" target="_blank">'
            f'Ver {prep} {STORES[o["store"]]}<span class="sr">: {e(o["title"])} (abre em nova aba)</span></a>')


def card(o, i, bot=None, h=2):
    t = e(o["title"])
    stamp = "\n  " + stamp_html(o) if seal(o) else ""
    alert = (f' <a class="alert" href="{e(tg_alert_url(bot, o["id"]))}" rel="noopener noreferrer" target="_blank">'
             f'Me avise se baixar (Telegram)<span class="sr">: alerta de preço de {t} (abre o Telegram)</span></a>' if bot else "")
    return f"""<li class="card">
  <div class="top">
    {cover(o, i)}
    <div class="head">
      <h{h} class="title">{t}</h{h}>
      <p class="author">{e(o["author"])}</p>
    </div>
  </div>{stamp}
  <p class="price">{price_html(o)}</p>
  <p class="meta">{meta_html(o)}</p>
  <p class="acts">{go(o)}{alert}</p>
</li>"""


def slide(o, i, k, n):
    stamp = "\n    " + stamp_html(o) if seal(o) else ""
    return f"""<div class="slide" id="d-{e(o["id"])}" role="group" aria-roledescription="slide" aria-label="{k} de {n}">
  {cover(o, i)}
  <div class="slide-body">{stamp}
    <h3 class="slide-title">{e(o["title"])}</h3>
    <p class="author">{e(o["author"])}</p>
    <p class="price">{price_html(o)}</p>
    <p class="meta">{meta_html(o)}</p>
    <p class="acts">{go(o)}</p>
  </div>
</div>"""


def hero(items, idx):
    """Carrossel só com CSS: passagem por @keyframes, pausa (hover, foco, checkbox),
    manual com scroll-snap em prefers-reduced-motion ou depois de tocar num indicador."""
    n = len(items)
    if not 3 <= n <= 5:
        return ""
    slides = "\n".join(slide(o, idx[o["id"]], k, n) for k, o in enumerate(items, 1))
    dots = "".join(f'<li><a href="#d-{e(o["id"])}"><span class="sr">Mostrar destaque {k} de {n}: '
                   f'{e(o["title"])}</span></a></li>' for k, o in enumerate(items, 1))
    return f"""<section class="hero hero--{n}" aria-roledescription="carrossel" aria-labelledby="h-destaque">
<h2 class="sr" id="h-destaque">Em destaque</h2>
<div class="hero-view">
<div class="hero-track">
{slides}
</div>
</div>
<div class="hero-bar">
<ol class="dots">{dots}</ol>
<p class="pause"><input type="checkbox" id="pausar"><label for="pausar">Pausar passagem</label></p>
</div>
</section>"""


def mini(o, i):
    return f"""<li class="mini">
  {cover(o, i, text=False)}
  <div class="mini-body">
    <h3 class="mini-title">{e(o["title"])}</h3>
    <p class="price">{price_html(o)}</p>
    <p class="meta">{meta_html(o)}</p>
  </div>
  {go(o)}
</li>"""


def section(sid, title, body, intro=""):
    intro = f'\n<p class="sec-intro">{intro}</p>' if intro else ""
    return f'<section class="sec" aria-labelledby="{sid}">\n<h2 id="{sid}">{title}</h2>{intro}\n{body}\n</section>'


def join_banner(ch):
    """Banner dos canais. Sem TELEGRAM_CHANNEL_ID nem WHATSAPP_CHANNEL_ID, não sai."""
    if not ch:
        return ""
    links = "".join(f"<li>{ext(url, f'Canal no {name}')}</li>" for name, url in ch)
    return f"""<section class="join" aria-labelledby="h-canais">
<h2 id="h-canais">Receba as próximas ofertas</h2>
<p>As mesmas ofertas do site, com o preço conferido, chegam no canal. Sem cadastro.</p>
<ul class="join-links">{links}</ul>
</section>"""


def monitor(bot):
    """Explica o alerta de preço. Sem TELEGRAM_BOT_USERNAME, não sai."""
    if not bot:
        return ""
    cta = ext(f"https://t.me/{bot}", f"Abrir o @{e(bot)} no Telegram").replace("<a ", '<a class="alert alert--solid" ', 1)
    return section("h-alerta", "Crie um alerta de preço", f"""<ol class="steps">
<li>Escolha um livro e toque em “Me avise se baixar (Telegram)”.</li>
<li>No Telegram, toque em Iniciar. O bot confirma o alerta.</li>
<li>Quando o preço cair abaixo do de hoje, avisamos você por lá.</li>
</ol>
<p class="acts">{cta}</p>""",
                   "Escolha um livro e avisamos no Telegram quando o preço cair.")


HOME_GRID = 8  # cards em "Ofertas ativas"; o resto vai para "Mais livros"
HOT_MAX = 4


def ranked(offers):
    """Destaque: featured primeiro; sem ele, selo válido e depois o maior desconto."""
    return sorted(offers, key=lambda o: (not o["featured"], seal(o) is None, -discount(o)))


def home_sections(offers, bot=None, ch=()):
    """Seções da home. Um livro aparece em no máximo 2: banner + destaques,
    ou banner/ativas/mais livros + maiores descontos."""
    idx = {o["id"]: i for i, o in enumerate(offers)}
    top = ranked(offers)
    slides = top[:5] if len(top) >= 3 else []
    curated = any(o["featured"] for o in offers)
    feat = [o for o in top[:4] if o["featured"] or not curated]
    in_feat = {o["id"] for o in feat}
    rest = [o for o in offers if o["id"] not in in_feat]
    grid, more = rest[:HOME_GRID], rest[HOME_GRID:]
    # ponytail: "Mais livros" = ofertas da 9ª em diante; com data/catalog.json, pode virar os monitorados.
    in_hero = {o["id"] for o in slides}
    pool = [o for o in offers if o["id"] not in in_hero]
    if any(o["trending_rank"] for o in offers):  # popularidade real, vinda do back
        hot_title = "Em alta"
        hot = sorted((o for o in pool if o["trending_rank"]), key=lambda o: o["trending_rank"])[:HOT_MAX]
    else:  # sem dado de popularidade, título honesto
        hot_title = "Maiores descontos agora"
        hot = sorted((o for o in pool if discount(o) > 0), key=lambda o: -discount(o))[:HOT_MAX]

    def cards(items):
        return "\n".join(card(o, idx[o["id"]], bot, h=3) for o in items)

    def minis(items, tag="ul"):
        return f'<{tag} class="minis">\n' + "\n".join(mini(o, idx[o["id"]]) for o in items) + f"\n</{tag}>"

    parts = [
        hero(slides, idx),
        feat and section("h-curadoria", "Destaques da curadoria" if curated else "Destaques de hoje",
                         f'<ol class="grid grid--feat">\n{cards(feat)}\n</ol>',
                         "" if curated else "Primeiro os que estão no menor preço do histórico, depois os maiores descontos."),
        section("h-nichos", "Por tipo de livro", nav(offers, None)),
        grid and section("h-ativas", "Ofertas ativas", f'<ol class="grid">\n{cards(grid)}\n</ol>'),
        join_banner(ch),
        more and section("h-mais", "Mais livros em oferta", minis(more)),
        hot and section("h-alta", hot_title, minis(hot, "ol")),
        monitor(bot),
    ]
    return "\n".join(p for p in parts if p)


def nav(offers, current):
    present = [g for g in GENRES if any(o["genre"] == g for o in offers)]
    items = [("/", "Todos", current is None)] + [(f"/{g}/", GENRES[g], g == current) for g in present]
    current_attr = ' aria-current="page"'
    links = "".join(
        f'<li><a href="{href}"{current_attr if cur else ""}>{e(label)}</a></li>'
        for href, label, cur in items)
    return f'<nav class="nichos" aria-label="Nichos"><ul>{links}</ul></nav>'


def ext(href, label):
    return (f'<a href="{e(href)}" rel="noopener noreferrer" target="_blank">{label}'
            '<span class="sr"> (abre em nova aba)</span></a>')


def internal(href, label, here):
    cur = ' aria-current="page"' if href == here else ""
    return f'<a href="{href}"{cur}>{label}</a>'


def foot(ch, here=""):
    follow = ""
    if ch:
        links = " ou no ".join(ext(url, name) for name, url in ch)
        follow = f'\n  <p>Siga as ofertas no {links}. {internal("/canais/", "Sobre os canais", here)}</p>'
    return f"""<footer class="foot">
  <p>Como associado da Amazon, ganhamos com compras qualificadas. Também participamos do programa de afiliados do Mercado Livre. Preços verificados no horário indicado; o preço final é o da loja.</p>{follow}
  <p>{internal("/privacidade/", "Privacidade", here)}</p>
</footer>"""


def shell(title, desc, mast, body, ch=(), here=""):
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
{foot(ch, here)}
</body>
</html>
"""


def page(all_offers, genre=None, bot=None, ch=()):
    offers = [o for o in all_offers if genre is None or o["genre"] == genre]
    latest = max(o["checked_at"] for o in offers)
    cards = "\n".join(card(o, i, bot) for i, o in enumerate(offers))
    n = len(offers)
    head = (f'<p class="brand"><a href="/">Ofertas Livros</a></p>\n<h1>{e(GENRES[genre])}</h1>' if genre
            else '<h1><a href="/">Ofertas Livros</a></h1>')
    mast = f"""{head}
<p class="lede">Só entra aqui livro que baixou de preço de verdade. Conferimos cada um na loja e comparamos com o histórico de preço.</p>
<p class="status">Atualizado em {when(latest)}, {n} {"oferta" if n == 1 else "ofertas"}.</p>
{nav(all_offers, genre)}"""
    title = (f"{e(GENRES[genre])}: ofertas de livros" if genre
             else "Ofertas Livros: descontos de livros conferidos na loja")
    desc = (f"{e(GENRES[genre])} em oferta" if genre else "Ofertas de livros") + (
        " na Amazon e no Mercado Livre, conferidas uma a uma e comparadas com o histórico de preço.")
    if genre is None:
        mast = mast.replace(f"\n{nav(all_offers, genre)}", "")  # na home, os nichos viram a seção 3
        return shell(title, desc, mast, home_sections(offers, bot, ch), ch)
    return shell(title, desc, mast, f'<ol class="grid">\n{cards}\n</ol>', ch)


def privacy(bot=None, ch=()):
    bot_name = (f'o bot <a href="https://t.me/{e(bot)}" rel="noopener noreferrer" target="_blank">@{e(bot)}</a>'
                if bot else "o nosso bot")
    mast = '<p class="brand"><a href="/">Ofertas Livros</a></p>\n<h1>Privacidade</h1>'
    body = f"""<article class="doc">
<h2>No site</h2>
<p>O site não tem cadastro, cookies, scripts nem ferramentas de análise. Ele é hospedado na Cloudflare, que recebe os dados técnicos de cada acesso (como o endereço IP) para entregar as páginas.</p>
<p>Ao clicar em uma oferta, você vai para a Amazon ou para o Mercado Livre. A partir daí valem as políticas de privacidade de cada loja.</p>
<h2>No alerta de preço do Telegram</h2>
<p>Quando você pede um alerta para {bot_name}, guardamos só o necessário para avisar você:</p>
<ul>
<li>o identificador da conversa com o bot no Telegram (chat_id);</li>
<li>o livro e o preço-alvo do alerta;</li>
<li>a data de criação e a data de expiração.</li>
</ul>
<p>Não guardamos seu nome, seu nome de usuário, seu telefone nem o texto das suas mensagens.</p>
<h2>Onde fica</h2>
<p>Num banco de dados Cloudflare D1, fora do código do site e sem acesso público. A Cloudflare opera esse banco para nós.</p>
<h2>Por quanto tempo</h2>
<p>Até o alerta disparar (ele é apagado quando a mensagem é enviada) ou por no máximo 90 dias, o que vier primeiro. Não guardamos histórico de alertas enviados.</p>
<h2>Como apagar</h2>
<ul>
<li><code>/remover</code> seguido do livro apaga um alerta;</li>
<li><code>/parar</code> apaga todos os seus dados;</li>
<li>bloquear o bot também apaga todos os seus dados.</li>
</ul>
</article>"""
    return shell("Privacidade: Ofertas Livros",
                 "O que o Ofertas Livros guarda, onde, por quanto tempo e como apagar.", mast, body, ch, "/privacidade/")


def canais(ch, bot=None):
    desc = {"Telegram": "as ofertas chegam assim que são publicadas, até 8 por dia, das 8h às 22h.",
            "WhatsApp": "um resumo por dia com até 5 ofertas."}
    items = "\n".join(f"<li>{ext(url, f'Canal no {name}')}: {desc[name]}</li>" for name, url in ch)
    alert = (f'<p>Quer saber de um livro só? Peça um alerta de preço ao {ext(f"https://t.me/{bot}", "@" + e(bot))} '
             'ou toque em “Me avise se baixar” na oferta.</p>' if bot else "")
    mast = '<p class="brand"><a href="/">Ofertas Livros</a></p>\n<h1>Canais</h1>'
    body = f"""<article class="doc">
<p>Os canais repetem as ofertas do site, com preço conferido e o horário da verificação. São só de leitura e não pedem cadastro.</p>
<ul>
{items}
</ul>
{alert}
<p>Os links dos canais são de afiliado: ganhamos com compras qualificadas, e o preço final é o da loja.</p>
</article>"""
    return shell("Canais: Ofertas Livros", "Siga as ofertas de livros no Telegram e no WhatsApp.", mast, body, ch, "/canais/")


MAX_REDIRECTS = 2000  # limite de regras estáticas do _redirects na Cloudflare


def redirects(offers):
    """Por livro: /r/<id> e /r/<id>/tg|wa (vencedora, com a tag do canal se for a Amazon) e
    /r/<id>/<loja> para cada loja elegível. Vencido ou loja fora do prazo cai na home pelo curinga.
    Até 5 regras por livro: cabem 399 livros com duas lojas (1.995 + curinga)."""
    tags, aff = channel_tags(), ml_affiliate()
    lines = []
    for o in offers:
        lines.append(f"/r/{o['id']} {affiliate_url(o, tags[''], aff)} 302\n")
        lines += [f"/r/{o['id']}/{s['store']} {affiliate_url(s, tags[''], aff)} 302\n" for s in o["stores"]]
        lines += [f"/r/{o['id']}{sfx} {affiliate_url(o, tags[sfx], aff)} 302\n" for sfx in ("/tg", "/wa")]  # ML: mesmo ml_url
    lines.append("/r/* / 302\n")
    if len(lines) > MAX_REDIRECTS:
        raise Invalid(f"{len(lines)} regras no _redirects (máximo {MAX_REDIRECTS})")
    return "".join(lines)


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
    books = load_books(doc)
    # ponytail: no --dev, "agora" é o checked_at mais recente do arquivo, para a demo não
    # esvaziar com dado parado; o deploy usa o relógio real.
    now = (max(s["checked_at"] for b in books for s in b["stores"]) if dev
           else datetime.now(timezone.utc))
    offers = resolve(books, now)
    bot, ch = tg_bot(), channels()
    # tudo validado e renderizado antes de tocar no dist/
    pages = {"index.html": page(offers, bot=bot, ch=ch), "privacidade/index.html": privacy(bot, ch)}
    for g in {o["genre"] for o in offers}:
        pages[f"{g}/index.html"] = page(offers, g, bot, ch)
    if ch:
        pages["canais/index.html"] = canais(ch, bot)
    rules = redirects(offers)
    shutil.rmtree(DIST, ignore_errors=True)
    shutil.copytree(STATIC, DIST)
    for path, body in pages.items():
        (DIST / path).parent.mkdir(exist_ok=True)
        (DIST / path).write_text(body, encoding="utf-8")
    (DIST / "_redirects").write_text(rules, encoding="utf-8")
    (DIST / "_headers").write_text(HEADERS, encoding="utf-8")
    print(f"ok: {len(offers)} ofertas ({len(books) - len(offers)} fora do prazo), "
          f"{len(pages)} páginas -> {DIST}")


def selftest():
    aff = ml_affiliate()
    ml_link = (f"https://www.mercadolivre.com.br/social/{aff}?matt_word={aff}"
               "&matt_tool=123&forceInApp=true&ref=AbC%2Fd%3D%3D")
    NOW = datetime(2026, 10, 18, 9, 0, tzinfo=BRT)  # relógio fixo
    amz = {"store": "amazon", "asin": "B0ABCDEFGH", "price_cents": 1990, "list_price_cents": 3990,
           "lowest_90d_cents": 1990, "checked_at": "2026-10-18T08:00:00-03:00"}
    mls = {**amz, "store": "mercadolivre", "ml_product_id": "MLB123", "ml_url": ml_link}
    del mls["asin"]
    good = {"id": "livro-1", "genre": "manga", "title": "T", "author": "A", "stores": [amz]}
    ml = {**good, "id": "livro-2", "genre": "ficcao", "stores": [mls]}

    def A(**kw):  # livro-1 só na Amazon, loja alterada
        return {**good, "stores": [{**amz, **kw}]}

    def M(**kw):  # livro-2 só no ML, loja alterada
        return {**ml, "stores": [{**mls, **kw}]}

    def load(*books, now=NOW):
        return load_offers({"version": 2, "offers": list(books)}, now)

    def rejects(*books, doc=None):
        try:
            load_books(doc if doc is not None else {"version": 2, "offers": list(books)})
        except Invalid:
            return True
        return False

    o = load(good, ml)
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
        assert rejects(M(ml_url=bad)), bad
    assert rejects({**ml, "stores": [{k: v for k, v in mls.items() if k != "ml_url"}]})
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
    assert rejects(A(ml_url=ml_link))  # ml_url na loja Amazon
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
        assert rejects(A(asin=bad)), bad
    for bad in ("MLB1.evil.com", "mlb1", "MLB", 123, ""):
        assert rejects(M(ml_product_id=bad)), bad
    assert load({**ml, "stores": [{k: v for k, v in mls.items() if k != "ml_product_id"}]})  # opcional
    # id usado no _redirects: injeção de linha / path
    for bad in ("x\n/r/y https://evil.com 302", "A", "a/b", "a b", "", "-a"):
        assert rejects({**good, "id": bad}), bad
    # campos extras (URL no JSON) e id da outra loja
    assert rejects({**good, "url": "https://evil.com"}) and rejects(A(url="https://evil.com"))
    assert rejects(A(ml_product_id="MLB1")) and rejects(A(ml_item_id="MLB1"))
    # duplicado, dinheiro em float/bool, data, store
    assert rejects(good, good)
    assert rejects(A(price_cents=19.9))
    assert rejects(A(price_cents=True))
    assert rejects(A(list_price_cents=100))
    assert rejects(A(checked_at="ontem"))
    assert rejects(A(checked_at="2026-10-18T08:00:00"))
    assert rejects(A(store="evil"))
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
    xss = load({**good, "title": '<script>alert(1)</script>"'})
    assert "<script>" not in page(xss) and "&lt;script&gt;" in page(xss)
    # botão de alerta: só com TELEGRAM_BOT_USERNAME válido
    assert "t.me" not in page(o) and 'class="alert"' not in page(o)
    pb = page(o, bot="OfertasLivrosBot")
    assert ('<a class="alert" href="https://t.me/OfertasLivrosBot?start=livro-1" '
            'rel="noopener noreferrer" target="_blank">Me avise se baixar') in pb
    assert pb.count("?start=") == 2  # um botão por card; o bloco de alerta usa t.me/<bot> sem start
    pb = page(xss, bot="OfertasLivrosBot")
    assert "<script>" not in pb and "alerta de preço de &lt;script&gt;" in pb
    saved = os.environ.pop("TELEGRAM_BOT_USERNAME", None)
    assert tg_bot() is None
    for ok in ("OfertasLivrosBot", "@abc_bot", "x1BOT"):
        os.environ["TELEGRAM_BOT_USERNAME"] = ok
        assert tg_bot() == ok.removeprefix("@")
    for bad in ("Ofertas", "bot", "1abcbot", "a" * 30 + "bot", "ab-cbot", "x.bot\n",
                'a"onbot', "abcbot?x=1"):
        os.environ["TELEGRAM_BOT_USERNAME"] = bad
        try:
            tg_bot()
            raise AssertionError(bad)
        except Invalid:
            pass
    os.environ.pop("TELEGRAM_BOT_USERNAME")
    if saved is not None:
        os.environ["TELEGRAM_BOT_USERNAME"] = saved
    try:
        tg_alert_url("OfertasLivrosBot", "a" * 65)
        raise AssertionError("id longo")
    except Invalid:
        pass
    # privacidade: linkada no rodapé de todas as páginas
    assert '<a href="/privacidade/">Privacidade</a>' in page(o)
    assert '<a href="/privacidade/" aria-current="page">' in privacy()
    pv = privacy("OfertasLivrosBot")
    assert all(w in pv for w in ("chat_id", "Cloudflare D1", "90 dias", "/parar", "bloquear o bot",
                                 "https://t.me/OfertasLivrosBot"))
    # _redirects: 4 linhas por livro de uma loja + curinga; tag da Amazon por canal
    saved = {k: os.environ.pop(k, None) for k in ("AMAZON_TAG_TG", "AMAZON_TAG_WA")}
    r = redirects(o).splitlines()
    t = partner_tag()
    assert len(r) == 9 and r[-1] == "/r/* / 302"
    assert f"/r/livro-1/amazon https://www.amazon.com.br/dp/B0ABCDEFGH?tag={t} 302" in r
    assert f"/r/livro-2/mercadolivre {ml_link} 302" in r
    assert not any("/r/livro-1/mercadolivre" in x or "/r/livro-2/amazon" in x for x in r)
    assert f"/r/livro-1/tg https://www.amazon.com.br/dp/B0ABCDEFGH?tag={t} 302" in r
    assert f"/r/livro-2/wa {ml_link} 302" in r and f"/r/livro-2 {ml_link} 302" in r
    os.environ.update(AMAZON_TAG_TG="sitetg-20", AMAZON_TAG_WA="")
    r = redirects(o).splitlines()
    assert "/r/livro-1/tg https://www.amazon.com.br/dp/B0ABCDEFGH?tag=sitetg-20 302" in r
    assert f"/r/livro-1/wa https://www.amazon.com.br/dp/B0ABCDEFGH?tag={t} 302" in r
    # duas lojas: vencedora no /r/<id>, /tg e /wa; uma rota por loja; tag do canal só na Amazon
    two = {**good, "id": "duas", "stores": [{**amz, "price_cents": 1890}, mls]}
    r = redirects(load(two)).splitlines()
    amz_url = "https://www.amazon.com.br/dp/B0ABCDEFGH?tag="
    assert r == [f"/r/duas {amz_url}{t} 302", f"/r/duas/amazon {amz_url}{t} 302",
                 f"/r/duas/mercadolivre {ml_link} 302", f"/r/duas/tg {amz_url}sitetg-20 302",
                 f"/r/duas/wa {amz_url}{t} 302", "/r/* / 302"]
    r = redirects(load({**two, "stores": [amz, {**mls, "price_cents": 1890}]})).splitlines()
    assert f"/r/duas {ml_link} 302" in r and f"/r/duas/tg {ml_link} 302" in r
    assert f"/r/duas/amazon {amz_url}{t} 302" in r                        # loja da seta, tag do site
    r = redirects(load(two, now=datetime(2026, 10, 18, 10, 31, tzinfo=BRT))).splitlines()
    assert "/r/duas/mercadolivre" not in "\n".join(r) and len(r) == 5      # ML fora do prazo: sem rota
    for bad in ("x&tag=evil", "a b", "x\n/r/y https://evil.com 302"):
        os.environ["AMAZON_TAG_TG"] = bad
        try:
            redirects(o)
            raise AssertionError(bad)
        except Invalid:
            pass
    for k, v in saved.items():
        os.environ.pop(k, None)
        if v is not None:
            os.environ[k] = v
    many = [{**good, "id": f"l-{n}", "stores": [amz, mls]} for n in range(400)]
    try:
        redirects(load(*many))  # 400 x 5 + curinga = 2.001
        raise AssertionError("limite do _redirects")
    except Invalid:
        pass
    assert len(redirects(load(*many[:399])).splitlines()) == 1996
    # canais: só com a env; validados; rel noopener noreferrer
    saved = {k: os.environ.pop(k, None) for k in ("TELEGRAM_CHANNEL_ID", "WHATSAPP_CHANNEL_ID")}
    assert channels() == [] and "/canais/" not in page(o)
    os.environ.update(TELEGRAM_CHANNEL_ID="@ofertaslivros", WHATSAPP_CHANNEL_ID="0029VaAbCdEfGhIjKlMnOp12")
    ch = channels()
    assert ch == [("Telegram", "https://t.me/ofertaslivros"),
                  ("WhatsApp", "https://whatsapp.com/channel/0029VaAbCdEfGhIjKlMnOp12")]
    for html_ in (page(o, ch=ch), canais(ch, "OfertasLivrosBot")):
        assert ('<a href="https://t.me/ofertaslivros" rel="noopener noreferrer" target="_blank">' in html_
                and 'href="https://whatsapp.com/channel/0029VaAbCdEfGhIjKlMnOp12" rel="noopener noreferrer"' in html_)
    assert '<a href="/canais/">' in page(o, ch=ch)
    for k, bad in (("TELEGRAM_CHANNEL_ID", "-1001234567890"), ("TELEGRAM_CHANNEL_ID", "@a/b"),
                   ("TELEGRAM_CHANNEL_ID", "abc"), ("WHATSAPP_CHANNEL_ID", "0029Va/../evil"),
                   ("WHATSAPP_CHANNEL_ID", "https://evil.com")):
        os.environ[k] = bad
        try:
            channels()
            raise AssertionError(bad)
        except Invalid:
            pass
        os.environ.update(TELEGRAM_CHANNEL_ID="@ofertaslivros", WHATSAPP_CHANNEL_ID="0029VaAbCdEfGhIjKlMnOp12")
    for k, v in saved.items():
        os.environ.pop(k, None)
        if v is not None:
            os.environ[k] = v
    # texto do post: mesmo brl/when/desconto/selo do card
    torto = load({**good, "title": "Torto Arado", "author": "Itamar Vieira Junior",
                  "stores": [{**amz, "price_cents": 4290, "list_price_cents": 7490, "lowest_90d_cents": 4590,
                              "checked_at": "2026-10-18T08:47:00-03:00", "history_since": "2026-06-01"}]})[0]
    nb = "\u00a0"
    assert post_text(torto, "https://ofertaslivros.com/r/livro-1/tg") == (
        "Menor preço em 90 dias\nTorto Arado, de Itamar Vieira Junior\n"
        f"R${nb}42,90 (de R${nb}74,90, -42%)\n"
        "Amazon · preço verificado em 18/10 às 08h47. O preço final é o da loja.\n"
        "Link de afiliado: https://ofertaslivros.com/r/livro-1/tg")
    plain = post_text({**torto, "seal": None, "list_price_cents": 4290}, "https://x.com/r/livro-1")
    assert plain.splitlines()[:2] == ["Torto Arado, de Itamar Vieira Junior", f"R${nb}42,90"]
    assert "Menor preço" not in post_text({**torto, "seal": "since"}, "https://x.com/r/livro-1")
    for bad in ("https://www.amazon.com.br/r/livro-1", "http://x.com/r/livro-1", "https://x.com/r/outro",
                "https://x.com/r/livro-1?u=https://evil.com", "https://x.com/r/livro-1/tg\nhttps://evil.com"):
        try:
            post_text(torto, bad)
            raise AssertionError(bad)
        except Invalid:
            pass
    assert brl(123456) == "R$ 1.234,56" and brl(5) == "R$ 0,05"
    # selo de 90 dias: só com history_since cobrindo 90 dias (checked_at 18/10 BRT)
    def stamp(**kw):
        return page(load(A(**kw)))
    assert 'class="stamp' not in stamp()                                   # sem histórico
    assert "Menor preço desde 21/07" in stamp(history_since="2026-07-21")  # 89 dias
    assert "Menor preço em 90 dias" not in stamp(history_since="2026-07-21")
    assert "Menor preço em 90 dias" in stamp(history_since="2026-07-20")   # 90 dias
    assert 'class="stamp' not in stamp(history_since="2026-07-20", lowest_90d_cents=1000)
    for bad in ("2026-10-19", "20260720", "2026-02-30", "2026-07-20T00:00", 20260720):
        assert rejects(A(history_since=bad)), bad
    assert rejects({**good, "history_start": "2026-07-01"})  # campo da proposta antiga, substituído
    # campos novos: tipo errado quebra o build
    for bad in ("true", 1, 0, None, "sim"):
        assert rejects({**good, "featured": bad}), bad
    for bad in (0, -1, True, 1.0, "1"):
        assert rejects({**good, "trending_rank": bad}), bad
    assert load({**good, "featured": True, "trending_rank": 3})[0]["trending_rank"] == 3
    # home: seções, carrossel sem JS, fallbacks honestos
    def offers_n(n, extra=None, store=None):
        return load(*({**good, "id": f"l-{k}", "title": f"Livro {k}", **(extra or {}).get(k, {}),
                       "stores": [{**amz, "price_cents": 4000 - 100 * k, "list_price_cents": 4000,
                                   **(store or {}).get(k, {})}]} for k in range(n)))
    saved = {k: os.environ.pop(k, None) for k in ("TELEGRAM_CHANNEL_ID", "WHATSAPP_CHANNEL_ID")}
    h = page(offers_n(14))
    assert "<script" not in h and h.count('aria-roledescription="slide"') == 5
    assert '<input type="checkbox" id="pausar"><label for="pausar">Pausar passagem</label>' in h
    assert "Destaques de hoje" in h and "Destaques da curadoria" not in h
    assert "Maiores descontos agora" in h and "Em alta" not in h        # sem trending_rank
    assert "Mais livros em oferta" in h and 'href="/manga/"' in h
    assert 'class="join"' not in h and "Crie um alerta" not in h         # sem canais nem bot
    assert max(h.count(f'href="/r/l-{k}"') for k in range(14)) <= 2      # no máximo 2 seções
    # fallback do destaque: selo válido antes do maior desconto (l-13 tem o maior)
    h = page(offers_n(10, store={2: {"history_since": "2026-06-01", "lowest_90d_cents": 3800}}))
    assert h.index('id="d-l-2"') < h.index('id="d-l-9"')
    assert "Mais livros" not in h                                        # sobram 6 para a grade
    h = page(offers_n(10, {7: {"featured": True}, 0: {"trending_rank": 2}, 1: {"trending_rank": 1}}))
    assert "Destaques da curadoria" in h and h.index('id="d-l-7"') < h.index('id="d-l-9"')
    sec = h[h.index('id="h-curadoria"'):h.index('id="h-nichos"')]
    assert sec.count('class="card"') == 1                               # só o curado
    alta = h[h.index("Em alta"):]
    assert alta.index('href="/r/l-1"') < alta.index('href="/r/l-0"')    # ordem do trending_rank
    h = page(offers_n(2), bot="OfertasLivrosBot", ch=[("Telegram", "https://t.me/ofertaslivros")])
    assert "carrossel" not in h                                          # menos de 3: sem banner
    assert 'class="join"' in h and "Receba as próximas ofertas" in h
    assert 'href="https://t.me/OfertasLivrosBot" rel="noopener noreferrer"' in h  # bloco de alerta, sem start
    g = page(offers_n(4), "manga")
    assert "carrossel" not in g and 'href="/manga/" aria-current="page"' in g
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
    # contrato v2: version, stores, isbn, image_url
    for d in ({"offers": [good]}, {"version": 1, "offers": [good]}, {"version": "2", "offers": [good]},
              {"version": 2.0, "offers": [good]}, {"version": True, "offers": [good]}, {"version": 2}, []):
        assert rejects(doc=d), d
    for bad in ([], [amz, mls, {**amz, "asin": "B0ABCDEFGJ"}], [amz, {**amz, "asin": "B0ABCDEFGJ"}],
                [mls, mls], [{**amz, "store": "americanas"}], [{**amz, "store": None}], None, amz, ["amazon"]):
        assert rejects({**good, "stores": bad}), bad
    assert len(load({**good, "stores": [amz, mls]})[0]["stores"]) == 2
    for ok in ("9788550807560", "8535902775", "853590277X"):
        assert load({**good, "isbn": ok})[0]["isbn"] == ok
    for bad in ("978855080756", "97885508075600", "853590277x", "X535902775", "978-8550807560",
                9788550807560, "9788550807560\n", ""):
        assert rejects({**good, "isbn": bad}), bad
    img = "https://http2.mlstatic.com/D_NQ_NP_123-MLA456-O.webp"
    assert load({**good, "image_url": img})[0]["image_url"] == img
    import contextlib
    import io
    for bad in ("http://http2.mlstatic.com/a.jpg", "https://evil.mlstatic.com/a.jpg",
                "https://http2.mlstatic.com.evil.com/a.jpg", "https://x@http2.mlstatic.com/a.jpg",
                "https://http2.mlstatic.com:8443/a.jpg", "https://HTTP2.mlstatic.com/a.jpg",
                "https://http2.mlstatic.com/a b.jpg", 'https://http2.mlstatic.com/a"onerror=x',
                "javascript:alert(1)", "https://[x", "//http2.mlstatic.com/a.jpg", 123, ""):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            assert load({**good, "image_url": bad})[0]["image_url"] is None, bad  # descarta, não quebra
        assert "image_url descartada" in err.getvalue(), bad
    # vencedora: menor preço; empate -> verificada mais recentemente
    a8, m8 = {**amz, "checked_at": "2026-10-18T08:00:00-03:00"}, {**mls, "checked_at": "2026-10-18T08:30:00-03:00"}
    def win(*stores, now=NOW):
        r = load({**good, "stores": list(stores)}, now=now)
        return r and r[0]["store"]
    assert win({**a8, "price_cents": 1890}, m8) == "amazon"
    assert win(a8, {**m8, "price_cents": 1890}) == "mercadolivre"
    assert win(a8, m8) == "mercadolivre"                                  # empate: ML verificado 08:30
    assert win({**a8, "checked_at": "2026-10-18T08:45:00-03:00"}, m8) == "amazon"
    r = load({**good, "stores": [a8, {**m8, "price_cents": 2190, "list_price_cents": 2490}]})[0]
    assert r["alt"]["store"] == "mercadolivre" and discount(r) == 50      # desconto da vencedora (1990/3990)
    r = load({**good, "stores": [{**a8, "price_cents": 2490}, {**m8, "list_price_cents": 2490}]})[0]
    assert r["store"] == "mercadolivre" and discount(r) == 20             # 1990 sobre 2490
    # frescor por loja, com o relógio injetado: ML até 2 h, Amazon até 12 h
    ml_cheap = {**m8, "price_cents": 990}
    assert win(a8, ml_cheap, now=datetime(2026, 10, 18, 10, 30, tzinfo=BRT)) == "mercadolivre"  # 2 h
    r = load({**good, "stores": [a8, ml_cheap]}, now=datetime(2026, 10, 18, 10, 31, tzinfo=BRT))[0]
    assert r["store"] == "amazon" and r["alt"] is None and len(r["stores"]) == 1  # ML velho saiu
    assert win(a8, now=datetime(2026, 10, 18, 20, 0, tzinfo=BRT)) == "amazon"     # 12 h
    late = datetime(2026, 10, 18, 20, 1, tzinfo=BRT)
    assert [x["id"] for x in load(good, M(checked_at="2026-10-18T19:00:00-03:00"), now=late)] == ["livro-2"]
    try:
        load(good, now=late)  # nenhum livro elegível
        raise AssertionError("lista vazia")
    except Invalid:
        pass
    assert load(A(checked_at="2026-10-18T09:04:00-03:00"))                 # 4 min no futuro: tolerado
    try:
        load(A(checked_at="2026-10-18T09:06:00-03:00"))
        raise AssertionError("futuro")
    except Invalid:
        pass
    # selo estrito: 90 dias em TODAS as lojas elegíveis e preço <= o mínimo de todas
    def seal_two(a, m):
        r = load({**good, "stores": [{**a8, **a}, {**m8, "price_cents": 2490, **m}]})[0]
        return r["seal"], r["since"]
    h90, h89 = "2026-07-20", "2026-07-21"
    assert seal_two({"history_since": h90}, {"history_since": h90}) == ("90d", None)
    assert seal_two({"history_since": h90}, {"history_since": h89}) == ("since", date(2026, 7, 21))
    assert seal_two({"history_since": h90}, {"history_since": "2026-10-10"}) == ("since", date(2026, 10, 10))
    assert seal_two({"history_since": h90}, {}) == (None, None)            # outra loja sem histórico
    assert seal_two({"history_since": h90}, {"history_since": h90, "lowest_90d_cents": 1890}) == (None, None)
    # loja velha não conta no selo
    r = load({**good, "stores": [{**a8, "history_since": h90}, {**m8, "price_cents": 2490}]},
             now=datetime(2026, 10, 18, 11, 0, tzinfo=BRT))[0]
    assert r["seal"] == "90d" and len(r["stores"]) == 1
    print("selftest ok")


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--selftest"]:
            selftest()
        else:
            build(dev=sys.argv[1:] == ["--dev"])
    except Invalid as err:
        sys.exit(f"build falhou: {err}")
