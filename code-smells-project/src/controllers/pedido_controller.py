"""Use cases de pedido.

As notificações saíram do handler e passaram a ser um colaborador injetado.
"""
from flask import jsonify, request

from src.schemas.validators import validar_pedido, validar_status_pedido
from src.serializers import pedido_serializer
from src.serializers.response import mensagem, ok


class PedidoController:
    def __init__(self, pedido_model, notification_service):
        self._pedidos = pedido_model
        self._notificacoes = notification_service

    def criar(self):
        dados = validar_pedido(request.get_json(silent=True))
        resultado = self._pedidos.criar(dados["usuario_id"], dados["itens"])

        self._notificacoes.pedido_criado(resultado["pedido_id"], dados["usuario_id"])

        return jsonify(
            ok(pedido_serializer.criacao(resultado), mensagem="Pedido criado com sucesso")
        ), 201

    def listar_todos(self):
        pedidos = self._pedidos.listar_todos()
        return jsonify(ok(pedido_serializer.many(pedidos))), 200

    def listar_por_usuario(self, usuario_id):
        pedidos = self._pedidos.listar_por_usuario(usuario_id)
        return jsonify(ok(pedido_serializer.many(pedidos))), 200

    def atualizar_status(self, pedido_id):
        novo_status = validar_status_pedido(request.get_json(silent=True))
        self._pedidos.atualizar_status(pedido_id, novo_status)

        self._notificacoes.status_alterado(pedido_id, novo_status)

        return jsonify(mensagem("Status atualizado")), 200
