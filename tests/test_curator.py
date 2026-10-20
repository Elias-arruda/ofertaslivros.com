"""Critérios de aceite de docs/produto/curator.md (seção 11). Rede sempre mockada."""
import io
import json
import re
import socket
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from collector import collect as c  # noqa: E402
from collector import curator as cur  # noqa: E402

TODAY = date(2026, 10, 19)
ML_URL = "https://www.mercadolivre.com.br/social/teste-aff?matt_word=teste-aff&matt_tool=1&ref=X"
MANGA, NEG, LIT, BIO, AUTOAJUDA = "13061816", "13061825", "7538039", "13611960", "7538148"


def isbn(n):
    base = f"97885{n:07d}"
    ck = (10 - sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(base)) % 10) % 10
    return base + str(ck)


def prod(n, genre=MANGA, lang="Português", price=40, cond="new", cur_id="BRL",
         status="active", orig=None, gtin=None, title=None, author="Autora"):
    attrs = [{"id": "GTIN", "value_name": gtin if gtin is not None else isbn(n)},
             {"id": "LANGUAGE", "value_name": lang},
             {"id": "BOOK_TITLE", "value_name": title or f"Livro {n}"}]
    if genre:
        attrs.append({"id": "BOOK_GENRE", "value_id": genre, "value_name": "x"})
    if author:
        attrs.append({"id": "AUTHOR", "value_name": author})
    w = {"item_id": f"MLB9{n}", "price": price, "currency_id": cur_id, "condition": cond}
    if orig:
        w["original_price"] = orig
    return {"id": f"MLB{n}", "status": status, "name": f"Nome {n}", "attributes": attrs,
            "buy_box_winner": w}


class Resp(io.BytesIO):
    def __init__(self, body, ctype="application/json;charset=UTF-8"):
        super().__init__(json.dumps(body).encode())
        self.headers = {"Content-Type": ctype}


class FakeML:
    def __init__(self):
        self.urls = []
        self.hl = []               # content do /highlights geral
        self.trends = []           # keywords do /trends
        self.search = {}           # q -> [ml_product_id]
        self.products = {}
        self.items = {}
        self.item_detail = {}      # item_id -> corpo do /items/{id}
        self.ctype = "application/json;charset=UTF-8"

    def rank(self, *pids):
        self.hl = [{"id": p, "position": i, "type": "PRODUCT"} for i, p in enumerate(pids, 1)]

    def __call__(self, req, timeout=None):
        assert timeout and timeout > 0
        assert req.get_header("User-agent", "").startswith("ofertaslivros-coletor/")
        self.urls.append(req.full_url)
        u = urlsplit(req.full_url)
        q = parse_qs(u.query)
        if u.path == "/oauth/token":
            return Resp({"access_token": "APP_USR-sentinela"})
        if u.path == f"/highlights/MLB/category/{cur.CATEGORY}":
            if "attributeValue" in q:  # como na produção (probe 39258219518)
                raise HTTPError(req.full_url, 400, "x", {}, None)
            return Resp({"query_data": {}, "content": self.hl}, self.ctype)
        if u.path.startswith("/items/"):
            iid = u.path.split("/")[2]
            if iid not in self.item_detail:
                raise HTTPError(req.full_url, 404, "x", {}, None)
            return Resp(self.item_detail[iid])
        if u.path.endswith("/items"):
            pid = u.path.split("/")[2]
            if pid not in self.items:
                raise HTTPError(req.full_url, 404, "x", {}, None)
            return Resp(self.items[pid])
        if u.path == "/products/search":
            if "q" in q:
                assert q["domain_id"] == ["MLB-BOOKS"] and q["site_id"] == ["MLB"]
                ids = self.search.get(q["q"][0], [])
            else:
                ids = ["MLB1"]
            return Resp({"paging": {"total": len(ids)},
                         "results": [{"id": i, "name": "x"} for i in ids]})
        if u.path == f"/trends/MLB/{cur.CATEGORY}":
            return Resp([{"keyword": k, "url": "https://lista.mercadolivre.com.br/x"}
                         for k in self.trends], self.ctype)
        if u.path.startswith("/products/"):
            pid = u.path.rsplit("/", 1)[1]
            if pid not in self.products:
                raise HTTPError(req.full_url, 404, "x", {}, None)
            return Resp(self.products[pid])
        raise AssertionError(f"rota inesperada {u.path}")


