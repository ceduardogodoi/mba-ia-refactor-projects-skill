"""Use case de relatório de vendas.

O cálculo das faixas de desconto vive no model de pedido — aqui só há
orquestração e serialização.
"""
from flask import jsonify

from src.serializers.response import ok


class RelatorioController:
    def __init__(self, pedido_model):
        self._pedidos = pedido_model

    def vendas(self):
        return jsonify(ok(self._pedidos.relatorio_vendas())), 200
