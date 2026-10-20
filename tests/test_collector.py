"""Critérios 1 a 4 de docs/produto/alerta-de-preco.md e contrato v2 de comparacao-lojas.md.
Rede sempre mockada; catálogo via fixture."""
import hashlib
import io
import json
import socket
import sys
from datetime import datetime, timezone
from decimal import Decimal
from http.client import RemoteDisconnected
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from collector import collect as c  # noqa: E402
from build import Invalid  # noqa: E402

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
HEADER = "asin,price_cents,list_price_cents,checked_at\n"
ISBN = "9788550807560"
IMG = "https://http2.mlstatic.com/D_NQ_NP_123-MLA0_102019-O.jpg"
ML_URL = "https://www.mercadolivre.com.br/social/teste-aff?matt_word=teste-aff&matt_tool=1&ref=X"
CATALOG = {"books": [
    {"id": "livro-duplo", "isbn": ISBN, "asin": "B0ABCDEFGH", "ml_product_id": "MLB11",
     "ml_url": ML_URL, "title": "Livro 1", "author": "A", "genre": "ficcao"},
    {"id": "livro-ml-2", "ml_product_id": "MLB22", "ml_url": ML_URL,
     "title": "Livro 2", "author": "B", "genre": "manga"},
]}


def prod(item="MLB9001", gtin=ISBN, img=IMG):
    p = {"id": "x", "status": "active", "pictures": [{"id": "1", "url": img}],
         "attributes": [{"id": "BRAND", "value_name": "Editora"}],
         "buy_box_winner": {"item_id": item, "price": 40, "currency_id": "BRL"}}
    if gtin:
        p["attributes"].append({"id": "GTIN", "value_name": gtin})
    return p


class FakeML:
    """Substitui urlopen: responde como a API do ML e registra todo host/rota chamada."""

    def __init__(self):
        self.hosts, self.paths = [], []
        self.products = {"MLB11": prod("MLB9001"), "MLB22": prod("MLB9002", gtin=None)}
        self.sale = {"amount": 39.9, "regular_amount": 59.9, "currency_id": "BRL"}
        self.items = {}  # /products/{id}/items; produto fora daqui responde 404
        self.sale_status = None  # ex.: 403, como o token de app recebe em produção
        self.on_call = None

    def __call__(self, req, timeout=None):
        assert timeout and timeout > 0, "toda request precisa de timeout"
        assert req.get_header("User-agent", "").startswith("ofertaslivros-coletor/")
        u = urlsplit(req.full_url)
        self.hosts.append(u.hostname)
        self.paths.append(u.path)
        if self.on_call:
            self.on_call()
        if u.path == "/oauth/token":
            body = {"access_token": "APP_USR-sentinela", "expires_in": 21600}
        elif u.path.startswith("/products/") and u.path.endswith("/items"):
            pid = u.path.split("/")[2]
            if pid not in self.items:
                raise HTTPError(req.full_url, 404, "x", {}, None)
            body = self.items[pid]
            pages = body.get("_pages") if isinstance(body, dict) else None
            if pages is not None:
                body = pages[int(parse_qs(u.query).get("offset", ["0"])[0])]
        elif u.path.startswith("/products/"):
            body = self.products[u.path.rsplit("/", 1)[1]]
        elif u.path.endswith("/sale_price"):
            assert u.query == "context=channel_marketplace"
            if self.sale_status:
                raise HTTPError(req.full_url, self.sale_status, "x", {}, None)
            body = self.sale
        else:
            raise AssertionError(f"rota inesperada {u.path}")
        return io.BytesIO(json.dumps(body).encode())


@pytest.fixture
def env(tmp_path, monkeypatch):
    fake = FakeML()
    monkeypatch.setattr(c, "_urlopen", fake)
    monkeypatch.setattr(c.time, "sleep", lambda s: None)

    def no_socket(host, *a, **k):  # qualquer rede real que escape do mock
        raise AssertionError(f"rede real chamada: {host}")
    monkeypatch.setattr(socket, "getaddrinfo", no_socket)
    monkeypatch.setenv("ML_CLIENT_ID", "id")
    monkeypatch.setenv("ML_CLIENT_SECRET", "segredo")
    monkeypatch.setenv("ML_AFFILIATE_ID", "teste-aff")
    monkeypatch.delenv("GITHUB_RUN_NUMBER", raising=False)
    cat = tmp_path / "catalog.json"
    cat.write_text(json.dumps(CATALOG))
    manual = tmp_path / "amazon_prices.csv"
    manual.write_text(HEADER + "B0ABCDEFGH,2990,4990,2026-10-18T08:00:00-03:00\n")
    hist = tmp_path / "history"

    def run(now=NOW, **kw):
        return c.run(hist, now=now, catalog=cat, manual=manual, **kw)
    return {"fake": fake, "hist": hist, "manual": manual, "cat": cat, "run": run}


def rows(hist):
    return [ln for p in sorted((hist / "price_history").glob("*.csv"))
            for ln in p.read_text().splitlines()[1:]]


def offers(hist):
    return {o["id"]: o for o in json.loads((hist / "offers.json").read_text())["offers"]}


