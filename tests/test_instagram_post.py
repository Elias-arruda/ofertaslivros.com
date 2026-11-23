"""Post diário no Instagram (instagram_post.py). Rede e Chrome sempre mockados."""
import io
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402
import instagram_post as ig  # noqa: E402

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=build.BRT)


def of(oid, price=60, seal=None, oferta=True, velho=False, checked=NOW):
    return {"id": oid, "price_cents": price, "list_price_cents": 100, "seal": seal, "oferta": oferta,
            "velho": velho, "checked_at": checked}


def log(*rows):
    return [{"offer_id": oid, "at": at, "price_cents": 1} for oid, at in rows]


def pid(offers, rows=(), now=NOW):
    o = ig.pick(offers, list(rows), now)
    return o and o["id"]


def test_janela_10h_20h():
    assert pid([of("a")], now=NOW.replace(hour=9, minute=59)) is None
    assert pid([of("a")], now=NOW.replace(hour=20)) is None
    assert pid([of("a")], now=NOW.replace(hour=10)) == "a"


def test_um_por_dia_brt():
    assert pid([of("a")], log(("x", NOW.replace(hour=10)))) is None
    assert pid([of("a")], log(("x", NOW - timedelta(days=1)))) == "a"


def test_maior_desconto_so_oferta_no_prazo():
    offers = [of("d10", price=90), of("d40", price=60), of("selo", price=95, seal="90d"),
              of("velha", price=10, velho=True), of("sem", price=5, oferta=False)]
    assert pid(offers) == "d40"


def test_nao_repete_livro_em_14_dias():
    a = [of("a"), of("b", price=90)]
    assert pid(a, log(("a", NOW - timedelta(days=13, hours=23)))) == "b"
    assert pid(a, log(("a", NOW - timedelta(days=14)))) == "a"


def test_nome_amarra_livro_preco_e_horario():
    assert ig.nome(of("torto-arado", price=4290)) == "torto-arado-4290-202610211200.jpg"
    with pytest.raises(build.Invalid):
        ig.nome(of("../x"))


OFERTA = {**of("torto-arado", price=4290), "list_price_cents": 7490, "title": "Torto @Arado #1 <b>",
          "author": "Itamar", "store": "amazon", "genre": "literatura-brasileira", "image_url": None,
          "since": date(2026, 10, 1)}


def test_legenda_texto_puro_sem_link_nem_mencao():
    t = ig.caption({**OFERTA, "seal": "90d"})
    assert t.splitlines()[:5] == ["Menor preço em 90 dias", "Torto Arado 1 <b>, de Itamar",
                                  f"{build.brl(4290)} (de {build.brl(7490)}, -42%) na Amazon",
                                  "Conferido às 12h00 de 21/10, o preço pode mudar.", "Link na bio."]
    assert "O preço final é o da loja." in t and "ganhamos com compras qualificadas" in t
    assert "http" not in t and "@" not in t
    assert t.splitlines()[-1] == "#livros #ofertasdelivros #literaturabrasileira"


def test_svg_escapa_dado_coletado_e_tem_o_rodape():
    s = ig.svg_post({**OFERTA, "seal": "since"}, None)
    assert "<b>" not in s and "&lt;b&gt;" in s
    assert build.brl(4290) in s and build.brl(7490) in s and "−42%" in s and "na Amazon" in s
    assert "Menor preço desde 01/10" in s and ">conferido<" in s and ">21/10<" in s and ">às 12h00<" in s
    assert "O preço final é o da loja." in s and "<image" not in s     # sem capa: placeholder do nicho
    assert "http://" not in s.replace('xmlns="http://www.w3.org/2000/svg"', "")  # nada remoto no SVG
    assert "<image href=\"data:image/jpeg;base64,AA\"" in ig.svg_post(OFERTA, "data:image/jpeg;base64,AA")


def test_titulo_longo_cabe_em_2_linhas():
    lines, size = ig.quebra("A guerra dos tronos: As crônicas de gelo e fogo, volume 1")
    assert len(lines) == 2 and size == 70 and lines[1].endswith("…")
    assert ig.quebra("Torto Arado") == (["Torto Arado"], 88)