@pytest.fixture
def env(tmp_path, monkeypatch):
    fake = FakeML()
    monkeypatch.setattr(c, "_urlopen", fake)
    monkeypatch.setattr(c.time, "sleep", lambda s: None)

    def no_socket(host, *a, **k):
        raise AssertionError(f"rede real chamada: {host}")
    monkeypatch.setattr(socket, "getaddrinfo", no_socket)
    monkeypatch.setenv("ML_CLIENT_ID", "id")
    monkeypatch.setenv("ML_CLIENT_SECRET", "segredo")
    monkeypatch.setenv("ML_AFFILIATE_ID", "teste-aff")
    cat = tmp_path / "catalog.json"
    cat.write_text(json.dumps({"_nota": "x", "books": [
        {"id": "ja-tenho", "isbn": isbn(999), "ml_product_id": "MLB999", "ml_url": ML_URL,
         "title": "Já tenho", "author": "A", "genre": "ficcao"}]}))
    seen = tmp_path / "curator_seen.json"
    md = tmp_path / "pr.md"

    links = tmp_path / "ml_links.tsv"

    def suggest(**kw):
        return cur.suggest(catalog=cat, seen_path=seen, summary_path=md, today=TODAY,
                           links_path=links, **kw)

    def books():
        return json.loads(cat.read_text())["books"]

    def add(*prods):
        for p in prods:
            fake.products[p["id"]] = p
        fake.rank(*(p["id"] for p in prods))
    return {"fake": fake, "cat": cat, "seen": seen, "md": md, "suggest": suggest, "links": links,
            "books": books, "add": add}


def new_ids(env):
    return [b["ml_product_id"] for b in env["books"]() if b.get("pendente")]


# ---- filtros (critérios 7 e 8) ----

def test_candidato_bom_vira_pendente_sem_link(env):
    env["add"](prod(1, orig=50))
    assert env["suggest"]() == 0
    b = env["books"]()[-1]
    assert b == {"id": "livro-1", "isbn": isbn(1), "genre": "manga",
                 "genre_source": "ml_book_genre", "title": "Livro 1",
                 "author": "Autora", "ml_product_id": "MLB1", "pendente": True}
    assert "ml_url" not in env["cat"].read_text().split("ja-tenho")[1].split("livro-1")[1]
    assert json.loads(env["seen"].read_text()) == {"MLB1": "2026-10-19"}
    assert c.read_catalog(env["cat"])[0]["id"] == "ja-tenho"  # pendente fora da coleta


@pytest.mark.parametrize("kw", [
    {"status": "inactive"}, {"lang": "Inglês"}, {"genre": AUTOAJUDA}, {"genre": None},
    {"cond": "used"}, {"cur_id": "USD"}, {"price": 14.99}, {"price": 400.01},
    {"author": None}, {"gtin": "9788500000000"},  # dígito errado
    {"gtin": f"{isbn(1)},{isbn(2)}"},  # dois ISBNs na ficha
])
def test_filtros_descartam(env, kw):
    env["add"](prod(1, **kw))
    assert env["suggest"]() == 0
    assert new_ids(env) == [] and not env["md"].exists()


def test_faixa_de_preco_inclusiva(env):
    env["add"](prod(1, price=15), prod(2, price=400))
    env["suggest"]()
    assert new_ids(env) == ["MLB1", "MLB2"]


def test_vencedor_usado_cai_para_o_menor_anuncio_novo(env):
    p = prod(1, cond="used")
    env["add"](p)
    env["fake"].items["MLB1"] = {"results": [
        {"item_id": "MLB71", "condition": "new", "currency_id": "BRL", "price": 55},
        {"item_id": "MLB72", "condition": "new", "currency_id": "BRL", "price": 45}]}
    env["suggest"]()
    assert new_ids(env) == ["MLB1"] and "45,00 |" in env["md"].read_text()


def test_sem_duplicado(env):
    env["seen"].write_text(json.dumps({"MLB2": "2026-09-01", "MLB3": "2026-01-01"}))
    env["add"](prod(999), prod(1, gtin=isbn(999)), prod(2), prod(3), prod(4, gtin=isbn(3)))
    env["suggest"]()
    # 999 no catálogo; 1 com ISBN do catálogo; 2 visto há < 180 dias; 3 visto há > 180
    # dias volta; 4 tem o mesmo ISBN do 3 e fica de fora
    assert new_ids(env) == ["MLB3"]
    assert json.loads(env["seen"].read_text()) == {"MLB2": "2026-09-01", "MLB3": "2026-10-19"}


def test_so_product_entra(env):
    env["fake"].products["MLB1"] = prod(1)
    env["fake"].hl = [{"id": "MLB1", "position": 1, "type": "PRODUCT"},
                            {"id": "MLBU123", "position": 2, "type": "USER_PRODUCT"},
                            {"id": "MLB5", "position": 3, "type": "ITEM"},
                            {"id": "MLB6/../x", "position": 4, "type": "PRODUCT"}]
    env["suggest"]()
    assert new_ids(env) == ["MLB1"]
    assert not any("MLB5" in u or "MLB6" in u for u in env["fake"].urls)


# ---- limites (critério 6) ----

def test_limite_por_nicho(env):
    env["add"](*(prod(n) for n in range(1, 21)))  # 20 mangás
    env["suggest"]()
    assert new_ids(env) == [f"MLB{n}" for n in range(1, 11)]


