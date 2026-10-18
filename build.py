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

BOOK_KEYS = {"id", "isbn", "genre", "title", "author", "image_url", "stores", "featured", "trending_rank",
             "blurb"}  # blurb: opcional, proposto ao contrato (frase curta da curadoria no banner)
BLURB_MAX = 140
STORE_COMMON = {"store", "price_cents", "list_price_cents", "lowest_90d_cents", "history_since", "checked_at",
                "price_points"}  # price_points: opcional, proposto ao contrato (gráfico do histórico)
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
    out["price_points"] = price_points(s.get("price_points"), out)
    out["url"] = affiliate_url(out, tag, aff)
    return out


MAX_POINTS = 90


def price_points(v, s):
    """Série opcional [{"date", "price_cents"}] -> [(date, cents)]. Estrita: até 90 pontos, datas
    crescentes entre history_since e o dia do checked_at, e nada abaixo do lowest_90d_cents
    dentro da janela (o gráfico não pode contradizer o selo)."""
    if v is None:
        return []
    k = f"{s['store']}.price_points"
    if not isinstance(v, list) or len(v) > MAX_POINTS:
        raise Invalid(f"{k} precisa ser lista com até {MAX_POINTS} pontos")
    if v and s["history_since"] is None:
        raise Invalid(f"{k} sem history_since")
    day, out = s["checked_at"].astimezone(BRT).date(), []
    for pt in v:
        if not isinstance(pt, dict) or set(pt) != {"date", "price_cents"}:
            raise Invalid(f'{k}: cada ponto é {{"date", "price_cents"}}: {pt!r}')
        d = _date(pt["date"], f"{k}.date", s["checked_at"])
        if d is None or d < s["history_since"]:
            raise Invalid(f"{k}: data antes do history_since ou vazia: {pt!r}")
        if out and d <= out[-1][0]:
            raise Invalid(f"{k}: datas precisam ser crescentes, sem repetir: {pt!r}")
        c = _cents(pt, "price_cents")
        if (day - d).days < 90 and c < s["lowest_90d_cents"]:
            raise Invalid(f"{k}: ponto abaixo do lowest_90d_cents: {pt!r}")
        out.append((d, c))
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
    bl = o.get("blurb")
    if bl is not None and (not isinstance(bl, str) or not bl.strip() or len(bl.strip()) > BLURB_MAX
                           or CTRL_RE.search(bl)):
        raise Invalid(f"blurb precisa ser texto de 1 a {BLURB_MAX} chars, sem controle: {bl!r}")
    out["blurb"] = bl and bl.strip()
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
                    "seal": seal, "since": since, "now": now})  # now: relógio do build, para o "visto hoje"
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
              f"{STORES[o['store']]} · preço verificado em {when(o['checked_at'])}. O preço final é o da loja."]
    a = o["alt"]
    if a and a["price_cents"] * 10 <= o["price_cents"] * 11:  # outra loja até 10% mais cara; sem link
        lines.append(f"Também {na(a['store'])} por {brl(a['price_cents'])}")
    lines.append(f"Link de afiliado: {url}")
    return "\n".join(lines)


def cover(o, small=False, eager=False):
    """Foto real do ML num quadro 2:3 neutro (object-fit: contain). Sem foto, um placeholder sóbrio
    que não finge ser capa: carimbo pequeno + título discreto (decorativo, o título está ao lado)."""
    cls = "cover cover--sm" if small else "cover"
    load = 'loading="eager" fetchpriority="high"' if eager else 'loading="lazy"'
    if o["image_url"]:
        return (f'<div class="{cls} cover--photo">\n'
                f'      <img src="{e(o["image_url"])}" alt="Capa de {e(o["title"])}, de {e(o["author"])}" '
                f'width="120" height="180" {load} decoding="async">\n    </div>')
    title = "" if small else f'\n      <span class="cover-t" aria-hidden="true">{e(o["title"])}</span>'
    return (f'<div class="{cls} cover--none">\n'
            f'      <img src="/capa.svg" alt="" width="120" height="180" {load} decoding="async">{title}\n    </div>')


