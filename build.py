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
# Domínio do <link rel="canonical">, do og:url, do JSON-LD e do sitemap.xml (o site responde em .com e .com.br): o .com.br.
SITE = "https://ofertaslivros.com.br"
# Conjunto fechado: o slug vira diretório em dist/, então nunca vem do JSON livre.
GENRES = {
    "literatura-brasileira": "Literatura brasileira",
    "ficcao": "Ficção",
    "romance": "Romance",
    "fantasia": "Fantasia e ficção científica",
    "suspense": "Suspense e policial",
    "mindset": "Mindset e hábitos",
    "negocios": "Negócios e finanças",
    "politica": "Política e sociedade",
    "historia": "História e biografias",
    "manga": "Mangá e HQ",
}
# Rotas de dist/ que nenhum slug de nicho pode ocupar.
RESERVED = {"r", "livro", "ofertas", "privacidade", "canais", "curadoria", "novidades", "fonts", "black-friday", "bot"}
if set(GENRES) & RESERVED:
    raise SystemExit("slug de GENRES reservado")

# Sempre re.fullmatch: com re.match + "$", "B0ABCDEFGH\n" passaria.
ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
ASIN_RE = re.compile(r"[A-Z0-9]{10}")
MLB_RE = re.compile(r"MLB\d{1,15}")
TAG_RE = re.compile(r"[A-Za-z0-9-]{1,64}")
CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")

ISBN_RE = re.compile(r"\d{9}[\dX]|\d{13}")
IMG_HOST = "http2.mlstatic.com"  # único host de foto liberado no img-src da CSP

# blurb: opcional, proposto ao contrato (frase curta da curadoria no banner).
# trending_rank: aceito no contrato, mas o site não mostra nada derivado dele (posição, "Em alta", ordem):
# ranking das lojas (/highlights, /trends, salesRank) é só interno (aba-curadoria.md §7, termos do ML 5.4).
BOOK_KEYS = {"id", "isbn", "genre", "title", "author", "image_url", "stores", "featured", "trending_rank",
             "blurb"}
BLURB_MAX = 140
STORE_COMMON = {"store", "price_cents", "list_price_cents", "lowest_90d_cents", "history_since", "checked_at",
                "price_points",  # opcional, proposto ao contrato (gráfico do histórico)
                "median_90d_cents"}  # opcional: mediana dos dias 8 a 90 (critério "em oferta", em_oferta)
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
TG_START_RE = re.compile(r"[A-Za-z0-9_-]{1,60}")  # ?start= aceita 64; 60 cabe no callback_data "add:<id>" do bot


def tg_bot():
    """Opcional: sem TELEGRAM_BOT_USERNAME o site sai sem o botão de alerta."""
    v = os.environ.get("TELEGRAM_BOT_USERNAME", "").removeprefix("@")
    if v and not TG_BOT_RE.fullmatch(v):
        raise Invalid("TELEGRAM_BOT_USERNAME com formato inválido")
    return v or None


def tg_alert_url(bot, oid):
    if not TG_START_RE.fullmatch(oid):  # id até 80 no offers.json; o bot aceita 60
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
    """Tag da Amazon por caminho do /r/. Sem AMAZON_TAG_TG/WA/BOT (ou vazias), usa a tag do site."""
    site = partner_tag()
    return {"": site, **{f"/{c}": _env_id(f"AMAZON_TAG_{c.upper()}", site)
                         if os.environ.get(f"AMAZON_TAG_{c.upper()}") else site
                         for c in ("tg", "wa", "bot")}}


def ml_affiliate():
    return _env_id("ML_AFFILIATE_ID", "exemplo")


ML_PARAMS = {"matt_word", "matt_tool", "forceInApp", "ref"}
# Etiquetas do painel aceitas além do próprio ML_AFFILIATE_ID (decisão do Elias, 2026-10-20:
# links novos saem com a etiqueta da marca). Quem prende o link à conta é o /social/<aff>.
ML_LABELS = {"ofertaslivros"}


def ml_url(raw, aff):
    """Aceita só o link completo do painel, preso à nossa conta (/social/<aff>) e com uma
    etiqueta nossa (matt_word = aff ou uma de ML_LABELS)."""
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
            or dict(params).get("matt_word") not in {aff} | ML_LABELS):
        raise Invalid(f"ml_url precisa ser o link completo do painel "
                      f"(/social/{aff}?matt_word={aff}|{'|'.join(sorted(ML_LABELS))}...), "
                      f"não meli.la: {raw!r}")
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
    out["median_90d_cents"] = _cents(s, "median_90d_cents") if "median_90d_cents" in s else None
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
    if not isinstance(oid, str) or len(oid) > 60 or not ID_RE.fullmatch(oid):
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
    # ponytail: capa provisória (Open Library, baixada à mão em static/capas/) para livro sem foto do ML.
    # Sai quando a Creators API der a imagem da Amazon.
    if out["image_url"] is None and isbn and (STATIC / "capas" / f"{isbn}.jpg").is_file():
        out["image_url"] = f"/capas/{isbn}.jpg"
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


VELHO = "Preço pode estar desatualizado"
VELHO_OFERTA = timedelta(days=7)  # Amazon vencida há mais que isso: deixa de ser oferta, fica na Curadoria com o preço
NEW_DAYS = 3  # badge "Novo": o livro entrou no histórico (history_since) nos últimos 3 dias
# Critério "em oferta" (curadoria-automatica.md §10.8, item 3, aprovado pelo Elias em 2026-10-19).
# Quem não é oferta fica só na Curadoria: fora dos destaques, das ofertas ativas, da contagem e dos canais.
OFERTA_MIN_DESCONTO = 10  # "de/por" mínimo, em %
HIST_DIAS = 30            # com histórico nosso a partir disso, o "de/por" deixa de contar
MEDIANA_MAX = 85          # preço <= 85% da mediana dos dias 8 a 90


def em_oferta(win, seal):
    """Loja vencedora -> é oferta? Com HIST_DIAS ou mais de histórico e a mediana: preço até 85% dela
    ou o selo de 90 dias. Sem isso (histórico curto ou sem median_90d_cents), o "de/por" >= 10%.
    O "menor preço desde" nunca promove. Amazon: o coletor só manda a mediana com a série manual
    cobrindo >= 80% da janela (curator.md 5.7); abaixo disso o campo falta e vale o "de/por"."""
    hs, med = win["history_since"], win["median_90d_cents"]
    if hs and med and (win["checked_at"].astimezone(BRT).date() - hs).days >= HIST_DIAS:
        return seal == "90d" or win["price_cents"] * 100 <= med * MEDIANA_MAX
    return discount(win) >= OFERTA_MIN_DESCONTO