def test_limite_diario_e_ordem(env, monkeypatch):
    monkeypatch.setattr(cur, "DAY_MAX", 7)
    gens = [MANGA, NEG, LIT, BIO]
    env["add"](*(prod(n, genre=gens[n % 4]) for n in range(1, 21)))
    env["suggest"]()
    assert new_ids(env) == [f"MLB{n}" for n in range(1, 8)]


def _cands(n, genres=25):
    return [{"genre": f"g{i % genres}", "ml_product_id": f"MLB{i}", "pos": i, "off": 0}
            for i in range(1, n + 1)]


def test_volume_criterio_5():
    got = cur.select(_cands(200), 0)
    assert len(got) == 50 and max(Counter(g["genre"] for g in got).values()) <= 10
    assert len(cur.select(_cands(200, genres=3), 0)) == 30  # 10 por gênero
    assert len(cur.select(_cands(12), 0)) == 12              # meta, não força
    assert len(cur.select(_cands(200), cur.ACTIVE_MAX - 5)) == 5
    assert cur.select(_cands(200), cur.ACTIVE_MAX) == []


def test_desconto_nao_ordena_nem_filtra():
    """curator.md §15, item 5: sem desconto como critério; livro com 0% entra."""
    x = {"genre": "manga", "ml_product_id": "MLB1", "pos": 1}
    got = cur.select([{**x, "off": 0}, {**x, "ml_product_id": "MLB2", "off": 30},
                      {**x, "ml_product_id": "MLB0", "pos": 2, "off": 90}], 0)
    assert [g["ml_product_id"] for g in got] == ["MLB1", "MLB2", "MLB0"]


def test_teto_do_catalogo(env):
    doc = json.loads(env["cat"].read_text())
    doc["books"] += [{"id": f"p-{n}", "ml_product_id": f"MLB5{n:03d}", "pendente": True,
                      "title": "t", "author": "a", "genre": "ficcao"}
                     for n in range(cur.ACTIVE_MAX - 5)]
    env["cat"].write_text(json.dumps(doc))
    env["add"](*(prod(n, genre=[MANGA, NEG][n % 2]) for n in range(1, 21)))
    env["suggest"]()
    assert len(env["books"]()) == cur.ACTIVE_MAX


def test_catalogo_no_teto_nem_chama_a_rede(env):
    doc = json.loads(env["cat"].read_text())
    doc["books"] += [{"id": f"p-{n}", "ml_product_id": f"MLB5{n:03d}", "pendente": True,
                      "title": "t", "author": "a", "genre": "ficcao"}
                     for n in range(cur.ACTIVE_MAX - 1)]
    env["cat"].write_text(json.dumps(doc))
    assert env["suggest"]() == 0 and env["fake"].urls == []


def test_catalogo_invalido_nao_comeca(env):
    env["cat"].write_text(json.dumps({"books": [{"id": "x", "pendente": True}]}))
    with pytest.raises(c.Invalid):
        env["suggest"]()
    assert env["fake"].urls == []


# ---- nunca escreve link, nunca Amazon, nunca HTML (critérios 1 a 3) ----

def test_so_api_do_ml_e_nenhum_html(env):
    env["add"](*(prod(n, genre=[MANGA, NEG, LIT][n % 3]) for n in range(1, 12)))
    env["suggest"]()
    cur.probe()
    assert {urlsplit(u).hostname for u in env["fake"].urls} == {"api.mercadolibre.com"}
    src = (ROOT / "collector" / "curator.py").read_text()
    # Amazon só como texto montado para a TSV (critério 1): nas duas constantes, nunca chamado
    assert [ln.split("=")[0].strip() for ln in src.splitlines() if "amazon." in ln.lower()
            and not ln.lstrip().startswith("#")] == ["AMAZON_DP", "AMAZON_SEARCH"]
    for bad in ("html.parser", "bs4", "BeautifulSoup", "playwright", "selenium"):
        assert bad not in src
    for b in env["books"]()[1:]:
        assert "ml_url" not in b and "asin" not in b


def test_resposta_html_aborta(env):
    env["add"](prod(1))
    env["fake"].ctype = "text/html; charset=utf-8"
    assert env["suggest"]() == 1
    assert new_ids(env) == [] and "/products/MLB1" not in " ".join(env["fake"].urls)


# ---- corpo do PR (critério 11) ----

def test_markdown_escapado(env):
    evil = "[clique](https://evil.example/x) <img src=x> | `rm` @elias \\ fim"
    env["add"](prod(1, title=evil, author="<b>@x</b>"))
    env["suggest"]()
    md = env["md"].read_text()
    row = next(ln for ln in md.splitlines() if ln.startswith("| 1 |"))
    cells = row.split(" | ")
    assert len(row.split("|")) == 12  # nenhum | extra quebrou a tabela
    for cell in cells[1:3]:
        assert re.fullmatch(r"`[^`]+`", cell)
        assert not set(cell[1:-1]) & set("[]()<>|`@\\")
    # fora dos code spans, toda URL é a montada pelo código
    outside = re.sub(r"`[^`\n]*`", "", md)
    assert re.findall(r"https?://\S+", outside) == ["https://www.mercadolivre.com.br/p/MLB1"] * 2
    assert "evil" not in outside and len(md) <= cur.SUMMARY_MAX
    # o catálogo guarda o título original (o build escapa no HTML)
    assert env["books"]()[-1]["title"] == evil


