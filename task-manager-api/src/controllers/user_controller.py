"""Use cases de User e autenticação."""
from flask import jsonify, request

from src.domain.errors import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from src.schemas.validators import (
    validar_login,
    validar_usuario_atualizacao,
    validar_usuario_criacao,
)
from src.serializers import task_serializer, user_serializer


class UserController:
    def __init__(self, users, tasks, logger):
        self._users = users
        self._tasks = tasks
        self._logger = logger

    def listar(self):
        return jsonify(user_serializer.many_com_contagem(self._users.listar_com_contagem())), 200

    def obter(self, user_id):
        usuario = self._exigir(user_id)
        tasks = self._tasks.listar_por_usuario(user_id)
        return jsonify(user_serializer.com_tasks(usuario, tasks)), 200

    def criar(self):
        dados = validar_usuario_criacao(request.get_json(silent=True))

        if self._users.buscar_por_email(dados["email"]):
            raise ConflictError("Email já cadastrado")

        usuario = self._users.criar(**dados)
        self._logger.info("usuário criado", extra={"user_id": usuario.id})
        return jsonify(user_serializer.publico(usuario)), 201

    def atualizar(self, user_id):
        usuario = self._exigir(user_id)
        dados = validar_usuario_atualizacao(request.get_json(silent=True))

        if "email" in dados:
            existente = self._users.buscar_por_email(dados["email"])
            if existente and existente.id != user_id:
                raise ConflictError("Email já cadastrado")

        return jsonify(user_serializer.publico(self._users.atualizar(usuario, dados))), 200

    def deletar(self, user_id):
        # As tasks vão junto por ON DELETE CASCADE — antes era um loop na rota.
        self._users.deletar(self._exigir(user_id))
        self._logger.info("usuário removido", extra={"user_id": user_id})
        return jsonify({"message": "Usuário deletado com sucesso"}), 200

    def tasks(self, user_id):
        self._exigir(user_id)
        tasks = self._tasks.listar_por_usuario(user_id)
        return jsonify(task_serializer.many_resumo(tasks)), 200

    def login(self):
        credenciais = validar_login(request.get_json(silent=True))
        usuario = self._users.buscar_por_email(credenciais["email"])

        # Não distingue email inexistente de senha errada.
        if usuario is None or not usuario.check_password(credenciais["password"]):
            self._logger.warning("tentativa de login rejeitada")
            raise UnauthorizedError("Credenciais inválidas")

        if not usuario.active:
            raise ForbiddenError("Usuário inativo")

        self._logger.info("login efetuado", extra={"user_id": usuario.id})
        # O campo `token` foi removido: ele era 'fake-jwt-token-' + id, derivável
        # do id do usuário. Enquanto não houver autenticação real, é melhor não
        # existir do que fingir existir.
        return jsonify({
            "message": "Login realizado com sucesso",
            "user": user_serializer.publico(usuario),
        }), 200

    def _exigir(self, user_id):
        usuario = self._users.buscar(user_id)
        if usuario is None:
            raise NotFoundError("Usuário não encontrado")
        return usuario