def resolve(books, now):
    """Livro -> oferta exibida: campos do livro + os da loja vencedora, só com lojas no prazo.
    Vencedora: menor price_cents; no empate, a verificada mais recentemente."""
    out = []
    for b in books:
        el = [s for s in b["stores"] if fresh(s, now)]
        # Amazon fora do prazo e nenhuma loja no prazo (decisão do Elias, 2026-10-21): o livro fica como
        # estava, com a última leitura da Amazon e o aviso VELHO. ML fora do prazo e sem Amazon: sai da lista.
        velho = not el
        if velho:
            el = [s for s in b["stores"] if s["store"] == "amazon"]
            if not el:
                continue
        win = min(el, key=lambda s: (s["price_cents"], -s["checked_at"].timestamp()))
        seal, since = seal_of(win, el)
        hs = [s["history_since"] for s in b["stores"]]
        novo = None not in hs and (now.astimezone(BRT).date() - min(hs)).days < NEW_DAYS
        out.append({**b, **win, "novo": novo, "oferta": em_oferta(win, seal) and not (velho and now - win["checked_at"] > VELHO_OFERTA), "velho": velho, "stores": el,
                    "alt": next((s for s in el if s is not win), None),
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


def ofertas(items):
    return [o for o in items if o["oferta"]]


FAIXAS = (40, 50)  # filtro por desconto: /ofertas/40/ e /ofertas/50/ (pedido do Elias, Black Friday 2026)


def com_desconto(items, t):
    """Faixa de desconto: oferta ativa, com preço no prazo e o desconto do card (off) >= t%. Só ofertas
    (decisão do Elias, 2026-11-05): o "de" de livro fora da vitrine não vale, e o card não mostra %.
    Sem os vencidos: desconto de preço velho não entra num filtro de "agora"."""
    return [o for o in ofertas(items) if not o["velho"] and off(o) >= t]


def faixas(offers, cur=None):
    """Pílulas Todas / 40%+ / 50%+, com a contagem. São links para páginas do build: funcionam sem JS."""
    opts = [("/ofertas/", "Todas", len(ofertas(offers)), 0)]
    opts += [(f"/ofertas/{t}/", f"{t}%+", len(com_desconto(offers, t)), t) for t in FAIXAS]
    cur_ = ' aria-current="page"'
    lis = "".join(f'<li><a class="pill" href="{h}"{cur_ if t == cur else ""}>{l}'
                  f'<span class="faixa-n">{n}<span class="sr"> livros</span></span></a></li>' for h, l, n, t in opts)
    return f'<nav class="faixas" aria-label="Faixa de desconto"><ul>{lis}</ul></nav>'


def recentes(items):
    """Entrada mais recente no histórico primeiro, depois o título. Nunca score nem ranking."""
    def key(o):
        hs = [s["history_since"] for s in o["stores"] if s["history_since"]]
        return (-(min(hs).toordinal() if hs else 0), fold(o["title"]))
    return sorted(items, key=key)


def sem_oferta(items):
    return recentes(o for o in items if not o["oferta"])


CAMPANHA = (date(2026, 11, 5), date(2026, 12, 1))  # inclusive, em BRT
BF_MIN = 30  # % de desconto para o destaque e para a página /black-friday/


def campanha(now):
    """None antes da janela, "on" dentro dela, "fim" depois. now: o relógio do build (o["now"])."""
    d = now.astimezone(BRT).date()
    return None if d < CAMPANHA[0] else "on" if d <= CAMPANHA[1] else "fim"


def bf_on(offers):
    return bool(offers) and campanha(offers[0]["now"]) == "on"


def forte(o):
    """Desconto grande durante a campanha: sticker e pílula invertidos (--text sobre --bg)."""
    return off(o) >= BF_MIN and campanha(o["now"]) == "on"


def off(o):
    """Desconto que pode aparecer na tela: só em oferta (sem oferta não mostra riscado nem %)."""
    return discount(o) if o["oferta"] else 0


def discount(o):
    return (o["list_price_cents"] - o["price_cents"]) * 100 // o["list_price_cents"]  # piso: não exagera


def seal(o):
    """"90d" só com 90 dias reais de histórico (CDC); "since" com histórico curto; senão None."""
    return o["seal"]


def post_text(o, url):
    """Texto puro do post nos canais (sem parse_mode). url = nosso /r/<id>[/tg|/wa], nunca a da loja."""
    p = urlsplit(url)
    if (p.scheme != "https" or not p.hostname or p.hostname in ALLOWED_HOSTS
            or p.path not in {f"/r/{o['id']}", f"/r/{o['id']}/tg", f"/r/{o['id']}/wa", f"/r/{o['id']}/bot"}
            or p.query or p.fragment):
        raise Invalid(f"post_text só aceita o /r/ do nosso domínio: {url!r}")
    if not o.get("oferta"):
        raise Invalid(f"post_text só publica oferta; {o['id']!r} está sem oferta")
    if o["velho"]:
        raise Invalid(f"post_text não publica preço fora do prazo: {o['id']!r}")
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


def series(s):
    """Série diária de uma loja (ou da vencedora, que traz os campos dela): os pontos anteriores ao dia
    da verificação + o preço atual, que vale para esse dia. Sem nenhum dia anterior, não há série."""
    day = s["checked_at"].astimezone(BRT).date()
    old = [(d, c) for d, c in s["price_points"] if d < day]
    return old + [(day, s["price_cents"])] if old else []


def chart_label(o, pts):
    """"90 dias" só com o selo de 90 dias válido E pontos cobrindo os 90 dias; senão "desde DD/MM"."""
    first, last = pts[0][0], pts[-1][0]
    lo, hi = min(c for _, c in pts), max(c for _, c in pts)
    when_ = "90 dias" if seal(o) == "90d" and (last - first).days >= 89 else f"desde {first:%d/%m}"
    return f"{when_}: {brl(lo)}" + (f" a {brl(hi)}" if hi > lo else "")


HC_W, HC_H, HC_X0, HC_X1, HC_Y0, HC_Y1 = 300, 164, 4, 204, 30, 118  # viewBox 300x164; nomes e preços atuais em x >= 210
HC_GAP = 7  # dias sem leitura que quebram a linha (Amazon lida à mão tem buracos)


def chart(o, pad="  "):
    """Histórico da página do livro (docs/marca/grafico-historico.md): uma linha por loja elegível,
    tracejado no menor preço mostrado, ponto no preço atual da vencedora. SVG estático, sem JS e sem
    style= (CSP). A frase vem do selo, nunca do desenho; a tabela por dia é o equivalente acessível."""
    w = hc_window(o)
    if not w:
        if not any(s["price_points"] for s in o["stores"]):
            return ""  # sem histórico no contrato: nada a dizer
        return f'\n{pad}<p class="hist">Primeira leitura em {o["checked_at"].astimezone(BRT):%d/%m}: {brl(o["price_cents"])}.</p>'
    lines, start, today = w
    first = min(pts[0][0] for _, pts in lines)  # o texto diz a data real; start é só o eixo
    span = (today - start).days
    cs = [c for _, pts in lines for _, c in pts]
    lo, hi = min(cs), max(cs)
    X = lambda d: HC_X0 + (d - start).days / span * (HC_X1 - HC_X0)
    Y = lambda c: HC_Y0 + ((hi - c) / (hi - lo) if hi > lo else 1) * (HC_Y1 - HC_Y0)
    svg, ends, segs, boxes, marks = [], [], [], [], []
    svg.append(f'<line class="hc-min" x1="{HC_X0}" y1="{HC_Y1}" x2="{HC_X1}" y2="{HC_Y1}"/>')
    segs.append(((HC_X0, HC_Y1), (HC_X1, HC_Y1)))
    for s, pts in lines:
        cls = "hc-ml" if s["store"] == "mercadolivre" else "hc-amz"  # ML amarelo, Amazon no --text (Elias, 2026-11-04)
        cut = [i == 0 or (d - pts[i - 1][0]).days > HC_GAP for i, (d, _) in enumerate(pts)] + [True]
        xy = [(X(d), Y(c)) for d, c in pts]
        # linha lisa; ponto solto (entre buracos) vira traço de comprimento zero, que a ponta redonda pinta
        d_ = "".join(f'{"M" if cut[i] else "L"}{x:.1f} {y:.1f}' + ("h0" if cut[i] and cut[i + 1] else "")
                     for i, (x, y) in enumerate(xy))
        svg.append(f'<path class="hc-line {cls}" d="{d_}"/>')
        segs.extend((xy[i - 1], xy[i]) if not cut[i] else (xy[i], xy[i]) for i in range(len(xy)))
        last, cur = pts[-1]
        name = STORES[s["store"]] + ("" if last == today else f", {last:%d/%m}")
        ends.append([Y(cur), s["store"] != o["store"], name, cls + ("" if last == today else " hc-old"), cur])
        marks.append(("now", cls, [(X(last), Y(cur))], cur, s["store"] == "amazon" and o["velho"]))
        # 3 marcadores por loja: o mais alto, o degrau mais recente (o último preço antes do atual que difere
        # dele em 3% ou mais: "quanto era logo antes") e o atual. Um valor igual a outro marcador não se repete.
        # Cada marcador tenta os pontos do seu patamar (o rótulo vai no primeiro que tiver espaço).
        top = max(c for _, c in pts)
        if top > cur:
            marks.append(("max", cls, [(X(d), Y(c)) for d, c in pts if c == top], top, False))
        i = next((i for i in reversed(range(len(pts))) if abs(pts[i][1] - cur) >= .03 * cur), None)
        if i is not None and pts[i][1] != top:
            j = i
            while j > 0 and pts[j - 1][1] == pts[i][1]:
                j -= 1
            marks.append(("mid", cls, [(X(d), Y(c)) for d, c in reversed(pts[j:i + 1])], pts[i][1], False))
    for k, _, at, _, _ in marks:  # o ponto atual é obstáculo para os rótulos
        if k == "now":
            boxes.extend((x - 6, y - 6, x + 6, y + 6) for x, y in at)

    def label(txt, x, y, cls):
        """Primeira posição livre (em cima, embaixo, à direita, à esquerda do ponto): dentro da área,
        sem cobrir linha, ponto ou outro rótulo. Nenhuma livre: False, e o marcador sai."""
        w = 7.2 * len(txt)
        for cx, base, anchor in ((x, y - 8, "middle"), (x, y + 17, "middle"), (x + 7, y + 4.5, "start"), (x - 7, y + 4.5, "end")):
            if anchor == "middle":
                cx = min(max(cx, HC_X0 + w / 2), HC_X1 - w / 2)
            x0 = cx - w / 2 if anchor == "middle" else cx if anchor == "start" else cx - w
            box = (x0 - 2, base - 12, x0 + w + 2, base + 3)
            if box[0] < 0 or box[2] > 207 or box[1] < 2 or box[3] > HC_Y1 + 22:
                continue
            if any(hc_hits(box, p, q) for p, q in segs) or any(
                    box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in boxes):
                continue
            boxes.append(box)
            svg.append(f'<text class="{cls}" x="{cx:.1f}" y="{base:.1f}" text-anchor="{anchor}">{txt}</text>')
            return True
        return False

    shown = {m[3] for m in marks if m[0] == "now"}
    for kind in ("max", "mid"):  # o mais alto tem prioridade; se não couber, o intermediário sai primeiro
        for k, cls, at, c, _ in marks:
            if k != kind:
                continue
            for x, y in at:
                boxes.append((x - 5, y - 5, x + 5, y + 5))  # o próprio ponto não pode ficar sob o rótulo
                if label(brl(c), x, y, f"hc-val {cls}"):
                    svg.append(f'<circle class="hc-pt {cls}" cx="{x:.1f}" cy="{y:.1f}" r="3.5"/>')
                    shown.add(c)
                    break
                boxes.pop()
    if lo not in shown:  # o menor só ganha rótulo se não estiver num marcador visível
        label(f"menor {brl(lo)}", HC_X0 + 3.6 * len(f"menor {brl(lo)}"), HC_Y1, "hc-lbl hc-lbl--min")
    for k, cls, at, c, velho in marks:  # o atual de cada loja, em vermelho/rosa, por cima das linhas
        if k == "now":
            x, y = at[0]
            svg.append(f'<circle class="hc-now{" hc-now--velho" if velho else ""}" cx="{x:.1f}" cy="{y:.1f}" r="5"/>')
    ends.sort()  # no empate de altura, a vencedora fica em cima
    for i in range(1, len(ends)):  # blocos de nome + preço atual (30u) sem colidir
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 30)
    for i in reversed(range(len(ends))):  # e sem descer até a linha das datas: a pilha sobe se precisar
        ends[i][0] = min(ends[i][0], HC_Y1 + 2 if i == len(ends) - 1 else ends[i + 1][0] - 30)
    for y, _, name, cls, cur in ends:
        svg.append(f'<text class="hc-name {cls}" x="210" y="{y + 4.5:.1f}">{e(name)}</text>'
                   f'<text class="hc-now-lbl" x="210" y="{y + 18.5:.1f}">{brl(cur)}</text>')
    svg.append(f'<text class="hc-lbl" x="{HC_X0}" y="{HC_H - 6}">{start:%d/%m}</text>'
               f'<text class="hc-lbl" x="{HC_X1}" y="{HC_H - 6}" text-anchor="end">hoje</text>')
    return f"""\n{pad}<figure class="hc" id="historico">
{pad}  <svg viewBox="0 0 {HC_W} {HC_H}" width="100%" role="img" aria-labelledby="hc-t" focusable="false"><title id="hc-t">{e(hc_title(lines, first, today))}</title>{"".join(svg)}</svg>
{pad}  <figcaption>{e(hc_phrase(o, first, lo, hi))}</figcaption>
{pad}  {hc_table(lines)}
{pad}</figure>"""


def hc_hits(box, p, q):
    """O segmento p-q passa pelo retângulo? Amostragem a cada ~2u: basta para rótulos de 13u."""
    n = max(1, int(max(abs(q[0] - p[0]), abs(q[1] - p[1])) / 2))
    return any(box[0] <= p[0] + (q[0] - p[0]) * k / n <= box[2] and box[1] <= p[1] + (q[1] - p[1]) * k / n <= box[3]
               for k in range(n + 1))


def hc_window(o):
    """(linhas [(loja, pontos)], início do eixo, hoje) ou None. Janela de 90 dias até hoje, eixo mínimo de 7.
    Amazon vencida há mais de 90 dias fica sem ponto na janela: sem gráfico (e sem link no card)."""
    lines = [(s, pts) for s in o["stores"] if (pts := series(s))]
    if not lines:
        return None
    # checked_at até 5 min no futuro (SKEW) pode cair no dia seguinte: o eixo vai até o último ponto
    today = max(o["now"].astimezone(BRT).date(), max(pts[-1][0] for _, pts in lines))
    start = max(min(pts[0][0] for _, pts in lines), today - timedelta(days=89))
    start = min(start, today - timedelta(days=6))  # eixo mínimo de 7 dias: histórico novo fica à direita
    lines = [(s, kept) for s, pts in lines if (kept := [(d, c) for d, c in pts if d >= start])]
    return (lines, start, today) if lines else None


def has_hc(o):
    return hc_window(o) is not None


def card_hist(o):
    """Selo do card + link "ver histórico" logo abaixo (decisão do Elias, 2026-11-04). Só com gráfico de verdade
    (has_hc): sem price_points, nada de link para gráfico vazio. Sem JS vai à âncora; com JS abre o modal."""
    if not has_hc(o):
        return stamp_html(o)
    oid = e(o["id"])
    return (f'{stamp_html(o)}<a class="ver-hist" href="/livro/{oid}/#historico" data-modal="{oid}">'
            f'ver histórico<span class="sr"> de preço: {e(o["title"])}</span></a>')


def hc_title(lines, start, today):
    out = [f"Preço desde {start:%d/%m}."]
    for s, pts in lines:
        cs = [c for _, c in pts]
        d, c = pts[-1]
        now_ = f"hoje {brl(c)}" if d == today else f"último {brl(c)} em {d:%d/%m}"
        out.append(f"{STORES[s['store']]}: menor {brl(min(cs))}, maior {brl(max(cs))}, {now_}.")
    return " ".join(out).replace("\u00a0", " ")


def hc_phrase(o, start, lo, hi):
    """Frase do selo (seal_of), para o gráfico nunca contradizer o selo do card."""
    quem = "O último preço visto é" if o["velho"] else "Hoje é"
    if o["seal"] == "90d":
        return f"{quem} o menor preço dos últimos 90 dias."
    if o["seal"] == "since":
        return f"{quem} o menor preço desde {o['since']:%d/%m}."
    return f"Desde {start:%d/%m}: {brl(lo)}" + (f" a {brl(hi)}." if hi > lo else ".")


def hc_table(lines):
    """Menor preço do dia por loja, do dia mais novo ao mais velho, só dias com leitura."""
    by = [dict(pts) for _, pts in lines]
    head = "".join(f'<th scope="col">{STORES[s["store"]]}</th>' for s, _ in lines)
    sem = '<span aria-hidden="true">—</span><span class="sr">sem leitura</span>'
    rows = "".join(f'<tr><th scope="row">{d:%d/%m}</th>' + "".join(f"<td>{brl(m[d]) if d in m else sem}</td>" for m in by) + "</tr>"
                   for d in sorted(set().union(*by), reverse=True))
    return (f'<details class="hc-tab"><summary>Ver preços por dia</summary><table><caption class="sr">Menor preço do dia, por loja</caption>'
            f'<thead><tr><th scope="col">Dia</th>{head}</tr></thead><tbody>{rows}</tbody></table></details>')


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
    old = f'. <span class="velho">{VELHO}</span>' if o["velho"] else ""
    return f'<span class="store">{na(o["store"])}</span>, {checked(o, o["now"])}{fell}{old}'


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
    g, t, oid, off_ = o["genre"], e(o["title"]), e(o["id"]), off(o)
    b = badge(o)
    bdg = f'<span class="badge badge--{b[0]}">{b[1]}</span>' if b else ""
    stk = (f'<span class="sticker{" sticker--forte" if forte(o) else ""}" aria-hidden="true">−{off_}%</span>'
           if off_ else "")
    old = (f' <s class="old"><span class="sr">De </span>{brl(o["list_price_cents"])}</s>'
           f'<span class="sr">, {off_}% de desconto</span>' if off_ else "")
    if not o["oferta"]:
        old = ' <span class="sem">Sem oferta agora</span>'
    velho = f' <span class="velho">{VELHO}</span>' if o["velho"] else ""
    hs = [s["history_since"] for s in o["stores"] if s["history_since"]]
    rec = f'{min(hs) if hs else "0000-00-00"}|{o["checked_at"].astimezone(timezone.utc):%Y-%m-%dT%H:%M}'
    return f"""<li class="card" data-g="{g}" data-id="{oid}" data-q="{e(fold(o["title"] + " " + o["author"]))}" data-preco="{o["price_cents"]}" data-off="{off_}" data-rec="{rec}" data-tipo="{tipo(o)}">
  <div class="sleeve">{obj(o)}{bdg}{stk}{alert_link(o, bot, full=False)}</div>
  <div class="card-body">
    <p class="card-meta">{avatar(g, "av av--sm")}<span><span class="store">{STORES[o["store"]]}</span> <span>{checked(o, o["now"])}</span>{velho}</span></p>
    <h{h} class="card-title"><a href="/livro/{oid}/" data-modal="{oid}">{t}</a></h{h}>
    <p class="card-sub">{e(o["author"])}</p>
    {card_hist(o)}
    <div class="card-foot"><p class="price"><span class="sr">Por </span><strong>{brl(o["price_cents"])}</strong>{old}</p>{alt_details(o)}{buy_circle(o)}</div>
  </div>
</li>"""


def tipo(o):
    return "oferta" if o["oferta"] else "sem-oferta"


def badge(o):
    """("novo", rótulo) só com dado real: history_since recente. Nada de "Em alta" (ranking é interno)
    nem "Só N em estoque" (não temos o dado)."""
    return ("novo", "Novo") if o["novo"] else None


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


SOON = '<span class="sr">, </span><span class="soon">em breve</span>'
CHANNELS = ("Telegram", "WhatsApp")


def cta(href, inner, cls, sr="", rel="noopener noreferrer"):
    """Link real quando há destino; sem ele (env ausente ou vazia), o mesmo componente no estado
    "em breve": <span> com aria-disabled, fora do tab, com a etiqueta também no texto acessível.
    Nunca <a href="#">."""
    if href:
        return f'<a class="{cls}" href="{e(href)}" rel="{rel}" target="_blank">{inner}{sr}</a>'
    return f'<span class="{cls} is-soon" aria-disabled="true">{inner}{SOON}</span>'


def chan_urls(ch):
    """{nome: url ou None} dos dois canais, sempre os dois (o ausente sai "em breve")."""
    links = dict(ch)
    return {n: links.get(n) for n in CHANNELS}


def alert_link(o, bot, full=True):
    """Me avise se baixar (Telegram): texto completo no hero, no modal e na página; sino no card.
    Sem TELEGRAM_BOT_USERNAME, o mesmo botão no estado "em breve"."""
    t = e(o["title"])
    href = tg_alert_url(bot, o["id"]) if bot else None
    if full:
        return cta(href, f'{icon("sino")}Me avise se baixar (Telegram)', "btn btn--ghost alert",
                   f'<span class="sr">: alerta de preço de {t} (abre o Telegram)</span>')
    return cta(href, f'{icon("sino")}<span class="sr">Me avise se baixar (Telegram): alerta de preço de {t}</span>', "bell")


def slide(o, k, n, bot=None):
    g, t = o["genre"], e(o["title"])
    chips = [f'<span class="chip chip--g">{icon("g-" + g)}{e(GENRES[g])}</span>']
    b = badge(o)
    if not o["oferta"]:  # livro da curadoria completando o hero: chip próprio, sem desconto nem riscado
        chips.append('<span class="chip chip--nov">Da curadoria</span>')
    elif b:
        chips.append(f'<span class="chip chip--{b[0]}">{b[1]}</span>')
    off = discount(o) if o["oferta"] else 0
    old = f' <s class="old"><span class="sr">De </span>{brl(o["list_price_cents"])}</s>' if off else ""
    pill = f'<span class="off-pill{" off-pill--forte" if forte(o) else ""}">−{off}%</span>' if off else ""
    blurb = f'\n    <p class="blurb">{e(o["blurb"])}</p>' if o["blurb"] else ""
    stamp = stamp_html(o)
    long = " hero-title--long" if len(o["title"]) > 38 else ""
    aria = f' role="group" aria-roledescription="slide" aria-label="{k} de {n}"' if n > 1 else ""
    return f"""<div class="slide" id="d-{e(o["id"])}" data-g="{g}" data-tipo="{tipo(o)}"{aria}>
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
    """Destaque logo depois do header, com 1 a 5 livros. Com 2 ou mais é carrossel: sem JS, passagem
    por @keyframes, pausa (hover, foco, checkbox) e segmentos que são links para cada slide; com JS,
    setas, arraste, contador e barra. Com 1 livro não há controles nem passagem."""
    n = len(items)
    if not 1 <= n <= 5:
        return ""
    slides = "\n".join(slide(o, k, n, bot) for k, o in enumerate(items, 1))
    if n == 1:
        return f"""<section class="hero hero--1" aria-labelledby="h-destaque">
<h2 class="sr" id="h-destaque">Em destaque</h2>
<div class="hero-view">
<div class="hero-track">
{slides}
</div>
</div>
</section>"""
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


def hero_items(offers):
    """Até 5 para o hero: as ofertas primeiro (featured, selo, desconto) e, se faltarem, livros sem
    oferta (entrada mais recente primeiro), marcados "Da curadoria"."""
    top = ranked(ofertas(offers))[:5]
    return top + sem_oferta(offers)[:5 - len(top)]


def section(sid, title, body, count=None, note="", unit=("oferta", "ofertas")):
    """Cabeçalho de seção: H2, contador com rótulo por extenso ("10 ofertas no momento") e uma frase curta.
    data-s/data-p: o app.js reescreve a contagem depois de buscar ou filtrar, no singular ou plural."""
    n = (f'<span class="sec-n" data-s="{unit[0]} no momento" data-p="{unit[1]} no momento">'
         f'{count} {unit[0] if count == 1 else unit[1]} no momento</span>' if count is not None else "")
    note = f'<p class="sec-note">{note}</p>' if note else ""
    return (f'<section class="sec" aria-labelledby="{sid}">\n<div class="sec-head"><h2 id="{sid}">{title}</h2>{n}{note}</div>'
            f'\n{body}\n</section>')


def aneis(cls=""):
    """Anéis de carimbo girando devagar: a textura dos blocos marinho (o "sulco" da spec)."""
    return f'<span class="aneis {cls}" aria-hidden="true"></span>'


def ch_buttons(ch, big=False):
    """WhatsApp verde e Telegram em contorno; o canal sem env sai "em breve"."""
    out = []
    for name, url in chan_urls(ch).items():
        cls = ("btn btn--wa" if name == "WhatsApp" else "btn btn--tg") + (" btn--big" if big else "")
        out.append(cta(url, f'{icon("wa" if name == "WhatsApp" else "tg")}Canal no {name}', cls,
                       '<span class="sr"> (abre em nova aba)</span>'))
    return "".join(out)


def strip_canais(ch, at):
    """Faixa dos canais dentro do grid, largura toda. Sem as envs, os botões saem "em breve"."""
    return f"""<li class="blk blk--canais" data-at="{at}">
  <span class="radar" aria-hidden="true"></span>
  <div><h3 class="blk-h">Receba as próximas ofertas <em>de graça</em></h3>
  <p>As mesmas ofertas do site, com o preço conferido, chegam no canal. Sem cadastro.</p></div>
  <div class="blk-acts">{ch_buttons(ch)}</div>{aneis()}
</li>"""


def banner_bot(bot, at):
    """Banner do alerta em 2 colunas do grid. Sem TELEGRAM_BOT_USERNAME, o botão sai "em breve"."""
    return f"""<li class="blk blk--bot" data-at="{at}">
  <span class="mascote" aria-hidden="true"><img src="/mavi.svg" alt="" width="640" height="640" decoding="async"></span>
  <p class="kicker">{icon("sino")}Alerta grátis no Telegram</p>
  <h3 class="blk-h">Escolha o livro. A gente avisa quando entrar em oferta.</h3>
  <p>{"Toque no sino de qualquer livro e o bot avisa quando ele entrar em oferta. Para apagar tudo, mande /parar ao bot." if bot
      else "Em breve: toque no sino de qualquer livro e o bot vai avisar quando ele entrar em oferta."}</p>
  <p>{cta(bot and f"https://t.me/{bot}", f'Ativar alertas{icon("seta")}', "go", '<span class="sr"> (abre o Telegram)</span>')}</p>{aneis()}
</li>"""


FEAT_MAX = 10
# Quantos cards a home mostra antes do "Ver todas" (celular, desktop). O CSS corta; a busca e o
# filtro do JS (classe .filtrando) mostram tudo. As páginas completas usam o "carregar mais" do JS.
CAP = (4, 24)  # ofertas na home (celular: 4 + 4 da curadoria cabem na meta de 5.000 px)
CUR_MAX = 8    # livros sem oferta na seção "Da curadoria" da home e do nicho


def mais(href, label, m=""):
    return f'<p class="mais{m}"><a class="btn btn--ghost" href="{href}">{icon("livro", "i i-livro")}{label}</a></p>'


def ver_todas(n, home):
    if not home or n <= CAP[0]:
        return ""
    return mais("/ofertas/", f"Ver todas as {n} ofertas",
                " mais--m" if n <= CAP[1] else "")  # só no celular quando o desktop já mostra todas


def feed(offers, bot=None, ch=(), full=False, pills="", items=None):
    """Ofertas ativas: ordenação (JS), grid com blocos intercalados e "Ver todas" / "carregar mais".
    Os blocos guardam a posição (data-at) para o JS recolocá-los depois de ordenar ou filtrar.
    Sem nenhuma oferta, um estado vazio que aponta para a curadoria e o alerta."""
    items = ofertas(offers) if items is None else items
    n = len(items)
    if not n:
        return ('<section class="sec" aria-labelledby="h-ativas">\n<div class="sec-head"><h2 id="h-ativas">Ofertas ativas</h2></div>\n'
                '<p class="vazio vazio--fixo">Nenhuma oferta conferida agora. Veja a <a href="/curadoria/">curadoria</a> '
                'ou toque no sino de um livro para ser avisado.</p>\n</section>')
    cards = [card(o, bot) for o in items]
    for at, html_ in ((8, strip_canais(ch, 8)), (4, banner_bot(bot, 4))):
        cards.insert(min(at, len(cards)), html_)
    tools = ('<div class="feed-tools" hidden><label for="ordem">Ordenar por</label><select id="ordem">'
             '<option value="">Em destaque</option><option value="preco">Menor preço</option>'
             '<option value="off">Maior desconto</option><option value="rec">Mais recentes</option></select></div>')
    more = ver_todas(n, not full) + (
        f'<p class="mais"><button class="btn btn--ghost js-mais" type="button" hidden>{icon("livro", "i i-livro")}'
        'Carregar mais ofertas</button></p>' if full else "")
    body = (f'{pills}{tools}\n<p class="vazio" hidden role="status">Nenhuma oferta com esse título ou autor. '
            f'Tente outro nome ou volte para Todos.</p>\n<ul class="grid feed{" feed--full" if full else " feed--home"}">\n'
            + "\n".join(cards) + f"\n</ul>\n{more}")
    return section("h-ativas", "Ofertas ativas", body, n, "Conferidas na loja. A que vence sai da lista.")


CUR_NOTE = "Livros escolhidos por nós, ainda sem oferta. Toque no sino e avisamos quando entrar em oferta."


def da_curadoria(offers, bot=None, genre=None, skip=()):
    """"Da curadoria": até CUR_MAX livros sem oferta, com o link para a área. Sem nenhum, a seção não sai.
    skip: os que já estão no hero vão para o fim (no celular aparecem 4)."""
    items = sem_oferta(offers)
    items = ([o for o in items if o["id"] not in skip] + [o for o in items if o["id"] in skip])[:CUR_MAX]
    if not items:
        return ""
    body = ('<ul class="grid feed feed--cur feed--home">\n' + "\n".join(card(o, bot) for o in items)
            + "\n</ul>\n" + mais(f"/curadoria/{'#' + genre if genre else ''}", "Ver toda a curadoria"))
    return section("h-da-curadoria", "Da curadoria", body, note=CUR_NOTE)


def ranked(offers):
    """Destaque: featured primeiro; sem ele, selo válido e depois o maior desconto."""
    return sorted(offers, key=lambda o: (not o["featured"], seal(o) is None, -discount(o)))


def bot_block(bot):
    """Capítulo marinho do alerta. Sem o bot, o botão sai "em breve". O pedido de livro é o form do fab."""
    url = bot and f"https://t.me/{bot}"
    steps = ("Escolha o livro e toque no sino", "No Telegram, toque em Iniciar", "Quando entrar em oferta, avisamos")
    lis = "".join(f'<li><span class="n">{k}</span>{t}</li>' for k, t in enumerate(steps, 1))
    return f"""<section class="bot" aria-labelledby="h-bot">
  <div class="bot-art" aria-hidden="true"><span class="radar radar--big"></span><span class="mascote mascote--big"><img src="/mavi.svg" alt="" width="640" height="640" decoding="async"></span></div>
  <div class="bot-text">
    <p class="kicker">{icon("sino")}Seu alerta no Telegram</p>
    <h2 id="h-bot">Avisamos quando o livro entrar em oferta. <em>Você só escolhe qual.</em></h2>
    <ol class="passos">{lis}</ol>
    <p class="bot-acts">{cta(url, f'Ativar no Telegram{icon("seta")}', "go", '<span class="sr"> (abre o Telegram)</span>')}</p>
    <p class="bot-note">{"O bot avisa uma vez por oferta, das 8h às 22h, e guarda o número da conversa, a sua lista e quando avisou. Para apagar tudo, mande /parar ao bot." if bot else "Quando estiver no ar, o bot vai guardar o número da conversa, a sua lista e quando avisou, e para apagar tudo bastará mandar /parar ao bot."} Veja a <a href="/privacidade/">privacidade</a>.</p>
  </div>{aneis("aneis--big")}
</section>"""


def channels_block(ch):
    """Seção dos canais (cartão claro). Canal sem env sai "em breve"; sem nenhum, sem o link de /canais/."""
    return f"""<section class="canais" aria-labelledby="h-canais">
  <p class="kicker kicker--muted">Canais gratuitos</p>
  <h2 id="h-canais">As ofertas inteiras, <em>no seu celular.</em></h2>
  <p class="canais-p">As mesmas ofertas do site, com o preço conferido e o horário da verificação. Só leitura, sem cadastro.</p>
  <p class="canais-acts">{ch_buttons(ch, big=True)}</p>
  {'<p><a class="link" href="/canais/">Como funcionam os canais</a></p>' if ch else ""}
</section>"""


def faq(bot, ch):
    """Perguntas sobre o que o site faz de verdade: curadoria, histórico, alerta, canais e afiliado."""
    qa = [("Como vocês escolhem as ofertas?",
           "Acompanhamos o preço de uma lista de livros na Amazon e no Mercado Livre. Só vira oferta o livro "
           "que está mais barato do que costuma ficar, e cada preço mostra o horário em que foi conferido na loja. "
           "Quando o preço volta a subir, o livro sai das ofertas e fica na curadoria; quando o preço fica velho, sai do site."),
          ("O que quer dizer “menor preço em 90 dias”?",
           "Que o preço de agora é o menor que registramos nos últimos 90 dias, em todas as lojas em que o livro "
           "está à venda. O selo só aparece quando temos 90 dias de histórico de verdade; com menos, mostramos "
           "“menor preço desde” a data em que começamos a acompanhar."),
          ("O preço do site é o mesmo da loja?",
           "Era no horário indicado em cada oferta. Preço muda rápido, então o preço final é sempre o da loja, "
           "na hora da compra.")]
    if bot:
        qa.append(("Como funciona o aviso de oferta?",
                   f'Toque no sino de um livro (ou em “Me avise se baixar”), ou mande o título ou o autor ao bot '
                   f'<a href="https://t.me/{e(bot)}" rel="noopener noreferrer" target="_blank">@' + e(bot) + '</a>. '
                   'Ele avisa por lá quando o livro entrar em oferta, com o mesmo critério do site e do canal: uma vez '
                   'por oferta, das 8h às 22h, e de novo se o preço cair mais. Em /lista você vê e tira livros; '
                   'para apagar tudo, /parar.'))
    else:  # o bot ainda não responde: nada de prometer que o alerta já funciona
        qa.append(("Como vai funcionar o aviso de oferta?",
                   "Em breve você poderá tocar no sino de um livro (ou em “Me avise se baixar”) e o nosso bot no "
                   "Telegram vai avisar quando ele entrar em oferta. Por enquanto o bot ainda não está no ar."))
    if ch:
        qa.append(("Onde mais recebo as ofertas?",
                   "Nos canais " + " e ".join(n for n, _ in ch) + ', que repetem as ofertas do site. '
                   '<a href="/canais/">Veja como funcionam</a>.'))
    else:
        qa.append(("Vai ter canal no Telegram ou no WhatsApp?",
                   "Em breve. Os canais vão repetir as ofertas do site, com o preço conferido e o horário da verificação."))
    qa.append(("Vocês ganham com isso?",
               "Sim. Os links são de afiliado: como associados da Amazon e afiliados do Mercado Livre, ganhamos uma "
               "comissão com compras qualificadas, sem custo a mais para você. Isso não muda qual oferta entra no site."))
    items = "".join(f'<details><summary>{q}{icon("chev")}</summary><p>{a}</p></details>' for q, a in qa)
    return f"""<section class="faq" aria-labelledby="h-faq">
  <p class="kicker kicker--muted">Perguntas</p>
  <h2 id="h-faq">Como o site funciona</h2>
  <div class="faq-list">{items}</div>
</section>"""


PEDIDO_OK = "Recebemos seu pedido. Obrigado! Se o livro entrar em oferta, ele aparece aqui e nos canais."


def fab():
    """Botão flutuante "Pedir um livro": <details> que abre o form sem JS (docs/produto/pedido-de-livro.md).
    O POST vai para SITE/pedido, onde o Worker (worker/pedido.js) confere o honeypot "site" e manda o pedido
    por e-mail; o destino fica só no segredo do Worker. Sem JS, a volta é SITE/#pedido-recebido e o :target mostra o
    aviso; com JS (app.js), o envio é por fetch e o aviso aparece no próprio painel."""
    return f"""<details class="fab-box" id="pedir">
<summary class="fab">{icon("busca")}<span class="fab-t">Pedir um livro</span></summary>
<form class="pedir" name="pedido" method="POST" action="{SITE}/pedido" accept-charset="utf-8">
<button class="pedir-x js-px" type="button" hidden>{icon("x")}<span class="sr">Fechar</span></button>
<p class="sr" aria-hidden="true"><label>Não preencha <input name="site" tabindex="-1" autocomplete="off"></label></p>
<p class="pedir-h">Qual livro você quer ver aqui?</p>
<label for="p-titulo">Nome do livro</label><input id="p-titulo" name="titulo" required maxlength="150" autocomplete="off">
<label for="p-autor">Autor do livro <span>(opcional)</span></label><input id="p-autor" name="autor" maxlength="100" autocomplete="off">
<button class="go" type="submit">Enviar pedido</button>
<p class="pedir-ok" role="status" data-ok="{PEDIDO_OK}"></p>
</form>
</details>
<p class="pedido-recebido" id="pedido-recebido">{PEDIDO_OK} <a href="#pedir">Fechar</a></p>"""


def home_sections(offers, bot=None, ch=()):
    """Hero (até 5, ofertas primeiro e livros sem oferta completando), destaques (ofertas fora do hero),
    filtro, ofertas ativas e "Da curadoria". Nas listas, o que já apareceu acima vai para o fim:
    nenhum livro em mais de 2 lugares, e no celular os primeiros cards são livros novos para quem rola."""
    slides = hero_items(offers)
    top = ranked(ofertas(offers))
    curated = any(o["featured"] for o in top)
    in_hero = {o["id"] for o in slides}
    feat = [o for o in top if o["id"] not in in_hero and (o["featured"] or not curated)][:FEAT_MAX]
    shown = in_hero | {o["id"] for o in feat}
    order = [o for o in offers if o["id"] not in shown] + [o for o in offers if o["id"] in shown]
    parts = [
        hero(slides, bot),
        feat and section("h-curadoria", "Destaques da curadoria" if curated else "Destaques de hoje",
                         '<ul class="grid grid--feat">\n' + "\n".join(card(o, bot) for o in feat) + "\n</ul>",
                         len(feat), "" if curated else "Primeiro o menor preço do histórico, depois o maior desconto."),
        nav(offers, None, filtro=True),
        feed(order, bot, ch, pills=faixas(offers)),
        da_curadoria(offers, bot, skip=in_hero),
        bot_block(bot),
        channels_block(ch),
        faq(bot, ch),
        fab(),
    ]
    return "\n".join(p for p in parts if p)


GENRE_DESC = {
    "literatura-brasileira": "Clássicos e contemporâneos daqui",
    "ficcao": "Clássicos e contemporâneos de fora",
    "romance": "Histórias de amor, do clássico ao novo",
    "fantasia": "Sagas, mundos mágicos e futuro",
    "suspense": "Thriller, mistério e crime",
    "mindset": "Foco, hábitos e desenvolvimento pessoal",
    "negocios": "Carreira, gestão e dinheiro",
    "politica": "Democracia, poder e ideias",
    "historia": "Do passado às vidas que marcaram",
    "manga": "Mangá, HQ e graphic novel",
}
assert set(GENRE_DESC) == set(GENRES)


def nav(offers, current, filtro=False):
    """Filtro por nicho: círculos com o ícone de cada nicho (o lugar do curador ilustrado).
    São links para /<nicho>/; com filtro=True (home e /ofertas/), o app.js filtra sem recarregar."""
    present = [g for g in GENRES if any(o["genre"] == g for o in offers)]
    def n(items):  # conta ofertas; nicho sem oferta conta os livros, sem "0 ofertas"
        k, m = len(ofertas(items)), len(items)
        return f'{k} {"oferta" if k == 1 else "ofertas"}' if k else f'{m} {"livro" if m == 1 else "livros"}'

    spines = "".join(f'<i data-g="{g}"></i>' for g in present)
    items = [("/", "", "Todos", "Ofertas e curadoria", offers,
              f'<span class="spines">{spines}</span>', current is None)]
    items += [(f"/{g}/", g, GENRES[g], GENRE_DESC[g], [o for o in offers if o["genre"] == g],
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
    "carimbo": '<circle cx="12" cy="12" r="10.5"/><circle cx="12" cy="12" r="7.8" stroke-width="1"/>'
               '<path fill="currentColor" stroke="none" transform="translate(12 12.4) scale(.6) translate(-16 -16.6)" '
               'd="M9.6 12.4C11.6 11.5 13.8 11.6 15.3 12.8V21.6C13.8 20.5 11.6 20.4 9.6 21.2ZM22.4 12.4C20.4 11.5 18.2 11.6 16.7 12.8V21.6C18.2 20.5 20.4 20.4 22.4 21.2Z"/>',
    "livro": '<path d="M3 6c3-1.5 6-1.5 9 0v13c-3-1.5-6-1.5-9 0zM21 6c-3-1.5-6-1.5-9 0v13c3-1.5 6-1.5 9 0z"/>',
    # um por nicho: o lugar do curador ilustrado, até haver arte
    "g-literatura-brasileira": '<path d="M5 19C5 10 11 5 19 5c0 8-5 14-14 14zM5 19l8-8M9 15h4M11 13V9"/>',
    "g-ficcao": '<path d="M15 4a7.5 7.5 0 1 0 5.5 11.5A6 6 0 0 1 15 4zM6 3v4M4 5h4"/>',
    "g-negocios": '<path d="M4 20h16M6 16l4.5-4.5 3 3L19 9M15 9h4v4"/>',
    "g-romance": '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    "g-fantasia": '<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2zM19 3v4M17 5h4"/>',
    "g-suspense": '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"/><circle cx="12" cy="12" r="2.5"/>',
    "g-mindset": '<path d="M3 20h18M6 20l5-9 3 5 2-3 3 7M11 11V4l5 2-5 2"/>',
    "g-politica": '<path d="M3 9l9-5 9 5M5 9v9M10 9v9M14 9v9M19 9v9M3 20h18"/>',
    "g-historia": '<path d="M6 3h12M6 21h12M7 3c0 5 5 6 5 9s-5 4-5 9M17 3c0 5-5 6-5 9s5 4 5 9"/>',
    "g-manga": '<path d="M4 4h16v12h-9l-4.5 4v-4H4z"/><path d="m13 6.5-3 4h3.5l-2.5 3.5"/>',
}
SPRITE = ('<svg class="sprite" hidden aria-hidden="true">'
          + "".join(f'<symbol id="i-{k}" viewBox="0 0 24 24">{v}</symbol>' for k, v in ICONS.items()) + "</svg>")
assert set(f"g-{g}" for g in GENRES) <= set(ICONS)


def icon(name, cls="i"):
    return f'<svg class="{cls}" aria-hidden="true" focusable="false"><use href="#i-{name}"/></svg>'


def carimbo(offers, cls):
    """Carimbo "conferido DD/MM às HHhMM" com o horário da coleta mais recente (estilo do v1: girado,
    vermelho, só CSS). Não é link nem botão. Sai duas vezes: na barra (desktop) e no topo do conteúdo
    (celular, onde a barra não tem largura); o CSS mostra uma só, então o leitor de tela lê uma só."""
    latest = max(o["checked_at"] for o in offers)
    d = latest.astimezone(BRT)
    return (f'<p class="carimbo {cls}"><span>conferido</span> <time datetime="{e(latest.isoformat())}">'
            f'<b>{d:%d/%m}</b> às {d:%H}h{d:%M}</time></p>')


def header(offers, ch):
    """Header de vidro. Buscar e tema só funcionam com JS: saem com hidden e o app.js mostra."""
    nav = [f'<button class="pill js-busca" type="button" hidden aria-expanded="false" aria-controls="busca">'
           f'{icon("busca")}<span class="pill-t">Buscar</span></button>',
           f'<button class="pill pill--ico js-tema" type="button" hidden aria-pressed="false">'
           f'{icon("sol", "i i-sol")}{icon("lua", "i i-lua")}<span class="sr">Tema escuro</span></button>']
    urls = chan_urls(ch)  # canal sem env: a mesma pílula, "em breve"
    nav.append(cta(urls["Telegram"], f'{icon("tg")}<span class="pill-t">Telegram</span>', "pill pill--tg",
                   '<span class="sr"> (abre em nova aba)</span>'))
    nav.append(cta(urls["WhatsApp"], f'{icon("wa")}<span class="pill-t">Canal no WhatsApp</span>', "pill pill--wa",
                   '<span class="sr"> (abre em nova aba)</span>'))
    return f"""<header class="top">
<div class="top-bar">
{brand()}
{carimbo(offers, "carimbo--bar")}
<nav class="acoes" aria-label="Atalhos">{"".join(nav)}</nav>
</div>
<div class="busca" id="busca" hidden><label class="sr" for="q">Buscar por título ou autor</label><input id="q" name="busca" type="search" placeholder="Título ou autor…" autocomplete="off" spellcheck="false" enterkeyhint="search"></div>
</header>"""


# Faixa da campanha: texto fixo (nenhum dado do JSON). Três tamanhos: completo, celular e ≤ 359 px.
FAIXA = ('<p class="sazonal"><a href="/black-friday/"><strong><span class="saz-11">11.11 e </span>Black Friday:</strong> '
         '<span class="saz-d">descontos comparados com o nosso histórico de preço. </span>'
         '<em><span class="saz-d">Ver os maiores</span><span class="saz-m">ver os maiores descontos</span></em></a></p>')


def intro(h1, text):
    return f'<div class="intro"><h1>{h1}</h1><p>{text}</p></div>'


AFFILIATE = ("Como associado da Amazon, ganhamos com compras qualificadas. Também participamos do programa "
             "de afiliados do Mercado Livre. Preços verificados no horário indicado; o preço final é o da loja.")


def foot(offers, bot=None, ch=(), here=""):
    """Rodapé: marca, colunas de links (só o que existe) e o aviso de associado na linha final."""
    present = [g for g in GENRES if any(o["genre"] == g for o in offers)]
    cols = [("Ofertas", [internal("/ofertas/", "Todas as ofertas", here), internal("/curadoria/", "Curadoria", here)]
             + ([internal("/black-friday/", "Black Friday", here)] if bf_on(offers) else [])
             + [internal(f"/{g}/", e(GENRES[g]), here) for g in present])]
    receber = ([internal("/canais/", "Canais", here)] if ch else
               [cta(None, n, "foot-soon") for n in CHANNELS]) + (
        [ext(f"https://t.me/{bot}", "Alerta no Telegram")] if bot else [cta(None, "Alerta de preço", "foot-soon")])
    cols.append(("Receber ofertas", receber))
    cols.append(("Sobre", [internal("/#h-faq", "Como o site funciona", here), internal("/privacidade/", "Privacidade", here)]))
    html_cols = "".join(f'<nav class="foot-col" aria-label="{t}"><p class="foot-t">{t}</p><ul>'
                        + "".join(f"<li>{x}</li>" for x in links) + "</ul></nav>" for t, links in cols)
    tg = chan_urls(ch)["Telegram"]
    social = cta(tg, f'{icon("tg")}' + (f'@{e(tg.rsplit("/", 1)[1])} no Telegram' if tg else "Canal no Telegram"), "pill",
                 '<span class="sr"> (abre em nova aba)</span>')
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
    off_, a, dr = off(o), o["alt"], drop(o)
    pts = series(o)
    lojas = [{"txt": f"Ver {na(o['store'])} por {brl(o['price_cents'])}", "href": f"/r/{o['id']}", "main": True}]
    if a:
        lojas.append({"txt": f"Também {na(a['store'])}: {brl(a['price_cents'])}", "href": f"/r/{o['id']}/{a['store']}",
                      "w": checked_txt(a, o["now"]), "main": False})
    kind = seal(o)
    return {"id": o["id"], "t": o["title"], "a": o["author"], "g": o["genre"], "gl": GENRES[o["genre"]],
            "img": o["image_url"], "p": brl(o["price_cents"]), "de": brl(o["list_price_cents"]) if off_ else None,
            "off": off_, "forte": forte(o), "nov": not o["oferta"], "blurb": o["blurb"],
            "selo": ("Menor preço em 90 dias" if kind == "90d" else
                     f"Menor preço desde {o['since']:%d/%m}" if kind == "since" else None), "desde": kind == "since",
            "meta": f"{STORES[o['store']]}, {checked_txt(o, o['now'])}"
                    + (f". Caiu {brl(dr[0])} desde {dr[1]:%d/%m}" if dr else "") + (f". {VELHO}" if o["velho"] else ""),
            "hist": chart_label(o, pts) if pts else None, "hc": has_hc(o), "lojas": lojas,
            "alerta": tg_alert_url(bot, o["id"]) if bot else None, "pag": f"/livro/{o['id']}/"}


def data_script(offers, bot):
    """<script type="application/json"> com os dados do modal. json.dumps e todo "<" vira \\u003c:
    nenhum </script> ou <!-- pode sair do bloco, venha o que vier no título."""
    raw = json.dumps([offer_json(o, bot) for o in offers], ensure_ascii=False, separators=(",", ":"))
    raw = raw.replace("<", "\\u003c")
    return f'<script type="application/json" id="ofertas">{raw}</script>'


def ld(obj):
    """<script type="application/ld+json">: bloco de dados (não executa, cabe na CSP script-src 'self').
    Sempre json.dumps, nunca f-string; < > & viram \\u003c \\u003e \\u0026, então nenhum </script> ou <!-- vindo
    do título ou do autor sai do bloco."""
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    raw = raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return f'<script type="application/ld+json">{raw}</script>'


def crumbs_ld(*items):
    """BreadcrumbList: (nome, caminho) a partir de Início; caminhos internos fixos (slug de GENRES, id de ID_RE)."""
    return ld({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": name, "item": SITE + path}
        for i, (name, path) in enumerate((("Início", "/"),) + items, 1)]})


def abs_img(o):
    """Capa em URL absoluta https para og:image/JSON-LD: a foto do ML (já presa a https://IMG_HOST) ou a
    capa local em /capas/ servida pelo SITE. Sem capa, None."""
    u = o["image_url"]
    return u and (SITE + u if u.startswith("/capas/") else u)


def book_ld(o):
    """Product + Book da página /livro/<id>/. O preço é o mesmo price_cents mostrado na página, em string
    com ponto (sem float); a url é a da própria página, nunca o /r/ nem o link de afiliado.
    Sem Offer quando o preço é velho (mais de 7 dias): não afirmamos preço nem estoque que não conferimos."""
    url = f"{SITE}/livro/{o['id']}/"
    d = {"@context": "https://schema.org", "@type": ["Product", "Book"], "name": o["title"],
         "author": {"@type": "Person", "name": o["author"]}, "url": url}
    if abs_img(o):
        d["image"] = abs_img(o)
    if o["isbn"]:
        d["isbn"] = o["isbn"]
    if not o["velho"]:
        c = o["price_cents"]
        d["offers"] = {"@type": "Offer", "price": f"{c // 100}.{c % 100:02d}", "priceCurrency": "BRL",
                       "availability": "https://schema.org/InStock", "url": url,
                       "seller": {"@type": "Organization", "name": STORES[o["store"]]}}
    return ld(d)


HOME_LD = ld({"@context": "https://schema.org", "@graph": [
    {"@type": "WebSite", "name": "Ofertas Livros", "url": SITE + "/", "inLanguage": "pt-BR"},
    {"@type": "Organization", "name": "Ofertas Livros", "url": SITE + "/", "logo": SITE + "/logo.svg"}]})


def sitemap(pages):
    """sitemap.xml com as páginas de render_pages (bot.json, /painel e /r/ não são páginas daqui).
    Sem <lastmod>: não há data confiável por página (o build roda a cada rodada de preço)."""
    urls = "".join(f"<url><loc>{e(SITE + '/' + k.removesuffix('index.html'))}</loc></url>\n" for k in sorted(pages))
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'


MODAL = f"""<dialog class="modal" id="detalhe" aria-labelledby="m-t">
<div class="m-top"><button class="arrow js-mprev" type="button">{icon("esq")}<span class="sr">Livro anterior</span></button><span class="m-n tnum"></span><button class="arrow js-mnext" type="button">{icon("dir")}<span class="sr">Próximo livro</span></button><button class="arrow m-x js-mx" type="button">{icon("x")}<span class="sr">Fechar</span></button></div>
<div class="m-grid">
<div class="obj hero-obj m-obj"><span class="pages" aria-hidden="true"></span><div class="cover"><img class="m-img" alt="" width="120" height="180" decoding="async"><span class="ini m-ini" aria-hidden="true"></span></div></div>
<div class="m-body"><p class="chips"><span class="chip chip--g"><svg class="i" aria-hidden="true" focusable="false"><use class="m-gi" href="#i-carimbo"/></svg><span class="m-g"></span></span></p><h2 class="m-t" id="m-t"></h2><p class="hero-sub m-a"></p><blockquote class="nota m-nota"><p class="m-blurb"></p></blockquote><p class="m-selo"><span class="stamp"></span></p><p class="meta m-meta"></p><p class="hist m-hist"></p><div class="m-hc"></div></div>
</div>
<div class="m-foot"><p class="price"><strong class="m-p"></strong> <s class="old m-de"></s> <span class="off-pill m-off"></span></p><div class="m-acts"></div></div>
</dialog>"""


def shell(offers, title, desc, body, ch=(), here="", style=None, bot=None, modal=False, img=None, head=""):
    """Esqueleto comum. title/desc/body já chegam escapados. style: nicho da página (acento global).
    img: URL absoluta da capa para og:image (crua; escapada aqui). head: JSON-LD pronto (ld()).
    O og:url entra com o canonical em render_pages."""
    ds = f' data-style="{style}"' if style in GENRES else ""
    og = (f'<meta property="og:image" content="{e(img)}">\n<meta name="twitter:card" content="summary_large_image">'
          if img else '<meta name="twitter:card" content="summary">')
    return f"""<!doctype html>
<html lang="pt-BR"{ds}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Ofertas Livros">
<meta property="og:locale" content="pt_BR">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
{og}{(chr(10) + head) if head else ""}
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
{header(offers, ch)}{(chr(10) + FAIXA) if bf_on(offers) else ""}
<main id="conteudo">
{carimbo(offers, "carimbo--m")}
{body}
</main>
{foot(offers, bot, ch, here)}{(chr(10) + MODAL + chr(10) + data_script(offers, bot)) if modal else ""}
</body>
</html>
"""


LEDE = ("Oferta aqui é livro que baixou de preço de verdade: conferimos cada um na loja e comparamos "
        "com o histórico. Os que ainda não baixaram ficam na curadoria, com alerta.")


def page(all_offers, genre=None, bot=None, ch=()):
    offers = [o for o in all_offers if genre is None or o["genre"] == genre]
    title = (f"{e(GENRES[genre])}: ofertas de livros" if genre
             else "Ofertas Livros: descontos de livros conferidos na loja")
    desc = (f"{e(GENRES[genre])} em oferta" if genre else "Ofertas de livros") + (
        " na Amazon e no Mercado Livre, conferidas uma a uma e comparadas com o histórico de preço.")
    if genre is None:
        # o H1 só promete "baixaram" quando o hero logo abaixo é todo de ofertas
        h1 = ("Livros que baixaram de verdade" if all(o["oferta"] for o in hero_items(offers))
              else "Livros conferidos na loja")
        body = intro(h1, LEDE) + "\n" + home_sections(offers, bot, ch)
    else:
        body = (intro(e(GENRES[genre]), LEDE) + f"\n{nav(all_offers, genre)}\n{feed(offers, bot, ch, full=True)}"
                + f"\n{da_curadoria(offers, bot, genre)}")
    head = crumbs_ld((GENRES[genre], f"/{genre}/")) if genre else HOME_LD
    return shell(all_offers, title, desc, body, ch, style=genre, bot=bot, modal=True, head=head)


TITLE_MAX = 60  # <title> das /livro/: acima disso o Google corta
TITLE_MIN = 20  # mas o título do livro nunca vira um toco ("O Pequeno P…")


def book_title(o):
    """'Título, Autor por R$ 25,75 | Ofertas Livros' (cru; escapar ao usar). Passou de TITLE_MAX: tira o
    subtítulo (depois de ':') e, se ainda não couber, corta o título na palavra com '…'. O preço e o autor nunca
    são cortados; com autor longo, o título guarda até TITLE_MIN chars, mesmo passando um pouco de TITLE_MAX."""
    tail = f", {o['author']} por {brl(o['price_cents'])} | Ofertas Livros"
    t, room = o["title"], max(TITLE_MAX - len(tail), TITLE_MIN)
    if len(t) > room:
        t = t.split(":")[0].strip() or t
    if len(t) > room:
        cut = t[:room - 1]
        t = (cut.rsplit(" ", 1)[0] if " " in cut else cut).rstrip(" ,.;-") + "…"
    return t + tail


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
    off_ = off(o)
    old = f' <s class="old"><span class="sr">De </span>{brl(o["list_price_cents"])}</s>' if off_ else ""
    pill = f'<span class="off-pill{" off-pill--forte" if forte(o) else ""}">−{off_}%</span>' if off_ else ""
    why = ("o último preço que vimos tem mais de 7 dias. Confira o preço atual na loja." if o["velho"]
           else "o preço ainda não baixou o bastante. Toque em “Me avise se baixar” e avisamos quando entrar em oferta.")
    nov = "" if o["oferta"] else f'\n    <p class="nov-nota">Sem oferta agora: {why}</p>'
    b = badge(o)
    chips = f'<span class="chip chip--g">{icon("g-" + g)}{e(GENRES[g])}</span>' + (
        f'<span class="chip chip--{b[0]}">{b[1]}</span>' if b else "")
    note = (f'<blockquote class="nota"><p>{e(o["blurb"])}</p><footer>{avatar(g)}Curadoria de {e(GENRES[g])}</footer></blockquote>'
            if o["blurb"] else "")
    body = f"""<p class="crumbs"><a href="/">Início</a> / <a href="/{g}/">{e(GENRES[g])}</a></p>
<article class="livro" data-g="{g}">
  {obj(o, "obj hero-obj livro-obj", eager=True)}
  <div class="livro-text">
    <p class="chips">{chips}</p>
    <h1 class="livro-h1">{t}</h1>
    <p class="hero-sub">{e(o["author"])}</p>
    {note}
    <div class="hero-deal">{stamp_html(o)}<p class="price"><span class="sr">Por </span><strong>{brl(o["price_cents"])}</strong>{old}</p>{pill}</div>
    <p class="meta">{meta_html(o)}</p>{chart(o, "    ")}{nov}
    <div class="hero-acts">{go(o)}{alert_link(o, bot)}</div>
    {store_list(o)}
  </div>
</article>"""
    return shell(offers, e(book_title(o)),
                 f"{t}, de {e(o['author'])}, por {brl(o['price_cents'])} {na(o['store'])}. Preço conferido na loja.",
                 body, ch, style=g, bot=bot, img=abs_img(o),
                 head=crumbs_ld((GENRES[g], f"/{g}/"), (o["title"], f"/livro/{o['id']}/")) + "\n" + book_ld(o))


def all_page(offers, bot=None, ch=()):
    """/ofertas/: a lista completa das ofertas (sem JS, é para onde o "Ver todas" leva)."""
    body = (intro("Todas as ofertas", LEDE) + f"\n{nav(offers, None, filtro=True)}\n"
            + feed(offers, bot, ch, full=True, pills=faixas(offers, 0)))
    return shell(offers, "Todas as ofertas de livros | Ofertas Livros",
                 "Todas as ofertas de livros ativas na Amazon e no Mercado Livre, conferidas uma a uma na loja "
                 "e comparadas com o histórico de preço de cada livro.", body, ch, "/ofertas/", bot=bot, modal=True)


def faixa_page(offers, t, bot=None, ch=()):
    """/ofertas/<t>/: livros com t% ou mais de desconto (com_desconto). Existe sempre, mesmo vazia."""
    h1 = f"Livros com {t}% ou mais de desconto"
    lede = (f"Ofertas ativas com pelo menos {t}% de desconto sobre o preço de lista da loja. "
            "Cada livro mostra quando conferimos o preço; o preço final é o da loja.")
    items = ranked(com_desconto(offers, t))
    lista = (feed(offers, bot, ch, full=True, pills=faixas(offers, t), items=items) if items else
             faixas(offers, t) + f'\n<p class="vazio vazio--fixo">Nenhum livro com {t}% ou mais de desconto agora. '
             'Veja todas as <a href="/ofertas/">ofertas ativas</a>.</p>')
    return shell(offers, f"{h1} | Ofertas Livros", f"{h1}, conferidos na loja.",
                 intro(h1, lede) + f"\n{nav(items, None, filtro=True) if items else ''}\n" + lista, ch, f"/ofertas/{t}/", bot=bot, modal=True)


BF_LEDE = ("Ofertas ativas com 30% ou mais de desconto ou no menor preço que vimos em 90 dias. "
           "Cada livro mostra quando conferimos o preço; o preço final é o da loja.")


def bf_page(offers, bot=None, ch=()):
    """/black-friday/: subconjunto das ofertas ativas (desconto >= BF_MIN ou selo de 90 dias), na ordem
    do ranked(). Depois da janela, só o aviso de encerramento, para os links compartilhados não quebrarem."""
    t, d = "Black Friday de livros | Ofertas Livros", "Livros com desconto grande, conferidos na loja."
    if campanha(offers[0]["now"]) == "fim":
        body = ('<div class="intro"><h1>A Black Friday 2026 acabou</h1><p>Veja as '
                '<a href="/ofertas/">ofertas ativas</a> de agora.</p></div>')
        return shell(offers, t, d, body, ch, "/black-friday/", bot=bot)
    items = ranked([o for o in offers if o["oferta"] and not o["velho"] and (off(o) >= BF_MIN or seal(o) == "90d")])
    lista = (feed(items, bot, ch, full=True) if items else
             '<p class="vazio vazio--fixo">Nenhum livro com desconto grande agora. '
             'Veja todas as <a href="/ofertas/">ofertas ativas</a>.</p>')
    return shell(offers, t, d, intro("Black Friday de livros", BF_LEDE) + "\n" + lista, ch, "/black-friday/",
                 bot=bot, modal=True)


CUR_INTRO = ("Uma seleção de livros escolhidos por regras a partir de sinais públicos e por nós. Alguns estão "
             "em oferta, outros não. O preço foi verificado no horário indicado, e o preço final é o da loja. "
             "Sem oferta agora? Toque no sino e avisamos quando o livro entrar em oferta.")


def curadoria_page(offers, bot=None, ch=()):
    """/curadoria/: todo livro com loja fresca, com ou sem oferta. Uma seção por nicho, na ordem de
    GENRES, com âncoras no topo; dentro dela, entrada mais recente primeiro. Nunca ordem de ranking."""
    present = [g for g in GENRES if any(o["genre"] == g for o in offers)]
    anchors = "".join(f'<li><a class="pill" href="#{g}">{avatar(g, "av av--sm")}{e(GENRES[g])}</a></li>' for g in present)
    secs = []
    for g in present:
        items = recentes(o for o in offers if o["genre"] == g)
        body = (f'<ul class="grid feed feed--full">\n' + "\n".join(card(o, bot) for o in items) + "\n</ul>\n"
                f'<p class="mais"><button class="btn btn--ghost js-mais" type="button" hidden>{icon("livro", "i i-livro")}'
                'Carregar mais livros</button></p>')
        secs.append(section(g, e(GENRES[g]), body, len(items), unit=("livro", "livros")))
    body = (intro("Curadoria: livros que valem a leitura", CUR_INTRO)
            + f'\n<nav class="ancoras" aria-label="Nichos da curadoria"><ul>{anchors}</ul></nav>\n' + "\n".join(secs))
    return shell(offers, "Curadoria: livros que valem a leitura | Ofertas Livros",
                 "Livros selecionados, com e sem oferta, por nicho.", body, ch, "/curadoria/", bot=bot, modal=True)


def privacy(offers, bot=None, ch=()):
    bot_name = (f'o bot <a href="https://t.me/{e(bot)}" rel="noopener noreferrer" target="_blank">@{e(bot)}</a>'
                if bot else "o nosso bot")
    body = f"""<h1 class="page-h1">Privacidade</h1>
<article class="doc">
<h2>No site</h2>
<p>O site não tem cadastro, cookies nem ferramentas de análise. Ele tem um script próprio, servido pelo próprio site, para a busca, os filtros e o tema; a única coisa que ele guarda é a sua escolha de tema claro ou escuro, no seu navegador (localStorage), e nada disso sai do aparelho. O site é hospedado na Cloudflare; o endereço ofertaslivros.com passa pelo Netlify só para redirecionar a este site. Os dois recebem os dados técnicos de cada acesso (como o endereço IP) para entregar as páginas.</p>
<h2>No pedido de livro</h2>
<p>O formulário “Pedir um livro” pede só o nome e o autor do livro. Ele é processado na Cloudflare, que usa o endereço IP só para barrar envios repetidos, sem guardá-lo, e envia o pedido ao nosso e-mail. O pedido (só o nome e o autor do livro, sem nenhum dado seu) fica guardado por 30 dias num banco de dados Cloudflare D1 e depois é apagado. Apagamos os pedidos do e-mail em até 30 dias.</p>
<p>Ao clicar em uma oferta, você vai para a Amazon ou para o Mercado Livre. A partir daí valem as políticas de privacidade de cada loja.</p>
<h2>Na lista de desejos do Telegram</h2>
<p>{"Quando você põe um livro ou um autor na sua lista com " + bot_name + ", ele avisa por lá quando o livro entrar em oferta. Para isso, guardamos" if bot else "A lista de desejos ainda não está no ar. Em breve você poderá pôr livros e autores numa lista com " + bot_name + ", que vai avisar quando eles entrarem em oferta. Quando isso funcionar, vamos guardar"} só o necessário para avisar você:</p>
<ul>
<li>o identificador da conversa com o bot no Telegram (chat_id);</li>
<li>a sua lista: os livros e os autores que você escolheu;</li>
<li>se os avisos estão pausados;</li>
<li>a data em que a conversa começou e a do último uso;</li>
<li>para cada livro já avisado, o preço e a data do último aviso, para não repetir o mesmo aviso.</li>
</ul>
<p>Não guardamos seu nome, seu nome de usuário, seu telefone, seu idioma nem o texto das suas mensagens: o que você manda ao bot serve só para achar o livro na hora e é descartado.</p>
<p>Se você pedir um livro pelo bot, o pedido vai para a curadoria sem nenhum dado seu.</p>
<h2>Onde fica</h2>
<p>Num banco de dados Cloudflare D1, fora do código do site e sem acesso público. A Cloudflare opera esse banco para nós. As mensagens passam pelo Telegram, que tem a política de privacidade dele.</p>
{"" if bot else "<p>Quando a lista de desejos estiver no ar, valerá o seguinte:</p>"}
<h2>Por quanto tempo</h2>
<p>A lista fica guardada enquanto você usa o bot. Uma conversa sem nenhuma mensagem ou toque por 12 meses é apagada por inteiro, sem aviso. O preço do último aviso de um livro é apagado quando ele sai da oferta.</p>
<h2>Como apagar</h2>
<ul>
<li>em <code>/lista</code>, toque em “Tirar” para tirar um item;</li>
<li><code>/parar</code> apaga a sua lista e todos os seus dados;</li>
<li>bloquear o bot também apaga todos os seus dados.</li>
</ul>
</article>"""
    return shell(offers, "Privacidade: Ofertas Livros",
                 "O que o Ofertas Livros guarda, onde, por quanto tempo e como apagar.", body, ch, "/privacidade/", bot=bot)


def canais(offers, ch, bot=None):
    desc = {"Telegram": "as ofertas chegam assim que são publicadas, até 8 por dia, das 8h às 22h.",
            "WhatsApp": "um resumo por dia com até 5 ofertas."}
    items = "\n".join(f"<li>{ext(url, f'Canal no {name}')}: {desc[name]}</li>" for name, url in ch)
    alert = (f'<p>Quer saber de um livro só? Mande o título ao {ext(f"https://t.me/{bot}", "@" + e(bot))} '
             'ou toque em “Me avise se baixar” na oferta: o bot avisa quando ele entrar em oferta. Para apagar tudo, mande /parar ao bot.</p>'
             if bot else "")
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


def bot_key(text):
    """Chave de busca do bot: fold e só [a-z0-9] separados por espaço (worker/bot.js normaliza igual)."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", fold(text)).split())


