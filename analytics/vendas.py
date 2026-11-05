"""Importa no D1 (tabela sales) o CSV de vendas exportado do painel de afiliados.

Uso (na máquina do Elias, nunca no Actions):
    python3 analytics/vendas.py amazon ~/ofertaslivros-vendas/amazon/<dia>/csv/linked/<arquivo>.csv [--dry-run]

O CSV vem do botão de exportar do painel dos Associados (relatório "Produto relacionado", em CSV),
pelo fluxo da exceção das regras 1 e 2 do CLAUDE.md. Fica fora do repo, que é público. Este script não faz
request à Amazon: só lê o arquivo local e grava no D1 pela API da Cloudflare (token CF_D1_TOKEN no .env).
"""
import csv
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

DB_ID = "aa8a7b0d-e44f-4c1c-8c11-b6e204460e32"  # ofertaslivros-analytics (não é segredo)
SCHEMA = """CREATE TABLE IF NOT EXISTS sales (
  store TEXT NOT NULL, order_date TEXT NOT NULL,
  tracking TEXT NOT NULL DEFAULT '', item_id TEXT NOT NULL DEFAULT '', title TEXT,
  qty INTEGER NOT NULL, revenue_cents INTEGER, commission_cents INTEGER,
  status TEXT NOT NULL, source_file TEXT NOT NULL, imported_at TEXT NOT NULL,
  UNIQUE (store, order_date, item_id, tracking, status))"""
INSERT = """INSERT INTO sales (store, order_date, tracking, item_id, title, qty, revenue_cents, commission_cents,
  status, source_file, imported_at)
  SELECT j.value->>'store', j.value->>'order_date', j.value->>'tracking', j.value->>'item_id', j.value->>'title',
    j.value->>'qty', j.value->>'revenue_cents', j.value->>'commission_cents', j.value->>'status',
    j.value->>'source_file', j.value->>'imported_at' FROM json_each(?1) AS j"""

# Colunas do relatório "Produto relacionado" (Linked-Product) que viram uma linha por status.
STATUS_COLS = {
    "pedido": ("Items Ordered", "Ordered Revenue", None),
    "enviado": ("Items Shipped", "Items Shipped Revenue", "Items Shipped Earnings"),
    "devolvido": ("Items Returned", "Items Returned Revenue", "Items Returned Earnings"),
}


def _num(v):
    """'1.0' / '-' / '' -> Decimal (o painel usa '-' para vazio)."""
    v = (v or "").strip()
    return Decimal(v) if v not in ("", "-") else Decimal(0)


def cents(v):
    return int((_num(v) * 100).quantize(Decimal(1)))


def parse_amazon(text, source_file, now=None):
    """CSV Linked-Product -> linhas de sales. Linhas sem item pedido/enviado/devolvido são ignoradas
    (a linha 'Other' só traz cliques)."""
    now = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    missing = ({"Date", "ASIN", "Product Title"} | {c for cols in STATUS_COLS.values() for c in cols if c}) - set(reader.fieldnames or [])
    if missing:
        raise SystemExit(f"CSV não parece o 'Produto relacionado' da Amazon; faltam colunas: {sorted(missing)}")
    rows = []
    for r in reader:
        day = datetime.strptime(r["Date"].strip(), "%m-%d-%Y").date().isoformat()
        for status, (qcol, rcol, ecol) in STATUS_COLS.items():
            qty = int(_num(r[qcol]))
            if not qty:
                continue
            rows.append({"store": "amazon", "order_date": day, "tracking": "", "item_id": r["ASIN"].strip(),
                         "title": r["Product Title"].strip()[:300], "qty": qty, "revenue_cents": cents(r[rcol]),
                         "commission_cents": cents(r[ecol]) if ecol else None, "status": status,
                         "source_file": source_file, "imported_at": now})
    return rows


def period(text):
    """Primeiro e último dia do CSV (inclusive): o período que o import substitui."""
    days = [datetime.strptime(r["Date"].strip(), "%m-%d-%Y").date().isoformat()
            for r in csv.DictReader(io.StringIO(text.lstrip("﻿")))]
    return (min(days), max(days)) if days else None


def _env():
    env = dict(os.environ)
    p = Path(__file__).resolve().parent.parent / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


def d1(env, sql, params=()):
    url = f"https://api.cloudflare.com/client/v4/accounts/{env['CF_ACCOUNT_ID']}/d1/database/{DB_ID}/query"
    req = urllib.request.Request(url, json.dumps({"sql": sql, "params": list(params)}).encode(),
                                 {"Authorization": f"Bearer {env['CF_D1_TOKEN']}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:  # só o status e o erro da API, nunca o token
        raise SystemExit(f"D1: {e.code} {e.read()[:300]!r}")


def main(argv):
    if len(argv) < 2 or argv[0] != "amazon":
        raise SystemExit(__doc__)
    path = Path(argv[1]).expanduser()
    text = path.read_text(encoding="utf-8-sig")
    rows, per = parse_amazon(text, path.name), period(text)
    print(f"{path.name}: período {per}, {len(rows)} linhas com pedido/envio/devolução")
    if "--dry-run" in argv or not per:
        return
    env = _env()
    for k in ("CF_ACCOUNT_ID", "CF_D1_TOKEN"):
        if not env.get(k):
            raise SystemExit(f"{k} ausente no .env")
    # ponytail: DELETE e INSERT em duas chamadas (a API não garante transação entre elas);
    # se o INSERT falhar, é só rodar de novo: o import do período é idempotente.
    d1(env, SCHEMA)
    d1(env, "DELETE FROM sales WHERE store = 'amazon' AND order_date BETWEEN ?1 AND ?2", per)
    if rows:
        d1(env, INSERT, [json.dumps(rows)])
    print("gravado no D1")


if __name__ == "__main__":
    main(sys.argv[1:])
