"""Tratamento de erro centralizado.

Substitui os doze blocos `except:` sem tipo, que devolviam `{'error': 'Erro
interno'}` sem registrar nada — e que capturavam inclusive KeyboardInterrupt e
SystemExit.

O formato `{"error": ...}` é o mesmo do projeto original; o que muda é que
agora existe um único lugar que o produz, e que erros inesperados deixam de
virar página HTML de 500.
"""
from flask import jsonify
from werkzeug.exceptions import HTTPException

from src.domain.errors import DomainError


def _erro(mensagem, status):
    return jsonify({"error": mensagem}), status


def register(app, logger):
    @app.errorhandler(DomainError)
    def _dominio(exc):
        return _erro(exc.message, exc.status)

    @app.errorhandler(HTTPException)
    def _http(exc):
        return _erro(exc.description, exc.code)

    @app.errorhandler(Exception)
    def _inesperado(exc):
        # Stack completa no log; mensagem genérica para o cliente.
        logger.exception("erro não tratado")
        return _erro("Erro interno", 500)
