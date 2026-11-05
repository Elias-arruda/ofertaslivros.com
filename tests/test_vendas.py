import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analytics"))
import vendas  # noqa: E402

HEADER = ("Date,Category,Product Title,ASIN,Clicks,Indirect Items Ordered,Direct Items Ordered,Items Ordered,"
          "Direct Conversion Rate,Order Quantity,Product Conversion Rate,Order Conversion Rate,Commission Rate,"
          "Ordered Revenue,Items Shipped,Items Returned,Items Shipped Revenue,Items Shipped Earnings,"
          "Items Returned Revenue,Items Returned Earnings,Total Earnings")
REAL = HEADER + "\n11-04-2026,-,-,Other,63.0,0.0,0.0,0.0,0,0.0,0,0,-,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0\n"  # export de 2026-11-05


def test_export_real_sem_pedidos():
    assert vendas.parse_amazon(REAL, "f.csv") == []
    assert vendas.period(REAL) == ("2026-11-04", "2026-11-04")


def test_linha_com_pedido_envio_e_devolucao():
    csv = HEADER + "\n11-03-2026,Livros,Torto Arado,8556520049,10,0,2,2.0,0,2,0,0,4.5,79.80,2.0,1.0,79.80,3.59,39.90,-1.80,1.79\n"
    rows = vendas.parse_amazon(csv, "f.csv", now="t")
    by = {r["status"]: r for r in rows}
    assert set(by) == {"pedido", "enviado", "devolvido"}
    assert by["pedido"]["qty"] == 2 and by["pedido"]["revenue_cents"] == 7980 and by["pedido"]["commission_cents"] is None
    assert by["enviado"]["commission_cents"] == 359 and by["devolvido"]["commission_cents"] == -180
    assert by["enviado"]["order_date"] == "2026-11-03" and by["enviado"]["item_id"] == "8556520049"


def test_csv_errado_para():
    with pytest.raises(SystemExit, match="faltam colunas"):
        vendas.parse_amazon("Número de rastreamento,cliques\nOther,9.0\n", "f.csv")


def test_sql_do_import_no_sqlite():
    """O mesmo SQL do D1 (schema, json_each e a chave sem NULL) roda no SQLite."""
    csv = HEADER + "\n11-03-2026,Livros,Torto Arado,8556520049,10,0,2,2.0,0,2,0,0,4.5,79.80,2.0,0,79.80,3.59,0,0,3.59\n"
    rows = vendas.parse_amazon(csv, "f.csv", now="t")
    db = sqlite3.connect(":memory:")
    db.execute(vendas.SCHEMA)
    import json
    db.execute(vendas.INSERT, [json.dumps(rows)])
    assert db.execute("SELECT status, qty, commission_cents FROM sales ORDER BY status").fetchall() == [
        ("enviado", 2, 359), ("pedido", 2, None)]
    with pytest.raises(sqlite3.IntegrityError):  # reimportar sem apagar o período bate na UNIQUE
        db.execute(vendas.INSERT, [json.dumps(rows)])
