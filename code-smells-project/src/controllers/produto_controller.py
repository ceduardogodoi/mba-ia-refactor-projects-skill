"""Use cases de produto.

Valida entrada, chama o model, escolhe status code e serializa. Não escreve SQL
e não trata exceção genérica — o middleware de erro faz isso uma vez só.
"""
from flask import jsonify, request

from src.domain.errors import NotFoundError
from src.schemas.validators import validar_filtros_busca, validar_produto
from src.serializers import produto_serializer
from src.serializers.response import mensagem, ok


class ProdutoController:
    def __init__(self, produto_model):
        self._produtos = produto_model

    def listar(self):
        produtos = self._produtos.listar()
        return jsonify(ok(produto_serializer.many(produtos))), 200

    def buscar(self):
        filtros = validar_filtros_busca(request.args)
        produtos = self._produtos.buscar(**filtros)
        dados = produto_serializer.many(produtos)
        return jsonify(ok(dados, total=len(dados))), 200

    def obter(self, id):
        produto = self._produtos.buscar_por_id(id)
        if produto is None:
            raise NotFoundError("Produto não encontrado")
        return jsonify(ok(produto_serializer.one(produto))), 200

    def criar(self):
        dados = validar_produto(request.get_json(silent=True))
        produto_id = self._produtos.criar(**dados)
        return jsonify(ok({"id": produto_id}, mensagem="Produto criado")), 201

    def atualizar(self, id):
        # A existência é checada antes da validação para preservar o 404 do
        # contrato original mesmo quando o corpo também é inválido.
        if self._produtos.buscar_por_id(id) is None:
            raise NotFoundError("Produto não encontrado")

        dados = validar_produto(request.get_json(silent=True))
        self._produtos.atualizar(id, **dados)
        return jsonify(mensagem("Produto atualizado")), 200

    def deletar(self, id):
        if self._produtos.buscar_por_id(id) is None:
            raise NotFoundError("Produto não encontrado")

        self._produtos.deletar(id)
        return jsonify(mensagem("Produto deletado")), 200