def bot_json(offers, now):
    """Catálogo público do bot do Telegram (docs/produto/bot-lista-de-desejos.md §7.2): busca e o aviso pronto.
    texto só com oferta no prazo (o Worker não calcula oferta nem formata preço); valido_ate = checked_at +
    FRESH da loja que vence primeiro, para o cron não mandar preço que venceu depois do deploy."""
    # ponytail: autores divididos em , ; & e " e " erram nome com " e "; campo authors no contrato se aparecer caso real
    livros = [{"id": o["id"], "titulo": o["title"], "autor": o["author"],
               "busca": bot_key(f"{o['title']} {o['author']}"),
               "autores": [k for a in re.split(r",|;|&| e ", o["author"]) if (k := bot_key(a))],
               "preco_cents": o["price_cents"],
               "desconto": off(o),  # % do "de/por" (0 sem oferta): desempate dos avisos no cron do bot
               # a loja que vence primeiro: o texto pode citar a outra ("Também no ...")
               "valido_ate": min(s["checked_at"] + FRESH[s["store"]] for s in o["stores"]).astimezone(timezone.utc)
                             .isoformat(timespec="seconds"),
               "texto": post_text(o, f"{SITE}/r/{o['id']}/bot") if o["oferta"] and not o["velho"] else None}
              for o in offers]
    return json.dumps({"version": 1, "gerado_em": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
                       "livros": livros}, ensure_ascii=False)


