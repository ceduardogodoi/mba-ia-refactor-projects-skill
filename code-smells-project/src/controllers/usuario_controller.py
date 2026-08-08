"""Use cases de usuário e autenticação."""
from flask import jsonify, request

from src.domain.errors import NotFoundError, UnauthorizedError
from src.schemas.validators import validar_login, validar_usuario
from src.serializers import usuario_serializer
from src.serializers.response import ok


class UsuarioController:
    def __init__(self, usuario_model, logger):
        self._usuarios = usuario_model
        self._logger = logger

    def listar(self):
        usuarios = self._usuarios.listar()
        return jsonify(ok(usuario_serializer.many(usuarios))), 200

    def obter(self, id):
        usuario = self._usuarios.buscar_por_id(id)
        if usuario is None:
            raise NotFoundError("Usuário não encontrado")
        return jsonify(ok(usuario_serializer.one(usuario))), 200

    def criar(self):
        dados = validar_usuario(request.get_json(silent=True))
        usuario_id = self._usuarios.criar(**dados)
        self._logger.info("usuário criado", extra={"usuario_id": usuario_id})
        return jsonify(ok({"id": usuario_id})), 201

    def login(self):
        credenciais = validar_login(request.get_json(silent=True))
        usuario = self._usuarios.autenticar(**credenciais)

        if usuario is None:
            # Sem distinguir email inexistente de senha errada, e sem registrar o
            # email tentado em texto puro.
            self._logger.warning("tentativa de login rejeitada")
            raise UnauthorizedError("Email ou senha inválidos")

        self._logger.info("login efetuado", extra={"usuario_id": usuario["id"]})
        return jsonify(ok(usuario_serializer.sessao(usuario), mensagem="Login OK")), 200
