"""Endpoints de sistema: índice e health check.

O health check deixou de expor `secret_key`, `debug`, `db_path` e `ambiente` —
é um endpoint público e sem autenticação, então só informa status e
conectividade.
"""
from flask import jsonify

VERSAO = "1.0.0"


class SistemaController:
    def __init__(self, produto_model, usuario_model, pedido_model):
        self._produtos = produto_model
        self._usuarios = usuario_model
        self._pedidos = pedido_model

    def index(self):
        return jsonify({
            "mensagem": "Bem-vindo à API da Loja",
            "versao": VERSAO,
            "endpoints": {
                "produtos": "/produtos",
                "usuarios": "/usuarios",
                "pedidos": "/pedidos",
                "login": "/login",
                "relatorios": "/relatorios/vendas",
                "health": "/health",
            },
        }), 200

    def health(self):
        return jsonify({
            "status": "ok",
            "database": "connected",
            "counts": {
                "produtos": self._produtos.contar(),
                "usuarios": self._usuarios.contar(),
                "pedidos": self._pedidos.contar(),
            },
            "versao": VERSAO,
        }), 200
