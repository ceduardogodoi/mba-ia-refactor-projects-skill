"""Use cases de Category.

Estava dentro de `report_routes.py`, que também não era um controller. Agora
tem módulo próprio, com o nome do domínio que representa.
"""
from flask import jsonify, request

from src.domain.errors import NotFoundError
from src.schemas.validators import (
    validar_categoria_atualizacao,
    validar_categoria_criacao,
)
from src.serializers import category_serializer


class CategoryController:
    def __init__(self, categories):
        self._categories = categories

    def listar(self):
        pares = self._categories.listar_com_contagem()
        return jsonify(category_serializer.many_com_contagem(pares)), 200

    def criar(self):
        dados = validar_categoria_criacao(request.get_json(silent=True))
        categoria = self._categories.criar(**dados)
        return jsonify(category_serializer.publico(categoria)), 201

    def atualizar(self, cat_id):
        categoria = self._exigir(cat_id)
        dados = validar_categoria_atualizacao(request.get_json(silent=True))
        return jsonify(category_serializer.publico(
            self._categories.atualizar(categoria, dados)
        )), 200

    def deletar(self, cat_id):
        # As tasks associadas têm category_id anulado por ON DELETE SET NULL,
        # em vez de ficarem apontando para um id inexistente.
        self._categories.deletar(self._exigir(cat_id))
        return jsonify({"message": "Categoria deletada"}), 200

    def _exigir(self, cat_id):
        categoria = self._categories.buscar(cat_id)
        if categoria is None:
            raise NotFoundError("Categoria não encontrada")
        return categoria
