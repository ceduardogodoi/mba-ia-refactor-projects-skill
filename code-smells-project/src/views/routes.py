"""Camada de roteamento.

Tabela de conteúdo da API: método + path -> função de controller. Nenhuma regra,
nenhuma validação, nenhum acesso a dados. Os 19 endpoints originais estão aqui,
com os mesmos métodos e paths.
"""
from flask import Blueprint


def build_blueprints(produto, usuario, pedido, relatorio, admin, sistema):
    return (
        _produtos(produto),
        _usuarios(usuario),
        _pedidos(pedido),
        _relatorios(relatorio),
        _admin(admin),
        _sistema(sistema),
    )


def _produtos(c):
    bp = Blueprint("produtos", __name__)
    bp.add_url_rule("/produtos", "listar", c.listar, methods=["GET"])
    bp.add_url_rule("/produtos/busca", "buscar", c.buscar, methods=["GET"])
    bp.add_url_rule("/produtos/<int:id>", "obter", c.obter, methods=["GET"])
    bp.add_url_rule("/produtos", "criar", c.criar, methods=["POST"])
    bp.add_url_rule("/produtos/<int:id>", "atualizar", c.atualizar, methods=["PUT"])
    bp.add_url_rule("/produtos/<int:id>", "deletar", c.deletar, methods=["DELETE"])
    return bp


def _usuarios(c):
    bp = Blueprint("usuarios", __name__)
    bp.add_url_rule("/usuarios", "listar", c.listar, methods=["GET"])
    bp.add_url_rule("/usuarios/<int:id>", "obter", c.obter, methods=["GET"])
    bp.add_url_rule("/usuarios", "criar", c.criar, methods=["POST"])
    bp.add_url_rule("/login", "login", c.login, methods=["POST"])
    return bp


def _pedidos(c):
    bp = Blueprint("pedidos", __name__)
    bp.add_url_rule("/pedidos", "criar", c.criar, methods=["POST"])
    bp.add_url_rule("/pedidos", "listar", c.listar_todos, methods=["GET"])
    bp.add_url_rule(
        "/pedidos/usuario/<int:usuario_id>", "listar_por_usuario",
        c.listar_por_usuario, methods=["GET"],
    )
    bp.add_url_rule(
        "/pedidos/<int:pedido_id>/status", "atualizar_status",
        c.atualizar_status, methods=["PUT"],
    )
    return bp


def _relatorios(c):
    bp = Blueprint("relatorios", __name__)
    bp.add_url_rule("/relatorios/vendas", "vendas", c.vendas, methods=["GET"])
    return bp


def _admin(c):
    bp = Blueprint("admin", __name__)
    bp.add_url_rule("/admin/reset-db", "resetar_banco", c.resetar_banco, methods=["POST"])
    bp.add_url_rule("/admin/query", "executar_query", c.executar_query, methods=["POST"])
    return bp


def _sistema(c):
    bp = Blueprint("sistema", __name__)
    bp.add_url_rule("/", "index", c.index, methods=["GET"])
    bp.add_url_rule("/health", "health", c.health, methods=["GET"])
    return bp
