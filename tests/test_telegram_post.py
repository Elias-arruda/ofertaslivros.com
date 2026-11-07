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
    assert len(ids(five)) == 1
    hoje = [("x", NOW - timedelta(hours=1), 1)] * 7
    assert len(ids(five, log(*hoje))) == 1
    assert ids(five, log(*hoje, ("y", NOW, 1))) == []
    ontem = [("x", NOW - timedelta(days=1), 1)] * 8  # outro dia BRT não conta
    assert len(ids(five, log(*ontem))) == 1


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



def test_intervalo_espalha_os_posts_do_canal_pela_janela():
    assert tp.INTERVALO_MIN == 105                                      # 14 h * 60 / 8
    a = [of("a")]
    assert tp.pick(a, log(("x", NOW - timedelta(minutes=104), 1)), NOW, intervalo_min=tp.INTERVALO_MIN) == []
    assert ids(a, log(("x", NOW - timedelta(minutes=104), 1))) == ["a"]  # sem intervalo (o resumo wa) não trava
    # um dia de execuções a cada 5 min: 8 posts, todos >= 105 min um do outro, o último antes das 22h
    offers, rows = [of(f"o{i}") for i in range(20)], []
    for m in range(0, 24 * 60, 5):
        now = NOW.replace(hour=0, minute=0) + timedelta(minutes=m)
        for o in tp.pick(offers, rows, now, intervalo_min=tp.INTERVALO_MIN):
            rows.append({"offer_id": o["id"], "at": now, "price_cents": o["price_cents"]})
    ats = [r["at"] for r in rows]
    assert len(ats) == tp.POR_DIA
    assert all(b - a >= timedelta(minutes=105) for a, b in zip(ats, ats[1:]))
    assert ats[0].hour == 8 and ats[-1].hour < 22 and ats[-1] - ats[0] >= timedelta(hours=12)


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


def test_posta_texto_puro_com_link_tg_e_e_idempotente(run, monkeypatch):
    monkeypatch.setattr(tp, "POR_EXECUCAO", 2)
    calls = run()
    assert [m for m, _ in calls] == ["sendMessage", "sendPhoto"]   # maior desconto primeiro; foto só do ML
    (_, msg), (_, photo) = calls
    assert "parse_mode" not in msg and "parse_mode" not in photo
    assert "link_preview_options" not in msg                            # prévia da nossa página, com a capa
    assert msg["chat_id"] == "@ofertaslivros"
    assert "Torto *Arado* <b>, de Itamar" in msg["text"]                 # literal
    assert msg["text"].endswith("Link: https://ofertaslivros.com.br/livro/torto-arado/")
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


def test_dedup_e_por_canal(run, monkeypatch):
    monkeypatch.setattr(tp, "POR_EXECUCAO", 2)
    run.csv.write_text("posted_at,channel,offer_id,store,price_cents\n"
                       f"{NOW.isoformat()},wa,torto-arado,amazon,4290\n", encoding="utf-8")
    assert [d.get("text", d.get("caption")).splitlines()[0] for _, d in run()] == ["Torto *Arado* <b>, de Itamar",
                                                                                   "Com foto, de Autora"]


def test_foto_recusada_vai_como_texto(run, monkeypatch):
    monkeypatch.setattr(tp, "POR_EXECUCAO", 2)
    calls = []

    def fake(token, method, data):
        calls.append(method)
        if method == "sendPhoto":
            raise RuntimeError("Telegram sendPhoto: 400 wrong file")
    monkeypatch.setattr(tp, "telegram", fake)
    run()
    assert calls == ["sendMessage", "sendPhoto", "sendMessage"]
    assert len(run.csv.read_text().splitlines()) == 3


@pytest.mark.parametrize("code,ok", [
    (200, True),
    (301, False),   # livro retirado: vai para o nicho
    (302, False),
    (404, False),   # página fora do deploy
])
def test_no_ar(monkeypatch, code, ok):
    class Resp:
        status = code
        def __enter__(self): return self
        def __exit__(self, *a): return False

    class Opener:
        def open(self, req, timeout):
            assert req.get_method() == "HEAD"
            assert req.get_header("User-agent").startswith("ofertaslivros-telegram/")
            if code == 200:
                return Resp()
            raise tp.urllib.error.HTTPError(req.full_url, code, "x", {"Location": "/manga/"}, None)
    monkeypatch.setattr(tp.urllib.request, "build_opener", lambda *h: Opener())
    assert tp.no_ar("https://ofertaslivros.com.br/livro/a/") is ok


def test_resumo_wa_no_chat_do_admin_uma_vez_por_dia(run, monkeypatch):
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID")
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "123456")
    calls = run()
    assert [m for m, _ in calls] == ["sendMessage", "sendMessage", "sendPhoto", "sendMessage", "sendMessage"]
    assert all(d["chat_id"] == "123456" and "parse_mode" not in d for _, d in calls)
    texts = [d.get("text") for _, d in calls]
    assert texts[0] == "Resumo WhatsApp de 21/10: 2 ofertas" and texts[-1] == "fim do resumo"
    assert texts[1].endswith("Link: https://ofertaslivros.com.br/livro/torto-arado/") and "caption" not in calls[2][1]
    assert sum(",wa," in line for line in run.csv.read_text().splitlines()) == 2
    assert len(run()) == 5                                                # 2ª execução no mesmo dia: nada


def test_resumo_wa_antes_das_11h_e_sem_oferta_nao_sai(run, monkeypatch):
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID")
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "123456")
    tp.main(run.csv.parent / "offers.json", run.csv, now=NOW.replace(hour=10, minute=59))
    run.live["ok"] = False
    assert run() == [] and not run.csv.exists()


@pytest.mark.parametrize("bad", ["@elias", "-100123", "12a", "1" * 21])
def test_admin_chat_id_invalido(run, monkeypatch, bad):
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", bad)
    with pytest.raises(build.Invalid):
        run()


def test_resumo_wa_que_falhou_no_meio_nao_sai_de_novo(run, monkeypatch):
    monkeypatch.delenv("TELEGRAM_CHANNEL_ID")
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "123456")

    def cai(token, method, data):
        raise RuntimeError("Telegram sendMessage: 502")
    monkeypatch.setattr(tp, "telegram", cai)
    with pytest.raises(RuntimeError):
        run()
    assert sum(",wa," in line for line in run.csv.read_text().splitlines()) == 2
    monkeypatch.setattr(tp, "telegram", lambda *a: pytest.fail("reenviou o resumo"))
    run()


def test_canal_respeita_o_intervalo_entre_execucoes(run):
    csv_path, offers = run.csv, run.csv.parent / "offers.json"
    assert len(run()) == 1                                                # 1 por execução
    tp.main(offers, csv_path, now=NOW + timedelta(minutes=104))
    assert len(csv_path.read_text().splitlines()) == 2                     # cabeçalho + 1: cedo demais
    tp.main(offers, csv_path, now=NOW + timedelta(minutes=105))
    assert len(csv_path.read_text().splitlines()) == 3