MAX_REDIRECTS = 2000  # limite de regras estáticas do _redirects na Cloudflare


def redirects(offers):
    """/novidades/ (página antiga) vai para /curadoria/. Por livro: /r/<id> e /r/<id>/tg|wa|bot
    (vencedora, com a tag do canal se for a Amazon) e /r/<id>/<loja> para cada loja elegível.
    Vencido ou loja fora do prazo cai na home pelo curinga; o livro com a Amazon vencida (velho) segue no /r/.
    Até 6 regras por livro: cabem 333 livros com duas lojas (1.998 + curinga + /novidades/)."""
    tags, aff = channel_tags(), ml_affiliate()
    lines = ["/novidades/ /curadoria/ 301\n"]  # destino interno fixo, nunca vindo do JSON
    for o in offers:
        lines.append(f"/r/{o['id']} {affiliate_url(o, tags[''], aff)} 302\n")
        lines += [f"/r/{o['id']}/{s['store']} {affiliate_url(s, tags[''], aff)} 302\n" for s in o["stores"]]
        lines += [f"/r/{o['id']}{sfx} {affiliate_url(o, tags[sfx], aff)} 302\n" for sfx in ("/tg", "/wa", "/bot")]  # ML: mesmo ml_url
    lines.append("/r/* / 302\n")
    if len(lines) > MAX_REDIRECTS:
        raise Invalid(f"{len(lines)} regras no _redirects (máximo {MAX_REDIRECTS})")
    return "".join(lines)