def test_slug_e_asin_provavel():
    taken = {"livro"}
    assert cur.slug("Mangá: Ação & Cia!", taken) == "manga-acao-cia"
    assert cur.slug("Mangá ação cia", taken) == "manga-acao-cia-2"
    assert cur.slug("???", taken) == "livro-2"
    s = cur.slug("x" * 200, taken)
    assert len(s) <= c.ID_MAX and c.ID_RE.fullmatch(s)
    assert cur.asin_provavel("9780306406157") == "0306406152"
    assert cur.asin_provavel("9791234567896") == "-"


# ---- probe e segredos (critérios 12 e 13) ----

def test_probe_status_e_contagens_sem_conteudo(env, capsys):
    env["add"](prod(1), prod(2))
    assert cur.probe() == 0
    out = capsys.readouterr().out
    assert "highlights geral: /highlights/MLB/category/MLB437616 -> 200" in out
    assert "content=2 tipos=PRODUCT:2" in out
    assert "BOOK_GENRE=" not in out
    assert "products/search isbn: /products/search -> 200" in out and "total=1" in out
    assert "trends: /trends/MLB/MLB437616 -> 200" in out
    assert "Livro" not in out and "lista.mercadolivre" not in out and "MLB1" not in out


def test_token_fora_do_log(env, capsys):
    env["add"](prod(1))
    cur.probe()
    env["suggest"]()
    out = capsys.readouterr()
    for s in ("sentinela", "segredo"):
        assert s not in out.out and s not in out.err
        assert s not in env["md"].read_text()


def test_sem_credenciais_falha_sem_rede(env, monkeypatch):
    monkeypatch.delenv("ML_CLIENT_SECRET")
    assert env["suggest"]() == 1 and cur.probe() == 1
    assert env["fake"].urls == []


# ---- extração de ISBN (execução 39258304023: 16 de 16 descartados por "isbn") ----

def isbn10(n):
    """ISBN-10 equivalente ao isbn(n) (mesmos 9 dígitos depois do 978)."""
    d = isbn(n)[3:12]
    ck = (11 - sum((10 - i) * int(x) for i, x in enumerate(d)) % 11) % 11
    return d + ("X" if ck == 10 else str(ck))


def hyphen(s):
    return f"{s[:3]}-{s[3:5]}-{s[5:9]}-{s[9:12]}-{s[12]}"


def test_isbn10_vira_isbn13_com_digito_certo():
    assert c.isbn10_to_13("8535914846") == "9788535914849"
    assert c.isbn10_to_13("080442957X") == "9780804429573"  # X no verificador
    assert c.isbn10_to_13("8535914847") is None             # checksum do ISBN-10 errado
    assert c.isbn10_to_13("853591484X") is None
    for n in (1, 7, 123, 4567):
        assert c.isbn10_to_13(isbn10(n)) == isbn(n) and c.isbn_ok(isbn(n))


@pytest.mark.parametrize("attr", [
    {"id": "GTIN", "value_name": isbn10(1)},                          # ISBN-10
    {"id": "GTIN", "value_name": hyphen(isbn(1))},                    # hífen
    {"id": "GTIN", "value_name": "978 85 0000001 " + isbn(1)[-1]},    # espaço
    {"id": "GTIN", "value_name": f"ISBN-13: {hyphen(isbn(1))}"},
    {"id": "GTIN", "value_name": f"{isbn(1)}, {isbn10(1)}"},          # múltiplo, mesmo livro
    {"id": "GTIN", "value_name": f"7891234567895; {hyphen(isbn(1))}"},  # EAN + ISBN
    {"id": "ISBN", "value_name": isbn(1)},                            # outro id de atributo
    {"id": "GTIN", "value_name": None, "values": [{"id": None, "name": isbn(1)}]},
])
def test_formatos_de_isbn_aceitos(env, attr):
    p = prod(1)
    p["attributes"] = [attr] + [a for a in p["attributes"] if a["id"] != "GTIN"]
    env["add"](p)
    assert env["suggest"]() == 0
    assert env["books"]()[-1]["isbn"] == isbn(1)


@pytest.mark.parametrize("gtin,why", [
    (isbn(1)[:-1] + str((int(isbn(1)[-1]) + 1) % 10), "isbn_invalido"),  # checksum ISBN-13
    (isbn10(1)[:-1] + ("0" if isbn10(1)[-1] != "0" else "1"), "isbn_invalido"),  # ISBN-10
    ("7891234567895", "isbn_invalido"),         # EAN que não é livro
    (f"{isbn(1)},{hyphen(isbn(2))}", "isbn_multiplo"),
])
def test_isbn_invalido_descarta_com_motivo(env, capsys, gtin, why):
    env["add"](prod(1, gtin=gtin))
    assert env["suggest"]() == 0
    assert new_ids(env) == []
    assert f"descartes: 1 {why}" in capsys.readouterr().out