def price_html(o):
    off = discount(o)
    old = (f' <s class="old"><span class="sr">De </span>{brl(o["list_price_cents"])}</s>'
           f' <span class="off">−{off}%</span>' if off else "")
    return f'<span class="sr">Por </span><strong>{brl(o["price_cents"])}</strong>{old}'


def stamp_html(o):
    """Pílula vermelha cheia (90 dias reais) ou contorno ("desde"), sempre logo acima do preço."""
    kind = seal(o)
    return ('<p class="stamp">Menor preço em 90 dias</p>' if kind == "90d" else
            f'<p class="stamp stamp--since">Menor preço desde {o["since"]:%d/%m}</p>'
            if kind == "since" else "")


def deal(o, pad="      "):
    """Selo colado ao preço: os dois num bloco só, na mesma ordem em todo lugar."""
    stamp = stamp_html(o)
    stamp = f"\n{pad}  {stamp}" if stamp else ""
    return f'<div class="deal">{stamp}\n{pad}  <p class="price">{price_html(o)}</p>\n{pad}</div>'


def series(o):
    """Pontos do gráfico da vencedora: os anteriores ao dia da verificação + o preço atual,
    que vale para hoje. Sem price_points, ou com menos de 2, não há gráfico."""
    if len(o["price_points"]) < 2:
        return []
    day = o["checked_at"].astimezone(BRT).date()
    return [(d, c) for d, c in o["price_points"] if d < day] + [(day, o["price_cents"])]


def chart_label(o, pts):
    """"90 dias" só com o selo de 90 dias válido E pontos cobrindo os 90 dias; senão "desde DD/MM"."""
    first, last = pts[0][0], pts[-1][0]
    lo, hi = min(c for _, c in pts), max(c for _, c in pts)
    when_ = "90 dias" if seal(o) == "90d" and (last - first).days >= 89 else f"desde {first:%d/%m}"
    return f"{when_}: {brl(lo)}" + (f" a {brl(hi)}" if hi > lo else "")


def chart(o, pad="  "):
    """Sparkline em SVG inline (sem JS, sem style=): x pela data, y pelo preço, ponto vermelho no atual."""
    pts = series(o)
    if not pts:
        return ""
    W, H, M = 120, 32, 3
    first, span = pts[0][0], max((pts[-1][0] - pts[0][0]).days, 1)
    lo, hi = min(c for _, c in pts), max(c for _, c in pts)
    xy = [(M + (d - first).days / span * (W - 2 * M),
           M + ((hi - c) / (hi - lo) if hi > lo else .5) * (H - 2 * M)) for d, c in pts]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    label = chart_label(o, pts)
    title = f"Preço {na(o['store'])} de {first:%d/%m} a {pts[-1][0]:%d/%m}: {label.split(': ', 1)[1]}"
    return (f'\n{pad}<p class="hist"><svg class="spark" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'aria-hidden="true" focusable="false"><title>{e(title)}</title>'
            f'<line class="spark-base" x1="0" y1="{H - .5}" x2="{W}" y2="{H - .5}"/>'
            f'<polyline class="spark-line" points="{line}"/>'
            f'<circle class="spark-dot" cx="{xy[-1][0]:.1f}" cy="{xy[-1][1]:.1f}" r="3"/></svg>'
            f'<span>{e(label)}</span></p>')


def checked(s, now):
    """"visto hoje às 08h47" ou "visto em 17/10 às 08h47", relativo ao relógio do build (BRT).
    ponytail: o "hoje" congela no build; vale porque o cron refaz o site bem antes de virar o dia."""
    d = s["checked_at"].astimezone(BRT)
    day = "hoje" if d.date() == now.astimezone(BRT).date() else f"em {d:%d/%m}"
    return f'visto {day} às <time datetime="{e(s["checked_at"].isoformat())}">{d:%H}h{d:%M}</time>'


