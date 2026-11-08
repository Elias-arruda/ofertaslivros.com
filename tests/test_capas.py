"""collector/capas.py: só a lógica local; rede nunca é chamada."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from collector import capas as cp  # noqa: E402


def test_vtex_url_so_ean_exato_e_cdn_da_loja():
    p = [{"items": [{"ean": "1", "images": [{"imageUrl": "https://livrariascuritiba.vteximg.com.br/arquivos/ids/9/a.jpg?v=1"}]}]}]
    assert cp.vtex_url(cp.VTEX[0], "1", p) == "https://livrariascuritiba.vteximg.com.br/arquivos/ids/9-400-600/a.jpg"
    assert cp.vtex_url(cp.VTEX[0], "2", p) is None                       # EAN diferente
    assert cp.vtex_url(cp.VTEX[1], "1", p) is None                       # CDN de outra loja
    evil = [{"items": [{"ean": "1", "images": [{"imageUrl": "https://evil.com/arquivos/ids/9/a.jpg"}]}]}]
    assert cp.vtex_url(cp.VTEX[0], "1", evil) is None


def test_jpeg():
    assert cp.jpeg(cp.JPEG + b"x" * 3000)
    assert not cp.jpeg(b"\x89PNG" + b"x" * 3000) and not cp.jpeg(cp.JPEG)


def test_pendentes_so_isbn_valido(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "CAPAS", tmp_path)
    (tmp_path / "9788535914061.jpg").write_bytes(b"x")
    books = [{"isbn": "9786555640786"}, {"isbn": "853591406X"},
             {"isbn": "9788535914061"},                      # já tem capa
             {"isbn": "9786555640786", "ml_url": "x"},        # tem ML
             {"isbn": next(iter(cp.RECUSADAS))},
             {"isbn": "../../etc/x"}, {"isbn": "97865556407861"}, {"isbn": 123}, {}]
    assert [b["isbn"] for b in cp.pendentes(books)] == ["9786555640786", "853591406X"]


def test_todo_livro_no_site_tem_capa():
    """Livro fora de pendente precisa de foto: ml_product_id (o coletor pega a do ML) ou static/capas/<isbn>.jpg.
    Capa recusada sem ML = o livro fica pendente até ganhar uma das duas."""
    import json
    cat = json.loads((ROOT / "collector" / "catalog.json").read_text())
    books = cat["books"] if isinstance(cat, dict) else cat
    sem = [b["id"] for b in books if not b.get("pendente") and not b.get("ml_product_id")
           and not (cp.CAPAS / f"{b.get('isbn')}.jpg").is_file()]
    assert not sem, f"livros sem capa no site: {sem}"