# ---- ISBN opcional e prova de livro (probe 39259800320: a ficha não traz GTIN) ----

def no_gtin(n, **kw):
    p = prod(n, **kw)
    p["attributes"] = [a for a in p["attributes"] if a["id"] != "GTIN"]
    return p


def test_livro_sem_isbn_passa(env):
    env["add"](no_gtin(1, orig=50))
    assert env["suggest"]() == 0
    assert env["books"]()[-1] == {"id": "livro-1", "genre": "manga",
                                  "genre_source": "ml_book_genre", "title": "Livro 1",
                                  "author": "Autora", "ml_product_id": "MLB1",
                                  "pendente": True}
    row = next(ln for ln in env["md"].read_text().splitlines() if ln.startswith("| 1 |"))
    assert row.split(" | ")[7:9] == ["-", "-"]  # ISBN e ASIN provável


def test_dois_sem_isbn_nao_viram_duplicado(env):
    env["add"](no_gtin(1), no_gtin(2))
    env["suggest"]()
    assert new_ids(env) == ["MLB1", "MLB2"]


def test_papelaria_e_nao_livro(env, capsys):
    papel = {"id": "MLB1", "status": "active", "name": "Caderno",
             "attributes": [{"id": "BRAND", "value_name": "Tilibra"},
                            {"id": "COLOR", "value_name": "Azul"},
                            {"id": "PAPER_TYPE", "value_name": "Pautado"},
                            {"id": "GRAMMAGE", "value_name": "90 g"},
                            {"id": "GTIN", "value_name": "7891234567895"}],
             "buy_box_winner": {"item_id": "MLB91", "price": 40, "currency_id": "BRL",
                                "condition": "new"}}
    env["add"](papel, no_gtin(2, title=" ", author="A"), no_gtin(3, author=" "))
    assert env["suggest"]() == 0
    assert new_ids(env) == [] and not env["md"].exists()
    assert "descartes: 3 nao_livro" in capsys.readouterr().out


def test_idioma_ausente_e_descarte(env, capsys):
    p = no_gtin(1)
    p["attributes"] = [a for a in p["attributes"] if a["id"] != "LANGUAGE"]
    env["add"](p)
    env["suggest"]()
    assert new_ids(env) == [] and "descartes: 1 idioma" in capsys.readouterr().out


def test_motivos_no_log(env, capsys):
    env["add"](no_gtin(1), prod(2, gtin="9788500000000"), prod(3, lang="Inglês"),
               prod(4, genre=AUTOAJUDA), prod(5, author=None))
    env["suggest"]()
    assert new_ids(env) == ["MLB1"]
    assert ("descartes: 1 idioma, 1 isbn_invalido, 1 nao_livro, 1 nicho"
            in capsys.readouterr().out)


def test_isbn_vem_do_products_quando_o_highlights_nao_traz_atributos(env):
    env["add"](prod(1, gtin=hyphen(isbn(1))))
    assert all("attributes" not in it for it in env["fake"].hl)
    env["suggest"]()
    assert "https://api.mercadolibre.com/products/MLB1" in env["fake"].urls
    assert new_ids(env) == ["MLB1"]


def test_gtin_isbn10_nao_conta_como_divergente_no_coletor():
    assert c.product_gtins({"attributes": [{"id": "GTIN", "value_name": "8535914846"}]}) \
        == {"9788535914849"}


# ---- fontes: highlights geral + trends, nicho só pela ficha ----

def test_trends_como_segunda_fonte(env, capsys):
    env["add"](prod(1))
    env["fake"].products["MLB2"] = prod(2, genre=NEG)
    env["fake"].trends = ["termo a", "termo b"]
    env["fake"].search = {"termo a": ["MLB1", "MLB2"], "termo b": ["MLB2"]}
    env["suggest"]()
    assert new_ids(env) == ["MLB1", "MLB2"]
    assert f"| {cur.TREND_POS + 2} |" in env["md"].read_text()  # MLB2: 2º do 1º termo
    assert not any("attributeValue" in u or "lista.mercadolivre" in u
                   for u in env["fake"].urls)
    out = capsys.readouterr().out
    assert "/highlights: 1 produtos, 1 novos" in out and "/trends: 3 produtos, 2 novos" in out
    assert "termo" not in out


def test_highlights_fora_trends_basta(env):
    env["fake"].products["MLB2"] = prod(2)
    env["fake"].ctype = "text/html"  # /highlights e /trends quebram juntos no fake
    assert env["suggest"]() == 1
    env["fake"].ctype = "application/json"
    env["fake"].trends, env["fake"].search = ["t"], {"t": ["MLB2"]}
    assert env["suggest"]() == 0 and new_ids(env) == ["MLB2"]