def drop(o):
    """(queda em centavos, data) do último preço diferente do atual na série, se era maior.
    Se o último diferente foi menor (o preço subiu depois), não há queda a mostrar."""
    day = o["checked_at"].astimezone(BRT).date()
    for d, c in reversed([pt for pt in o["price_points"] if pt[0] < day]):
        if c != o["price_cents"]:
            return (c - o["price_cents"], d) if c > o["price_cents"] else None
    return None


def meta_html(o):
    dr = drop(o)
    fell = f'. <span class="drop">Caiu {brl(dr[0])} desde {dr[1]:%d/%m}</span>' if dr else ""
    return f'<span class="store">{na(o["store"])}</span>, {checked(o, o["now"])}{fell}'


def na(store):
    return f'{"no" if store == "mercadolivre" else "na"} {STORES[store]}'


def go(o):
    """Link de afiliado da vencedora: sempre o nosso /r/<id>, nunca a URL da loja."""
    return (f'<a class="go" href="/r/{e(o["id"])}" rel="sponsored noopener noreferrer" target="_blank">'
            f'Ver {na(o["store"])} por {brl(o["price_cents"])}'
            f'<span class="sr">: {e(o["title"])} (abre em nova aba)</span></a>')


def buy(o):
    """Botão da vencedora + seta (<details> nativo) com a outra loja elegível, se houver."""
    a = o["alt"]
    if not a:
        return f'<div class="buy">{go(o)}</div>'
    other = (f'<details class="alt"><summary><span class="sr">Outra loja: {STORES[a["store"]]}</span></summary>\n'
             f'      <p class="alt-box"><a href="/r/{e(o["id"])}/{a["store"]}" rel="sponsored noopener noreferrer" '
             f'target="_blank">Também {na(a["store"])}: {brl(a["price_cents"])}'
             f'<span class="sr">, {e(o["title"])} (abre em nova aba)</span></a>'
             f'<span class="alt-when">{checked(a, o["now"])}</span></p></details>')
    return f'<div class="buy">{go(o)}\n    {other}</div>'


def card(o, bot=None, h=2):
    t = e(o["title"])
    alert = (f' <a class="alert" href="{e(tg_alert_url(bot, o["id"]))}" rel="noopener noreferrer" target="_blank">'
             f'Me avise se baixar (Telegram)<span class="sr">: alerta de preço de {t} (abre o Telegram)</span></a>' if bot else "")
    return f"""<li class="card">
  <div class="top">
    {cover(o)}
    <div class="head">
      <h{h} class="title">{t}</h{h}>
      <p class="author">{e(o["author"])}</p>
      {deal(o)}
    </div>
  </div>
  <p class="meta">{meta_html(o)}</p>{chart(o)}
  <div class="acts">{buy(o)}{alert}</div>
</li>"""


def slide(o, k, n):
    # Emoção, depois decisão: a frase da curadoria (se houver) vem logo antes do preço
    blurb = f'\n    <p class="blurb">{e(o["blurb"])}</p>' if o["blurb"] else ""
    return f"""<div class="slide" id="d-{e(o["id"])}" role="group" aria-roledescription="slide" aria-label="{k} de {n}">
  {cover(o, eager=k == 1)}
  <div class="slide-body">
    <h3 class="slide-title">{e(o["title"])}</h3>
    <p class="author">{e(o["author"])}</p>{blurb}
    {deal(o, "    ")}
    <p class="meta">{meta_html(o)}</p>{chart(o, "    ")}
    <div class="acts">{buy(o)}</div>
  </div>
</div>"""


def hero(items):
    """Carrossel só com CSS: passagem por @keyframes, pausa (hover, foco, checkbox),
    manual com scroll-snap em prefers-reduced-motion ou depois de tocar num indicador."""
    n = len(items)
    if not 3 <= n <= 5:
        return ""
    slides = "\n".join(slide(o, k, n) for k, o in enumerate(items, 1))
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