# form-action e connect-src: só o POST do pedido de livro para o Worker no SITE (/pedido, fab).
HEADERS = f"""/*
  Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' https://http2.mlstatic.com; font-src 'self'; connect-src {SITE}; base-uri 'none'; form-action {SITE}; frame-ancestors 'none'
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


def render_pages(offers, bot=None, ch=()):
    """{caminho em dist/: HTML}. Uma página por nicho presente, por livro e a lista completa."""
    pages = {"index.html": page(offers, bot=bot, ch=ch), "privacidade/index.html": privacy(offers, bot, ch),
             "ofertas/index.html": all_page(offers, bot, ch), "curadoria/index.html": curadoria_page(offers, bot, ch)}
    for t in FAIXAS:
        pages[f"ofertas/{t}/index.html"] = faixa_page(offers, t, bot, ch)
    for g in {o["genre"] for o in offers}:
        pages[f"{g}/index.html"] = page(offers, g, bot, ch)
    if ch:
        pages["canais/index.html"] = canais(offers, ch, bot)
    if offers and campanha(offers[0]["now"]):  # antes da janela não existe; depois, só o aviso de fim
        pages["black-friday/index.html"] = bf_page(offers, bot, ch)
    for o in offers:  # id validado por ID_RE: seguro como diretório
        pages[f"livro/{o['id']}/index.html"] = book_page(o, offers, bot, ch)
    # canonical pelo caminho em dist/ (slugs de GENRES e ids de ID_RE), num lugar só para todas as páginas
    def url(k):
        return e(SITE + "/" + k.removesuffix("index.html"))
    return {k: v.replace('<link rel="icon"', f'<link rel="canonical" href="{url(k)}">\n<meta property="og:url" content="{url(k)}">\n'
                         '<link rel="icon"', 1) for k, v in pages.items()}


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
    pages = render_pages(offers, bot, ch)  # tudo validado e renderizado antes de tocar no dist/
    rules = redirects(offers)
    catalogo_bot = bot_json(offers, now)
    shutil.rmtree(DIST, ignore_errors=True)
    shutil.copytree(STATIC, DIST)
    for path, body in pages.items():
        (DIST / path).parent.mkdir(parents=True, exist_ok=True)
        (DIST / path).write_text(body, encoding="utf-8")
    (DIST / "_redirects").write_text(rules, encoding="utf-8")
    (DIST / "bot.json").write_text(catalogo_bot, encoding="utf-8")
    (DIST / "sitemap.xml").write_text(sitemap(pages), encoding="utf-8")
    (DIST / "_headers").write_text(HEADERS, encoding="utf-8")
    print(f"ok: {len(ofertas(offers))} ofertas, {len(sem_oferta(offers))} sem oferta ({len(books) - len(offers)} fora do prazo), "
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

    def vis(h):  # o HTML visível: sem o esqueleto do modal e sem o JSON (testados à parte)
        return re.sub(r'<script type="application/json".*?</script>', "", h.replace(MODAL, ""), flags=re.S)

    o = load(good, ml)
    assert o[0]["url"] == "https://www.amazon.com.br/dp/B0ABCDEFGH?tag=" + partner_tag()
    assert o[1]["url"] == ml_link
    marca = ml_link.replace(f"matt_word={aff}", "matt_word=ofertaslivros")
    assert load(M(ml_url=marca))[0]["url"] == marca  # etiqueta da marca, mesma conta
    assert rejects(M(ml_url=marca.replace(f"/social/{aff}", "/social/evil")))
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
    assert re.search(r'href="/manga/"[^>]*aria-current="page"', p)
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
    # botão de alerta: link real só com TELEGRAM_BOT_USERNAME válido; sem ele, o mesmo sino "em breve"
    p0 = page(o)
    assert "t.me" not in p0 and '<a class="bell"' not in p0
    assert p0.count('<span class="bell is-soon" aria-disabled="true">') == vis(p0).count('class="card"')
    pb = page(o, bot="ofertaslivros_bot")
    assert '<a class="bell" href="https://t.me/ofertaslivros_bot?start=livro-1" rel="noopener noreferrer" target="_blank">' in pb
    assert pb.count('class="bell"') == 2 and pb.count('"alerta":"https://t.me/ofertaslivros_bot?start=') == 2  # sino por card + modal
    assert ">Me avise se baixar (Telegram)<" not in pb[pb.index('id="h-ativas"'):].split("<dialog")[0]  # no card só o sino
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
        tg_alert_url("ofertaslivros_bot", "a" * 61)
        raise AssertionError("id longo")
    except Invalid:
        pass
    # marca: favicon SVG no <head>, logo no topo (h1 só na home) e negativo no rodapé, em todas as páginas
    every = (page(o), page(o, "manga"), privacy(o), canais(o, [("Telegram", "https://t.me/x")]),
             book_page(o[0], o), all_page(o))
    for h in every:  # marca, fontes locais e o app.js em todas as páginas
        head = h[:h.index("</head>")]
        assert '<link rel="icon" type="image/svg+xml" href="/favicon.svg">' in head
        assert '<script src="/app.js" defer></script>' in head and h.count("<script") == h.count("</script>")
        assert ('<link rel="preload" href="/fonts/fraunces-latin-full-normal.woff2" as="font" type="font/woff2" crossorigin>'
                in head and head.count('rel="preload"') == 1)
        assert h.count('src="/logo.svg" alt="Ofertas Livros"') == 2 and h.count('src="/logo-negativo.svg" alt="Ofertas Livros"') == 2
        assert not re.search(r"https?://[^\"]*(fonts\.|googleapis|gstatic|jsdelivr|unpkg|cdn)", h)  # nenhuma fonte/script externo
        assert h.count("<h1") == 1
    for h in every:  # header: logo colado à esquerda (sem espaço de menu), carimbo na barra e no conteúdo, sem número solto
        top = h[h.index('<header class="top">'):h.index("</header>")]
        assert "menu-slot" not in top and "<button" not in top.split('class="brand"')[0]
        assert top.count('class="carimbo carimbo--bar"') == 1 and h.count('class="carimbo carimbo--m"') == 1
        assert "tnum" not in top and 'class="live"' not in top
        assert top.index('class="brand"') < top.index("carimbo--bar") < top.index("js-busca") < top.index("pill--tg")
    assert all((STATIC / f).is_file() for f in ("favicon.svg", "logo.svg", "logo-negativo.svg", "app.js", "grao.svg", "mavi.svg",
                                                "fonts/fraunces-latin-full-normal.woff2", "fonts/fraunces-latin-full-italic.woff2",
                                                "fonts/outfit-latin-wght-normal.woff2", "fonts/SOURCES.md"))
    assert "<rect" not in (STATIC / "logo-negativo.svg").read_text()  # sem caixa no tema escuro
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    assert "http" not in css and "@import" not in css  # CSS sem nada externo
    assert set(re.findall(r"url\(([^)]*)\)", css)) <= {"/fonts/fraunces-latin-full-normal.woff2", "/fonts/fraunces-latin-full-italic.woff2",
                                                      "/fonts/outfit-latin-wght-normal.woff2", "/grao.svg", "/chevron.svg"}
    assert all(f"--g-{g}:" in css and f'[data-g="{g}"]' in css for g in GENRES)  # um acento por nicho
    # privacidade: linkada no rodapé de todas as páginas
    assert '<a href="/privacidade/">Privacidade</a>' in page(o)
    assert '<a href="/privacidade/" aria-current="page">' in privacy(o)
    pv = privacy(o, "ofertaslivros_bot")
    assert all(w in pv for w in ("No pedido de livro", "Cloudflare", "endereço IP", "30 dias"))  # pedido de livro
    assert all(w in pv for w in ("Na lista de desejos do Telegram", "chat_id", "Cloudflare D1", "12 meses", "/lista",
                                 "/parar", "bloquear o bot", "https://t.me/ofertaslivros_bot",
                                 "o pedido vai para a curadoria sem nenhum dado seu", "fica guardado por 30 dias"))
    # critério 36: o modelo antigo (preço-alvo, 90 dias, /remover) sai da privacidade e dos textos do alerta
    for b_ in ("ofertaslivros_bot", None):
        pv_ = privacy(o, b_)
        assert not any(w in pv_ for w in ("preço-alvo", "/remover", "90 dias", "não guarda o pedido")), b_
        for t_ in (faq(b_, ()), banner_bot(b_, 4), bot_block(b_)):
            assert "preço de hoje" not in t_ and "quando ele disparar" not in t_ and "entrar em oferta" in t_, b_
    assert all("/parar" in t_ for t_ in (faq("ofertaslivros_bot", ()), banner_bot("ofertaslivros_bot", 4),
                                          bot_block("ofertaslivros_bot")))
    # _redirects: /novidades/ -> /curadoria/ (interno), 4 linhas por livro de uma loja + curinga; tag por canal
    saved = {k: os.environ.pop(k, None) for k in ("AMAZON_TAG_TG", "AMAZON_TAG_WA", "AMAZON_TAG_BOT")}
    r = redirects(o).splitlines()
    t = partner_tag()
    assert len(r) == 12 and r[0] == "/novidades/ /curadoria/ 301" and r[-1] == "/r/* / 302"
    assert [x for x in r if not x.startswith("/r/")] == ["/novidades/ /curadoria/ 301"]  # única regra fora do /r/
    assert f"/r/livro-1/amazon https://www.amazon.com.br/dp/B0ABCDEFGH?tag={t} 302" in r
    assert f"/r/livro-2/mercadolivre {ml_link} 302" in r
    assert not any("/r/livro-1/mercadolivre" in x or "/r/livro-2/amazon" in x for x in r)
    assert f"/r/livro-1/tg https://www.amazon.com.br/dp/B0ABCDEFGH?tag={t} 302" in r
    assert f"/r/livro-2/wa {ml_link} 302" in r and f"/r/livro-2 {ml_link} 302" in r
    assert f"/r/livro-1/bot https://www.amazon.com.br/dp/B0ABCDEFGH?tag={t} 302" in r  # sem AMAZON_TAG_BOT: tag do site
    assert f"/r/livro-2/bot {ml_link} 302" in r
    os.environ.update(AMAZON_TAG_TG="sitetg-20", AMAZON_TAG_WA="", AMAZON_TAG_BOT="sitebot-20")
    r = redirects(o).splitlines()
    assert "/r/livro-1/bot https://www.amazon.com.br/dp/B0ABCDEFGH?tag=sitebot-20 302" in r
    assert "/r/livro-1/tg https://www.amazon.com.br/dp/B0ABCDEFGH?tag=sitetg-20 302" in r
    assert f"/r/livro-1/wa https://www.amazon.com.br/dp/B0ABCDEFGH?tag={t} 302" in r
    # duas lojas: vencedora no /r/<id>, /tg e /wa; uma rota por loja; tag do canal só na Amazon
    two = {**good, "id": "duas", "stores": [{**amz, "price_cents": 1890}, mls]}
    r = redirects(load(two)).splitlines()
    amz_url = "https://www.amazon.com.br/dp/B0ABCDEFGH?tag="
    assert r[1:] == [f"/r/duas {amz_url}{t} 302", f"/r/duas/amazon {amz_url}{t} 302",
                 f"/r/duas/mercadolivre {ml_link} 302", f"/r/duas/tg {amz_url}sitetg-20 302",
                 f"/r/duas/wa {amz_url}{t} 302", f"/r/duas/bot {amz_url}sitebot-20 302", "/r/* / 302"]
    r = redirects(load({**two, "stores": [amz, {**mls, "price_cents": 1890}]})).splitlines()
    assert f"/r/duas {ml_link} 302" in r and f"/r/duas/tg {ml_link} 302" in r
    assert f"/r/duas/amazon {amz_url}{t} 302" in r                        # loja da seta, tag do site
    r = redirects(load(two, now=datetime(2026, 10, 18, 10, 31, tzinfo=BRT))).splitlines()
    assert "/r/duas/mercadolivre" not in "\n".join(r) and len(r) == 7      # ML fora do prazo: sem rota
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
    many = [{**good, "id": f"l-{n}", "stores": [amz, mls]} for n in range(334)]
    try:
        redirects(load(*many))  # 334 x 6 + curinga + /novidades/ = 2.006
        raise AssertionError("limite do _redirects")
    except Invalid:
        pass
    assert len(redirects(load(*many[:333])).splitlines()) == 2000
    # bot.json: texto = post_text com /r/<id>/bot só em oferta no prazo; valido_ate = checked_at + FRESH
    bj = json.loads(bot_json(load(two, {**good, "id": "sem", "author": "Neil Gaiman e Terry Pratchett; Ação",
                                        "stores": [{**amz, "list_price_cents": amz["price_cents"]}]}), NOW))
    assert bj["version"] == 1 and [b["id"] for b in bj["livros"]] == ["duas", "sem"]
    duas, sem = bj["livros"]
    assert duas["texto"] == post_text(load(two)[0], f"{SITE}/r/duas/bot") and duas["texto"].endswith("/r/duas/bot")
    assert sem["texto"] is None and sem["autores"] == ["neil gaiman", "terry pratchett", "acao"]
    assert duas["desconto"] == discount(load(two)[0]) > 0 and sem["desconto"] == 0
    assert duas["valido_ate"] == (mls_at := min(s["checked_at"] + FRESH[s["store"]] for s in load(two)[0]["stores"])) \
        .astimezone(timezone.utc).isoformat(timespec="seconds") and mls_at < load(two)[0]["checked_at"] + FRESH["amazon"]
    velha = load({**good, "id": "velha", "stores": [amz]}, now=NOW + timedelta(days=1))[0]  # Amazon vencida, ainda oferta
    assert velha["oferta"] and velha["velho"]
    assert json.loads(bot_json([velha], NOW))["livros"][0]["texto"] is None
    assert bot_key("Mangá: Ação!  Vol. 2") == "manga acao vol 2"
    assert "Disallow: /bot.json" in (STATIC / "robots.txt").read_text()
    # canais: só com a env; validados; rel noopener noreferrer
    saved = {k: os.environ.pop(k, None) for k in ("TELEGRAM_CHANNEL_ID", "WHATSAPP_CHANNEL_ID")}
    assert channels() == [] and "/canais/" not in page(o)
    os.environ.update(TELEGRAM_CHANNEL_ID="@ofertaslivros", WHATSAPP_CHANNEL_ID="0029VaAbCdEfGhIjKlMnOp12")
    ch = channels()
    assert ch == [("Telegram", "https://t.me/ofertaslivros"),
                  ("WhatsApp", "https://whatsapp.com/channel/0029VaAbCdEfGhIjKlMnOp12")]
    for html_ in (page(o, ch=ch), canais(o, ch, "ofertaslivros_bot")):
        assert ('href="https://t.me/ofertaslivros" rel="noopener noreferrer" target="_blank">' in html_
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
    assert post_text(torto, "https://ofertaslivros.com.br/r/livro-1/tg") == (
        "Menor preço em 90 dias\nTorto Arado, de Itamar Vieira Junior\n"
        f"R${nb}42,90 (de R${nb}74,90, -42%)\n"
        "Amazon · preço verificado em 18/10 às 08h47. O preço final é o da loja.\n"
        "Link de afiliado: https://ofertaslivros.com.br/r/livro-1/tg")
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
        return vis(page(load(A(**kw))))
    assert 'class="stamp' not in stamp()                                   # sem histórico
    assert "Menor preço desde 21/07" in stamp(history_since="2026-07-21")  # 89 dias
    assert "Menor preço em 90 dias" not in stamp(history_since="2026-07-21")
    assert "Menor preço em 90 dias" in stamp(history_since="2026-07-20")   # 90 dias
    # selo colado ao preço: pílula (90 dias) ou contorno (desde), logo antes do preço do card
    assert re.search(r'<p class="stamp">Menor preço em 90 dias</p>\s*<div class="card-foot"><p class="price">',
                     stamp(history_since="2026-07-20"))
    assert re.search(r'<p class="stamp stamp--since">Menor preço desde 21/07</p>\s*<div class="card-foot"><p class="price">',
                     stamp(history_since="2026-07-21"))
    assert stamp().count('<p class="price">') == stamp(history_since="2026-07-20").count('<p class="price">')
    x = stamp(history_since="2026-07-20")
    assert x.count("−50%") == 2 and x[x.index('id="h-ativas"'):].count("−50%") == 1  # uma vez no hero, uma no card
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
    def livro(**kw):  # o gráfico do histórico fica na página do livro
        r = load(A(**kw))
        return vis(book_page(r[0], r))
    h = livro(history_since="2026-10-01", price_points=ok_pp)
    svg = h[h.index('<figure class="hc" id="historico">'):h.index("</svg>", h.index('<figure class="hc" id="historico">'))]
    assert h.count('<figure class="hc" id="historico">') == 1 and 'role="img" aria-labelledby="hc-t"' in svg and "style=" not in svg
    assert "Amazon: menor R$ 19,90, maior R$ 29,90, hoje R$ 19,90." in svg  # title para leitor de tela
    assert '<path class="hc-line hc-amz" d="M4.0 30.0h0M109.9 74.0h0M204.0 118.0h0"/>' in svg  # buracos de 9 e 8 dias: pontos soltos
    # 3 marcadores com valor: o mais alto, o degrau mais recente e o atual (vermelho/rosa, com o preço embaixo do nome)
    assert '<text class="hc-val hc-amz" x="32.8" y="22.0" text-anchor="middle">R$\u00a029,90</text><circle class="hc-pt hc-amz" cx="4.0" cy="30.0"' in svg
    assert '<text class="hc-val hc-amz" x="109.9" y="66.0" text-anchor="middle">R$\u00a024,90</text><circle class="hc-pt hc-amz" cx="109.9"' in svg
    assert svg.count('class="hc-pt') == 2 and 'class="hc-now" cx="204.0" cy="118.0"' in svg
    assert '>Amazon</text><text class="hc-now-lbl" x="210" y="136.5">R$\u00a019,90</text>' in svg
    assert ">menor R$" not in svg  # o menor é o atual: sem rótulo repetido
    assert "<figcaption>Hoje é o menor preço desde 01/10.</figcaption>" in h  # frase do selo
    h = livro(history_since="2026-10-01", lowest_90d_cents=1000, price_points=pp(("2026-10-12", 2990), ("2026-10-17", 2490)))
    assert '<path class="hc-line hc-amz" d="M4.0 30.0L170.7 74.0L204.0 118.0"/>' in h  # 7 dias, retas entre leituras
    assert "<figcaption>Desde 12/10: R$\u00a019,90 a R$\u00a029,90.</figcaption>" in h      # sem selo: faixa de preço
    tb = livro(history_since="2026-10-01", price_points=ok_pp)
    assert '<tr><th scope="row">18/10</th><td>R$\u00a019,90</td></tr>' in tb and tb.index(">18/10</th>") < tb.index(">01/10</th>")
    assert 'class="hc"' in livro(history_since="2026-10-01", price_points=ok_pp[:1])  # 1 dia antes de hoje já é série
    assert "Primeira leitura em 18/10: R$\u00a019,90." in livro(history_since="2026-10-18", price_points=pp(("2026-10-18", 1990)))
    assert 'class="hc"' not in livro(history_since="2026-10-01") and 'class="hist"' not in livro(history_since="2026-10-01")
    # ponto de hoje: vale o preço atual verificado, não o do ponto
    r = load(A(history_since="2026-10-01", price_points=pp(("2026-10-01", 2990), ("2026-10-18", 2500))))[0]
    assert series(r) == [(date(2026, 10, 1), 2990), (date(2026, 10, 18), 1990)]
    # eixo de no máximo 90 dias e no mínimo 7; buraco de mais de 7 dias quebra a linha
    full = pp(("2026-07-20", 2990), ("2026-09-01", 2490))
    h = livro(history_since="2026-07-20", price_points=full)
    assert '<text class="hc-lbl" x="4" y="158">21/07</text>' in h and "M" in h[h.index('d="M'):][4:30]
    assert "<figcaption>Hoje é o menor preço dos últimos 90 dias.</figcaption>" in h
    h = livro(history_since="2026-10-15", price_points=pp(("2026-10-15", 2990)))
    assert '<text class="hc-lbl" x="4" y="158">12/10</text>' in h  # 3 dias de histórico, eixo de 7
    h = livro(history_since="2026-10-01", price_points=pp(("2026-10-01", 1990), ("2026-10-10", 1990)))
    assert 'class="hc-guide"' not in h and "<figcaption>Hoje é o menor preço desde 01/10.</figcaption>" in h
    # duas lojas: uma linha cada, cor do ML, tracejado no menor das duas, ponto na vencedora (ML)
    two_pp = load({**good, "stores": [{**amz, "history_since": "2026-10-01", "price_points": ok_pp},
                                      {**mls, "price_cents": 1890, "history_since": "2026-10-05",
                                       "price_points": pp(("2026-10-05", 2190), ("2026-10-12", 2090))}]})
    h = vis(book_page(two_pp[0], two_pp))
    assert 'class="hc-line hc-amz"' in h and 'class="hc-line hc-ml"' in h and 'class="hc-now-lbl" x="210"' in h and ">R$\u00a018,90</text>" in h
    assert '<th scope="col">Amazon</th><th scope="col">Mercado Livre</th>' in h and '<span class="sr">sem leitura</span>' in h
    assert h.count('class="hc-now"') == 2 and "Mercado Livre: menor R$ 18,90, maior R$ 21,90, hoje R$ 18,90." in h  # atual das duas lojas
    assert '>Mercado Livre</text><text class="hc-now-lbl"' in h and '>Amazon</text><text class="hc-now-lbl"' in h
    empate = load({**good, "stores": [{**amz, "price_cents": 1890, "lowest_90d_cents": 1890, "history_since": "2026-10-01", "price_points": ok_pp},
                                      {**mls, "price_cents": 1890, "history_since": "2026-10-05",
                                       "price_points": pp(("2026-10-05", 2190), ("2026-10-12", 2090))}]})
    ys = [float(y) for y in re.findall(r'<text class="(?:hc-name[^"]*|hc-now-lbl)" x="210" y="([\d.]+)"', vis(book_page(empate[0], empate)))]
    assert len(ys) == 4 and max(ys) <= 139 and all(b - a >= 14 for a, b in zip(sorted(ys), sorted(ys)[1:]))  # sem colidir com as datas
    # Amazon vencida há mais de 90 dias: sem gráfico nem link, sem quebrar o build (review do PR #91)
    old_ = load(A(checked_at="2026-07-01T10:00:00-03:00", history_since="2026-06-20",
                  price_points=pp(("2026-06-20", 2990), ("2026-06-25", 2490))), now=datetime(2026, 10, 18, 12, tzinfo=BRT))[0]
    assert old_["velho"] and not has_hc(old_) and 'class="hc"' not in chart(old_) and "ver-hist" not in card(old_)
    # texto com a data real do primeiro ponto, mesmo com o eixo puxado para 7 dias
    h = livro(history_since="2026-10-15", lowest_90d_cents=1000, price_points=pp(("2026-10-15", 2990)))
    assert "<figcaption>Desde 15/10: " in h and "Preço desde 15/10." in h and ">12/10</text>" in h
    # ponto solto de outra loja (entre buracos) ganha marcador
    solto = load({**good, "stores": [{**amz, "history_since": "2026-10-01", "price_points": ok_pp},
                                     {**mls, "price_cents": 1890, "history_since": "2026-09-01",
                                      "price_points": pp(("2026-09-01", 2190), ("2026-10-05", 2090))}]})
    hs = vis(book_page(solto[0], solto))
    ml_d = re.search(r'class="hc-line hc-ml" d="([^"]+)"', hs).group(1)
    assert ml_d.count("h0") == 3 and "L" not in ml_d  # 01/09, 05/10 e hoje: buracos de 34 e 13 dias
    # degrau intermediário relevante ganha rótulo; o menor ganha rótulo quando não é o atual
    h = livro(history_since="2026-10-01", lowest_90d_cents=1000, price_points=pp(
        ("2026-10-01", 2990), *((f"2026-10-{d:02d}", 2490) for d in range(5, 11)), ("2026-10-14", 1500)))
    svg = h[h.index('<figure class="hc"'):h.index("</svg>", h.index('<figure class="hc"'))]
    assert ">R$\u00a015,00</text>" in svg and ">R$\u00a029,90</text>" in svg and ">R$\u00a024,90<" not in svg  # intermediário = degrau mais recente
    assert ">menor R$" not in h  # o menor já está num marcador
    h2 = livro(history_since="2026-10-01", lowest_90d_cents=1000, price_points=pp(
        ("2026-10-01", 2990), ("2026-10-05", 1500), *((f"2026-10-{d:02d}", 2490) for d in range(10, 18))))
    assert ">R$\u00a024,90</text>" in h2 and ">menor R$\u00a015,00</text>" in h2  # menor fora dos marcadores ganha rótulo
    fig = h[h.index('<figure class="hc"'):h.index("</figure>")]
    assert fig.count("<circle") == 3 and fig.count('class="hc-pt') == 2 and fig.count('class="hc-now"') == 1  # 3 marcadores por loja
    # card: link "ver histórico" só com gráfico; o modal busca o #historico da página só quando há gráfico
    def card_of(**kw):
        return card(load(A(**kw))[0])
    c = card_of(history_since="2026-10-01", price_points=ok_pp)
    assert '<a class="ver-hist" href="/livro/livro-1/#historico" data-modal="livro-1">ver histórico' in c
    assert c.index('class="stamp') < c.index('class="ver-hist"')
    for kw in ({"history_since": "2026-10-01"}, {"history_since": "2026-10-18", "price_points": pp(("2026-10-18", 1990))}):
        assert "ver-hist" not in card_of(**kw), kw  # sem série: sem link
    assert offer_json(load(A(history_since="2026-10-01", price_points=ok_pp))[0], None)["hc"] is True
    assert offer_json(load(A(history_since="2026-10-01"))[0], None)["hc"] is False
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
                       "stores": [{**amz, "price_cents": 4000 - 100 * k, "list_price_cents": 6000,  # >= 33%: ofertas
                                   **(store or {}).get(k, {})}]} for k in range(n)))
    saved = {k: os.environ.pop(k, None) for k in ("TELEGRAM_CHANNEL_ID", "WHATSAPP_CHANNEL_ID")}
    h = vis(page(offers_n(14)))
    assert h.count('aria-roledescription="slide"') == 5
    assert '<input type="checkbox" id="pausar"><label for="pausar">Pausar</label>' in h  # pausa sem JS (WCAG 2.2.2)
    assert "Destaques de hoje" in h and "Destaques da curadoria" not in h
    assert "Em alta" not in h and 'class="badge' not in h and 'class="chip chip--' not in h.replace("chip--g", "")
    assert 'href="/manga/"' in h and "data-filtro" in h
    for cls in ('blk--bot', 'blk--canais', 'class="bot"', 'class="canais"', 'class="fab-box"'):
        assert cls in h, cls                                               # sem bot nem canais: tudo "em breve"
    assert "t.me" not in h and "whatsapp.com" not in h
    hero_ids = re.findall(r'<div class="slide" id="d-([a-z0-9-]+)"', h)
    feat = h[h.index('id="h-curadoria"'):h.index('id="h-filtro"')]
    assert len(hero_ids) == 5 and feat.count('class="card"') == 9 and not any(f'data-id="{i}"' in feat for i in hero_ids)
    assert h[h.index('id="h-ativas"'):].count('class="card"') == 14       # o feed tem todas (busca/filtro do JS)
    assert re.search(r'id="h-ativas">Ofertas ativas</h2><span class="sec-n"[^>]*>14 ofertas no momento</span>', h)
    assert '<p class="mais mais--m"><a class="btn btn--ghost" href="/ofertas/">' in h  # 14: "ver todas" só no celular (corta em 4)
    big = vis(page(offers_n(30)))
    assert '<p class="mais"><a class="btn btn--ghost" href="/ofertas/">' in big and "Ver todas as 30 ofertas" in big  # > 24
    # fallback do destaque: selo válido antes do maior desconto
    h = page(offers_n(10, store={2: {"history_since": "2026-06-01", "lowest_90d_cents": 3800}}))
    assert h.index('id="d-l-2"') < h.index('id="d-l-9"')
    h = vis(page(offers_n(10, {**{k: {"featured": True} for k in range(7)}, 8: {"trending_rank": 2}, 9: {"trending_rank": 1}})))
    feat = h[h.index('id="h-curadoria"'):h.index('id="h-filtro"')]
    assert "Destaques da curadoria" in h and feat.count('class="card"') == 2 and 'data-id="l-0"' in feat and 'data-id="l-1"' in feat  # só curados, fora do hero
    assert "Em alta" not in h and "rank" not in h and "badge--alta" not in h  # trending_rank nunca aparece (§7)
    h = vis(page(offers_n(2), bot="ofertaslivros_bot", ch=[("Telegram", "https://t.me/ofertaslivros")]))
    assert h.count('class="slide"') == 2 and "Destaques" not in h        # 2 ofertas: as duas no hero, sem destaques
    for cls in ('blk--bot', 'blk--canais', 'class="bot"', 'class="canais"', 'class="fab"'):
        assert cls in h, cls
    assert 'href="https://t.me/ofertaslivros_bot" rel="noopener noreferrer"' in h  # bloco do alerta, sem start
    # pedir um livro: um form só (Worker /pedido no SITE), título e autor, honeypot; nada de dado do visitante
    forms = re.findall(r"<form[^>]*>", h)
    assert forms == [f'<form class="pedir" name="pedido" method="POST" action="{SITE}/pedido" accept-charset="utf-8">']
    pf = h[h.index('<form class="pedir"'):h.index("</form>")]
    assert re.findall(r'<input[^>]*name="([^"]+)"', pf) == ["site", "titulo", "autor"]
    assert ('name="titulo" required maxlength="150"' in pf and 'name="autor" maxlength="100"' in pf
            and '<input name="site" tabindex="-1"' in pf and not re.search(r'type="(email|tel)"|name="(nome|email|tel)', pf))
    assert '<button class="pedir-x js-px" type="button" hidden>' in pf  # X só com JS: sem JS o <summary> fecha
    assert '<details class="fab-box" id="pedir">' in h and 'id="pedido-recebido"' in h and "Recebemos seu pedido" in h
    g = vis(page(offers_n(4), "manga"))
    assert "carrossel" not in g and re.search(r'href="/manga/"[^>]*aria-current="page"', g)
    assert '<html lang="pt-BR" data-style="manga">' in page(offers_n(4), "manga")
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
    # critério "em oferta" (em_oferta, curadoria-automatica.md §10.8 item 3), com e sem median_90d_cents
    def em(store, **kw):
        return load({**good, "stores": [{**(amz if store == "amazon" else mls), **kw}]})[0]["oferta"]
    assert (OFERTA_MIN_DESCONTO, HIST_DIAS, MEDIANA_MAX) == (10, 30, 85)
    h29, h30, h90 = "2026-09-19", "2026-09-18", "2026-07-20"   # NOW = 18/10: 29, 30 e 90 dias de histórico
    for st in STORES:  # 1. menos de 30 dias (ou sem history_since): "de/por" >= 10%, a mediana não conta
        assert em(st, price_cents=9100, list_price_cents=10000, lowest_90d_cents=9000) is False      # 9%
        assert em(st, price_cents=9000, list_price_cents=10000, lowest_90d_cents=8000) is True       # 10%
        assert em(st, price_cents=9000, list_price_cents=10000, lowest_90d_cents=8000, history_since=h29,
                  median_90d_cents=20000) is True
        assert em(st, price_cents=5000, list_price_cents=5000, lowest_90d_cents=5000, history_since=h29,
                  median_90d_cents=20000) is False                                                   # 25% da mediana, 29 dias
    # 2. 30 dias ou mais com a mediana: <= 85% dela ou selo de 90 dias; "de/por" de 40% sozinho não.
    # 4. Na Amazon igual: a mediana só vem com cobertura >= 80% (o coletor confere); sem ela, critério 3.
    ml30 = {"history_since": h30, "median_90d_cents": 10000, "lowest_90d_cents": 8000}
    for st in STORES:
        assert em(st, price_cents=8500, list_price_cents=8500, **ml30) is True                       # 85%
        assert em(st, price_cents=8501, list_price_cents=8501, **ml30) is False
        assert em(st, price_cents=6000, list_price_cents=10000, history_since=h30, median_90d_cents=6500,
                  lowest_90d_cents=5000) is False                                                    # 40% no de/por, 92% da mediana
        assert em(st, price_cents=9900, list_price_cents=9900, lowest_90d_cents=9900, history_since=h90,
                  median_90d_cents=9900) is True                                                     # selo de 90 dias
        # 3. 30 dias ou mais sem a mediana: volta ao "de/por" (o selo sozinho não basta)
        assert em(st, price_cents=6000, list_price_cents=10000, lowest_90d_cents=5000, history_since=h30) is True
        assert em(st, price_cents=9900, list_price_cents=9900, lowest_90d_cents=9900, history_since=h90) is False
    # 5. "menor preço desde" não promove; a informação continua no card
    assert em("amazon", price_cents=9900, list_price_cents=9900, lowest_90d_cents=9900, history_since="2026-10-10") is False
    assert em("amazon", price_cents=9000, list_price_cents=10000, lowest_90d_cents=9000, history_since="2026-10-10") is True
    desde = vis(page(load(A(price_cents=9900, list_price_cents=9900, lowest_90d_cents=9900, history_since="2026-10-10"))))
    assert 'data-tipo="sem-oferta"' in desde and '<p class="stamp stamp--since">Menor preço desde 10/10</p>' in desde
    assert 'id="h-da-curadoria"' in desde and "Nenhuma oferta conferida agora" in desde
    for bad in (0, -1, 1.5, "100", True, None):                                     # mediana inválida quebra o build
        assert rejects(A(median_90d_cents=bad)), bad
    assert load(A(median_90d_cents=1))[0]["median_90d_cents"] == 1 and load(good)[0]["median_90d_cents"] is None
    assert {"curadoria", "novidades"} <= RESERVED and not set(GENRES) & RESERVED   # slugs reservados
    def nov(i, hs=None, title=None, **kw):
        st = {**amz, "price_cents": 5000, "list_price_cents": 5000, "lowest_90d_cents": 4500, **kw}
        if hs:
            st["history_since"] = hs
        return {**good, "id": f"nov-{i}", "title": title or f"Novo {i}", "genre": "manga", "stores": [st]}
    mix_books = [*[{**good, "id": f"l-{k}", "title": f"Livro {k}", "stores": [{**amz, "price_cents": 4000 - 100 * k,
                                                                               "list_price_cents": 6000}]} for k in range(5)],
                 nov(1, "2026-10-01", "Zeta"), nov(2, "2026-10-17", "Beta"), nov(3, "2026-10-17", "Alfa"), nov(4)]
    mix = load(*mix_books)
    h = vis(page(mix, bot="ofertaslivros_bot"))
    hero_ = h[:h.index('id="h-filtro"')]
    ativas = h[h.index('id="h-ativas"'):h.index('id="h-da-curadoria"')]
    novs = h[h.index('id="h-da-curadoria"'):]
    assert "nov-" not in hero_ and "nov-" not in ativas
    assert re.findall(r'data-id="(nov-\d)"', novs) == ["nov-3", "nov-2", "nov-1", "nov-4"]  # history_since desc, título
    assert re.search(r'id="h-ativas">Ofertas ativas</h2><span class="sec-n"[^>]*>5 ofertas no momento</span>', h)  # só ofertas
    assert re.search(r'id="h-da-curadoria">Da curadoria</h2><p class="sec-note">Livros escolhidos por nós', h)
    assert '<p class="mais"><a class="btn btn--ghost" href="/curadoria/">' in novs and "Ver toda a curadoria" in novs
    assert '<span class="cur-c">5 ofertas</span>' in h                                      # "Todos" conta ofertas
    assert re.search(r'<span class="sec-n"[^>]*>1 oferta no momento</span>', vis(page(load(good))))  # singular
    card_n = novs[novs.index('data-id="nov-2"'):]
    card_n = card_n[:card_n.index("</li>")]
    assert ('class="sticker"' not in card_n and "<s " not in card_n and "desconto" not in card_n
            and not re.search(r"(?i)\bofertas?\b", card_n.replace('data-tipo="sem-oferta"', "").replace("Sem oferta agora", ""))
            and 'data-tipo="sem-oferta"' in card_n and '<span class="sem">Sem oferta agora</span>' in card_n)
    assert ('class="buy-c"' in card_n and 'class="bell"' in card_n and "visto hoje às" in card_n
            and 'class="badge badge--novo">Novo<' in card_n)                                # loja, horário, compra, sino, Novo
    assert vis(page(load(*mix_books, *(nov(k) for k in range(5, 15))))).count('data-tipo="sem-oferta"') == CUR_MAX  # até 8
    pg = render_pages(mix)
    assert "nov-" not in pg["ofertas/index.html"].split('id="ofertas"')[0].split("<main")[1]  # /ofertas/ só com ofertas
    assert "novidades/index.html" not in pg and "livro/nov-1/index.html" in pg
    assert "Sem oferta agora: o preço" in pg["livro/nov-1/index.html"] and "oferta conferida" not in pg["livro/nov-1/index.html"]
    gm = vis(page(mix, "manga"))
    assert gm.index('id="h-ativas"') < gm.index('id="h-da-curadoria"') and 'href="/curadoria/#manga"' in gm  # nicho
    blob = json.loads(re.search(r'id="ofertas">(.*?)</script>', page(mix)).group(1))
    assert all(d["off"] == 0 and d["de"] is None and d["nov"] for d in blob if d["id"].startswith("nov-"))
    try:
        post_text(next(o for o in mix if o["id"] == "nov-1"), "https://ofertaslivros.com.br/r/nov-1/tg")
        raise AssertionError("post_text aceitou livro sem oferta")
    except Invalid:
        pass
    assert post_text(mix[0], "https://ofertaslivros.com.br/r/l-0/tg")                         # oferta passa
    # /curadoria/: todo livro fresco, com ou sem oferta, uma seção por nicho na ordem de GENRES
    cur_books = [*mix_books, {**nov(5, "2026-10-12"), "genre": "literatura-brasileira"}, {**good, "id": "fc-1", "genre": "ficcao"}]
    cpg = render_pages(load(*cur_books))
    cp = cpg["curadoria/index.html"]
    cv = vis(cp)
    order = ["literatura-brasileira", "ficcao", "manga"]
    assert re.findall(r'<section class="sec" aria-labelledby="([a-z-]+)">', cv) == order
    assert re.findall(r'<a class="pill" href="#([a-z-]+)">', cv) == order               # âncoras no topo
    mg = cv[cv.index('id="manga"'):]
    assert re.findall(r'data-id="([a-z0-9-]+)"', mg) == ["nov-3", "nov-2", "nov-1", "l-0", "l-1", "l-2", "l-3", "l-4", "nov-4"]
    assert mg.count('data-tipo="oferta"') == 5 and mg.count('data-tipo="sem-oferta"') == 4  # com e sem oferta
    assert "<ol" not in cv and "<h1>Curadoria: livros que valem a leitura</h1>" in cv
    assert "o preço final é o da loja" in cv[cv.index('class="intro"'):cv.index("</div>", cv.index('class="intro"'))]
    assert ("ganhamos com compras qualificadas" in cp and "o preço final é o da loja" in cp.split('class="foot-legal"')[1]
            and '<meta name="description" content="Livros selecionados, com e sem oferta, por nicho.">' in cp)
    assert '<a href="/curadoria/" aria-current="page">Curadoria</a>' in cp
    for path, h in cpg.items():                                            # o menu tem Curadoria, não Novidades
        assert "/novidades/" not in h and "Novidade" not in h and '<a href="/curadoria/"' in h, path
    # nada de ranking na tela (§7, critério 10), mesmo com trending_rank nos dados
    banido = re.compile(r"(?i)\bn[º°o]\.?\s*\d|\b\d+\s*[ºª°]|\btop\s*\d|mais\s+vendid|mais\s+procurad|best.?seller|"
                        r"em\s+alta|tend[êe]ncia|\d+\s*(vendid|compra|avalia)")
    tr = render_pages(load(*({**b, "trending_rank": k + 1} for k, b in enumerate(cur_books))), "ofertaslivros_bot",
                      [("Telegram", "https://t.me/ofertaslivros")])
    for path in ("index.html", "curadoria/index.html", "manga/index.html"):
        assert not banido.search(tr[path]), (path, banido.search(tr[path]))
    assert set(re.findall(r'<ol class="([^"]*)"', tr["index.html"])) <= {"segs", "passos"}  # nenhuma <ol> de livros
    x = curadoria_page(load({**good, "title": '<img src=x onerror=alert(1)>', "author": '"><script>alert(1)</script>'}))
    assert "<img src=x" not in x and "<script>alert" not in x and "&lt;img src=x onerror=alert(1)&gt;" in x  # XSS
    # sem nenhuma oferta: só a curadoria, sem carrossel nem "0 ofertas"
    only = load(nov(1, "2026-10-01"), nov(2, "2026-10-17"))
    h = vis(page(only))
    assert "Destaques" not in h and 'class="tnum"' not in h and "0 oferta" not in h
    hero_ = h[h.index('<section class="hero'):h.index("</section>")]
    assert (hero_.count('data-tipo="sem-oferta"') == 2                                       # hero só sem oferta
            and not re.search(r"(?i)\bofertas?\b", hero_.replace('data-tipo="sem-oferta"', "")))
    assert "<h1>Livros conferidos na loja</h1>" in h and "baixaram de verdade</h1>" not in h
    assert 'Nenhuma oferta conferida agora. Veja a <a href="/curadoria/">curadoria</a>' in h and 'id="h-da-curadoria"' in h
    assert '<span class="cur-c">2 livros</span>' in h
    assert "Nenhuma oferta conferida agora" in render_pages(only)["ofertas/index.html"]
    # hero logo depois do header com qualquer número de livros: ofertas primeiro, sem oferta completando até 5
    def hero_of(items, bot=None):
        h = vis(page(items, bot=bot))
        if '<section class="hero' not in h:
            return None, h
        return h[h.index('<section class="hero'):h.index("</section>", h.index('<section class="hero'))], h
    def ofs(n):
        return [{**good, "id": f"o-{k}", "title": f"Oferta {k}", "stores": [{**amz, "price_cents": 4000 - 100 * k,
                                                                             "list_price_cents": 6000}]} for k in range(n)]
    for n in (1, 2, 5):
        hr, h = hero_of(load(*ofs(n)))
        assert hr.count('class="slide"') == n and 'data-tipo="sem-oferta"' not in hr, n
        assert h.index('class="intro"') < h.index('<section class="hero') < h.index('id="h-filtro"')  # ordem da spec
        assert ("<h1>Livros que baixaram de verdade</h1>" in h) and (f'class="hero hero--{n}"' in hr)
    hr, h = hero_of(load(*ofs(1)))
    for ctl in ('class="hero-nav"', "segs", "js-prev", "js-next", "pausar", "aria-roledescription"):
        assert ctl not in hr, ctl                                               # 1 slide: sem controles nem passagem
    hr, h = hero_of(load(*ofs(2)))
    assert 'aria-roledescription="carrossel"' in hr and "js-next" in hr and 'id="pausar"' in hr
    mix1 = load(*ofs(1), nov(1, "2026-10-01"), nov(2, "2026-10-17"), nov(3, "2026-10-16"), nov(4, "2026-10-15"), nov(5, "2026-10-14"))
    hr, h = hero_of(mix1, bot="ofertaslivros_bot")
    tipos = re.findall(r'class="slide" id="d-([a-z0-9-]+)" data-g="\w+" data-tipo="([\w-]+)"', hr)
    assert tipos == [("o-0", "oferta")] + [(f"nov-{k}", "sem-oferta") for k in range(2, 6)]
    sl = hr[hr.index('id="d-nov-2"'):hr.index('id="d-nov-3"')]
    assert '<span class="chip chip--nov">Da curadoria</span>' in sl and "off-pill" not in sl and "<s " not in sl
    assert not re.search(r"(?i)\bofertas?\b", sl.replace('data-tipo="sem-oferta"', "")) and 'href="/r/nov-2"' in sl and "Me avise se baixar (Telegram)" in sl
    assert "<h1>Livros conferidos na loja</h1>" in h                                       # hero misturado: H1 sem "baixaram"
    nv = h[h.index('id="h-da-curadoria"'):]
    assert max(h.count(f'href="/livro/nov-{k}/"') for k in range(1, 6)) <= 2              # hero + curadoria, no máximo
    assert nv.index('data-id="nov-1"') < nv.index('data-id="nov-2"')                       # a que está no hero vai para o fim
    assert hero_of(load(nov(1)))[0].count('class="slide"') == 1                            # 0 ofertas, 1 sem oferta
    # envs vazias (vars ausentes no Actions chegam como ""): bot e canais ausentes, sem quebrar o build
    saved = {k: os.environ.pop(k, None) for k in ("TELEGRAM_BOT_USERNAME", "TELEGRAM_CHANNEL_ID", "WHATSAPP_CHANNEL_ID")}
    os.environ.update(TELEGRAM_BOT_USERNAME="", TELEGRAM_CHANNEL_ID="", WHATSAPP_CHANNEL_ID="")
    assert tg_bot() is None and channels() == []
    pages0 = render_pages(load(*ofs(2)), tg_bot(), channels())
    assert "canais/index.html" not in pages0
    for path, h in pages0.items():   # nenhum link para t.me/WhatsApp, nenhum href="#"; o que depende deles diz "em breve"
        assert not re.search(r'href="(https://t\.me|https://whatsapp\.com|#")', h) and 'href="#"' not in h, path
    h = pages0["index.html"]
    soon = re.findall(r'<span class="([^"]*) is-soon" aria-disabled="true">(.*?)<span class="sr">, </span><span class="soon">em breve</span></span>', h)
    kinds = [k for k, _ in soon]
    for k in ("pill pill--tg", "pill pill--wa", "bell", "btn btn--ghost alert", "go",
              "btn btn--tg", "btn btn--wa", "foot-soon"):
        assert k in kinds, k                                                   # header, card, hero, banner, bloco, canais, FAB, rodapé
    assert any("Canal no WhatsApp" in t for k, t in soon if k == "pill pill--wa")  # texto acessível: "Canal no WhatsApp, em breve"
    assert not re.search(r"<(?:a|button)[^>]*\bis-soon", h) and "tabindex" not in re.sub(r'<p class="sr" aria-hidden="true"><label>Não preencha .*?</p>', "", h.split("<dialog")[0])  # só o honeypot
    assert "Em breve você poderá tocar no sino" in h and "Ele avisa por lá" not in h  # FAQ não promete o alerta
    assert "A lista de desejos ainda não está no ar" in pages0["privacidade/index.html"]
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "is-soon" in js and "aria-disabled" in js and "em breve" in js                  # modal sem bot: sino "em breve"
    hb = render_pages(load(*ofs(2)), "ofertaslivros_bot", [("Telegram", "https://t.me/ofertaslivros"),
                                                            ("WhatsApp", "https://whatsapp.com/channel/0029VaAbCdEfGhIjKlMnOp12")])
    h = hb["index.html"]
    assert "is-soon" not in h and 'class="soon"' not in h and "canais/index.html" in hb  # com as envs: tudo link real
    assert '<a class="pill pill--wa" href="https://whatsapp.com/channel/0029VaAbCdEfGhIjKlMnOp12"' in h
    assert '<a class="bell" href="https://t.me/ofertaslivros_bot?start=o-0"' in h and '<summary class="fab">' in h  # o fab não depende do bot
    for k, v in saved.items():
        os.environ.pop(k, None)
        if v is not None:
            os.environ[k] = v
    # nenhum livro em mais de 2 seções da home (hero ou destaques + ofertas ativas)
    h = vis(page(offers_n(14, {k: {"trending_rank": k + 1} for k in range(14)})))
    assert max(h.count(f'href="/livro/l-{k}/"') for k in range(14)) <= 2
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
    # Amazon fora do prazo: o livro fica como estava (preço, desconto, oferta, /r/ com a tag) + o aviso
    vel = load(good, M(checked_at="2026-10-18T19:00:00-03:00"), now=late)
    assert [x["id"] for x in vel] == ["livro-1", "livro-2"] and vel[0]["velho"] and not vel[1]["velho"]
    v, fresco = vel[0], load(good)[0]
    assert (v["price_cents"], v["oferta"], v["seal"], off(v)) == (fresco["price_cents"], fresco["oferta"], fresco["seal"], off(fresco))
    assert v in ofertas(vel) and v in hero_items(vel)
    c = card(v)
    assert brl(1990) in c and "−50%" in c and f'<span class="velho">{VELHO}</span>' in c and VELHO not in card(fresco)
    assert f'<span class="velho">{VELHO}</span>' in book_page(v, vel) and brl(1990) in book_page(v, vel)
    assert offer_json(v, None)["meta"].endswith(f". {VELHO}") and offer_json(v, None)["p"] == brl(1990)
    assert f"/r/livro-1 https://www.amazon.com.br/dp/B0ABCDEFGH?tag={t} 302" in redirects(vel).splitlines()
    try:
        post_text(v, "https://x.com/r/livro-1")  # canal nunca publica preço vencido
        raise AssertionError("post_text aceitou preço fora do prazo")
    except Invalid:
        pass
    only_ml = {**good, "stores": [{**mls, "checked_at": "2026-10-18T08:00:00-03:00"}]}
    assert [x["id"] for x in load(only_ml, M(checked_at="2026-10-18T19:00:00-03:00"), now=late)] == ["livro-2"]  # ML vencido sai
    assert load(good, now=late)[0]["velho"]                                 # só Amazon vencida: publica com o aviso
    sem = load(good, now=datetime(2026, 10, 25, 8, 1, tzinfo=BRT))[0]       # 7 dias e 1 min: vai para a Curadoria
    assert sem["velho"] and not sem["oferta"] and off(sem) == 0 and sem not in ofertas([sem])
    assert load(good, now=datetime(2026, 10, 25, 8, 0, tzinfo=BRT))[0]["oferta"]  # 7 dias: ainda oferta
    c = card(sem)
    assert brl(1990) in c and VELHO in c and 'href="/r/livro-1"' in c and 'data-tipo="sem-oferta"' in c
    bp = book_page(sem, [sem])
    assert "tem mais de 7 dias" in bp and "não baixou o bastante" not in bp
    try:
        load(only_ml, now=late)  # nenhum livro elegível
        raise AssertionError("lista vazia")
    except Invalid:
        pass
    assert not load(A(checked_at="2026-10-18T09:04:00-03:00"))[0]["velho"]  # 4 min no futuro: tolerado
    assert load(A(checked_at="2026-10-18T09:06:00-03:00"))[0]["velho"]       # 6 min: fora do prazo, com o aviso
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
    # card: compra em círculo (loja e preço no nome acessível); seta só com a segunda loja elegível
    one = vis(page(load(good)))
    assert ('<a class="buy-c" href="/r/livro-1" rel="sponsored noopener noreferrer" target="_blank">' in one
            and "<span class=\"sr\">Ver na Amazon por R$\u00a019,90: T (abre em nova aba)</span>" in one and '<details class="alt"' not in one)
    two = load({**good, "stores": [amz, {**mls, "price_cents": 1890, "checked_at": "2026-10-18T08:30:00-03:00"}]})
    home12 = vis(page(load(*({**good, "id": f"x-{k}", "stores": [amz, {**mls, "price_cents": 1890}]} for k in range(12)))))
    assert home12.count('class="buy-c"') == home12.count('class="card"') == 12 + 7  # feed + destaques (12 - 5 do hero)
    assert home12.count('<details class="alt"') == home12.count('class="card"') + 5            # seta em cada card e em cada slide
    for h in (vis(page(two)), vis(page(two, "manga")), home12):
        assert "Ver no Mercado Livre por R$\u00a018,90" in h
        assert '<span class="sr">Outra loja: Amazon</span></summary>' in h
        assert '/amazon" rel="sponsored noopener noreferrer" target="_blank">Também na Amazon: R$\u00a019,90' in h
    h = vis(page(two))
    assert h[h.index('id="h-ativas"'):].count("visto hoje às") == 2           # no card: vencedora + a outra na seta
    assert ('<span class="store">Mercado Livre</span> <span>visto hoje às <time datetime="2026-10-18T08:30:00-03:00">08h30</time>'
            in h)
    assert '<span class="alt-when">visto hoje às <time datetime="2026-10-18T08:00:00-03:00">08h00</time>' in h
    bp = vis(book_page(two[0], two, "ofertaslivros_bot"))                   # página: as duas lojas por extenso
    assert ">Ver no Mercado Livre por R$\u00a018,90<svg" in bp and '<p class="other"><a class="btn btn--ghost" href="/r/livro-1/amazon"' in bp
    assert 'no Mercado Livre</span>, visto hoje às <time datetime="2026-10-18T08:30:00-03:00">08h30</time>' in bp
    assert ">Me avise se baixar (Telegram)<span" in bp                       # texto completo na página
    # urgência honesta: "visto em DD/MM" quando não é hoje (relógio do build); nada de contador
    h = vis(page(load(A(checked_at="2026-10-17T22:00:00-03:00"))))
    assert 'visto em 17/10 às <time datetime="2026-10-17T22:00:00-03:00">22h00</time>' in h and "visto hoje" not in h
    x = vis(page(load(A(checked_at="2026-10-18T01:30:00Z"))))
    assert x[x.index('id="h-ativas"'):].count("visto em 17/10 às") == 1        # 22h30 BRT do dia 17 (no card)
    assert ('<p class="carimbo carimbo--bar"><span>conferido</span> <time datetime="2026-10-17T22:00:00-03:00">'
            '<b>17/10</b> às 22h00</time></p>') in h                          # o carimbo do topo também
    # "caiu R$ X desde DD/MM": último preço diferente do atual na série, se era maior (hero e página)
    def fell(price=1990, **kw):
        return livro(history_since="2026-10-01", price_cents=price, **kw)
    assert "Caiu R$\u00a05,00 desde 10/10</span>" in fell(price_points=ok_pp)
    assert "Caiu R$\u00a010,00 desde 01/10" in fell(price_points=pp(("2026-10-01", 2990), ("2026-10-12", 1990)))
    assert "Caiu R$\u00a010,00 desde 01/10" in fell(price_points=pp(("2026-10-01", 2990), ("2026-10-18", 2500)))  # hoje não conta
    assert "Caiu" not in fell(2490, price_points=pp(("2026-10-01", 2990), ("2026-10-10", 1990)))  # subiu depois de cair
    assert "Caiu" not in fell(price_points=pp(("2026-10-01", 1990))) and "Caiu" not in fell()
    h = fell(price_points=pp(("2026-10-01", 2990)))
    assert "Caiu R$\u00a010,00 desde 01/10" in h and 'class="hist"' not in h        # 1 ponto: queda sim, gráfico não
    assert not re.search(r"acaba|restam|minutos|últimas", page(o))
    assert '<details class="alt"' not in page(load({**good, "stores": [amz, {**mls, "price_cents": 1890}]},
                                       now=datetime(2026, 10, 18, 10, 31, tzinfo=BRT)))  # ML velho: sem seta
    # capa real (só mlstatic) x placeholder do nicho (gradiente + inicial, decorativo); alt, dimensões, lazy
    h = vis(page(load({**good, "image_url": img})))
    assert (f'<div class="cover"><img src="{img}" alt="Capa de T, de A" width="120" height="180" '
            'loading="lazy" decoding="async"></div>' in h and "/capa.svg" not in h)
    h = vis(page(load(good)))
    assert '<div class="cover cover--none" aria-hidden="true"><span class="ini">T</span></div>' in h
    assert '<span class="pages" aria-hidden="true"></span>' in h            # o miolo do livro atrás da capa
    isbn_capa = next(STATIC.glob("capas/*.jpg")).stem                      # capa provisória local
    assert load({**good, "isbn": isbn_capa})[0]["image_url"] == f"/capas/{isbn_capa}.jpg"
    assert load({**good, "isbn": isbn_capa, "image_url": img})[0]["image_url"] == img  # foto do ML ganha
    h = vis(page(load({**good, "image_url": img, "title": 'O "x" <b>', "author": "A & B"})))
    assert 'alt="Capa de O &quot;x&quot; &lt;b&gt;, de A &amp; B"' in h and '"x" <b>' not in h
    h = vis(page(offers_n(5, {k: {"image_url": img} for k in range(5)})))
    hero_ = h[:h.index('id="h-filtro"')]
    assert hero_.count('loading="eager" fetchpriority="high"') == 1 and h.count('loading="eager"') == 1
    assert hero_.index('loading="eager"') < hero_.index('loading="lazy"')
    assert h.count("<img ") == h.count('width="120" height="180"') + 4 + h.count('src="/mavi.svg"')  # + logos (topo e rodapé) e a Mavi
    assert h.count('src="/mavi.svg"') == 2 and "i-carimbo" not in h.split('class="mascote')[1][:200]  # Mavi no banner e no capítulo do bot
    r = load({**good, "image_url": img})
    assert vis(book_page(r[0], r)).count('loading="eager" fetchpriority="high"') == 1  # na página do livro a capa é a LCP
    h = vis(page(offers_n(5, {0: {"blurb": '<i>"Duas" & irmãs</i>'}})))
    assert h.count('class="blurb"') == 1 and '<i>"Duas"' not in h
    assert re.search(r'<p class="blurb">&lt;i&gt;&quot;Duas&quot; &amp; irmãs&lt;/i&gt;</p>\s*<div class="hero-deal">', h)
    assert 'class="blurb"' not in vis(page(offers_n(5)))
    # CSP: só a foto do ML entra além do próprio site
    csp = HEADERS.split("Content-Security-Policy: ")[1].splitlines()[0]
    assert csp == ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' https://http2.mlstatic.com; "
                   "font-src 'self'; connect-src https://ofertaslivros.com.br; base-uri 'none'; form-action https://ofertaslivros.com.br; "
                   "frame-ancestors 'none'")                                 # só o POST do pedido de livro
    # JS: só o nosso arquivo, sem script inline executável; o JSON embutido não fecha o <script> antes da hora
    evil = '</script><script>alert(1)</script><!--'
    h = page(load({**good, "title": evil, "author": "</SCRIPT>"}), bot="ofertaslivros_bot")
    blob = re.search(r'<script type="application/json" id="ofertas">(.*?)</script>', h, re.S).group(1)
    assert "<" not in blob and json.loads(blob)[0]["t"] == evil and json.loads(blob)[0]["a"] == "</SCRIPT>"
    assert h.count("<script") == h.count("</script>") == 3                      # app.js + JSON-LD + JSON, nada mais
    assert re.findall(r"<script(?: [^>]*)?>", h) == ['<script type="application/ld+json">', '<script src="/app.js" defer>',
                                                     '<script type="application/json" id="ofertas">']
    assert "<script>" not in vis(h) and "&lt;/script&gt;&lt;script&gt;" in vis(h)
    d0 = json.loads(blob)[0]
    assert d0["lojas"][0]["href"] == "/r/livro-1" and d0["pag"] == "/livro/livro-1/" and d0["alerta"].startswith("https://t.me/")
    assert '<dialog class="modal" id="detalhe"' in h and h.count('id="ofertas"') == 1
    assert '<dialog' not in privacy(o) and 'id="ofertas"' not in book_page(o[0], o)  # modal só onde há cards
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|\beval\s*\(|new\s+Function|document\.write|"
                         r"set(?:Timeout|Interval)\s*\(\s*['\"`]|https?://(?!http2\.mlstatic\.com|t\.me)", js)
    assert len(js.encode()) < 15_000                                          # meta: menos de 15 KB
    if shutil.which("node"):                                                    # sintaxe, se houver node
        import subprocess
        subprocess.run(["node", "--check", str(STATIC / "app.js")], check=True)
    # contraste dos tokens (docs/marca/contraste.py lê o style.css; sai com erro se algum par falhar)
    import subprocess
    subprocess.run([sys.executable, "-I", str(ROOT / "docs" / "marca" / "contraste.py")], check=True, stdout=subprocess.DEVNULL)
    # badge só com dado real: "Novo" = history_since nos últimos 3 dias
    def badges(*stores, **kw):
        return re.findall(r'class="badge badge--(\w+)">', vis(page(load({**good, **kw, "stores": list(stores)}))))
    assert badges(amz) == []                                                    # sem histórico: não sabemos se é novo
    assert badges({**amz, "history_since": "2026-10-16"}) == ["novo"]          # 2 dias
    assert badges({**amz, "history_since": "2026-10-18"}) == ["novo"]
    assert badges({**amz, "history_since": "2026-10-15"}) == []                # 3 dias: já não é novo
    assert badges({**amz, "history_since": "2026-10-17"}, {**mls, "price_cents": 2990}) == []  # outra loja sem histórico
    assert badges({**amz, "history_since": "2026-10-17"}, trending_rank=4) == ["novo"]  # ranking nunca vira badge
    assert badges(amz, trending_rank=1) == []
    assert not re.search(r"(?i)estoque|ao vivo|restam|últimas unidades", vis(page(offers_n(14))))
    # páginas geradas: home, nichos, /ofertas/, /livro/<id>/ e privacidade; /canais/ só com canal
    pg = render_pages(load(good, ml))
    assert set(pg) == {"index.html", "privacidade/index.html", "ofertas/index.html", "curadoria/index.html", "manga/index.html",
                       "ofertas/40/index.html", "ofertas/50/index.html",
                       "ficcao/index.html", "livro/livro-1/index.html", "livro/livro-2/index.html"}
    assert "canais/index.html" in render_pages(load(good), ch=[("Telegram", "https://t.me/ofertaslivros")])
    for path, h in pg.items():                                                 # canonical absoluto, um por página
        assert re.findall(r'<link rel="canonical" href="([^"]+)">', h) == [SITE + "/" + path.removesuffix("index.html")], path
    assert '<link rel="canonical" href="https://ofertaslivros.com.br/livro/livro-1/">' in pg["livro/livro-1/index.html"]
    assert '<link rel="canonical" href="https://ofertaslivros.com.br/">' in pg["index.html"]
    # SEO: Open Graph em todas, og:url = canonical; og:image só com capa (sem arte padrão da marca em static/)
    for path, h in pg.items():
        head = h[:h.index("</head>")]
        can = re.search(r'<link rel="canonical" href="([^"]+)">', head).group(1)
        assert re.findall(r'<meta property="og:url" content="([^"]+)">', head) == [can], path
        title = re.search(r"<title>(.*?)</title>", head).group(1)
        desc = re.search(r'<meta name="description" content="([^"]*)">', head).group(1)
        assert f'<meta property="og:title" content="{title}">' in head and f'<meta property="og:description" content="{desc}">' in head
        for m in ('og:type" content="website', 'og:site_name" content="Ofertas Livros', 'og:locale" content="pt_BR'):
            assert f'<meta property="{m}">' in head, (path, m)
        assert ('og:image' in head) == ('twitter:card" content="summary_large_image' in head), path
        assert 'og:image' in head or 'twitter:card" content="summary"' in head, path
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', head, re.S):
            json.loads(raw)                                                    # JSON-LD válido
    assert "og:image" not in pg["index.html"] and "og:image" not in pg["livro/livro-1/index.html"]  # good não tem capa
    assert 120 <= len(html.unescape(re.search(r'<meta name="description" content="([^"]*)">', pg["ofertas/index.html"]).group(1))) <= 160

    def lds(h):
        return [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)]
    home = lds(pg["index.html"])[0]["@graph"]
    assert [x["@type"] for x in home] == ["WebSite", "Organization"] and home[1]["logo"] == SITE + "/logo.svg"
    assert [x["@type"] for x in lds(pg["manga/index.html"])] == ["BreadcrumbList"]
    assert [i["item"] for i in lds(pg["manga/index.html"])[0]["itemListElement"]] == [SITE + "/", SITE + "/manga/"]
    capa = load({**good, "title": "Mindset: a nova psicologia do sucesso", "author": "Carol S. Dweck", "isbn": "9788547000240",
                 "image_url": img, "stores": [{**amz, "price_cents": 2575}]})
    bp = render_pages(capa)["livro/livro-1/index.html"]
    assert f"<title>Mindset, Carol S. Dweck por R${nb}25,75 | Ofertas Livros</title>" in bp
    assert f'<meta property="og:image" content="{e(img)}">' in bp and 'content="summary_large_image"' in bp
    bc, prod = lds(bp)
    assert [(i["position"], i["name"], i["item"]) for i in bc["itemListElement"]] == [
        (1, "Início", SITE + "/"), (2, "Mangá e HQ", SITE + "/manga/"), (3, capa[0]["title"], SITE + "/livro/livro-1/")]
    assert prod["@type"] == ["Product", "Book"] and prod["isbn"] == "9788547000240" and prod["image"] == img
    assert prod["author"] == {"@type": "Person", "name": "Carol S. Dweck"} and prod["url"] == SITE + "/livro/livro-1/"
    assert prod["offers"] == {"@type": "Offer", "price": "25.75", "priceCurrency": "BRL", "availability": "https://schema.org/InStock",
                              "url": SITE + "/livro/livro-1/", "seller": {"@type": "Organization", "name": "Amazon"}}
    assert f"<strong>R${nb}25,75</strong>" in bp                                  # o mesmo preço da página
    assert lds(book_ld({**capa[0], "price_cents": 100005}))[0]["offers"]["price"] == "1000.05"
    assert "offers" not in lds(book_ld({**capa[0], "velho": True}))[0]        # preço velho: sem Offer
    local = load({**good, "isbn": isbn_capa})[0]                               # capa local vira URL absoluta do SITE
    assert abs_img(local) == f"{SITE}/capas/{isbn_capa}.jpg" and f'og:image" content="{SITE}/capas/' in book_page(local, [local])
    for t in ("T" * 200, "Um título bem comprido sem subtítulo nenhum para cortar aqui"):  # corta o título, nunca o preço
        bt = book_title({**capa[0], "title": t})
        assert len(bt) <= TITLE_MAX + 6 and bt.endswith(f", Carol S. Dweck por R${nb}25,75 | Ofertas Livros") and "…" in bt, bt
    assert book_title({**capa[0], "title": "Um título bem comprido sem subtítulo"}).startswith("Um título bem…, Carol")
    assert book_title({**capa[0], "title": "O Pequeno Príncipe", "author": "Antoine de Saint-Exupéry"}).startswith("O Pequeno Príncipe, ")
    assert book_title({**capa[0], "title": "Curto"}) == f"Curto, Carol S. Dweck por R${nb}25,75 | Ofertas Livros"
    # JSON-LD com dado coletado: nada fecha o <script>, e o JSON volta igual
    evil = "</script><script>alert(1)</script>"
    xp = render_pages(load({**good, "title": evil, "author": "<!-- & >"}))["livro/livro-1/index.html"]
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', xp, re.S)
    assert len(blocks) == 2 and all("<" not in b and ">" not in b and "&" not in b for b in blocks)
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert(1)" in blocks[1]
    assert json.loads(blocks[1])["name"] == evil and json.loads(blocks[1])["author"]["name"] == "<!-- & >"
    assert re.findall(r"<script(?: [^>]*)?>", xp) == ['<script type="application/ld+json">'] * 2 + ['<script src="/app.js" defer>']
    assert "<script>alert" not in xp and "&lt;/script&gt;" in xp[:xp.index("</head>")]  # title/og:title escapados
    # sitemap: todas as páginas, URL absoluta, sem bot.json, /painel nem /r/
    sm = sitemap(pg)
    assert sorted(re.findall(r"<loc>([^<]+)</loc>", sm)) == sorted(SITE + "/" + k.removesuffix("index.html") for k in pg)
    assert "bot.json" not in sm and "/r/" not in sm and "painel" not in sm and "lastmod" not in sm
    assert "Sitemap: https://ofertaslivros.com.br/sitemap.xml" in (STATIC / "robots.txt").read_text()
    lv = pg["livro/livro-1/index.html"]
    assert "<h1 class=\"livro-h1\">T</h1>" in lv and '<html lang="pt-BR" data-style="manga">' in lv
    assert 'href="/r/livro-1" rel="sponsored noopener noreferrer" target="_blank"' in lv
    assert 'href="/livro/livro-1/" data-modal="livro-1"' in pg["index.html"]  # o modal é atalho para a página real
    assert pg["ofertas/index.html"].count('class="card"') == 2 and "feed--full" in pg["ofertas/index.html"]
    for path, h in pg.items():                                                 # rodapé obrigatório em todas
        assert "ganhamos com compras qualificadas" in h and "o preço final é o da loja" in h, path
    # Black Friday: janela por data em BRT (bordas inclusive), destaque >= BF_MIN e a página /black-friday/
    assert campanha(datetime(2026, 11, 5, 2, 59, tzinfo=timezone.utc)) is None   # 04/11 23h59 BRT
    assert campanha(datetime(2026, 11, 5, 3, 0, tzinfo=timezone.utc)) == "on"    # 05/11 00h00 BRT
    assert campanha(datetime(2026, 12, 2, 2, 59, tzinfo=timezone.utc)) == "on"   # 01/12 23h59 BRT
    assert campanha(datetime(2026, 12, 2, 3, 0, tzinfo=timezone.utc)) == "fim"   # 02/12 00h00 BRT

    def bf(day, *books):  # "_h": horas desde a verificação (padrão 1 h, no prazo)
        n = datetime(2026, *day, 9, 0, tzinfo=BRT)
        return load(*[{**{k: v for k, v in b.items() if k != "_h"}, "stores": [
            {**s, "checked_at": (n - timedelta(hours=b.get("_h", 1))).isoformat()} for s in b["stores"]]}
            for b in books], now=n)
    pr = lambda p, de, **k: [{**amz, "price_cents": p, "list_price_cents": de, "lowest_90d_cents": p, **k}]  # noqa: E731
    b30 = {**good, "id": "bf-30", "stores": pr(7000, 10000)}
    b29 = {**good, "id": "bf-29", "stores": pr(7100, 10000)}
    b90 = {**good, "id": "bf-90d", "stores": pr(8000, 10000, history_since="2026-08-01")}  # 20%, mas selo de 90 dias
    bvel = {**good, "id": "bf-velho", "stores": pr(5000, 10000), "_h": 48}                # Amazon vencida: velho
    bnao = {**good, "id": "bf-nao", "stores": pr(9500, 10000)}                            # 5%: sem oferta
    # Faixas de desconto: /ofertas/40/ e /ofertas/50/ sempre existem; sem vencidos; livro sem oferta entra
    b50 = {**good, "id": "bf-50", "stores": pr(5000, 10000)}
    b40 = {**good, "id": "bf-40", "stores": pr(6000, 10000)}
    fo = bf((11, 10), b50, b40, b30, bvel, bnao)
    fp = render_pages(fo)
    ids = lambda h: re.findall(r'data-id="([^"]+)"', h.split('class="grid feed')[1])  # noqa: E731
    assert ids(fp["ofertas/40/index.html"]) == ["bf-50", "bf-40"] and ids(fp["ofertas/50/index.html"]) == ["bf-50"]
    for path in ("index.html", "ofertas/index.html", "ofertas/40/index.html", "ofertas/50/index.html"):
        assert '<a class="pill" href="/ofertas/40/"' in fp[path] and '50%+<span class="faixa-n">1<span class="sr"> livros</span></span>' in fp[path], path
    assert '<a class="pill" href="/ofertas/40/" aria-current="page">' in fp["ofertas/40/index.html"]
    assert re.search(r'Todos</span>.*?2 ofertas', fp["ofertas/40/index.html"])                      # nichos contam a faixa
    assert 'aria-current="page">Todas' in fp["ofertas/index.html"] and 'aria-current="page">Todas' not in fp["index.html"]
    assert com_desconto([{"id": "nov", "velho": False, "oferta": False, "price_cents": 5000,
                          "list_price_cents": 10000}], 50) == []                                 # fora da vitrine: não entra
    assert all(len(com_desconto(fo, t)) <= len(ofertas(fo)) for t in FAIXAS)
    assert 'data-id="bf-50"' in fp["ofertas/50/index.html"] and 'data-off="50"' in fp["ofertas/50/index.html"]
    vazio = render_pages(bf((11, 10), b30))["ofertas/50/index.html"]
    assert "Nenhum livro com 50% ou mais de desconto agora." in vazio and 'class="card"' not in vazio
    for day, on in (((11, 4), False), ((11, 5), True), ((12, 1), True), ((12, 2), False)):
        bo = bf(day, b30, b29, b90, bvel, bnao)
        pg = render_pages(bo)
        for path, h in pg.items():
            foot_bf = re.search(r'<a href="/black-friday/"( aria-current="page")?>Black Friday</a>', h)
            assert ('class="sazonal"' in h) == on and bool(foot_bf) == on, (day, path)
            if 'class="card"' in h:
                assert ("sticker--forte" in vis(h)) == on, (day, path)
        assert ('"forte":true' in pg["index.html"]) == on                               # pílula do modal
        if day == (11, 4):
            assert "black-friday/index.html" not in pg
        elif day == (12, 2):                                                   # links compartilhados não quebram
            fim = pg["black-friday/index.html"]
            assert "A Black Friday 2026 acabou" in fim and 'href="/ofertas/"' in fim and 'class="card"' not in fim
        else:
            bfp = pg["black-friday/index.html"]
            assert re.findall(r'<li class="card"[^>]* data-id="([^"]+)"', bfp) == ["bf-90d", "bf-30"]  # ranked: selo primeiro
            assert "<h1>Black Friday de livros</h1>" in bfp and "visto hoje às 08h00" in bfp
            assert "ganhamos com compras qualificadas" in bfp and "o preço final é o da loja" in bfp
            assert '<a href="/black-friday/" aria-current="page">Black Friday</a>' in bfp
            assert not re.search(r"(?i)ranking|mais vendid|posição|termina|restam|estoque|últimas", vis(bfp))
            assert bfp.index('class="skip"') < bfp.index('class="sazonal"') < bfp.index('<main')  # pular é o 1º foco
            cards = {o["id"]: card(o) for o in bo}
            assert 'class="sticker sticker--forte"' in cards["bf-30"]
            assert 'class="sticker"' in cards["bf-29"] and "--forte" not in cards["bf-29"]
            assert "sticker" not in cards["bf-nao"]
            assert "off-pill--forte" in book_page(bo[0], bo) and "off-pill--forte" in slide(bo[0], 1, 1)
            assert "off-pill--forte" not in book_page(bo[1], bo)
            vazio = render_pages(bf(day, b29, bnao))["black-friday/index.html"]
            assert "Nenhum livro com desconto grande agora." in vazio and 'class="card"' not in vazio
    # post: linha "também" só com a outra loja elegível até 10% mais cara, sem URL de loja
    def post(ml_price, now=NOW):
        r = load({**good, "title": "Torto Arado", "author": "Itamar Vieira Junior",
                  "stores": [{**amz, "price_cents": 4290, "list_price_cents": 7490, "lowest_90d_cents": 4290},
                             {**mls, "price_cents": ml_price, "list_price_cents": 7490,
                              "checked_at": "2026-10-18T08:40:00-03:00"}]}, now=now)[0]
        return post_text(r, "https://ofertaslivros.com.br/r/livro-1/wa")
    assert post(4719).splitlines() == [
        "Torto Arado, de Itamar Vieira Junior", f"R${nb}42,90 (de R${nb}74,90, -42%)",
        "Amazon · preço verificado em 18/10 às 08h00. O preço final é o da loja.",
        f"Também no Mercado Livre por R${nb}47,19", "Link de afiliado: https://ofertaslivros.com.br/r/livro-1/wa"]
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