def test_nicho_so_pela_ficha(env, capsys):
    env["add"](prod(1, genre=None), prod(2, genre=LIT))
    env["suggest"]()
    assert [b["genre"] for b in env["books"]()[1:]] == ["ficcao"]
    assert "1 nicho" in capsys.readouterr().out


def test_orcamento_de_fichas(env, monkeypatch, capsys):
    monkeypatch.setattr(cur, "LOOKUP_MAX", 3)
    env["add"](*(prod(n, genre=[MANGA, NEG][n % 2]) for n in range(1, 6)))
    env["suggest"]()
    assert sum("/products/MLB" in u and "/items" not in u for u in env["fake"].urls) == 3
    assert "2 adiado" in capsys.readouterr().out


def test_probe_formato_dos_atributos_sem_valor(env, capsys):
    p = prod(1, gtin=f"{hyphen(isbn(1))}, {isbn10(1)}", title="Titulo Secreto",
             author="Autora Secreta")
    env["add"](p, prod(2), prod(3), prod(4))
    env["fake"].trends = ["termo secreto"]
    assert cur.probe() == 0
    out = capsys.readouterr().out
    assert "GTIN: value_name len=" in out and "hifen=sim" in out and "valores=2" in out
    assert "atributos=AUTHOR,BOOK_GENRE,BOOK_TITLE,GTIN,LANGUAGE" in out
    assert "isbn: ok" in out
    assert out.count("/products -> 200") == 3  # só os 3 primeiros PRODUCT
    assert "products/search q (1º termo do trends): /products/search -> 200" in out
    for leak in ("Secret", "secreto", isbn(1), isbn(1)[3:8], isbn10(1), "MLB91", "sentinela"):
        assert leak not in out


# ---- B5 (critério 15) ----

def test_b5_exclui_por_titulo_forte_e_subgenero(env, capsys):
    p3 = prod(3)
    p3["attributes"].append({"id": "BOOK_SUBGENRES", "values": [{"id": "76494427", "name": "x"}]})
    env["add"](prod(1, title="Bíblia Sagrada"), prod(2, title="VADE MECUM 2026"), p3,
               prod(4, title="Apostilas de Inglês"), prod(5, title="Bibliografia comentada"))
    env["suggest"]()
    # 1 a 4 saem (plural conta); "bibliografia" não é a palavra inteira
    assert new_ids(env) == ["MLB5"]
    assert "4 b5" in capsys.readouterr().out


def test_b5_fraca_vai_para_revisao(env, capsys):
    env["add"](prod(1, title="Guia do Concurso Público"), prod(2),
               prod(3, title="Concurso", lang="Inglês"))  # já cai no idioma: não vai à revisão
    env["suggest"]()
    assert new_ids(env) == ["MLB2"]
    out = capsys.readouterr().out
    assert "1 revisar_b5" in out and "1 idioma" in out and "revisar_b5 (catalog-curator confere): MLB1" in out
    assert "Concurso" not in out  # título da API fora do log
    assert "https://www.mercadolivre.com.br/p/MLB1" in env["md"].read_text()
    assert "MLB1" not in json.loads(env["seen"].read_text())  # volta se a lista mudar


def test_so_revisar_b5_ainda_grava_o_resumo(env):
    env["add"](prod(1, title="Edital comentado"))
    assert env["suggest"]() == 0 and new_ids(env) == []
    assert "https://www.mercadolivre.com.br/p/MLB1" in env["md"].read_text()


# ---- ml_links.tsv (§10.4, fila) ----

def test_ml_links_tsv_fila_e_preserva_colado(env):
    env["add"](prod(1, title="=SOMA(1;2) Livro"), prod(2))
    env["suggest"]()
    lines = env["links"].read_text().splitlines()
    assert lines[0] == "\t".join(cur.ML_LINKS_COLS)
    rows = [ln.split("\t") for ln in lines[1:]]
    assert [r[1] for r in rows] == ["MLB1", "MLB2"] and all(len(r) == 5 for r in rows)
    assert rows[0][2] == "SOMA(1;2) Livro" and rows[0][3].endswith("/p/MLB1")
    assert rows[0][4] == ""
    # o Elias cola o link na linha do MLB2; a próxima execução preserva
    rows[1][4] = ML_URL
    env["links"].write_text("\n".join(["\t".join(cur.ML_LINKS_COLS)]
                                      + ["\t".join(r) for r in rows]) + "\n")
    env["add"](prod(3))
    env["suggest"]()
    rows = [ln.split("\t") for ln in env["links"].read_text().splitlines()[1:]]
    assert [(r[1], r[4]) for r in rows] == [("MLB1", ""), ("MLB2", ML_URL), ("MLB3", "")]
    assert "ja-tenho" not in env["links"].read_text()  # já tem ml_url


