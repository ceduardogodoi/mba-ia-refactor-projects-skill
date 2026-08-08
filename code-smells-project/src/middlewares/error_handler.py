"""Tratamento de erro centralizado.

Substitui os 16 blocos `try / except Exception -> jsonify(str(e)), 500` que
estavam copiados nos handlers. As camadas internas levantam erros de domínio;
só aqui se decide status code, e só aqui se decide o que o cliente vê.
"""
from flask import jsonify
from werkzeug.exceptions import HTTPException

from src.domain.errors import DomainError


def _erro(mensagem, status):
    return jsonify({"erro": mensagem, "sucesso": False}), status


def register(app, logger):
    @app.errorhandler(DomainError)
    def _dominio(exc):
        return _erro(exc.message, exc.status)

    @app.errorhandler(HTTPException)
    def _http(exc):
        # 404 de rota inexistente, 405 de método errado, etc.
        return _erro(exc.description, exc.code)

    @app.errorhandler(Exception)
    def _inesperado(exc):
        # A stack completa vai para o log; o cliente recebe mensagem genérica.
        # Antes, `str(e)` devolvia o texto da query SQL ao chamador.
        logger.exception("erro não tratado")
        return _erro("Erro interno", 500)
