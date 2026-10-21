"""Critérios de aceite do canal do Telegram (distribuicao-canais.md §10). Rede sempre mockada."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build  # noqa: E402
import telegram_post as tp  # noqa: E402

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=build.BRT)


def of(oid, price=60, seal=None, oferta=True, velho=False, checked=NOW):
    return {"id": oid, "price_cents": price, "list_price_cents": 100, "seal": seal, "oferta": oferta,
            "velho": velho, "checked_at": checked}


def log(*rows):
    return [{"offer_id": oid, "at": at, "price_cents": price} for oid, at, price in rows]


def ids(offers, rows=(), now=NOW):
    return [o["id"] for o in tp.pick(offers, list(rows), now)]


def test_janela_08h_22h():
    assert ids([of("a")], now=NOW.replace(hour=7, minute=59)) == []
    assert ids([of("a")], now=NOW.replace(hour=22)) == []
    assert ids([of("a")], now=NOW.replace(hour=8)) == ["a"]


def test_limite_por_execucao_e_por_dia():
    five = [of(c) for c in "abcde"]
    assert len(ids(five)) == 2
    hoje = [("x", NOW - timedelta(hours=1), 1)] * 7
    assert len(ids(five, log(*hoje))) == 1
    assert ids(five, log(*hoje, ("y", NOW, 1))) == []
    ontem = [("x", NOW - timedelta(days=1), 1)] * 8  # outro dia BRT não conta
    assert len(ids(five, log(*ontem))) == 2


def test_so_oferta_com_preco_no_prazo():
    assert ids([of("a", oferta=False), of("b", velho=True), of("c")]) == ["c"]


def test_ordem_selo_desconto_recente(monkeypatch):
    offers = [of("d10", price=90), of("d40", price=60), of("selo", price=95, seal="90d"),
              of("d40-novo", price=60, checked=NOW + timedelta(minutes=1))]
    monkeypatch.setattr(tp, "POR_EXECUCAO", 4)
    assert ids(offers) == ["selo", "d40-novo", "d40", "d10"]


def test_nao_repete_em_7_dias_salvo_preco_menor_depois_de_24h():
    a = [of("a", price=60)]
    assert ids(a, log(("a", NOW - timedelta(days=6, hours=23), 60))) == []
    assert ids(a, log(("a", NOW - timedelta(days=7), 60))) == ["a"]
    assert ids(a, log(("a", NOW - timedelta(hours=23), 70))) == []     # mais barato, mas antes de 24 h
    assert ids(a, log(("a", NOW - timedelta(hours=24), 70))) == ["a"]
    assert ids(a, log(("a", NOW - timedelta(days=2), 60))) == []       # mesmo preço
    assert ids(a, log(("a", NOW - timedelta(days=8), 60), ("a", NOW - timedelta(days=1), 60))) == []  # vale o último


AMZ = {"store": "amazon", "asin": "B0ABCDEFGH", "price_cents": 4290, "list_price_cents": 7490,
       "lowest_90d_cents": 4290, "checked_at": "2026-10-21T11:00:00-03:00"}


@pytest.fixture
def run(tmp_path, monkeypatch):
    doc = {"version": 2, "offers": [
        {"id": "torto-arado", "genre": "literatura-brasileira", "title": "Torto *Arado* <b>", "author": "Itamar",
         "stores": [AMZ]},
        {"id": "com-foto", "genre": "ficcao", "title": "Com foto", "author": "Autora",
         "image_url": "https://http2.mlstatic.com/D_x.jpg", "stores": [{**AMZ, "price_cents": 5000}]},
        {"id": "sem-desconto", "genre": "ficcao", "title": "Sem", "author": "A",
         "stores": [{**AMZ, "list_price_cents": 4290}]},
        {"id": "vencida", "genre": "ficcao", "title": "Vencida", "author": "A",       # Amazon com 16 h
         "stores": [{**AMZ, "price_cents": 1000, "checked_at": "2026-10-20T20:00:00-03:00"}]},
    ]}
    (tmp_path / "offers.json").write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@ofertaslivros")
    calls, live = [], {"ok": True}
    monkeypatch.setattr(tp, "telegram", lambda token, method, data: calls.append((method, data)))
    monkeypatch.setattr(tp, "no_ar", lambda url: live["ok"])
    csv_path = tmp_path / "channel_posts.csv"

    def go():
        tp.main(tmp_path / "offers.json", csv_path, now=NOW)
        return calls
    go.csv, go.live = csv_path, live
    return go


def test_posta_texto_puro_com_link_tg_e_e_idempotente(run):
    calls = run()
    assert [m for m, _ in calls] == ["sendMessage", "sendPhoto"]   # maior desconto primeiro; foto só do ML
    (_, msg), (_, photo) = calls
    assert "parse_mode" not in msg and "parse_mode" not in photo
    assert msg["link_preview_options"] == {"is_disabled": True}         # sem clique de robô na loja
    assert msg["chat_id"] == "@ofertaslivros"
    assert "Torto *Arado* <b>, de Itamar" in msg["text"]                 # literal
    assert msg["text"].endswith("Link de afiliado: https://ofertaslivros.com.br/r/torto-arado/tg")
    assert "O preço final é o da loja." in msg["text"] and "amazon.com" not in msg["text"]
    assert photo["photo"] == "https://http2.mlstatic.com/D_x.jpg" and photo["caption"].startswith("Com foto")
    assert run.csv.read_text().splitlines()[0] == "posted_at,channel,offer_id,store,price_cents"
    assert len(run()) == 2                                                # 2ª execução: nada novo


def test_link_fora_do_ar_nao_posta_nem_grava(run):
    run.live["ok"] = False
    assert run() == [] and not run.csv.exists()


def test_sem_token_nao_posta(run, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    assert run() == []


def test_dedup_e_por_canal(run):
    run.csv.write_text("posted_at,channel,offer_id,store,price_cents\n"
                       f"{NOW.isoformat()},wa,torto-arado,amazon,4290\n", encoding="utf-8")
    assert [d.get("text", d.get("caption")).splitlines()[0] for _, d in run()] == ["Torto *Arado* <b>, de Itamar",
                                                                                   "Com foto, de Autora"]


def test_foto_recusada_vai_como_texto(run, monkeypatch):
    calls = []

    def fake(token, method, data):
        calls.append(method)
        if method == "sendPhoto":
            raise RuntimeError("Telegram sendPhoto: 400 wrong file")
    monkeypatch.setattr(tp, "telegram", fake)
    run()
    assert calls == ["sendMessage", "sendPhoto", "sendMessage"]
    assert len(run.csv.read_text().splitlines()) == 3


@pytest.mark.parametrize("code,loc,ok", [
    (302, "https://www.amazon.com.br/dp/B0ABCDEFGH?tag=x-20", True),
    (302, "https://www.mercadolivre.com.br/social/x", True),
    (302, "/", False),                                   # curinga: oferta fora do deploy
    (302, "https://ofertaslivros.com.br/", False),
    (302, "http://www.amazon.com.br/dp/B0ABCDEFGH", False),
    (302, "https://evil.example/", False),
    (404, "", False),
    (200, None, False),
])
def test_no_ar(monkeypatch, code, loc, ok):
    class Opener:
        def open(self, req, timeout):
            assert req.get_method() == "HEAD"
            if code == 200:
                return None
            raise tp.urllib.error.HTTPError(req.full_url, code, "x", {"Location": loc}, None)
    monkeypatch.setattr(tp.urllib.request, "build_opener", lambda *h: Opener())
    assert tp.no_ar("https://ofertaslivros.com.br/r/a/tg") is ok