def test_probe_procura_isbn_no_anuncio_dos_livros_sem_isbn(env, capsys, monkeypatch):
    monkeypatch.setattr(c, "CATALOG", env["cat"])
    monkeypatch.delenv("ML_AFFILIATE_ID")  # como no job do probe: sem a variável
    doc = json.loads(env["cat"].read_text())
    doc["books"] += [{"id": "sem-isbn", "genre": "ficcao", "title": "T", "author": "A",
                      "ml_product_id": "MLB50", "ml_url": ML_URL.replace("ref=X", "ref=Y")},
                     {"id": "sem-nada", "genre": "ficcao", "title": "U", "author": "A",
                      "ml_product_id": "MLB60", "ml_url": ML_URL.replace("ref=X", "ref=Z")}]
    env["cat"].write_text(json.dumps(doc))
    p50 = prod(50)
    p50["attributes"] = [a for a in p50["attributes"] if a["id"] != "GTIN"]
    env["fake"].products.update({"MLB50": p50, "MLB60": {**p50, "buy_box_winner": None}})
    env["fake"].item_detail["MLB950"] = {"attributes": [{"id": "GTIN", "value_name": isbn(50)}]}
    assert cur.probe() == 0
    out = capsys.readouterr().out
    assert f"isbn sem-isbn: /products -> 200 /items -> 200 isbn={isbn(50)}" in out
    assert "isbn sem-nada: /products -> 200 /items -> - isbn=ausente" in out
    assert "isbn ja-tenho" not in out  # já tem isbn
    assert {urlsplit(u).hostname for u in env["fake"].urls} == {"api.mercadolibre.com"}