def test_capa_local_e_ml_sem_outros_hosts(monkeypatch):
    isbn = next(build.STATIC.glob("capas/*.jpg")).stem
    monkeypatch.setattr(ig.urllib.request, "build_opener", lambda *h: pytest.fail("foi à rede"))
    assert ig.capa({**OFERTA, "image_url": f"/capas/{isbn}.jpg"}).startswith("data:image/jpeg;base64,")
    assert ig.capa({**OFERTA, "image_url": "/capas/../../.env"}) is None
    assert ig.capa({**OFERTA, "image_url": "https://evil.example/x.jpg"}) is None

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass
    opener = lambda body: lambda *h: type("O", (), {"open": lambda self, req, timeout: R(body)})()  # noqa: E731
    monkeypatch.setattr(ig.urllib.request, "build_opener", opener(b"\x89PNG..."))
    assert ig.capa({**OFERTA, "image_url": "https://http2.mlstatic.com/D_x.jpg"}).startswith("data:image/png;")
    monkeypatch.setattr(ig.urllib.request, "build_opener", opener(b"<html>"))
    assert ig.capa({**OFERTA, "image_url": "https://http2.mlstatic.com/D_x.jpg"}) is None


def test_render_so_publica_jpeg_completo(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROME", "/bin/chrome")
    got = {}

    def chrome(cmd, **kw):
        got["cmd"] = cmd
        Path(next(a for a in cmd if a.startswith("--screenshot=")).split("=", 1)[1]).write_bytes(got["out"])
    monkeypatch.setattr(ig.subprocess, "run", chrome)
    got["out"] = b"\xff\xd8\xff\xe0jpeg"
    out = ig.render(OFERTA, tmp_path / "ig")
    assert out == tmp_path / "ig" / "torto-arado-4290-202610211200.jpg" and out.read_bytes() == got["out"]
    assert "--host-resolver-rules=MAP * ~NOTFOUND" in got["cmd"]                # sem rede no render
    got["out"] = b"\x89PNG"
    out.unlink()
    with pytest.raises(RuntimeError):
        ig.render(OFERTA, tmp_path / "ig")
    assert list((tmp_path / "ig").iterdir()) == []


AMZ = {"store": "amazon", "asin": "B0ABCDEFGH", "price_cents": 4290, "list_price_cents": 7490,
       "lowest_90d_cents": 4290, "checked_at": "2026-10-21T11:00:00-03:00"}


@pytest.fixture
def run(tmp_path, monkeypatch):
    doc = {"version": 2, "offers": [
        {"id": "torto-arado", "genre": "literatura-brasileira", "title": "Torto Arado", "author": "Itamar",
         "stores": [AMZ]},
        {"id": "menor", "genre": "ficcao", "title": "Menor", "author": "A", "stores": [{**AMZ, "price_cents": 6000}]},
    ]}
    (tmp_path / "offers.json").write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv("INSTAGRAM_TOKEN", "IGAAsegredo")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "17841400000000000")
    calls, st = [], {"live": True, "publish_error": False, "status": "FINISHED"}

    def graph(token, path, data=None):
        assert token == "IGAAsegredo"
        calls.append((path, data, run.csv.exists() and run.csv.read_text()))
        if path.endswith("/media"):
            return {"id": "1789"}
        if path.startswith("1789?"):
            return {"status_code": st["status"]}
        if st["publish_error"]:
            raise RuntimeError("Instagram media_publish: 500")
        return {"id": "999"}
    monkeypatch.setattr(ig, "graph", graph)
    monkeypatch.setattr(ig, "no_ar", lambda url: calls.append(("HEAD", url, None)) or st["live"])
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)

    def go(now=NOW):
        ig.main(tmp_path / "offers.json", run.csv, now=now)
        return calls
    run = go
    go.csv, go.st = tmp_path / "instagram_posts.csv", st
    return go


def test_publica_container_espera_e_publica_uma_vez_por_dia(run):
    calls = run()
    url = "https://ofertaslivros.com.br/ig/torto-arado-4290-202610211100.jpg"
    assert [c[0] for c in calls] == ["HEAD", "17841400000000000/media", "1789?fields=status_code",
                                     "17841400000000000/media_publish"]
    assert calls[0][1] == url and calls[1][1]["image_url"] == url
    assert calls[1][1]["caption"].startswith("Torto Arado, de Itamar")
    assert calls[3][1] == {"creation_id": "1789"}
    assert ",ig,torto-arado,amazon,4290" in calls[3][2]                     # gravado antes do publish
    assert len(run()) == 4                                                   # 2ª execução no dia: nada


def test_publish_que_falha_nao_posta_de_novo(run):
    run.st["publish_error"] = True
    with pytest.raises(RuntimeError):
        run()
    run.st["publish_error"] = False
    assert len(run()) == 4 and ",ig,torto-arado," in run.csv.read_text()


