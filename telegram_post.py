#!/usr/bin/env python3
"""Posta no canal do Telegram as ofertas do offers.json (docs/produto/distribuicao-canais.md). Só stdlib.

    python3 telegram_post.py <offers.json> <channel_posts.csv>

Oferta postável = a mesma do site (build.resolve + ofertas, sem preço vencido) e o texto é o build.post_text.
O estado é o channel_posts.csv do branch channel-posts (fora do price-history, para não disputar push com o
pipeline): uma linha por post, gravada depois do ok do Telegram.
Lê TELEGRAM_BOT_TOKEN e TELEGRAM_CHANNEL_ID do ambiente. O log só mostra contagens.
"""
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import build

CHANNEL = "tg"
# Valores iniciais da spec (§6), ainda em avaliação pelo Elias: mudar o número e abrir PR.
JANELA = (8, 22)          # horas BRT: posta das 08:00 às 21:59
POR_EXECUCAO, POR_DIA = 2, 8
REPOST_DIAS = 7           # mesmo livro só volta depois disso...
REPOST_MAIS_BARATO_H = 24  # ...ou com preço menor que o do último post, depois disso
CAPTION_MAX = 1024        # limite da legenda do sendPhoto
FIELDS = ("posted_at", "channel", "offer_id", "store", "price_cents")


def read_log(path):
    """Linhas do canal, em ordem de gravação (append-only)."""
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [{**r, "at": datetime.fromisoformat(r["posted_at"]), "price_cents": int(r["price_cents"])}
                for r in csv.DictReader(f) if r["channel"] == CHANNEL]


def pick(offers, log, now):
    """Ofertas a postar agora, na ordem, com janela, limites e repetição aplicados."""
    h = now.astimezone(build.BRT)
    if not JANELA[0] <= h.hour < JANELA[1]:
        return []
    hoje = sum(r["at"].astimezone(build.BRT).date() == h.date() for r in log)
    last = {r["offer_id"]: r for r in log}  # a última linha de cada livro vence

    def livre(o):
        r = last.get(o["id"])
        if r is None:
            return True
        dias = (now - r["at"]).total_seconds() / 86400
        return dias >= REPOST_DIAS or (dias * 24 >= REPOST_MAIS_BARATO_H and o["price_cents"] < r["price_cents"])

    cand = [o for o in build.ofertas(offers) if not o["velho"] and livre(o)]
    cand.sort(key=lambda o: (o["seal"] != "90d", -build.discount(o), -o["checked_at"].timestamp()))
    return cand[:max(0, min(POR_EXECUCAO, POR_DIA - hoje))]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def no_ar(url):
    """O /r/ já está publicado e leva a uma loja (não ao curinga da home)? Não segue o redirect:
    nenhum request sai para a loja."""
    try:
        urllib.request.build_opener(_NoRedirect).open(urllib.request.Request(url, method="HEAD"), timeout=10)
    except urllib.error.HTTPError as e:
        loc = urlsplit(e.headers.get("Location", ""))
        return e.code == 302 and loc.scheme == "https" and loc.hostname in build.ALLOWED_HOSTS
    return False


def telegram(token, method, data):
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.load(r)
    except urllib.error.HTTPError as e:  # o erro do urllib não leva a URL (com o token)
        try:
            body = json.load(e)
        except ValueError:
            body = {"error_code": e.code}
    if not body.get("ok"):
        raise RuntimeError(f"Telegram {method}: {body.get('error_code')} {body.get('description', '')}")


def post(token, chat, o, text):
    """Texto puro, sem parse_mode: título e autor vêm de dado coletado. Foto só a do ML (https),
    a capa local de /capas/ fica fora até o Elias decidir. Sem prévia do link: o servidor do Telegram
    seguiria o /r/ até a loja e geraria um clique de robô no link de afiliado a cada post.
    Foto recusada (404 no ML etc.) cai no texto: senão a mesma oferta travaria o canal a cada execução."""
    img = o["image_url"]
    if img and img.startswith("https://") and len(text) <= CAPTION_MAX:
        try:
            return telegram(token, "sendPhoto", {"chat_id": chat, "photo": img, "caption": text})
        except RuntimeError as err:
            print(f"tg: foto recusada, vai sem foto ({err})")
    telegram(token, "sendMessage", {"chat_id": chat, "text": text, "link_preview_options": {"is_disabled": True}})


def main(offers_path, log_path, now=None):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHANNEL_ID", "").removeprefix("@")
    if not token or not chat:
        print("::warning::tg: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHANNEL_ID ausente; nada postado")
        return
    if not build.TG_CHANNEL_RE.fullmatch(chat):
        raise build.Invalid("TELEGRAM_CHANNEL_ID precisa ser o @username público do canal")
    now = now or datetime.now(timezone.utc)
    offers = build.resolve(build.load_books(json.loads(Path(offers_path).read_text(encoding="utf-8"))), now)
    posted = fora = 0
    for o in pick(offers, read_log(log_path), now):
        url = f"{build.SITE}/r/{o['id']}/{CHANNEL}"
        if not no_ar(url):
            fora += 1
            continue
        post(token, f"@{chat}", o, build.post_text(o, url))
        new = not log_path.exists()
        with log_path.open("a", newline="", encoding="utf-8") as f:  # só depois do ok do Telegram
            w = csv.writer(f)
            if new:
                w.writerow(FIELDS)
            w.writerow((now.isoformat(timespec="seconds"), CHANNEL, o["id"], o["store"], o["price_cents"]))
        posted += 1
    print(f"tg: {posted} postadas, {fora} sem /r/ no ar")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], Path(sys.argv[2]))