def test_probe_isbn_catalogo_ilegivel_nao_derruba(env, capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(c, "CATALOG", tmp_path / "nao-existe.json")
    env["add"](prod(1))
    assert cur.probe() == 0
    assert "isbn: catálogo ilegível (FileNotFoundError)" in capsys.readouterr().out

# ---- retirada (critério 14; §10.8, item 6) ----

def _st(pub="2026-08-01", anuncio="2026-10-19", oferta=None):
    return {"publicado": pub, "ultimo_anuncio": anuncio, "ultima_oferta": oferta}


def test_retirada_mista():
    auto = {"genre_source": "ml_book_genre"}
    books = [{"id": "manual-sem-oferta"}, {"id": "auto-sem-oferta", **auto},
             {"id": "auto-oferta-recente", **auto}, {"id": "auto-novo", **auto},
             {"id": "manual-sem-anuncio"}, {"id": "auto-30-dias", **auto},
             {"id": "pendente", "pendente": True, **auto}, {"id": "sem-estado", **auto}]
    st = {"curadoria_ok": "2026-10-19", "curadoria": {
        "manual-sem-oferta": _st(), "auto-sem-oferta": _st(oferta="2026-09-18"),
        "auto-oferta-recente": _st(oferta="2026-09-25"), "auto-novo": _st(pub="2026-10-01"),
        "manual-sem-anuncio": _st(anuncio="2026-09-18"), "auto-30-dias": _st(pub="2026-09-19"),
        "pendente": _st()}}
    got = [(b["id"], why) for b, why in cur.retire(books, st, TODAY)]
    assert got == [("auto-sem-oferta", "sem_oferta"), ("manual-sem-anuncio", "sem_anuncio")]
    # data futura = relógio recomeçado (o coletor zera na próxima coleta): não sai hoje
    st["curadoria"]["manual-sem-anuncio"]["ultima_oferta"] = "2099-01-01"
    got = [(b["id"], why) for b, why in cur.retire(books, st, TODAY)]
    assert got == [("auto-sem-oferta", "sem_oferta")]


def test_retirada_nao_roda_com_dado_parado_ou_em_massa(capsys):
    books = [{"id": f"l{n}"} for n in range(30)]
    cu = {b["id"]: _st(anuncio="2026-09-01") for b in books}
    cu["l0"] = _st()  # livro novo com data de hoje não conta como coleta ok
    assert cur.retire(books, {"curadoria": cu}, TODAY) == []
    assert cur.retire(books, {"curadoria": cu, "curadoria_ok": "2026-10-16"}, TODAY) == []
    assert cur.retire(books, {"curadoria": cu, "curadoria_ok": "2099-01-01"}, TODAY) == []
    ok = {"curadoria": cu, "curadoria_ok": "2026-10-18"}
    assert cur.retire(books, ok, TODAY) == []                       # 29 > RETIRE_MAX
    assert len(cur.retire(books[:21], ok, TODAY)) == 20
    assert cur.retire(books[:21], ok, TODAY, recent=81) == []       # 81 + 20 > 100 na semana
    assert cur.retire(books[1:3], ok, TODAY) == []                  # esvaziaria o catálogo
    out = capsys.readouterr().out
    assert "retirada pulada" in out and "tetos 25/100" in out


def test_retirada_no_pr_e_id_nunca_volta(env, tmp_path):
    doc = json.loads(env["cat"].read_text())
    doc["books"].append({"id": "livro-1", "genre": "manga", "genre_source": "ml_book_genre",
                         "title": "Livro 1", "author": "A", "ml_product_id": "MLB777",
                         "ml_url": ML_URL.replace("ref=X", "ref=Y")})
    env["cat"].write_text(json.dumps(doc))
    hist = tmp_path / "hist"
    hist.mkdir()
    (hist / "state.json").write_text(json.dumps({"curadoria_ok": "2026-10-19", "curadoria": {
        "ja-tenho": _st(), "livro-1": _st(oferta="2026-09-01")}}))
    env["add"](prod(1))  # mesmo título: o slug não pode reaproveitar livro-1
    assert env["suggest"](history=hist) == 0
    d = json.loads(env["cat"].read_text())
    assert [b["id"] for b in d["books"]] == ["ja-tenho", "livro-1-2"]
    assert d["retirados"] == {"livro-1": "2026-10-19"}
    assert json.loads(env["seen"].read_text())["MLB777"] == "2026-10-19"
    md = env["md"].read_text()
    assert "1 retirados" in md and "`livro-1`" in md and "PR sensível" in md
    # gate 9 também à mão: livro com id retirado não passa no load_catalog
    d["books"].append({**d["books"][0], "id": "livro-1", "isbn": isbn(5), "ml_product_id": "MLB5",
                       "ml_url": ML_URL.replace("ref=X", "ref=Z")})
    with pytest.raises(c.Invalid, match="retirado"):
        c.load_catalog(d)


def test_so_retirada_ja_grava_o_pr(env, tmp_path):
    doc = json.loads(env["cat"].read_text())
    doc["books"][0]["genre_source"] = "ml_book_genre"
    doc["books"].append({"id": "outro", "genre": "ficcao", "title": "O", "author": "A",
                         "asin": "B0ABCDEFGH"})
    env["cat"].write_text(json.dumps(doc))
    hist = tmp_path / "hist"
    hist.mkdir()
    (hist / "state.json").write_text(json.dumps({"curadoria_ok": "2026-10-19", "curadoria": {
        "ja-tenho": _st(oferta="2026-09-01"), "outro": _st()}}))
    assert env["suggest"](history=hist) == 0  # nenhum candidato na descoberta
    assert [b["id"] for b in env["books"]()] == ["outro"]


# ---- fila manual da Amazon (§10.5; critério 11) ----

def _pub(n, **kw):
    return {"id": f"pub-{n}", "genre": "ficcao", "title": f"Título {n}", "author": "Fulana",
            "ml_product_id": f"MLB{n}", "ml_url": ML_URL.replace("ref=X", f"ref=R{n}"), **kw}


def test_amazon_todo(env, tmp_path):
    import os
    books = [_pub(1, isbn=isbn(1)), _pub(2), _pub(3, isbn="9791234567896"),
             {**_pub(4, isbn=isbn(4)), "asin": "B0ABCDEFGH"}] + [_pub(n) for n in range(5, 16)]
    env["cat"].write_text(json.dumps({"books": books}))
    p1 = prod(1)
    p1["attributes"] += [{"id": "BOOK_PUBLISHER", "value_name": "Editora\tX"},
                         {"id": "BOOK_EDITION", "value_name": "2ª"}]
    for n in range(2, 16):
        env["fake"].products[f"MLB{n}"] = prod(n)
    env["fake"].products["MLB1"] = p1
    tsv = tmp_path / "amazon_links.tsv"
    assert cur.amazon_todo(env["cat"], tsv, TODAY) == 0
    lines = tsv.read_text().splitlines()
    assert lines[0].split("\t") == cur.AMAZON_LINKS_COLS
    rows = [ln.split("\t") for ln in lines[1:]]
    assert len(rows) == cur.AMAZON_QUEUE_DAY and all(len(r) == 9 for r in rows)
    assert "pub-4" not in tsv.read_text()  # já tem asin
    r1, r2, r3 = rows[:3]
    assert r1[4] == "Editora X / 2ª" and r1[6] == f"https://www.amazon.com.br/dp/{r1[5]}"
    assert r2[5] == "-" and r2[6] == "https://www.amazon.com.br/s?k=T%C3%ADtulo+2+Fulana"
    assert r3[6] == "https://www.amazon.com.br/s?k=9791234567896"
    assert not any("amazon" in u for u in env["fake"].urls)  # regra 1: só texto
    # mesmo dia: nada novo; o que o Elias preencheu fica
    rows[0][7] = isbn(1)
    tsv.write_text("\n".join("\t".join(r) for r in [cur.AMAZON_LINKS_COLS] + rows) + "\n")
    cur.amazon_todo(env["cat"], tsv, date.fromtimestamp(tsv.stat().st_mtime))
    assert len(tsv.read_text().splitlines()) == 11 and isbn(1) in tsv.read_text()
    # dia seguinte: entram as que faltam (4 restantes, abaixo do teto)
    os.utime(tsv, (0, 0))
    cur.amazon_todo(env["cat"], tsv, TODAY)
    assert len(tsv.read_text().splitlines()) == 1 + 14
