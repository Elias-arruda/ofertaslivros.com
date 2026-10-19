import pytest


@pytest.fixture(autouse=True)
def _fora_do_actions(monkeypatch):
    """No Actions o coletor imprime ::add-mask::<token> de propósito (o GitHub esconde o valor);
    os testes de "token fora do log" conferem a saída como se fosse fora do Actions."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
