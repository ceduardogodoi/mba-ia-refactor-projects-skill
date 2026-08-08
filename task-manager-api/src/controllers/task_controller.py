"""Use cases de Task.

Valida, orquestra, escolhe status code e serializa. Não escreve query e não
recalcula regra que o model já tem.
"""
from flask import jsonify, request

from src.domain.errors import NotFoundError
from src.schemas.validators import (
    validar_filtros_task,
    validar_task_atualizacao,
    validar_task_criacao,
)
from src.serializers import task_serializer


class TaskController:
    def __init__(self, tasks, users, categories, notifications):
        self._tasks = tasks
        self._users = users
        self._categories = categories
        self._notifications = notifications

    def listar(self):
        return jsonify(task_serializer.many_full(self._tasks.listar())), 200

    def obter(self, task_id):
        return jsonify(task_serializer.full(self._exigir(task_id))), 200

    def buscar(self):
        filtros = validar_filtros_task(request.args)
        return jsonify(task_serializer.many_basic(self._tasks.buscar_filtrado(**filtros))), 200

    def criar(self):
        dados = validar_task_criacao(request.get_json(silent=True))
        self._exigir_relacoes(dados)

        task = self._tasks.criar(dados)
        if task.user_id:
            self._notifications.task_atribuida(task)
        return jsonify(task_serializer.basic(task)), 201

    def atualizar(self, task_id):
        # A existência é checada antes da validação, para preservar o 404 do
        # contrato original mesmo quando o corpo também é inválido.
        task = self._exigir(task_id)
        dados = validar_task_atualizacao(request.get_json(silent=True))
        self._exigir_relacoes(dados)

        return jsonify(task_serializer.basic(self._tasks.atualizar(task, dados))), 200

    def deletar(self, task_id):
        self._tasks.deletar(self._exigir(task_id))
        return jsonify({"message": "Task deletada com sucesso"}), 200

    def estatisticas(self):
        por_status = self._tasks.contar_por_status()
        total = self._tasks.contar()
        concluidas = por_status.get("done", 0)

        return jsonify({
            "total": total,
            "pending": por_status.get("pending", 0),
            "in_progress": por_status.get("in_progress", 0),
            "done": concluidas,
            "cancelled": por_status.get("cancelled", 0),
            "overdue": self._tasks.contar_atrasadas(),
            "completion_rate": round((concluidas / total) * 100, 2) if total > 0 else 0,
        }), 200

    # ------------------------------------------------------------------ apoio

    def _exigir(self, task_id):
        task = self._tasks.buscar(task_id)
        if task is None:
            raise NotFoundError("Task não encontrada")
        return task

    def _exigir_relacoes(self, dados):
        if dados.get("user_id") and self._users.buscar(dados["user_id"]) is None:
            raise NotFoundError("Usuário não encontrado")
        if dados.get("category_id") and self._categories.buscar(dados["category_id"]) is None:
            raise NotFoundError("Categoria não encontrada")