def mini(o):
    return f"""<li class="mini">
  {cover(o, small=True)}
  <div class="mini-body">
    <h3 class="mini-title">{e(o["title"])}</h3>
    <p class="price">{price_html(o)}</p>
    <p class="meta">{meta_html(o)}</p>
  </div>
  {buy(o)}
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
        hot_title = "Outros descontos"
        hot = sorted((o for o in pool if discount(o) > 0), key=lambda o: -discount(o))[:HOT_MAX]

    def cards(items):
        return "\n".join(card(o, bot, h=3) for o in items)

    def minis(items, tag="ul"):
        return f'<{tag} class="minis">\n' + "\n".join(mini(o) for o in items) + f"\n</{tag}>"

    parts = [
        hero(slides),
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


# ponytail: o texto do logotipo usa fonte do sistema dentro do SVG (muda por aparelho);
# converter em curvas na rodada de refinamento da marca (docs/marca/README.md).
def brand(tag="p", src="/logo.svg"):
    """Logo "Carimbo" (360x72). Na home é o h1; nas outras páginas, um <p> acima do h1."""
    return (f'<{tag} class="brand"><a href="/"><img src="{src}" alt="Ofertas Livros" '
            f'width="200" height="40"></a></{tag}>')


def foot(ch, here=""):
    follow = ""
    if ch:
        links = " ou no ".join(ext(url, name) for name, url in ch)
        follow = f'\n  <p>Siga as ofertas no {links}. {internal("/canais/", "Sobre os canais", here)}</p>'
    return f"""<footer class="foot">
  {brand(src="/logo-negativo.svg")}
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
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
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


def carimbo(dt):
    """Assinatura "feito à mão": carimbo girado com a hora da coleta mais recente. Só CSS."""
    d = dt.astimezone(BRT)
    return (f'<p class="carimbo">conferido <time datetime="{e(dt.isoformat())}">'
            f'<b>{d:%d/%m}</b> às {d:%H}h{d:%M}</time></p>')


