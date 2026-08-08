"""Envelope de resposta.

Único lugar que decide a forma externa de uma resposta bem-sucedida. O envelope
de erro é responsabilidade do middleware de erro.
"""


def ok(dados, **extra):
    """Resposta com corpo de dados: {"dados": ..., "sucesso": true}."""
    payload = {"dados": dados, "sucesso": True}
    payload.update(extra)
    return payload


def mensagem(texto):
    """Resposta de comando sem corpo de dados: {"sucesso": true, "mensagem": ...}."""
    return {"sucesso": True, "mensagem": texto}
