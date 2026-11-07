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
    sql = vendas.import_sql(rows, ("2026-11-03", "2026-11-03"))
    db.executescript(sql)
    db.executescript(sql)  # reimportar o mesmo período substitui, não duplica
    assert db.execute("SELECT status, qty, commission_cents FROM sales ORDER BY status").fetchall() == [
        ("enviado", 2, 359), ("pedido", 2, None)]


def test_titulo_com_aspas_nao_quebra_o_sql():
    csv = HEADER + "\n11-03-2026,Livros,\"O'Brien'); DROP TABLE sales;--\",X1,1,0,1,1.0,0,1,0,0,4,10,0,0,0,0,0,0,0\n"
    db = sqlite3.connect(":memory:")
    db.execute(vendas.SCHEMA)
    db.executescript(vendas.import_sql(vendas.parse_amazon(csv, "f.csv", now="t"), ("2026-11-03", "2026-11-03")))
    assert db.execute("SELECT title FROM sales").fetchone()[0] == "O'Brien'); DROP TABLE sales;--"


def test_periodo_invalido_para():
    with pytest.raises(SystemExit, match="período inválido"):
        vendas.import_sql([], ("2026-11-03' OR 1=1 --", "2026-11-03"))
