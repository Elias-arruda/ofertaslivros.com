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
import unicodedata
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
    # vars ausente no Actions chega como string vazia: vale o default (require_prod barra o de exemplo)
    v = os.environ.get(name) or default
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


NEW_DAYS = 3  # badge "Novo": o livro entrou no histórico (history_since) nos últimos 3 dias


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
        hs = [s["history_since"] for s in b["stores"]]
        novo = None not in hs and (now.astimezone(BRT).date() - min(hs)).days < NEW_DAYS
        out.append({**b, **win, "novo": novo, "stores": el, "alt": next((s for s in el if s is not win), None),
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


def checked_txt(s, now):
    d = s["checked_at"].astimezone(BRT)
    return f'visto {"hoje" if d.date() == now.astimezone(BRT).date() else f"em {d:%d/%m}"} às {d:%H}h{d:%M}'


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
            f'Ver {na(o["store"])} por {brl(o["price_cents"])}{icon("seta")}'
            f'<span class="sr">: {e(o["title"])} (abre em nova aba)</span></a>')


def alt_details(o):
    """Seta (<details> nativo) com a outra loja elegível, se houver."""
    a = o["alt"]
    if not a:
        return ""
    return (f'<details class="alt"><summary>{icon("chev")}<span class="sr">Outra loja: {STORES[a["store"]]}</span></summary>'
            f'<p class="alt-box"><a href="/r/{e(o["id"])}/{a["store"]}" rel="sponsored noopener noreferrer" '
            f'target="_blank">Também {na(a["store"])}: {brl(a["price_cents"])}'
            f'<span class="sr">, {e(o["title"])} (abre em nova aba)</span></a>'
            f'<span class="alt-when">{checked(a, o["now"])}</span></p></details>')


def buy(o):
    """Botão da vencedora + seta com a outra loja."""
    return f'<div class="buy">{go(o)}{alt_details(o)}</div>'


def buy_circle(o):
    """Botão de compra do card: círculo com a seta; loja e preço no nome acessível."""
    return (f'<a class="buy-c" href="/r/{e(o["id"])}" rel="sponsored noopener noreferrer" target="_blank">{icon("seta")}'
            f'<span class="sr">Ver {na(o["store"])} por {brl(o["price_cents"])}: {e(o["title"])} (abre em nova aba)</span></a>')


def fold(text):
    """Minúsculas sem acento, para a busca do app.js (que dobra a consulta do mesmo jeito)."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def card(o, bot=None, h=3):
    """Card da vitrine. O título (link para /livro/<id>/, que o JS abre no modal) cobre o card;
    a compra, a seta e o sino ficam por cima."""
    g, t, oid, off = o["genre"], e(o["title"]), e(o["id"]), discount(o)
    b = badge(o)
    bdg = f'<span class="badge badge--{b[0]}">{b[1]}</span>' if b else ""
    stk = f'<span class="sticker" aria-hidden="true">−{off}%</span>' if off else ""
    old = (f' <s class="old"><span class="sr">De </span>{brl(o["list_price_cents"])}</s>'
           f'<span class="sr">, {off}% de desconto</span>' if off else "")
    hs = [s["history_since"] for s in o["stores"] if s["history_since"]]
    rec = f'{min(hs) if hs else "0000-00-00"}|{o["checked_at"].astimezone(timezone.utc):%Y-%m-%dT%H:%M}'
    return f"""<li class="card" data-g="{g}" data-id="{oid}" data-q="{e(fold(o["title"] + " " + o["author"]))}" data-preco="{o["price_cents"]}" data-off="{off}" data-rec="{rec}">
  <div class="sleeve">{obj(o)}{bdg}{stk}{alert_link(o, bot, full=False)}</div>
  <div class="card-body">
    <p class="card-meta">{avatar(g, "av av--sm")}<span><span class="store">{STORES[o["store"]]}</span> <span>{checked(o, o["now"])}</span></span></p>
    <h{h} class="card-title"><a href="/livro/{oid}/" data-modal="{oid}">{t}</a></h{h}>
    <p class="card-sub">{e(o["author"])}</p>
    {stamp_html(o)}
    <div class="card-foot"><p class="price"><span class="sr">Por </span><strong>{brl(o["price_cents"])}</strong>{old}</p>{alt_details(o)}{buy_circle(o)}</div>
  </div>
</li>"""


def badge(o):
    """("alta" | "novo", rótulo) só com dado real: trending_rank do back ou history_since recente.
    "Só N em estoque" não existe: não temos o dado."""
    return ("alta", "Em alta") if o["trending_rank"] else ("novo", "Novo") if o["novo"] else None


def obj(o, cls="obj", eager=False):
    """O objeto-metáfora: a capa sobre o miolo do livro (páginas e fita na cor do nicho).
    Sem foto, a capa vira o gradiente do nicho com a inicial (decorativa: o título está ao lado)."""
    load = 'loading="eager" fetchpriority="high"' if eager else 'loading="lazy"'
    if o["image_url"]:
        cover = (f'<div class="cover"><img src="{e(o["image_url"])}" alt="Capa de {e(o["title"])}, de {e(o["author"])}" '
                 f'width="120" height="180" {load} decoding="async"></div>')
    else:
        cover = f'<div class="cover cover--none" aria-hidden="true"><span class="ini">{e(o["title"][:1].upper())}</span></div>'
    return f'<div class="{cls}"><span class="pages" aria-hidden="true"></span>{cover}</div>'


def avatar(g, cls="av"):
    """Círculo do nicho: hoje um ícone desenhado; troca pela ilustração do curador quando houver arte."""
    return f'<span class="{cls}" data-g="{g}" aria-hidden="true">{icon("g-" + g)}</span>'


def alert_link(o, bot, full=True):
    """Me avise se baixar (Telegram): texto completo no hero, no modal e na página; sino no card."""
    if not bot:
        return ""
    t = e(o["title"])
    label = ('Me avise se baixar (Telegram)' f'<span class="sr">: alerta de preço de {t} (abre o Telegram)</span>' if full
             else f'<span class="sr">Me avise se baixar (Telegram): alerta de preço de {t}</span>')
    cls = "btn btn--ghost alert" if full else "bell"
    return (f'<a class="{cls}" href="{e(tg_alert_url(bot, o["id"]))}" rel="noopener noreferrer" target="_blank">'
            f'{icon("sino")}{label}</a>')


def slide(o, k, n, bot=None):
    g, t = o["genre"], e(o["title"])
    chips = [f'<span class="chip chip--g">{icon("g-" + g)}{e(GENRES[g])}</span>']
    b = badge(o)
    if b:
        chips.append(f'<span class="chip chip--{b[0]}">{b[1]}</span>')
    off = discount(o)
    old = f' <s class="old"><span class="sr">De </span>{brl(o["list_price_cents"])}</s>' if off else ""
    pill = f'<span class="off-pill">−{off}%</span>' if off else ""
    blurb = f'\n    <p class="blurb">{e(o["blurb"])}</p>' if o["blurb"] else ""
    stamp = stamp_html(o)
    long = " hero-title--long" if len(o["title"]) > 38 else ""
    return f"""<div class="slide" id="d-{e(o["id"])}" data-g="{g}" role="group" aria-roledescription="slide" aria-label="{k} de {n}">
  <div class="hero-glow" aria-hidden="true"></div>
  <div class="slide-text">
    <p class="chips">{"".join(chips)}</p>
    <h3 class="hero-title{long}">{t}</h3>
    <p class="hero-sub">{e(o["author"])}</p>{blurb}
    <div class="hero-deal">{stamp}<p class="price"><span class="sr">Por </span><strong>{brl(o["price_cents"])}</strong>{old}</p>{pill}</div>
    <p class="meta">{meta_html(o)}</p>
    <div class="hero-acts">{buy(o)}<a class="btn btn--ghost" href="/livro/{e(o["id"])}/" data-modal="{e(o["id"])}">Ver detalhes<span class="sr"> de {t}</span></a>{alert_link(o, bot)}</div>
    <p class="sign">{avatar(g)}Curadoria de {e(GENRES[g])}</p>
  </div>
  {obj(o, "obj hero-obj", eager=k == 1)}
</div>"""


def hero(items, bot=None):
    """Carrossel. Sem JS: passagem por @keyframes, pausa (hover, foco, checkbox) e segmentos que
    são links para cada slide. Com JS: setas, arraste, contador e barra que avança no animationend."""
    n = len(items)
    if not 3 <= n <= 5:
        return ""
    slides = "\n".join(slide(o, k, n, bot) for k, o in enumerate(items, 1))
    segs = "".join(f'<li><a href="#d-{e(o["id"])}"><span class="sr">Mostrar destaque {k} de {n}: '
                   f'{e(o["title"])}</span><i></i></a></li>' for k, o in enumerate(items, 1))
    return f"""<section class="hero hero--{n}" aria-roledescription="carrossel" aria-labelledby="h-destaque">
<h2 class="sr" id="h-destaque">Em destaque</h2>
<div class="hero-view">
<div class="hero-track">
{slides}
</div>
</div>
<div class="hero-nav">
<ol class="segs">{segs}</ol>
<p class="hero-count tnum" hidden><span class="js-n">1</span>/{n}</p>
<button class="arrow js-prev" type="button" hidden>{icon("esq")}<span class="sr">Destaque anterior</span></button>
<button class="arrow js-next" type="button" hidden>{icon("dir")}<span class="sr">Próximo destaque</span></button>
<p class="pause"><input type="checkbox" id="pausar"><label for="pausar">Pausar</label></p>
</div>
</section>"""


def section(sid, title, body, count=None, note=""):
    """Cabeçalho de seção: H2, contador colado e uma frase curta."""
    n = f'<span class="sec-n">{count} no momento</span>' if count is not None else ""
    note = f'<p class="sec-note">{note}</p>' if note else ""
    return (f'<section class="sec" aria-labelledby="{sid}">\n<div class="sec-head"><h2 id="{sid}">{title}</h2>{n}{note}</div>'
            f'\n{body}\n</section>')


def aneis(cls=""):
    """Anéis de carimbo girando devagar: a textura dos blocos marinho (o "sulco" da spec)."""
    return f'<span class="aneis {cls}" aria-hidden="true"></span>'


def ch_buttons(ch, big=False):
    """WhatsApp verde e Telegram em contorno, só os canais com env."""
    out = []
    for name, url in ch:
        cls = "btn btn--wa" if name == "WhatsApp" else "btn btn--tg"
        out.append(f'<a class="{cls}{" btn--big" if big else ""}" href="{e(url)}" rel="noopener noreferrer" target="_blank">'
                   f'{icon("wa" if name == "WhatsApp" else "tg")}Canal no {name}<span class="sr"> (abre em nova aba)</span></a>')
    return "".join(out)


def strip_canais(ch, at):
    """Faixa dos canais dentro do grid, largura toda. Só com TELEGRAM_CHANNEL_ID ou WHATSAPP_CHANNEL_ID."""
    if not ch:
        return ""
    return f"""<li class="blk blk--canais" data-at="{at}">
  <span class="radar" aria-hidden="true"></span>
  <div><h3 class="blk-h">Receba as próximas ofertas <em>de graça</em></h3>
  <p>As mesmas ofertas do site, com o preço conferido, chegam no canal. Sem cadastro.</p></div>
  <div class="blk-acts">{ch_buttons(ch)}</div>{aneis()}
</li>"""


def banner_bot(bot, at):
    """Banner do alerta em 2 colunas do grid. Só com TELEGRAM_BOT_USERNAME."""
    if not bot:
        return ""
    return f"""<li class="blk blk--bot" data-at="{at}">
  <span class="mascote" aria-hidden="true">{icon("carimbo", "i i-carimbo")}</span>
  <p class="kicker">{icon("sino")}Alerta grátis no Telegram</p>
  <h3 class="blk-h">Escolha o livro. A gente avisa quando baixar.</h3>
  <p>Toque no sino de qualquer oferta e o bot guarda o preço de hoje.</p>
  <p><a class="go" href="https://t.me/{e(bot)}" rel="noopener noreferrer" target="_blank">Ativar alertas{icon("seta")}<span class="sr"> (abre o Telegram)</span></a></p>{aneis()}
</li>"""


def ranking(offers, bot, at):
    """"Em alta agora": só com trending_rank vindo do back (popularidade real)."""
    hot = sorted((o for o in offers if o["trending_rank"]), key=lambda o: o["trending_rank"])[:10]
    if not hot:
        return ""
    items = "".join(
        f'<li class="rank-i" data-g="{o["genre"]}"><span class="rank-n">{k}</span>'
        f'<span class="rank-t"><a href="/livro/{e(o["id"])}/" data-modal="{e(o["id"])}">{e(o["title"])}</a>'
        f'<span class="rank-a">{e(o["author"])}</span></span>{buy_circle(o)}</li>'
        for k, o in enumerate(hot, 1))
    return f"""<li class="blk blk--rank" data-at="{at}">
  <div class="rank-head">{icon("raio")}<h3 class="blk-h" id="h-alta">Em alta agora</h3></div>
  <ol class="rank" aria-labelledby="h-alta">{items}</ol>
</li>"""


FEAT_MAX = 10
FEED_NOJS = 24  # sem JS, a home mostra 24 e leva a /ofertas/; com JS, 12 e "Carregar mais"


def feed(offers, bot=None, ch=(), full=False):
    """Ofertas ativas: ordenação (JS), grid com blocos intercalados e "carregar mais".
    Os blocos guardam a posição (data-at) para o JS recolocá-los depois de ordenar ou filtrar."""
    n = len(offers)
    cards = [card(o, bot) for o in offers]
    blocks = [(4, banner_bot(bot, 4)), (8, strip_canais(ch, 8)), (12, ranking(offers, bot, 12))]
    for at, html_ in sorted(blocks, reverse=True):
        if html_:
            cards.insert(min(at, len(cards)), html_)
    tools = ('<div class="feed-tools" hidden><label for="ordem">Ordenar por</label><select id="ordem">'
             '<option value="">Em destaque</option><option value="preco">Menor preço</option>'
             '<option value="off">Maior desconto</option><option value="rec">Mais recentes</option></select></div>')
    more = ("" if full or n <= FEED_NOJS else
            f'<p class="mais"><a class="btn btn--ghost" href="/ofertas/">{icon("livro", "i i-livro")}Ver todas as {n} ofertas</a></p>')
    more += f'<p class="mais"><button class="btn btn--ghost js-mais" type="button" hidden>{icon("livro", "i i-livro")}Carregar mais ofertas</button></p>'
    body = (f'{tools}\n<p class="vazio" hidden role="status">Nenhum livro com esse título ou autor. '
            f'Tente outro nome ou volte para Todos.</p>\n<ol class="grid feed{" feed--full" if full else ""}">\n'
            + "\n".join(cards) + f"\n</ol>\n{more}")
    return section("h-ativas", "Ofertas ativas", body, n, "Conferidas na loja. A que vence sai da lista.")


def ranked(offers):
    """Destaque: featured primeiro; sem ele, selo válido e depois o maior desconto."""
    return sorted(offers, key=lambda o: (not o["featured"], seal(o) is None, -discount(o)))


def bot_block(bot):
    """Capítulo marinho do alerta. "Pedir um livro" também abre o bot: não há formulário
    (site sem backend, CSP form-action 'none')."""
    if not bot:
        return ""
    url = f"https://t.me/{e(bot)}"
    steps = ("Escolha o livro e toque no sino", "No Telegram, toque em Iniciar", "Quando o preço cair, avisamos")
    lis = "".join(f'<li><span class="n">{k}</span>{t}</li>' for k, t in enumerate(steps, 1))
    return f"""<section class="bot" aria-labelledby="h-bot">
  <div class="bot-art" aria-hidden="true"><span class="radar radar--big"></span><span class="mascote mascote--big">{icon("carimbo", "i i-carimbo")}</span></div>
  <div class="bot-text">
    <p class="kicker">{icon("sino")}Seu alerta no Telegram</p>
    <h2 id="h-bot">Avisamos quando o livro baixar. <em>Você só escolhe qual.</em></h2>
    <ol class="passos">{lis}</ol>
    <p class="bot-acts"><a class="go" href="{url}" rel="noopener noreferrer" target="_blank">Ativar no Telegram{icon("seta")}<span class="sr"> (abre o Telegram)</span></a>
    <a class="btn btn--ivory" href="{url}" rel="noopener noreferrer" target="_blank">Pedir um livro<span class="sr"> ao bot (abre o Telegram)</span></a></p>
    <p class="bot-note">O bot guarda só o necessário para avisar você e apaga o alerta quando ele dispara. Veja a <a href="/privacidade/">privacidade</a>.</p>
  </div>{aneis("aneis--big")}
</section>"""


def channels_block(ch):
    """Seção dos canais (cartão claro). Só com as envs dos canais."""
    if not ch:
        return ""
    return f"""<section class="canais" aria-labelledby="h-canais">
  <p class="kicker kicker--muted">Canais gratuitos</p>
  <h2 id="h-canais">As ofertas inteiras, <em>no seu celular.</em></h2>
  <p class="canais-p">As mesmas ofertas do site, com o preço conferido e o horário da verificação. Só leitura, sem cadastro.</p>
  <p class="canais-acts">{ch_buttons(ch, big=True)}</p>
  <p><a class="link" href="/canais/">Como funcionam os canais</a></p>
</section>"""


def faq(bot, ch):
    """Perguntas sobre o que o site faz de verdade: curadoria, histórico, alerta, canais e afiliado."""
    qa = [("Como vocês escolhem as ofertas?",
           "Acompanhamos o preço de uma lista de livros na Amazon e no Mercado Livre. Só entra no site o livro "
           "que está mais barato do que costuma ficar, e cada preço mostra o horário em que foi conferido na loja. "
           "Quando o preço volta a subir ou fica velho, a oferta sai da lista."),
          ("O que quer dizer “menor preço em 90 dias”?",
           "Que o preço de agora é o menor que registramos nos últimos 90 dias, em todas as lojas em que o livro "
           "está à venda. O selo só aparece quando temos 90 dias de histórico de verdade; com menos, mostramos "
           "“menor preço desde” a data em que começamos a acompanhar."),
          ("O preço do site é o mesmo da loja?",
           "Era no horário indicado em cada oferta. Preço muda rápido, então o preço final é sempre o da loja, "
           "na hora da compra.")]
    if bot:
        qa.append(("Como funciona o alerta de preço?",
                   f'Toque no sino de um livro (ou em “Me avise se baixar”) e o bot <a href="https://t.me/{e(bot)}" '
                   'rel="noopener noreferrer" target="_blank">@' + e(bot) + '</a> guarda o preço de hoje. Quando ele cair, '
                   'avisamos por lá. Para parar, mande /parar ao bot.'))
    if ch:
        qa.append(("Onde mais recebo as ofertas?",
                   "Nos canais " + " e ".join(n for n, _ in ch) + ', que repetem as ofertas do site. '
                   '<a href="/canais/">Veja como funcionam</a>.'))
    qa.append(("Vocês ganham com isso?",
               "Sim. Os links são de afiliado: como associados da Amazon e afiliados do Mercado Livre, ganhamos uma "
               "comissão com compras qualificadas, sem custo a mais para você. Isso não muda qual oferta entra no site."))
    items = "".join(f'<details><summary>{q}{icon("chev")}</summary><p>{a}</p></details>' for q, a in qa)
    return f"""<section class="faq" aria-labelledby="h-faq">
  <p class="kicker kicker--muted">Perguntas</p>
  <h2 id="h-faq">Como o site funciona</h2>
  <div class="faq-list">{items}</div>
</section>"""


def fab(bot):
    """Botão flutuante "Pedir um livro": abre o bot (sem formulário)."""
    if not bot:
        return ""
    return (f'<a class="fab" href="https://t.me/{e(bot)}" rel="noopener noreferrer" target="_blank">{icon("busca")}'
            '<span class="fab-t">Pedir um livro</span><span class="sr"> ao bot do Telegram (abre o Telegram)</span></a>')


def home_sections(offers, bot=None, ch=()):
    """Hero (5), destaques (até 10, sem repetir o hero), filtro e o feed completo
    (a busca, o filtro e a ordenação do JS trabalham sobre ele)."""
    top = ranked(offers)
    slides = top[:5] if len(top) >= 3 else []
    curated = any(o["featured"] for o in offers)
    in_hero = {o["id"] for o in slides}
    feat = [o for o in top if o["id"] not in in_hero and (o["featured"] or not curated)][:FEAT_MAX] if slides else []
    parts = [
        hero(slides, bot),
        feat and section("h-curadoria", "Destaques da curadoria" if curated else "Destaques de hoje",
                         '<ol class="grid grid--feat">\n' + "\n".join(card(o, bot) for o in feat) + "\n</ol>",
                         len(feat), "" if curated else "Primeiro o menor preço do histórico, depois o maior desconto."),
        nav(offers, None, filtro=True),
        feed(offers, bot, ch),
        bot_block(bot),
        channels_block(ch),
        faq(bot, ch),
        fab(bot),
    ]
    return "\n".join(p for p in parts if p)


GENRE_DESC = {
    "literatura-brasileira": "Clássicos e contemporâneos daqui",
    "ficcao": "Romance, fantasia e suspense",
    "negocios": "Carreira, gestão e dinheiro",
    "nao-ficcao": "História, ciência e ensaio",
    "manga": "Mangá, HQ e graphic novel",
}
assert set(GENRE_DESC) == set(GENRES)


def nav(offers, current, filtro=False):
    """Filtro por nicho: círculos com o ícone de cada nicho (o lugar do curador ilustrado).
    São links para /<nicho>/; com filtro=True (home e /ofertas/), o app.js filtra sem recarregar."""
    present = [g for g in GENRES if any(o["genre"] == g for o in offers)]
    def n(k):
        return f'{k} {"oferta" if k == 1 else "ofertas"}'
    spines = "".join(f'<i data-g="{g}"></i>' for g in present)
    items = [("/", "", "Todos", "Tudo o que está em oferta", len(offers),
              f'<span class="spines">{spines}</span>', current is None)]
    items += [(f"/{g}/", g, GENRES[g], GENRE_DESC[g], sum(o["genre"] == g for o in offers),
               avatar(g, "av av--lg"), g == current) for g in present]
    lis = "".join(
        f'<li><a class="cur" href="{href}" data-f="{g}"{f" data-g={chr(34)}{g}{chr(34)}" if g else ""}'
        f'{" aria-current=" + chr(34) + "page" + chr(34) if cur else ""}>'
        f'<span class="ring" aria-hidden="true">{pic}</span><span class="cur-n">{e(label)}</span>'
        f'<span class="cur-d">{e(desc)}</span><span class="cur-c">{n(k)}</span></a></li>'
        for href, g, label, desc, k, pic, cur in items)
    attr = " data-filtro" if filtro else ""
    return (f'<section class="filtros" aria-labelledby="h-filtro"><h2 id="h-filtro">Filtrar por categoria</h2>'
            f'<nav aria-label="Nichos"><ul class="rail"{attr}>{lis}</ul></nav></section>')


def ext(href, label):
    return (f'<a href="{e(href)}" rel="noopener noreferrer" target="_blank">{label}'
            '<span class="sr"> (abre em nova aba)</span></a>')


def internal(href, label, here):
    cur = ' aria-current="page"' if href == here else ""
    return f'<a href="{href}"{cur}>{label}</a>'


def brand(cls="brand"):
    """Logo B (wordmark em curvas, 274x32). Duas imagens: a positiva no tema claro e a negativa
    (sem fundo) no escuro; o CSS mostra uma só, então o leitor de tela lê um nome só."""
    return (f'<a class="{cls}" href="/"><img class="logo-claro" src="/logo.svg" alt="Ofertas Livros" '
            'width="274" height="32"><img class="logo-escuro" src="/logo-negativo.svg" alt="Ofertas Livros" '
            'width="274" height="32"></a>')


# Ícones desenhados para o site (traço 2, viewBox 24), num sprite só: cada uso é um <use>.
ICONS = {
    "busca": '<circle cx="11" cy="11" r="7"/><path d="m16.5 16.5 4.5 4.5"/>',
    "sol": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "lua": '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    "tg": '<path d="M21 4 3 11.2l6 2.3L18 7.5l-7 7.3.3 5.2 3-3.6 4.2 3.1z"/>',
    "wa": '<path d="M4 20l1.3-3.9A8.5 8.5 0 1 1 8.2 19z"/><path d="M9.2 8.6c-.3 2.9 3.2 6.4 6.2 6.2l.6-1.7-2-.9-.9.8a5 5 0 0 1-2.3-2.3l.8-.9-.9-2z"/>',
    "seta": '<path d="M7 17 17 7M8 7h9v9"/>',
    "sino": '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0"/>',
    "chev": '<path d="m6 9 6 6 6-6"/>',
    "esq": '<path d="m15 6-6 6 6 6"/>',
    "dir": '<path d="m9 6 6 6-6 6"/>',
    "x": '<path d="M6 6l12 12M18 6 6 18"/>',
    "raio": '<path d="M13 3 5 14h6l-1 7 8-11h-6z"/>',
    "carimbo": '<circle cx="12" cy="12" r="10.5"/><circle cx="12" cy="12" r="7.8" stroke-width="1"/>'
               '<path fill="currentColor" stroke="none" transform="translate(12 12.4) scale(.6) translate(-16 -16.6)" '
               'd="M9.6 12.4C11.6 11.5 13.8 11.6 15.3 12.8V21.6C13.8 20.5 11.6 20.4 9.6 21.2ZM22.4 12.4C20.4 11.5 18.2 11.6 16.7 12.8V21.6C18.2 20.5 20.4 20.4 22.4 21.2Z"/>',
    "livro": '<path d="M3 6c3-1.5 6-1.5 9 0v13c-3-1.5-6-1.5-9 0zM21 6c-3-1.5-6-1.5-9 0v13c3-1.5 6-1.5 9 0z"/>',
    # um por nicho: o lugar do curador ilustrado, até haver arte
    "g-literatura-brasileira": '<path d="M5 19C5 10 11 5 19 5c0 8-5 14-14 14zM5 19l8-8M9 15h4M11 13V9"/>',
    "g-ficcao": '<path d="M15 4a7.5 7.5 0 1 0 5.5 11.5A6 6 0 0 1 15 4zM6 3v4M4 5h4"/>',
    "g-negocios": '<path d="M4 20h16M6 16l4.5-4.5 3 3L19 9M15 9h4v4"/>',
    "g-nao-ficcao": '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.3 1.1 2.2h5c0-.9.4-1.6 1.1-2.2A6 6 0 0 0 12 3z"/>',
    "g-manga": '<path d="M4 4h16v12h-9l-4.5 4v-4H4z"/><path d="m13 6.5-3 4h3.5l-2.5 3.5"/>',
}
SPRITE = ('<svg class="sprite" hidden aria-hidden="true">'
          + "".join(f'<symbol id="i-{k}" viewBox="0 0 24 24">{v}</symbol>' for k, v in ICONS.items()) + "</svg>")
assert set(f"g-{g}" for g in GENRES) <= set(ICONS)


def icon(name, cls="i"):
    return f'<svg class="{cls}" aria-hidden="true" focusable="false"><use href="#i-{name}"/></svg>'


def live(offers):
    """Pílula do topo: horário real da coleta mais recente e o número de ofertas no ar.
    Nada de "ao vivo": o site é gerado pelo cron, então o rótulo diz quando conferimos."""
    latest, now, n = max(o["checked_at"] for o in offers), offers[0]["now"], len(offers)
    d = latest.astimezone(BRT)
    day = "" if d.date() == now.astimezone(BRT).date() else f" em {d:%d/%m}"
    return (f'<p class="live"><span class="dot" aria-hidden="true"></span>Conferido{day} às '
            f'<time datetime="{e(latest.isoformat())}">{d:%H}h{d:%M}</time> <b class="tnum">{n}</b>'
            f'<span class="sr"> {"oferta ativa" if n == 1 else "ofertas ativas"}</span></p>')


def header(offers, ch):
    """Header de vidro. Buscar e tema só funcionam com JS: saem com hidden e o app.js mostra."""
    links = dict(ch)
    nav = [f'<button class="pill js-busca" type="button" hidden aria-expanded="false" aria-controls="busca">'
           f'{icon("busca")}<span class="pill-t">Buscar</span></button>',
           f'<button class="pill pill--ico js-tema" type="button" hidden aria-pressed="false">'
           f'{icon("sol", "i i-sol")}{icon("lua", "i i-lua")}<span class="sr">Tema escuro</span></button>']
    if "Telegram" in links:
        nav.append(f'<a class="pill pill--tg" href="{e(links["Telegram"])}" rel="noopener noreferrer" target="_blank">'
                   f'{icon("tg")}<span class="pill-t">Telegram</span><span class="sr"> (canal, abre em nova aba)</span></a>')
    if "WhatsApp" in links:
        nav.append(f'<a class="pill pill--wa" href="{e(links["WhatsApp"])}" rel="noopener noreferrer" target="_blank">'
                   f'{icon("wa")}<span class="pill-t">Canal no WhatsApp</span><span class="sr"> (abre em nova aba)</span></a>')
    return f"""<header class="top">
<div class="top-bar">
{brand()}
{live(offers)}
<nav class="acoes" aria-label="Atalhos">{"".join(nav)}</nav>
</div>
<div class="busca" id="busca" hidden><label class="sr" for="q">Buscar por título ou autor</label><input id="q" type="search" placeholder="Buscar por título ou autor" autocomplete="off" spellcheck="false" enterkeyhint="search"></div>
</header>"""


def intro(h1, text):
    return f'<div class="intro"><h1>{h1}</h1><p>{text}</p></div>'


AFFILIATE = ("Como associado da Amazon, ganhamos com compras qualificadas. Também participamos do programa "
             "de afiliados do Mercado Livre. Preços verificados no horário indicado; o preço final é o da loja.")


def foot(offers, bot=None, ch=(), here=""):
    """Rodapé: marca, colunas de links (só o que existe) e o aviso de associado na linha final."""
    present = [g for g in GENRES if any(o["genre"] == g for o in offers)]
    cols = [("Ofertas", [internal("/ofertas/", "Todas as ofertas", here)]
             + [internal(f"/{g}/", e(GENRES[g]), here) for g in present])]
    receber = ([internal("/canais/", "Canais", here)] if ch else []) + (
        [ext(f"https://t.me/{bot}", "Alerta no Telegram")] if bot else [])
    if receber:
        cols.append(("Receber ofertas", receber))
    cols.append(("Sobre", [internal("/#h-faq", "Como o site funciona", here), internal("/privacidade/", "Privacidade", here)]))
    html_cols = "".join(f'<nav class="foot-col" aria-label="{t}"><p class="foot-t">{t}</p><ul>'
                        + "".join(f"<li>{x}</li>" for x in links) + "</ul></nav>" for t, links in cols)
    tg = dict(ch).get("Telegram")
    social = (f'<a class="pill" href="{e(tg)}" rel="noopener noreferrer" target="_blank">{icon("tg")}'
              f'@{e(tg.rsplit("/", 1)[1])} no Telegram<span class="sr"> (abre em nova aba)</span></a>' if tg else "")
    return f"""<footer class="foot">
  <div class="foot-grid">
    <div class="foot-brand">{brand("brand brand--foot")}<p>Livros que baixaram de preço de verdade, conferidos na loja.</p>{social}</div>
    <div class="foot-cols">{html_cols}</div>
  </div>
  <p class="foot-legal">{AFFILIATE}</p>
</footer>"""


def offer_json(o, bot):
    """Dados do modal de uma oferta, em texto puro (o app.js escreve com textContent).
    Os links são só os nossos (/r/..., /livro/..., t.me): o JS confere o formato de novo."""
    off, a, dr = discount(o), o["alt"], drop(o)
    pts = series(o)
    lojas = [{"txt": f"Ver {na(o['store'])} por {brl(o['price_cents'])}", "href": f"/r/{o['id']}", "main": True}]
    if a:
        lojas.append({"txt": f"Também {na(a['store'])}: {brl(a['price_cents'])}", "href": f"/r/{o['id']}/{a['store']}",
                      "w": checked_txt(a, o["now"]), "main": False})
    kind = seal(o)
    return {"id": o["id"], "t": o["title"], "a": o["author"], "g": o["genre"], "gl": GENRES[o["genre"]],
            "img": o["image_url"], "p": brl(o["price_cents"]), "de": brl(o["list_price_cents"]) if off else None,
            "off": off, "blurb": o["blurb"],
            "selo": ("Menor preço em 90 dias" if kind == "90d" else
                     f"Menor preço desde {o['since']:%d/%m}" if kind == "since" else None), "desde": kind == "since",
            "meta": f"{STORES[o['store']]}, {checked_txt(o, o['now'])}"
                    + (f". Caiu {brl(dr[0])} desde {dr[1]:%d/%m}" if dr else ""),
            "hist": chart_label(o, pts) if pts else None, "lojas": lojas,
            "alerta": tg_alert_url(bot, o["id"]) if bot else None, "pag": f"/livro/{o['id']}/"}


def data_script(offers, bot):
    """<script type="application/json"> com os dados do modal. json.dumps e todo "<" vira \\u003c:
    nenhum </script> ou <!-- pode sair do bloco, venha o que vier no título."""
    raw = json.dumps([offer_json(o, bot) for o in offers], ensure_ascii=False, separators=(",", ":"))
    raw = raw.replace("<", "\\u003c")
    return f'<script type="application/json" id="ofertas">{raw}</script>'


MODAL = f"""<dialog class="modal" id="detalhe" aria-labelledby="m-t">
<div class="m-top"><button class="arrow js-mprev" type="button">{icon("esq")}<span class="sr">Livro anterior</span></button><span class="m-n tnum"></span><button class="arrow js-mnext" type="button">{icon("dir")}<span class="sr">Próximo livro</span></button><button class="arrow m-x js-mx" type="button">{icon("x")}<span class="sr">Fechar</span></button></div>
<div class="m-grid">
<div class="obj hero-obj m-obj"><span class="pages" aria-hidden="true"></span><div class="cover"><img class="m-img" alt="" width="120" height="180" decoding="async"><span class="ini m-ini" aria-hidden="true"></span></div></div>
<div class="m-body"><p class="chips"><span class="chip chip--g"><svg class="i" aria-hidden="true" focusable="false"><use class="m-gi" href="#i-carimbo"/></svg><span class="m-g"></span></span></p><h2 class="m-t" id="m-t"></h2><p class="hero-sub m-a"></p><blockquote class="nota m-nota"><p class="m-blurb"></p></blockquote><p class="m-selo"><span class="stamp"></span></p><p class="meta m-meta"></p><p class="hist m-hist"></p></div>
</div>
<div class="m-foot"><p class="price"><strong class="m-p"></strong> <s class="old m-de"></s> <span class="off-pill m-off"></span></p><div class="m-acts"></div></div>
</dialog>"""


def shell(offers, title, desc, body, ch=(), here="", style=None, bot=None, modal=False):
    """Esqueleto comum. title/desc/body já chegam escapados. style: nicho da página (acento global)."""
    ds = f' data-style="{style}"' if style in GENRES else ""
    return f"""<!doctype html>
<html lang="pt-BR"{ds}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="theme-color" content="#edf1f5" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0f1729" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="light dark">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="preload" href="/fonts/fraunces-latin-full-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/style.css">
<script src="/app.js" defer></script>
</head>
<body>
{SPRITE}
<div class="bg-blobs" aria-hidden="true"><i></i><i></i><i></i></div>
<a class="skip" href="#conteudo">Pular para o conteúdo</a>
{header(offers, ch)}
<main id="conteudo">
{body}
</main>
{foot(offers, bot, ch, here)}{(chr(10) + MODAL + chr(10) + data_script(offers, bot)) if modal else ""}
</body>
</html>
"""


LEDE = ("Só entra aqui livro que baixou de preço de verdade. Conferimos cada um na loja "
        "e comparamos com o histórico de preço.")


def page(all_offers, genre=None, bot=None, ch=()):
    offers = [o for o in all_offers if genre is None or o["genre"] == genre]
    title = (f"{e(GENRES[genre])}: ofertas de livros" if genre
             else "Ofertas Livros: descontos de livros conferidos na loja")
    desc = (f"{e(GENRES[genre])} em oferta" if genre else "Ofertas de livros") + (
        " na Amazon e no Mercado Livre, conferidas uma a uma e comparadas com o histórico de preço.")
    if genre is None:
        body = intro("Livros que baixaram de verdade", LEDE) + "\n" + home_sections(offers, bot, ch)
    else:
        body = intro(e(GENRES[genre]), LEDE) + f"\n{nav(all_offers, genre)}\n{feed(offers, bot, ch, full=True)}"
    return shell(all_offers, title, desc, body, ch, style=genre, bot=bot, modal=True)


def store_list(o):
    """Na página e no modal a outra loja aparece inteira (no card ela é só a seta)."""
    a = o["alt"]
    if not a:
        return ""
    return (f'<p class="other"><a class="btn btn--ghost" href="/r/{e(o["id"])}/{a["store"]}" rel="sponsored noopener noreferrer" '
            f'target="_blank">Também {na(a["store"])}: {brl(a["price_cents"])}{icon("seta")}'
            f'<span class="sr">, {e(o["title"])} (abre em nova aba)</span></a>'
            f'<span class="alt-when">{checked(a, o["now"])}</span></p>')


def book_page(o, offers, bot=None, ch=()):
    """/livro/<id>/: a página real dos detalhes (o modal do JS é só um atalho para ela)."""
    g, t = o["genre"], e(o["title"])
    off = discount(o)
    old = f' <s class="old"><span class="sr">De </span>{brl(o["list_price_cents"])}</s>' if off else ""
    pill = f'<span class="off-pill">−{off}%</span>' if off else ""
    b = badge(o)
    chips = f'<span class="chip chip--g">{icon("g-" + g)}{e(GENRES[g])}</span>' + (
        f'<span class="chip chip--{b[0]}">{b[1]}</span>' if b else "")
    note = (f'<blockquote class="nota"><p>{e(o["blurb"])}</p><footer>{avatar(g)}Curadoria de {e(GENRES[g])}</footer></blockquote>'
            if o["blurb"] else "")
    body = f"""<p class="crumbs"><a href="/">Ofertas</a> / <a href="/{g}/">{e(GENRES[g])}</a></p>
<article class="livro" data-g="{g}">
  {obj(o, "obj hero-obj livro-obj", eager=True)}
  <div class="livro-text">
    <p class="chips">{chips}</p>
    <h1 class="livro-h1">{t}</h1>
    <p class="hero-sub">{e(o["author"])}</p>
    {note}
    <div class="hero-deal">{stamp_html(o)}<p class="price"><span class="sr">Por </span><strong>{brl(o["price_cents"])}</strong>{old}</p>{pill}</div>
    <p class="meta">{meta_html(o)}</p>{chart(o, "    ")}
    <div class="hero-acts">{go(o)}{alert_link(o, bot)}</div>
    {store_list(o)}
  </div>
</article>"""
    return shell(offers, f"{t}, de {e(o['author'])}: oferta conferida | Ofertas Livros",
                 f"{t}, de {e(o['author'])}, por {brl(o['price_cents'])} {na(o['store'])}. Preço conferido na loja.",
                 body, ch, style=g, bot=bot)


def all_page(offers, bot=None, ch=()):
    """/ofertas/: a lista completa (sem JS, é para onde o "Ver todas" leva)."""
    body = (intro("Todas as ofertas", LEDE) + f"\n{nav(offers, None, filtro=True)}\n{feed(offers, bot, ch, full=True)}")
    return shell(offers, "Todas as ofertas de livros | Ofertas Livros",
                 "Todas as ofertas de livros ativas, conferidas na loja.", body, ch, "/ofertas/", bot=bot, modal=True)


def privacy(offers, bot=None, ch=()):
    bot_name = (f'o bot <a href="https://t.me/{e(bot)}" rel="noopener noreferrer" target="_blank">@{e(bot)}</a>'
                if bot else "o nosso bot")
    body = f"""<h1 class="page-h1">Privacidade</h1>
<article class="doc">
<h2>No site</h2>
<p>O site não tem cadastro, cookies nem ferramentas de análise. Ele tem um script próprio, servido pelo próprio site, para a busca, os filtros e o tema; a única coisa que ele guarda é a sua escolha de tema claro ou escuro, no seu navegador (localStorage), e nada disso sai do aparelho. O site é hospedado na Cloudflare, que recebe os dados técnicos de cada acesso (como o endereço IP) para entregar as páginas.</p>
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
    return shell(offers, "Privacidade: Ofertas Livros",
                 "O que o Ofertas Livros guarda, onde, por quanto tempo e como apagar.", body, ch, "/privacidade/", bot=bot)


def canais(offers, ch, bot=None):
    desc = {"Telegram": "as ofertas chegam assim que são publicadas, até 8 por dia, das 8h às 22h.",
            "WhatsApp": "um resumo por dia com até 5 ofertas."}
    items = "\n".join(f"<li>{ext(url, f'Canal no {name}')}: {desc[name]}</li>" for name, url in ch)
    alert = (f'<p>Quer saber de um livro só? Peça um alerta de preço ao {ext(f"https://t.me/{bot}", "@" + e(bot))} '
             'ou toque em “Me avise se baixar” na oferta.</p>' if bot else "")
    body = f"""<h1 class="page-h1">Canais</h1>
<article class="doc">
<p>Os canais repetem as ofertas do site, com preço conferido e o horário da verificação. São só de leitura e não pedem cadastro.</p>
<ul>
{items}
</ul>
{alert}
<p>Os links dos canais são de afiliado: ganhamos com compras qualificadas, e o preço final é o da loja.</p>
</article>"""
    return shell(offers, "Canais: Ofertas Livros", "Siga as ofertas de livros no Telegram e no WhatsApp.", body, ch, "/canais/", bot=bot)


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
  Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' https://http2.mlstatic.com; font-src 'self'; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Strict-Transport-Security: max-age=31536000
"""


def require_prod(doc):
    """Fail-closed: sem --dev, nada de tag de exemplo nem dado de exemplo no ar.
    Cada loja presente no offers.json exige o seu ID de afiliado real."""
    stores = {s.get("store") for o in doc.get("offers") or [] if isinstance(o, dict)
              for s in o.get("stores") or [] if isinstance(s, dict)}
    for store, name in (("amazon", "AMAZON_PARTNER_TAG"), ("mercadolivre", "ML_AFFILIATE_ID")):
        if store not in stores:
            continue
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
    pages = {"index.html": page(offers, bot=bot, ch=ch), "privacidade/index.html": privacy(offers, bot, ch)}
    for g in {o["genre"] for o in offers}:
        pages[f"{g}/index.html"] = page(offers, g, bot, ch)
    if ch:
        pages["canais/index.html"] = canais(offers, ch, bot)
    pages["ofertas/index.html"] = all_page(offers, bot, ch)
    for o in offers:  # id validado por ID_RE: seguro como diretório
        pages[f"livro/{o['id']}/index.html"] = book_page(o, offers, bot, ch)
    rules = redirects(offers)
    shutil.rmtree(DIST, ignore_errors=True)
    shutil.copytree(STATIC, DIST)
    for path, body in pages.items():
        (DIST / path).parent.mkdir(parents=True, exist_ok=True)
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
    both = {"offers": [{"stores": [{"store": "amazon"}, {"store": "mercadolivre"}]}]}
    only_ml = {"offers": [{"stores": [{"store": "mercadolivre"}]}]}
    for env, doc in (({}, both), ({}, only_ml),
                     ({"AMAZON_PARTNER_TAG": "minha-20", "ML_AFFILIATE_ID": "exemplo"}, both),
                     ({"AMAZON_PARTNER_TAG": "minha-20", "ML_AFFILIATE_ID": "eu"},
                      {**both, "_exemplo": True})):
        os.environ.update(env)
        try:
            require_prod(doc)
            raise AssertionError((env, doc))
        except Invalid:
            pass
    require_prod(both)  # env real e dado real: passa
    os.environ["AMAZON_PARTNER_TAG"] = ""  # vars ausente no Actions
    assert partner_tag() == "exemplo-20"
    require_prod(only_ml)  # vazio = ausente; só ML não exige a tag
    os.environ.pop("AMAZON_PARTNER_TAG")
    require_prod(only_ml)  # só ML: a tag da Amazon não é exigida
    try:
        require_prod(both)
        raise AssertionError("Amazon sem tag passou")
    except Invalid:
        pass
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