def test_container_com_erro_nao_grava(run):
    run.st["status"] = "ERROR"
    with pytest.raises(RuntimeError):
        run()
    assert not run.csv.exists()


def test_imagem_fora_do_site_nao_posta(run):
    run.st["live"] = False
    assert [c[0] for c in run()] == ["HEAD"] and not run.csv.exists()


def test_sem_token_ou_user_avisa_e_nao_posta(run, monkeypatch, capsys):
    monkeypatch.delenv("INSTAGRAM_TOKEN")
    assert run() == [] and "::warning::" in capsys.readouterr().out
    monkeypatch.setenv("INSTAGRAM_TOKEN", "x")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "")
    assert run() == []


@pytest.mark.parametrize("bad", ["@conta", "123/../me", "12a"])
def test_user_id_invalido(run, monkeypatch, bad):
    monkeypatch.setenv("INSTAGRAM_USER_ID", bad)
    with pytest.raises(build.Invalid):
        run()


def test_render_no_deploy_respeita_o_log(run, monkeypatch, tmp_path):
    feitos = []
    monkeypatch.setattr(ig, "render", lambda o, d: feitos.append(o["id"]) or d / ig.nome(o))
    ig.main_render(tmp_path / "offers.json", tmp_path / "nao-existe.csv", tmp_path / "ig", now=NOW)
    assert feitos == ["torto-arado"]
    run()
    ig.main_render(tmp_path / "offers.json", run.csv, tmp_path / "ig", now=NOW)
    assert feitos == ["torto-arado"]                                         # já postou hoje: não gera


def test_graph_token_so_no_header_e_fora_do_erro(monkeypatch):
    seen = {}

    def urlopen(req, timeout):
        seen["url"], seen["auth"] = req.full_url, req.get_header("Authorization")
        body = io.BytesIO(json.dumps({"error": {"code": 190, "message": "token IGAAsegredo inválido"}}).encode())
        raise ig.urllib.error.HTTPError(req.full_url, 400, "x", {}, body)
    monkeypatch.setattr(ig.urllib.request, "build_opener",
                        lambda *h: type("O", (), {"open": lambda self, req, timeout: urlopen(req, timeout)})())
    with pytest.raises(RuntimeError) as e:
        ig.graph("IGAAsegredo", "123/media", {"image_url": "u", "caption": "c"})
    assert "IGAAsegredo" not in str(e.value) and "190" in str(e.value)
    assert "IGAAsegredo" not in seen["url"] and seen["auth"] == "Bearer IGAAsegredo"
    assert seen["url"].startswith("https://graph.instagram.com/")


def test_graph_nao_segue_redirect(monkeypatch):
    handlers = []

    def opener(*h):
        handlers.extend(h)

        class O:
            def open(self, req, timeout):
                raise ig.urllib.error.HTTPError(req.full_url, 302, "x", {"Location": "https://evil.example/"},
                                                io.BytesIO(b""))
        return O()
    monkeypatch.setattr(ig.urllib.request, "build_opener", opener)
    with pytest.raises(RuntimeError, match="302"):
        ig.graph("t", "1/media", {})
    assert ig.tp._NoRedirect in handlers


def test_legenda_cabe_em_2200_e_normaliza_arroba_e_cerquilha():
    t = ig.caption({**OFERTA, "seal": None, "title": "\uff20perfil \ufe5ftag " + "x" * 5000, "author": "\ufe6ba" * 3000})
    assert len(t) <= ig.CAPTION_MAX and not any(c in t.rsplit("\n", 1)[0] for c in "@#\uff20\uff03\ufe5f\ufe6b")
    assert t.splitlines()[0].startswith("perfil tag xxx") and "…, de " in t.splitlines()[0]


def test_render_mostra_o_erro_do_chrome(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROME", "/bin/chrome")

    def falha(cmd, **kw):
        raise ig.subprocess.CalledProcessError(1, cmd, stderr=b"linha 1\nNo usable sandbox!")
    monkeypatch.setattr(ig.subprocess, "run", falha)
    with pytest.raises(RuntimeError, match="No usable sandbox"):
        ig.render(OFERTA, tmp_path / "ig")


def test_webp_exige_assinatura_completa():
    assert all(not k.startswith(b"RIFF") for k in ig.MAGIC)  # RIFF sozinho (ex.: WAV) não passa