# ---- critério 1: append-only, uma linha nova por item do ML por execução ----

def test_criterio1_append_only(env):
    hist = env["hist"]
    assert env["run"]() == 0
    shard = hist / "price_history" / "2026-10.csv"
    before = shard.read_bytes()
    n_before = len(rows(hist))
    assert n_before == 3  # 2 do ML + 1 manual
    assert env["run"]() == 0
    after = shard.read_bytes()
    assert len(rows(hist)) == n_before + 2  # +1 por item do ML; o manual não duplica
    assert hashlib.sha256(after[:len(before)]).digest() == hashlib.sha256(before).digest()
    assert "livro-duplo,mercadolivre,3990,5990,2026-10-18T12:00:00+00:00,ml_api" in rows(hist)
    assert "livro-duplo,amazon,2990,4990,2026-10-18T11:00:00+00:00,manual" in rows(hist)
    # produto -> vencedor -> sale_price do vencedor
    assert env["fake"].paths[:3] == ["/oauth/token", "/products/MLB11",
                                     "/items/MLB9001/sale_price"]


def test_token_nao_vaza_no_log(env, capsys):
    env["run"]()
    out = capsys.readouterr()
    assert "sentinela" not in out.out + out.err and "segredo" not in out.out + out.err


def test_virada_de_mes(env):
    env["manual"].write_text(HEADER + "B0ABCDEFGH,2990,4990,2026-10-31T22:30:00-03:00\n")
    now = datetime(2026, 11, 1, 3, 0, tzinfo=timezone.utc)
    env["run"](now=now)
    env["run"](now=now)
    nov = (env["hist"] / "price_history" / "2026-11.csv").read_text().splitlines()
    assert [ln for ln in nov if ln.endswith(",manual")] == [
        "livro-duplo,amazon,2990,4990,2026-11-01T01:30:00+00:00,manual"]
    assert not (env["hist"] / "price_history" / "2026-10.csv").exists()


def test_csv_com_bom_do_excel(env):
    env["manual"].write_bytes(b"\xef\xbb\xbf" + (HEADER + "B0ABCDEFGH,2990,4990,"
                                                 "2026-10-18T08:00:00-03:00\n").encode())
    assert env["run"]() == 0
    assert any(r.endswith(",manual") for r in rows(env["hist"]))


# ---- critério 2: nenhuma request para a Amazon ----

def test_criterio2_nenhum_host_amazon(env):
    env["run"]()
    hosts = env["fake"].hosts
    assert hosts and set(hosts) == {"api.mercadolibre.com"}
    assert not [h for h in hosts if "amazon" in h]


def test_criterio2_sem_credenciais_nao_chama_rede_e_falha(env, monkeypatch):
    monkeypatch.delenv("ML_CLIENT_ID")
    assert env["run"]() == 1  # ML no catálogo e nada coletado: job vermelho
    assert env["fake"].hosts == []
    assert len(rows(env["hist"])) == 1  # o manual já validado é gravado


# ---- critério 3: entrada manual inválida falha sem gravar nada ----

@pytest.mark.parametrize("line", [
    "B0ABCDEFGH,2990,4990,2026-10-18T08:00:00",       # sem fuso
    "B0ABCDEFGH,29.90,4990,2026-10-18T08:00:00-03:00",  # preço não inteiro
    "B0ABCDEFGH,2990,49.9,2026-10-18T08:00:00-03:00",
    "B0ABCDEFGH,1e3,4990,2026-10-18T08:00:00-03:00",
    "B0ABCDEFGH,-10,4990,2026-10-18T08:00:00-03:00",
    "B0ABCDEFGH,2990,1000001,2026-10-18T08:00:00-03:00",  # acima de R$ 10.000
    "b0abcdefgh,2990,4990,2026-10-18T08:00:00-03:00",   # fora do ASIN_RE
    "B0ABC,2990,4990,2026-10-18T08:00:00-03:00",
    "B0ZZZZZZZZ,2990,4990,2026-10-18T08:00:00-03:00",   # fora do catálogo
    "B0ABCDEFGH,4990,2990,2026-10-18T08:00:00-03:00",   # de < por
    "B0ABCDEFGH,2990,4990,2027-01-01T08:00:00-03:00",   # futuro
    "B0ABCDEFGH,2990,4990,2026-10-10T08:00:00-03:00",   # mais de 7 dias
    "B0ABCDEFGH,2990,4990",                              # coluna faltando
])
def test_criterio3_manual_invalido_nao_grava(env, line):
    good = "B0ABCDEFGH,2990,4990,2026-10-17T08:00:00-03:00\n"
    env["manual"].write_text(HEADER + good + line + "\n")
    with pytest.raises(Invalid):
        env["run"]()
    assert not env["hist"].exists()  # nem a linha boa, nem o ML, nem offers.json
    assert env["fake"].hosts == []


def test_criterio3_main_sai_com_erro(env, monkeypatch):
    env["manual"].write_text(HEADER + "B0ABCDEFGH,29.90,4990,2026-10-18T08:00:00-03:00\n")
    monkeypatch.setattr(c, "MANUAL_CSV", env["manual"])
    monkeypatch.setattr(c, "CATALOG", env["cat"])
    with pytest.raises(SystemExit) as e:
        c.main(["run", "--history", str(env["hist"])])
    assert e.value.code != 0 and not env["hist"].exists()