def page(all_offers, genre=None, bot=None, ch=()):
    offers = [o for o in all_offers if genre is None or o["genre"] == genre]
    latest = max(o["checked_at"] for o in offers)
    cards = "\n".join(card(o, bot) for o in offers)
    n = len(offers)
    head = (f'{brand()}\n<h1>{e(GENRES[genre])}</h1>' if genre else brand("h1"))
    mast = f"""{head}
<p class="lede">Só entra aqui livro que baixou de preço de verdade. Conferimos cada um na loja e comparamos com o histórico de preço.</p>
<p class="status">{n} {"oferta ativa" if n == 1 else "ofertas ativas"}.</p>
{carimbo(latest)}
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
    mast = f'{brand()}\n<h1>Privacidade</h1>'
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
    mast = f'{brand()}\n<h1>Canais</h1>'
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
  Content-Security-Policy: default-src 'none'; style-src 'self'; img-src 'self' https://http2.mlstatic.com; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
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
    pb = page(o, bot="ofertaslivros_bot")
    assert ('<a class="alert" href="https://t.me/ofertaslivros_bot?start=livro-1" '
            'rel="noopener noreferrer" target="_blank">Me avise se baixar') in pb
    assert pb.count("?start=") == 2  # um botão por card; o bloco de alerta usa t.me/<bot> sem start
    pb = page(xss, bot="ofertaslivros_bot")
    assert "<script>" not in pb and "alerta de preço de &lt;script&gt;" in pb
    saved = os.environ.pop("TELEGRAM_BOT_USERNAME", None)
    assert tg_bot() is None
    for ok in ("ofertaslivros_bot", "@abc_bot", "x1BOT"):
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
        tg_alert_url("ofertaslivros_bot", "a" * 65)
        raise AssertionError("id longo")
    except Invalid:
        pass
    # marca: favicon SVG no <head>, logo no topo (h1 só na home) e negativo no rodapé, em todas as páginas
    for h in (page(o), page(o, "manga"), privacy(), canais([("Telegram", "https://t.me/x")])):
        head = h[:h.index("</head>")]
        assert '<link rel="icon" type="image/svg+xml" href="/favicon.svg">' in head
        assert h.count('alt="Ofertas Livros" width="200" height="40"') == 2 and 'src="/logo-negativo.svg"' in h
    assert '<h1 class="brand"><a href="/"><img src="/logo.svg"' in page(o)
    assert '<h1 class="brand">' not in page(o, "manga") and '<p class="brand"><a href="/"><img src="/logo.svg"' in privacy()
    assert all((STATIC / f).is_file() for f in ("favicon.svg", "logo.svg", "logo-negativo.svg"))
    # privacidade: linkada no rodapé de todas as páginas
    assert '<a href="/privacidade/">Privacidade</a>' in page(o)
    assert '<a href="/privacidade/" aria-current="page">' in privacy()
    pv = privacy("ofertaslivros_bot")
    assert all(w in pv for w in ("chat_id", "Cloudflare D1", "90 dias", "/parar", "bloquear o bot",
                                 "https://t.me/ofertaslivros_bot"))
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
    for html_ in (page(o, ch=ch), canais(ch, "ofertaslivros_bot")):
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
    # selo colado ao preço: pílula (90 dias) ou contorno (desde), logo antes do <p class="price">
    assert re.search(r'<div class="deal">\s*<p class="stamp">Menor preço em 90 dias</p>\s*<p class="price">',
                     stamp(history_since="2026-07-20"))
    assert re.search(r'<p class="stamp stamp--since">Menor preço desde 21/07</p>\s*<p class="price">',
                     stamp(history_since="2026-07-21"))
    assert stamp().count('<p class="price">') == stamp(history_since="2026-07-20").count('<p class="price">')
    assert stamp(history_since="2026-07-20").count("−50%") == 2  # uma vez por ficha (destaque + lista compacta)
    assert 'class="stamp' not in stamp(history_since="2026-07-20", lowest_90d_cents=1000)
    for bad in ("2026-10-19", "20260720", "2026-02-30", "2026-07-20T00:00", 20260720):
        assert rejects(A(history_since=bad)), bad
    # price_points: opcional, estrito; gráfico da vencedora com 2+ pontos
    def pp(*pts):
        return [{"date": d, "price_cents": c} for d, c in pts]
    ok_pp = pp(("2026-10-01", 2990), ("2026-10-10", 2490))
    assert load(A(history_since="2026-10-01", price_points=[]))[0]["price_points"] == []
    assert load(A(history_since="2026-10-01", price_points=ok_pp))[0]["price_points"] == [
        (date(2026, 10, 1), 2990), (date(2026, 10, 10), 2490)]
    def days(n):  # n pontos diários a partir de 01/07
        return pp(*((str(date(2026, 7, 1) + timedelta(d)), 2990) for d in range(n)))
    assert load(A(history_since="2026-07-01", price_points=days(MAX_POINTS)))
    assert rejects(A(history_since="2026-07-01", price_points=days(MAX_POINTS + 1)))  # mais de 90
    for bad in ("x", {}, ok_pp[0], [{**ok_pp[0], "x": 1}], [{"date": "2026-10-01"}], [{"price_cents": 2990}], ["2026-10-01"],
                pp(("2026-10-19", 2990)),                         # depois do checked_at (18/10)
                pp(("2026-09-30", 2990)),                         # antes do history_since
                pp(("01/10/2026", 2990)), pp(("2026-02-30", 2990)), [{"date": None, "price_cents": 2990}],
                pp(("2026-10-10", 2490), ("2026-10-01", 2990)),  # ordem errada
                pp(("2026-10-01", 2990), ("2026-10-01", 2490)),  # data repetida
                pp(("2026-10-01", 29.9)), pp(("2026-10-01", 0)), pp(("2026-10-01", True)),
                pp(("2026-10-01", 1890))):                        # abaixo do lowest_90d_cents (1990)
        assert rejects(A(history_since="2026-10-01", price_points=bad)), bad
    assert rejects(A(price_points=ok_pp))                                 # sem history_since
    assert load(A(history_since="2026-06-01", price_points=pp(("2026-06-10", 990))))  # fora da janela de 90 dias
    h = stamp(history_since="2026-10-01", price_points=ok_pp)
    assert h.count('<p class="hist"><svg class="spark"') == 1 and "<span>desde 01/10: R$ 19,90 a R$ 29,90</span>" in h
    assert "<title>Preço na Amazon de 01/10 a 18/10: R$ 19,90 a R$ 29,90</title>" in h
    assert 'class="spark-dot" cx="117.0" cy="29.0"' in h and 'points="3.0,3.0 63.4,16.0 117.0,29.0"' in h
    assert "style=" not in h[h.index("<svg"):h.index("</svg>")]
    assert 'class="hist"' not in stamp(history_since="2026-10-01", price_points=ok_pp[:1])  # 1 ponto: sem gráfico
    assert 'class="hist"' not in stamp(history_since="2026-10-01")                          # sem série
    # ponto de hoje: vale o preço atual verificado, não o do ponto
    r = load(A(history_since="2026-10-01", price_points=pp(("2026-10-01", 2990), ("2026-10-18", 2500))))[0]
    assert series(r) == [(date(2026, 10, 1), 2990), (date(2026, 10, 18), 1990)]
    # rótulo: "90 dias" só com o selo de 90 dias e a série cobrindo os 90 dias
    full = pp(("2026-07-20", 2990), ("2026-09-01", 2490))
    assert "<span>90 dias: R$ 19,90 a R$ 29,90</span>" in stamp(history_since="2026-07-20", price_points=full)
    assert "<span>desde 01/08: " in stamp(history_since="2026-07-20", price_points=pp(("2026-08-01", 2990), ("2026-09-01", 2490)))
    assert "<span>desde 21/07: " in stamp(history_since="2026-07-21", price_points=pp(("2026-07-21", 2990), ("2026-09-01", 2490)))
    assert "<span>desde 20/07: " in stamp(history_since="2026-07-20", lowest_90d_cents=1000,  # sem selo
                                          price_points=pp(("2026-07-20", 2990), ("2026-09-01", 2490)))
    assert "<span>desde 01/10: R$ 19,90</span>" in stamp(history_since="2026-10-01",       # preço parado
                                                              price_points=pp(("2026-10-01", 1990), ("2026-10-10", 1990)))
    # gráfico da vencedora (ML), não da outra loja
    two_pp = load({**good, "stores": [{**amz, "history_since": "2026-10-01", "price_points": ok_pp},
                                      {**mls, "price_cents": 1890, "history_since": "2026-10-05",
                                       "price_points": pp(("2026-10-05", 2190), ("2026-10-12", 2090))}]})
    assert "<span>desde 05/10: R$ 18,90 a R$ 21,90</span>" in page(two_pp) and "desde 01/10" not in page(two_pp)
    assert rejects({**good, "history_start": "2026-07-01"})  # campo da proposta antiga, substituído
    # campos novos: tipo errado quebra o build
    for bad in ("true", 1, 0, None, "sim"):
        assert rejects({**good, "featured": bad}), bad
    for bad in (0, -1, True, 1.0, "1"):
        assert rejects({**good, "trending_rank": bad}), bad
    assert load({**good, "featured": True, "trending_rank": 3})[0]["trending_rank"] == 3
    # blurb: opcional, até 140 chars, escapado, só no banner e antes do preço
    for bad in ("", "   ", "x" * 141, "a\x00b", "linha\nquebrada", 1, True, ["x"]):
        assert rejects({**good, "blurb": bad}), bad
    assert load({**good, "blurb": "x" * 140})[0]["blurb"] == "x" * 140
    assert load({**good, "blurb": "  Duas irmãs.  "})[0]["blurb"] == "Duas irmãs."
    assert load(good)[0]["blurb"] is None
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
    assert "Outros descontos" in h and "Em alta" not in h        # sem trending_rank
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
    h = page(offers_n(2), bot="ofertaslivros_bot", ch=[("Telegram", "https://t.me/ofertaslivros")])
    assert "carrossel" not in h                                          # menos de 3: sem banner
    assert 'class="join"' in h and "Receba as próximas ofertas" in h
    assert 'href="https://t.me/ofertaslivros_bot" rel="noopener noreferrer"' in h  # bloco de alerta, sem start
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
    # card: botão com loja e preço da vencedora; seta só com a segunda loja elegível
    one = page(load(good))
    assert ">Ver na Amazon por R$\u00a019,90<" in one and "<details" not in one
    two = load({**good, "stores": [amz, {**mls, "price_cents": 1890, "checked_at": "2026-10-18T08:30:00-03:00"}]})
    home12 = page(load(*({**good, "id": f"x-{k}", "stores": [amz, {**mls, "price_cents": 1890}]} for k in range(12))))
    assert 'class="mini"' in home12 and home12.count("<details") == home12.count('class="go"')  # listas compactas também
    for h in (page(two), page(two, "manga"), home12):
        assert ">Ver no Mercado Livre por R$\u00a018,90<" in h
        assert ('<details class="alt"><summary><span class="sr">Outra loja: Amazon</span></summary>' in h)
        assert ('<a href="/r/' in h and '/amazon" rel="sponsored noopener noreferrer" target="_blank">'
                'Também na Amazon: R$\u00a019,90' in h)
    h = page(two)
    assert h.count("<details") == h.count('class="go"') and h.count("visto hoje às") == 4  # 2 seções x 2 lojas
    assert 'no Mercado Livre</span>, visto hoje às <time datetime="2026-10-18T08:30:00-03:00">08h30</time>' in h
    assert '<span class="alt-when">visto hoje às <time datetime="2026-10-18T08:00:00-03:00">08h00</time>' in h
    # urgência honesta: "visto em DD/MM" quando não é hoje (relógio do build); nada de contador
    h = page(load(A(checked_at="2026-10-17T22:00:00-03:00")))
    assert 'visto em 17/10 às <time datetime="2026-10-17T22:00:00-03:00">22h00</time>' in h and "visto hoje" not in h
    assert page(load(A(checked_at="2026-10-18T01:30:00Z"))).count("visto em 17/10 às") == 2  # 22h30 BRT do dia 17
    # "caiu R$ X desde DD/MM": último preço diferente do atual na série, se era maior
    def fell(price=1990, **kw):
        return page(load(A(history_since="2026-10-01", price_cents=price, **kw)))
    assert "Caiu R$\u00a05,00 desde 10/10</span>" in fell(price_points=ok_pp)
    assert "Caiu R$\u00a010,00 desde 01/10" in fell(price_points=pp(("2026-10-01", 2990), ("2026-10-12", 1990)))
    assert "Caiu R$\u00a010,00 desde 01/10" in fell(price_points=pp(("2026-10-01", 2990), ("2026-10-18", 2500)))  # hoje não conta
    assert "Caiu" not in fell(2490, price_points=pp(("2026-10-01", 2990), ("2026-10-10", 1990)))  # subiu depois de cair
    assert "Caiu" not in fell(price_points=pp(("2026-10-01", 1990))) and "Caiu" not in fell()
    h = fell(price_points=pp(("2026-10-01", 2990)))
    assert "Caiu R$\u00a010,00 desde 01/10" in h and 'class="hist"' not in h        # 1 ponto: queda sim, gráfico não
    assert not re.search(r"acaba|restam|minutos|últimas", page(o))
    assert "<details" not in page(load({**good, "stores": [amz, {**mls, "price_cents": 1890}]},
                                       now=datetime(2026, 10, 18, 10, 31, tzinfo=BRT)))  # ML velho: sem seta
    # capa real (só mlstatic) x placeholder sóbrio; alt, dimensões, lazy e eager só no 1º slide
    h = page(load({**good, "image_url": img}))
    assert (f'<div class="cover cover--photo">\n      <img src="{img}" alt="Capa de T, de A" width="120" height="180" '
            'loading="lazy" decoding="async">' in h and "/capa.svg" not in h)
    h = page(load(good))
    assert ('<div class="cover cover--none">\n      <img src="/capa.svg" alt="" width="120" height="180" '
            'loading="lazy" decoding="async">\n      <span class="cover-t" aria-hidden="true">T</span>' in h)
    assert '<div class="cover cover--sm cover--none">\n      <img src="/capa.svg" alt="" width="120" height="180"' in h
    assert not re.search(r"cover--\d", h) and "Capa ilustrativa" not in h        # sem capa falsa colorida
    h = page(load({**good, "image_url": img, "title": 'O "x" <b>', "author": "A & B"}))
    assert 'alt="Capa de O &quot;x&quot; &lt;b&gt;, de A &amp; B"' in h and '"x" <b>' not in h
    h = page(offers_n(5, {k: {"image_url": img} for k in range(5)}))
    hero_ = h[:h.index('id="h-curadoria"')]
    assert hero_.count('loading="eager" fetchpriority="high"') == 1 and h.count('loading="eager"') == 1
    assert hero_.index('loading="eager"') < hero_.index('loading="lazy"')
    assert h.count("<img ") == h.count('width="120" height="180"') + 2                # + logo do topo e do rodapé
    h = page(offers_n(5, {0: {"blurb": '<i>"Duas" & irmãs</i>'}}))
    assert h.count('class="blurb"') == 1 and '<i>"Duas"' not in h
    assert re.search(r'<p class="blurb">&lt;i&gt;&quot;Duas&quot; &amp; irmãs&lt;/i&gt;</p>\s*<div class="deal">', h)
    assert 'class="blurb"' not in page(offers_n(5))
    # CSP: só a foto do ML entra além do próprio site
    csp = HEADERS.split("Content-Security-Policy: ")[1].splitlines()[0]
    assert "img-src 'self' https://http2.mlstatic.com;" in csp and csp.count("https://") == 1
    assert "script-src" not in csp and "default-src 'none'" in csp
    # post: linha "também" só com a outra loja elegível até 10% mais cara, sem URL de loja
    def post(ml_price, now=NOW):
        r = load({**good, "title": "Torto Arado", "author": "Itamar Vieira Junior",
                  "stores": [{**amz, "price_cents": 4290, "list_price_cents": 7490, "lowest_90d_cents": 4290},
                             {**mls, "price_cents": ml_price, "list_price_cents": 7490,
                              "checked_at": "2026-10-18T08:40:00-03:00"}]}, now=now)[0]
        return post_text(r, "https://ofertaslivros.com/r/livro-1/wa")
    assert post(4719).splitlines() == [
        "Torto Arado, de Itamar Vieira Junior", f"R${nb}42,90 (de R${nb}74,90, -42%)",
        "Amazon · preço verificado em 18/10 às 08h00. O preço final é o da loja.",
        f"Também no Mercado Livre por R${nb}47,19", "Link de afiliado: https://ofertaslivros.com/r/livro-1/wa"]
    assert "Também" not in post(4720)                                     # 10,02% mais cara
    t = post(4290)                                                        # empate: ML verificado depois vence
    assert t.splitlines()[2].startswith("Mercado Livre · ") and f"Também na Amazon por R${nb}42,90" in t
    assert "Também" not in post(4719, now=datetime(2026, 10, 18, 10, 41, tzinfo=BRT))  # ML fora do prazo
    w = post(3990)                                                        # ML vence; Amazon 7,5% mais cara
    assert w.splitlines()[2].startswith("Mercado Livre · ") and f"Também na Amazon por R${nb}42,90" in w
    assert "mercadolivre.com" not in w and "amazon.com" not in w and w.count("https://") == 1
    print("selftest ok")


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--selftest"]:
            selftest()
        else:
            build(dev=sys.argv[1:] == ["--dev"])
    except Invalid as err:
        sys.exit(f"build falhou: {err}")
