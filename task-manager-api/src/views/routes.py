"""Camada de roteamento.

Tabela de conteúdo da API: método + path -> função de controller. Nenhuma regra,
nenhuma validação, nenhum acesso a dados. Os 22 endpoints originais, com os
mesmos métodos e paths.

Antes, `routes/` continha os controllers, os models e os serializers.
"""
from flask import Blueprint


def build_blueprints(task, user, category, report, system):
    return (
        _tasks(task),
        _users(user),
        _categories(category),
        _reports(report),
        _system(system),
    )


def _tasks(c):
    bp = Blueprint("tasks", __name__)
    bp.add_url_rule("/tasks", "listar", c.listar, methods=["GET"])
    bp.add_url_rule("/tasks", "criar", c.criar, methods=["POST"])
    bp.add_url_rule("/tasks/search", "buscar", c.buscar, methods=["GET"])
    bp.add_url_rule("/tasks/stats", "estatisticas", c.estatisticas, methods=["GET"])
    bp.add_url_rule("/tasks/<int:task_id>", "obter", c.obter, methods=["GET"])
    bp.add_url_rule("/tasks/<int:task_id>", "atualizar", c.atualizar, methods=["PUT"])
    bp.add_url_rule("/tasks/<int:task_id>", "deletar", c.deletar, methods=["DELETE"])
    return bp


def _users(c):
    bp = Blueprint("users", __name__)
    bp.add_url_rule("/users", "listar", c.listar, methods=["GET"])
    bp.add_url_rule("/users", "criar", c.criar, methods=["POST"])
    bp.add_url_rule("/users/<int:user_id>", "obter", c.obter, methods=["GET"])
    bp.add_url_rule("/users/<int:user_id>", "atualizar", c.atualizar, methods=["PUT"])
    bp.add_url_rule("/users/<int:user_id>", "deletar", c.deletar, methods=["DELETE"])
    bp.add_url_rule("/users/<int:user_id>/tasks", "tasks", c.tasks, methods=["GET"])
    bp.add_url_rule("/login", "login", c.login, methods=["POST"])
    return bp


def _categories(c):
    bp = Blueprint("categories", __name__)
    bp.add_url_rule("/categories", "listar", c.listar, methods=["GET"])
    bp.add_url_rule("/categories", "criar", c.criar, methods=["POST"])
    bp.add_url_rule("/categories/<int:cat_id>", "atualizar", c.atualizar, methods=["PUT"])
    bp.add_url_rule("/categories/<int:cat_id>", "deletar", c.deletar, methods=["DELETE"])
    return bp


def _reports(c):
    bp = Blueprint("reports", __name__)
    bp.add_url_rule("/reports/summary", "resumo", c.resumo, methods=["GET"])
    bp.add_url_rule("/reports/user/<int:user_id>", "por_usuario", c.por_usuario, methods=["GET"])
    return bp


def _system(c):
    bp = Blueprint("system", __name__)
    bp.add_url_rule("/", "index", c.index, methods=["GET"])
    bp.add_url_rule("/health", "health", c.health, methods=["GET"])
    return bp