# ---- critério 4: id do catálogo inválido faz o build falhar ----

@pytest.mark.parametrize("bad", ["a" * 58, "Torto-Arado", "torto_arado", "a/b", "-a",
                                 "a\n/r/x https://evil.com 302", "", None])
def test_criterio4_id_invalido(bad, tmp_path, monkeypatch):
    monkeypatch.setenv("ML_AFFILIATE_ID", "teste-aff")
    doc = json.loads(json.dumps(CATALOG))
    doc["books"][0]["id"] = bad
    with pytest.raises(Invalid):
        c.load_catalog(doc)
    cat = tmp_path / "catalog.json"
    cat.write_text(json.dumps(doc))
    monkeypatch.setattr(c, "CATALOG", cat)
    with pytest.raises(SystemExit) as e:
        c.main(["export", str(tmp_path / "out.json")])
    assert e.value.code != 0 and not (tmp_path / "out.json").exists()


def test_criterio4_limite_57_e_export(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_AFFILIATE_ID", "teste-aff")
    doc = json.loads(json.dumps(CATALOG))
    doc["books"][0]["id"] = "a" * 57
    cat = tmp_path / "catalog.json"
    cat.write_text(json.dumps(doc))
    monkeypatch.setattr(c, "CATALOG", cat)
    assert c.main(["export", str(tmp_path / "out.json")]) == 0
    pub = json.loads((tmp_path / "out.json").read_text())["books"]
    assert pub[0] == {"id": "a" * 57, "title": "Livro 1", "author": "A", "genre": "ficcao",
                      "stores": ["amazon", "mercadolivre"]}


@pytest.mark.parametrize("change", [
    {"genre": "terror"}, {"ml_product_id": "MLB1.evil.com"},
    {"ml_url": "https://meli.la/abc"}, {"url": "https://evil.com"}, {"title": ""},
    {"store": "amazon"}, {"isbn": "9788550807561"},  # dígito verificador errado
    {"isbn": "978-85-508-0756-0"}, {"isbn": 9788550807560}, {"asin": "b0abc"},
])
def test_catalogo_rejeita(change, monkeypatch):
    monkeypatch.setenv("ML_AFFILIATE_ID", "teste-aff")
    doc = json.loads(json.dumps(CATALOG))
    doc["books"][0].update(change)
    with pytest.raises(Invalid):
        c.load_catalog(doc)


@pytest.mark.parametrize("drop", [("isbn",), ("ml_url",), ("asin", "ml_product_id", "ml_url")])
def test_catalogo_rejeita_faltando(drop, monkeypatch):
    # duas lojas sem isbn; produto sem link; livro sem loja nenhuma
    monkeypatch.setenv("ML_AFFILIATE_ID", "teste-aff")
    doc = json.loads(json.dumps(CATALOG))
    for k in drop:
        del doc["books"][0][k]
    with pytest.raises(Invalid):
        c.load_catalog(doc)


def test_catalogo_rejeita_duplicado(monkeypatch):
    monkeypatch.setenv("ML_AFFILIATE_ID", "teste-aff")
    doc = json.loads(json.dumps(CATALOG))
    doc["books"][1]["ml_product_id"] = "MLB11"
    with pytest.raises(Invalid):
        c.load_catalog(doc)


def test_catalogo_do_repo_e_valido(monkeypatch):
    # sem lista fixa de ids: o catálogo cresce a cada PR do curator
    monkeypatch.setenv("ML_AFFILIATE_ID", "elias-arruda")
    ids = [b["id"] for b in c.load_catalog(json.loads(c.CATALOG.read_text()),
                                           include_pending=True)]
    assert {"senhor-dos-aneis-box-trilogia", "irmao-do-jorel"} <= set(ids)


# ---- pendente (sugestão do curator, ainda sem link do painel) ----

PEND = {"id": "livro-pendente", "isbn": "9780306406157", "ml_product_id": "MLB33",
        "title": "Pendente", "author": "C", "genre": "negocios", "pendente": True}


def test_pendente_fica_fora_da_coleta_e_do_ar(env, capsys):
    doc = json.loads(json.dumps(CATALOG))
    doc["books"].append(dict(PEND))
    env["cat"].write_text(json.dumps(doc))
    assert env["run"]() == 0
    assert "/products/MLB33" not in env["fake"].paths  # nem request
    assert "livro-pendente" not in offers(env["hist"])
    assert not any(r.startswith("livro-pendente,") for r in rows(env["hist"]))
    assert "livro-pendente pendente" in capsys.readouterr().out
    out = env["hist"] / "public.json"
    c.export_catalog(c.read_catalog(env["cat"]), out)
    assert "livro-pendente" not in out.read_text()


def test_catalogo_so_com_pendentes_nao_quebra_o_pipeline(env):
    env["cat"].write_text(json.dumps({"books": [dict(PEND)]}))
    env["manual"].write_text(HEADER)
    assert env["run"]() == 0
    assert offers(env["hist"]) == {}
    assert env["fake"].paths == ["/oauth/token"]


@pytest.mark.parametrize("change", [
    {"ml_url": ML_URL}, {"asin": "B0ABCDEFGH"}, {"pendente": False}, {"pendente": "sim"},
    {"ml_product_id": None}, {"ml_product_id": "MLB11"},  # duplica um livro ativo
])
def test_pendente_rejeita(change, monkeypatch):
    monkeypatch.setenv("ML_AFFILIATE_ID", "teste-aff")
    doc = json.loads(json.dumps(CATALOG))
    p = {**PEND, **change}
    if p["ml_product_id"] is None:
        del p["ml_product_id"]
    doc["books"].append(p)
    with pytest.raises(Invalid):
        c.load_catalog(doc)


def test_resposta_html_aborta(monkeypatch):
    class Html(io.BytesIO):
        headers = {"Content-Type": "text/html; charset=utf-8"}
    monkeypatch.setattr(c, "_urlopen", lambda req, timeout=None: Html(b"{}"))
    with pytest.raises(c.MLError, match="não é JSON"):
        c.ml_request("/products/MLB1")


# ---- offers.json v2 ----

def test_offers_v2_contrato(env):
    env["run"]()
    o = offers(env["hist"])
    d = o["livro-duplo"]
    assert d["isbn"] == ISBN and d["image_url"] == IMG
    assert [s["store"] for s in d["stores"]] == ["amazon", "mercadolivre"]
    amz, ml = d["stores"]
    assert amz == {"store": "amazon", "asin": "B0ABCDEFGH", "price_cents": 2990,
                   "list_price_cents": 4990, "lowest_90d_cents": 2990,
                   "history_since": "2026-10-18", "checked_at": "2026-10-18T11:00:00+00:00"}
    assert ml["ml_product_id"] == "MLB11" and ml["ml_url"] == ML_URL
    assert ml["price_cents"] == 3990 and ml["list_price_cents"] == 5990
    assert [s["store"] for s in o["livro-ml-2"]["stores"]] == ["mercadolivre"]
    assert "isbn" not in o["livro-ml-2"]
    assert "winner" not in json.dumps(o)  # o back não escolhe a vencedora


def test_offers_menor_90d_e_history_since(env):
    hist = env["hist"]
    (hist / "price_history").mkdir(parents=True)
    (hist / "price_history" / "2026-07.csv").write_text(
        ",".join(c.HISTORY_COLS) + "\n"
        "livro-ml-2,mercadolivre,1000,1000,2026-07-10T12:00:00+00:00,ml_api\n"   # > 90 dias
        "livro-ml-2,mercadolivre,3500,5990,2026-07-25T12:00:00+00:00,ml_api\n")  # dentro
    env["run"]()
    ml = offers(hist)["livro-ml-2"]["stores"][0]
    assert ml["lowest_90d_cents"] == 3500 and ml["price_cents"] == 3990
    assert ml["history_since"] == "2026-07-10"
    env["fake"].sale = {"amount": 30, "regular_amount": None, "currency_id": "BRL"}
    env["run"]()
    ml = offers(hist)["livro-ml-2"]["stores"][0]
    assert ml["lowest_90d_cents"] == 3000 == ml["price_cents"] == ml["list_price_cents"]
    assert ml["history_since"] == "2026-07-10"  # fixo no state.json


def test_mediana_dias_8_a_90(env, monkeypatch):
    """aba-curadoria.md, critério 14: alta nos últimos 7 dias não muda a mediana."""
    monkeypatch.setattr(c, "EMIT_MEDIAN", True)
    hist = env["hist"]
    (hist / "price_history").mkdir(parents=True)
    head = ",".join(c.HISTORY_COLS) + "\n"
    (hist / "price_history" / "2026-07.csv").write_text(
        head + "livro-ml-2,mercadolivre,1000,1000,2026-07-10T12:00:00+00:00,ml_api\n")  # > 90 dias
    (hist / "price_history" / "2026-09.csv").write_text(head + "".join(
        f"livro-ml-2,mercadolivre,{p},9990,2026-09-{d}T12:00:00+00:00,ml_api\n"
        for d, p in [("01", 5000), ("01", 4500), ("02", 5100), ("03", 4000), ("04", 6000),
                     ("05", 5500)]))  # dia 01: vale o menor do dia
    (hist / "price_history" / "2026-10.csv").write_text(
        head + "livro-ml-2,mercadolivre,4000,9990,2026-10-11T02:00:00+00:00,ml_api\n"  # 10/10 BRT: dia 8
        + "".join(f"livro-ml-2,mercadolivre,9000,9990,2026-10-{d}T12:00:00+00:00,ml_api\n"
                  for d in ("12", "15", "17")))  # alta nos últimos 7 dias: fora
    env["run"]()
    ml = offers(hist)["livro-ml-2"]["stores"][0]
    assert ml["median_90d_cents"] == 4500  # 4000 4000 4500 5100 5500 6000 -> median_low
    assert "median_90d_cents" not in offers(hist)["livro-duplo"]["stores"][1]  # sem histórico


def test_mediana_fora_enquanto_o_build_nao_aceita(env, monkeypatch):
    monkeypatch.setattr(c, "EMIT_MEDIAN", False)
    hist = env["hist"]
    (hist / "price_history").mkdir(parents=True)
    (hist / "price_history" / "2026-09.csv").write_text(
        ",".join(c.HISTORY_COLS) + "\n"
        "livro-ml-2,mercadolivre,3500,5990,2026-09-01T12:00:00+00:00,ml_api\n")
    env["run"]()
    assert "median_90d_cents" not in json.dumps(offers(hist))


def test_mediana_le_o_shard_do_dia_90(env, monkeypatch):
    """01/03 01h UTC = 28/02 BRT: o dia 90 é 30/11, no 5º mês UTC para trás."""
    monkeypatch.setattr(c, "EMIT_MEDIAN", True)
    now = datetime(2027, 3, 1, 1, 0, tzinfo=timezone.utc)
    hist = env["hist"]
    (hist / "price_history").mkdir(parents=True)
    (hist / "price_history" / "2026-11.csv").write_text(
        ",".join(c.HISTORY_COLS) + "\n"
        "livro-ml-2,mercadolivre,3500,5990,2026-11-30T12:00:00+00:00,ml_api\n")
    _, _, _, daily = c.summarize(hist, now)
    assert list(daily[("livro-ml-2", "mercadolivre")]) == [c.date(2026, 11, 30)]


def test_mediana_amazon_exige_cobertura():
    from datetime import date, timedelta
    today = date(2026, 10, 18)
    window = [today - timedelta(days=n) for n in range(8, 91)]  # 83 dias; 80% = 66,4
    assert c.median_90d({d: 3000 for d in window[:66]}, "2026-01-01", today, "amazon") is None
    assert c.median_90d({d: 3000 for d in window[:67]}, "2026-01-01", today, "amazon") == 3000
    assert c.median_90d({d: 3000 for d in window[:10]}, "2026-01-01", today, "mercadolivre") == 3000
    # janela limitada ao history_since: 10 dias de série, 10 amostras = 100%
    since = (today - timedelta(days=17)).isoformat()
    assert c.median_90d({d: 3000 for d in window[:10]}, since, today, "amazon") == 3000
    assert c.median_90d({}, since, today, "mercadolivre") is None


def test_gtin_divergente_descarta_preco_do_ml(env, capsys):
    env["fake"].products["MLB11"] = prod(gtin="9780306406157")
    assert env["run"]() == 0
    assert not any(r.startswith("livro-duplo,mercadolivre") for r in rows(env["hist"]))
    assert [s["store"] for s in offers(env["hist"])["livro-duplo"]["stores"]] == ["amazon"]
    out = capsys.readouterr().out
    assert "GTIN do produto não bate" in out and "1 gtin_divergente" in out


def test_gtin_varios_valores_um_bate(env):
    env["fake"].products["MLB11"] = prod(gtin=f"9780306406157, {ISBN}")
    env["run"]()
    assert any(r.startswith("livro-duplo,mercadolivre") for r in rows(env["hist"]))


@pytest.mark.parametrize("img", ["https://evil.com/x.jpg", "http://http2.mlstatic.com/x.jpg",
                                 "https://http2.mlstatic.com/x.jpg?a=1",
                                 'https://http2.mlstatic.com/x"onerror=1.jpg',
                                 "https://http2.mlstatic.com.evil.com/x.jpg"])
def test_image_url_fora_do_cdn_e_ignorada(env, img):
    env["fake"].products["MLB11"] = prod(img=img)
    env["run"]()
    assert "image_url" not in offers(env["hist"])["livro-duplo"]


def test_offers_quebrado_nao_e_gravado(env, monkeypatch):
    def broken(*a):
        return {"version": 2, "offers": [{"id": "x", "genre": "ficcao", "title": "T",
                                          "author": "A", "stores": []}]}
    monkeypatch.setattr(c, "build_offers", broken)
    with pytest.raises(Invalid):
        env["run"]()
    assert not (env["hist"] / "offers.json").exists()


def _good_offer():
    return {"id": "livro", "isbn": ISBN, "genre": "ficcao", "title": "T", "author": "A",
            "image_url": IMG, "stores": [
                {"store": "amazon", "asin": "B0ABCDEFGH", "price_cents": 3490,
                 "list_price_cents": 6490, "lowest_90d_cents": 3490,
                 "history_since": "2026-07-01", "checked_at": "2026-10-18T08:52:00-03:00"},
                {"store": "mercadolivre", "ml_product_id": "MLB1", "ml_url": ML_URL,
                 "price_cents": 3290, "list_price_cents": 5990, "lowest_90d_cents": 3290,
                 "history_since": "2026-10-18", "checked_at": "2026-10-18T09:10:00-03:00"}]}


@pytest.mark.parametrize("mut", [
    lambda o: o.update(winner="amazon"),
    lambda o: o.update(image_url="https://evil.com/a.jpg"),
    lambda o: o.update(isbn="123"),
    lambda o: o["stores"].append(dict(o["stores"][0])),               # 3 lojas
    lambda o: o["stores"].__setitem__(1, dict(o["stores"][0])),       # loja repetida
    lambda o: o["stores"][0].update(price_cents=34.9),
    lambda o: o["stores"][0].update(lowest_90d_cents=9999),           # lowest > price
    lambda o: o["stores"][0].update(list_price_cents=100),
    lambda o: o["stores"][0].update(checked_at="2026-10-18T08:52:00"),
    lambda o: o["stores"][0].update(history_since="2026-12-01"),
    lambda o: o["stores"][0].update(url="https://evil.com"),
    lambda o: o["stores"][1].update(ml_url="https://meli.la/x"),
    lambda o: o.update(stores=["amazon"]),
    lambda o: o["stores"][0].update(median_90d_cents=0),
    lambda o: o["stores"][0].update(median_90d_cents="3000"),
])
def test_validate_offers_rejeita(mut, monkeypatch):
    monkeypatch.setenv("ML_AFFILIATE_ID", "teste-aff")
    o = _good_offer()
    c.validate_offers({"version": 2, "offers": [o]})
    mut(o)
    with pytest.raises(Invalid):
        c.validate_offers({"version": 2, "offers": [o]})


def test_validate_offers_exemplo_do_contrato(monkeypatch):
    monkeypatch.setenv("ML_AFFILIATE_ID", "teste-aff")
    assert c.validate_offers({"version": 2, "offers": [_good_offer()]})
    with pytest.raises(Invalid):
        c.validate_offers({"version": 1, "offers": []})


# ---- ML: inativo, moeda, malformado, falha total, deadline, rotação ----

def item(iid, price, cur="BRL", cond="new", **kw):
    it = {"item_id": iid, "seller_id": 999, "price": price, "currency_id": cur, **kw}
    if cond is not None:
        it["condition"] = cond
    return it


def test_buy_box_presente_nao_chama_items(env, capsys):
    assert env["run"]() == 0
    assert not [p for p in env["fake"].paths if p.endswith("/items")]
    out = capsys.readouterr().out
    assert ("ML diag: livro-duplo /products=200 buy_box=sim /items=- novos_brl=- "
            "caminho=buy_box") in out
    assert "ML: 2 ok, 0 inativo" in out


@pytest.mark.parametrize("status", ["active", None])  # doc: active com buy_box_winner null
def test_sem_buy_box_usa_preco_do_items(env, capsys, status):
    p = prod()
    p["buy_box_winner"] = None
    if status is None:
        del p["status"]
    env["fake"].products["MLB11"] = p
    env["fake"].sale_status = 403  # se chamasse sale_price, viraria erro
    env["fake"].items["MLB11"] = {"paging": {"total": 7, "limit": 50, "offset": 0}, "results": [
        item("MLB7001", 45, original_price=60),
        item("MLB7002", 20, cur="USD"),                # moeda diferente
        item("MLB7003", 25, status="paused"),          # não ativo
        item("MLB7004", 31.5, original_price=49.9),    # vence (JSON vira Decimal)
        item("x/../MLB1", 10),                         # item_id fora do MLB_RE
        item("MLB7005", 15, cond="used"),              # usado
        item("MLB7006", 12, cond=None),                # sem condition: descarta
    ]}
    env["fake"].items["MLB22"] = {"results": [item("MLB7007", 30, original_price="x")]}
    env["fake"].products["MLB22"]["buy_box_winner"] = None
    assert env["run"]() == 0
    assert not [p for p in env["fake"].paths if p.endswith("/sale_price")]
    hist = rows(env["hist"])
    assert "livro-duplo,mercadolivre,3150,4990,2026-10-18T12:00:00+00:00,ml_api" in hist
    assert "livro-ml-2,mercadolivre,3000,3000,2026-10-18T12:00:00+00:00,ml_api" in hist
    out = capsys.readouterr().out
    assert "ML diag: livro-duplo /products=200 buy_box=não /items=7 novos_brl=2 caminho=items" in out
    assert "999" not in out and "MLB700" not in out  # nada de vendedor nem anúncio no log


def test_items_pagina_todas_as_listagens_para_escolher_menor(env):
    p = prod()
    p["buy_box_winner"] = None
    env["fake"].products["MLB11"] = p
    env["fake"].items["MLB11"] = {"_pages": {
        0: {"paging": {"total": 2, "limit": 1, "offset": 0},
            "results": [item("MLB7001", 45)]},
        1: {"paging": {"total": 2, "limit": 1, "offset": 1},
            "results": [item("MLB7002", 25)]},
    }}
    assert env["run"]() == 0
    assert any(r.startswith("livro-duplo,mercadolivre,2500,2500,") for r in rows(env["hist"]))
    assert [p for p in env["fake"].paths if p.endswith("/items")] == [
        "/products/MLB11/items", "/products/MLB11/items"]


def test_items_total_acima_do_limite_falha_fechado(env):
    p = prod()
    p["buy_box_winner"] = None
    env["fake"].products["MLB11"] = p
    env["fake"].items["MLB11"] = {"paging": {"total": 1001, "limit": 50, "offset": 0},
                                   "results": []}
    assert env["run"]() == 1
    assert not any(r.startswith("livro-duplo,mercadolivre") for r in rows(env["hist"]))


def test_original_price_menor_ou_igual_vira_price():
    it = item("MLB1", 30, original_price=20)
    r = c.listing_row("b", json.loads(json.dumps(it), parse_float=Decimal), NOW)
    assert r["price_cents"] == r["list_price_cents"] == 3000


def test_buy_box_sale_price_403_cai_para_preco_do_winner(env, capsys):
    env["fake"].sale_status = 403
    env["fake"].products["MLB11"]["buy_box_winner"]["original_price"] = 55
    assert env["run"]() == 0
    hist = rows(env["hist"])
    assert "livro-duplo,mercadolivre,4000,5500,2026-10-18T12:00:00+00:00,ml_api" in hist
    assert "livro-ml-2,mercadolivre,4000,4000,2026-10-18T12:00:00+00:00,ml_api" in hist  # sem original
    out = capsys.readouterr().out
    assert "caminho=buy_box_preco_winner" in out


def test_buy_box_sale_price_403_sem_preco_no_winner_e_erro(env):
    env["fake"].sale_status = 403
    for pid in ("MLB11", "MLB22"):
        del env["fake"].products[pid]["buy_box_winner"]["price"]
    assert env["run"]() == 1
    assert not any(r.endswith(",ml_api") for r in rows(env["hist"]))


def test_buy_box_sale_price_500_nao_cai_para_winner(env):
    env["fake"].sale_status = 500
    assert env["run"]() == 1
    assert not any(r.endswith(",ml_api") for r in rows(env["hist"]))


@pytest.mark.parametrize("items", [
    None,                                              # 404: nenhum anúncio
    {"results": []},
    {"results": [item("MLB7002", 20, cur="USD")]},     # só moeda diferente
    {"results": [item("MLB7002", 20, cond="used")]},   # só usado
    {"results": [item("MLB7002", 20, cond=None)]},     # só sem condition
])
def test_sem_buy_box_e_sem_item_elegivel_e_inativo(env, capsys, items):
    env["fake"].products["MLB11"] = {"id": "x", "status": "active", "buy_box_winner": None}
    if items is not None:
        env["fake"].items["MLB11"] = items
    assert env["run"]() == 0
    ml = [r for r in rows(env["hist"]) if r.endswith(",ml_api")]
    assert len(ml) == 1 and ml[0].startswith("livro-ml-2,")
    out = capsys.readouterr().out
    assert "ML: 1 ok, 1 inativo, 0 gtin_divergente, 0 erro" in out
    assert "caminho=inativo" in out and not [p for p in env["fake"].paths
                                             if p.startswith("/items/MLB7")]


def test_produto_inativo_sem_itens(env):
    env["fake"].products["MLB11"] = {"id": "x", "status": "inactive", "buy_box_winner": None}
    assert env["run"]() == 0
    assert "/products/MLB11/items" in env["fake"].paths


def test_fallback_items_sem_amazon_e_sem_token_no_log(env, capsys):
    for pid in ("MLB11", "MLB22"):
        env["fake"].products[pid]["buy_box_winner"] = None
        env["fake"].items[pid] = {"results": [item("MLB7004", 30)]}
    assert env["run"]() == 0
    assert set(env["fake"].hosts) == {"api.mercadolibre.com"}
    out = capsys.readouterr()
    assert "sentinela" not in out.out + out.err and "segredo" not in out.out + out.err
    assert "Bearer" not in out.out + out.err


@pytest.mark.parametrize("bad", [
    {"sale": {"amount": 39.9, "regular_amount": None, "currency_id": "USD"}},
    {"sale": {"amount": 20000.0, "currency_id": "BRL"}},  # acima do teto
    {"sale": ["lista"]},
    {"prod": {"status": "active", "buy_box_winner": {"item_id": 123}}},
    {"prod": {"status": "active", "buy_box_winner": "x"}},
    {"prod": ["lista"]},
    {"prod": {"status": "active", "buy_box_winner": None}, "items": ["lista"]},
    {"prod": {"status": "active", "buy_box_winner": None}, "items": {"results": "x"}},
])
def test_resposta_ruim_vira_erro_e_job_vermelho(env, bad):
    if "sale" in bad:
        env["fake"].sale = bad["sale"]
    else:
        env["fake"].products["MLB11"] = bad["prod"]
    if "items" in bad:
        env["fake"].items["MLB11"] = bad["items"]
    assert env["run"]() == 1
    assert not any(r.startswith("livro-duplo,mercadolivre") for r in rows(env["hist"]))


def test_falha_total_sai_com_1(env, monkeypatch):
    def down(req, timeout=None):
        if urlsplit(req.full_url).path == "/oauth/token":
            return io.BytesIO(b'{"access_token": "t"}')
        raise HTTPError(req.full_url, 503, "x", {}, None)
    monkeypatch.setattr(c, "_urlopen", down)
    assert env["run"]() == 1
    assert len(rows(env["hist"])) == 1  # só o manual


def test_token_falha_sai_com_1(env, monkeypatch):
    def bad(req, timeout=None):
        raise HTTPError(req.full_url, 401, "x", {}, None)
    monkeypatch.setattr(c, "_urlopen", bad)
    assert env["run"]() == 1


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_deadline_adia_sem_erro(env, capsys):
    clk = Clock()

    def tick():  # cada request "leva" 15 s; orçamento é 40 s com o token incluso
        clk.t += 15
    env["fake"].on_call = tick
    assert env["run"](clock=clk) == 0
    assert "1 ok, 0 inativo, 0 gtin_divergente, 0 erro, 1 adiado" in capsys.readouterr().out
    assert env["fake"].paths.count("/oauth/token") == 1


def test_deadline_nao_espera_alem_do_orcamento():
    clk, waits = Clock(), []

    def flaky(req, timeout=None):
        raise HTTPError(req.full_url, 503, "x", {"Retry-After": "20"}, None)
    old, c._urlopen = c._urlopen, flaky
    try:
        with pytest.raises(c.Deadline):
            c.ml_request("/x", deadline=10, clock=clk, sleep=waits.append)
    finally:
        c._urlopen = old
    assert waits == []  # 20 s de espera estouraria os 10 s que sobram


def test_rotacao_pelo_run_number(env, monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_NUMBER", "7")  # 7 % 2 = 1: começa pelo segundo
    env["run"]()
    assert env["fake"].paths[1] == "/products/MLB22"


# ---- probe ----

def test_probe_nao_imprime_token(env, capsys):
    assert c.probe(["MLB11", "evil/../x"]) == 0
    out = capsys.readouterr().out
    assert "sentinela" not in out and "segredo" not in out
    assert "MLB11 /products -> 200" in out and "price_cents=3990 list_price_cents=5990" in out
    assert f"gtin=['{ISBN}']" in out and "ignorado" in out


# ---- dinheiro, backoff, fila ----

def test_to_cents():
    assert c.to_cents(Decimal("39.9")) == 3990 and c.to_cents(40) == 4000
    assert c.to_cents(json.loads("19.99", parse_float=Decimal)) == 1999
    assert c.to_cents(Decimal("10000")) == 1_000_000
    for bad in (Decimal("39.999"), Decimal("0"), Decimal("-1"), Decimal("NaN"),
                Decimal("10000.01"), 39.9, True, None):
        with pytest.raises(Invalid):
            c.to_cents(bad)


def test_backoff_429_e_queda_de_conexao(monkeypatch):
    calls, waits = [], []

    def flaky(req, timeout=None):
        calls.append(1)
        if len(calls) == 1:
            raise HTTPError(req.full_url, 429, "x", {"Retry-After": "٣"}, None)  # dígito não-ASCII
        if len(calls) == 2:
            raise RemoteDisconnected("x")
        return io.BytesIO(b'{"ok": 1}')
    monkeypatch.setattr(c, "_urlopen", flaky)
    assert c.ml_request("/x", sleep=waits.append) == {"ok": 1}
    assert waits == [1, 2]


def test_404_nao_repete(monkeypatch):
    calls = []

    def nf(req, timeout=None):
        calls.append(1)
        raise HTTPError(req.full_url, 404, "x", {}, None)
    monkeypatch.setattr(c, "_urlopen", nf)
    with pytest.raises(c.MLError):
        c.ml_request("/items/MLB1/sale_price?x=1", sleep=lambda s: None)
    assert len(calls) == 1


def test_fila_ordem():
    books = [{"id": i, "asin": "B0ABCDEFGH", "title": i} for i in "abc"]
    last = {"a": "2026-10-17T10:00:00+00:00", "b": "2026-10-10T10:00:00+00:00"}
    assert [b["id"] for b in c.amazon_queue(books, last)] == ["c", "b", "a"]


def test_fila_no_disco(env):
    env["run"]()
    q = (env["hist"] / "amazon_queue.csv").read_text().splitlines()
    assert q[1].startswith("livro-duplo,B0ABCDEFGH,Livro 1,2026-10-18T11:00:00+00:00,")
    assert "tag=" not in q[1]


def test_datas_da_retirada_no_state(env):
    """curadoria-automatica.md §10.8, item 6: o coletor mantém as datas que o curator lê."""
    env["run"]()
    cu = json.loads((env["hist"] / "state.json").read_text())["curadoria"]
    raw = json.loads((env["hist"] / "offers.json").read_text())
    o = {x["id"]: x for x in c.build.load_offers(raw, NOW)}
    assert set(cu) == {b["id"] for b in c.read_catalog(env["cat"])}
    for bid, st in cu.items():
        assert st["publicado"] == "2026-10-18"
        assert st["ultima_oferta"] == ("2026-10-18" if o.get(bid, {}).get("oferta") else None)
    assert any(st["ultima_oferta"] for st in cu.values())
    # 3 dias depois, sem preço fresco: nada avança, e quem sai do catálogo sai do estado
    later = datetime(2026, 10, 21, 23, 0, tzinfo=timezone.utc)
    books = c.read_catalog(env["cat"])
    st = c.load_state(env["hist"])
    c.track_curadoria(st, books[:1], {}, raw, later)
    assert st["curadoria"] == {books[0]["id"]: cu[books[0]["id"]]}
