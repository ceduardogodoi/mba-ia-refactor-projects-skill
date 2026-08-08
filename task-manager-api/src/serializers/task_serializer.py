"""Contrato externo de Task.

Único lugar que decide o formato de saída. Antes a conversão era feita campo a
campo em quatro funções diferentes, e o resultado divergia entre endpoints.

O `overdue` vem de `Task.is_overdue()` — a regra tem um dono, e este é um
chamador. As seis cópias inline que existiam nas rotas foram removidas.
"""


def _data(valor):
    return str(valor) if valor is not None else None


def basic(task):
    """Formato base, equivalente ao antigo `Task.to_dict()`."""
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "user_id": task.user_id,
        "category_id": task.category_id,
        "created_at": _data(task.created_at),
        "updated_at": _data(task.updated_at),
        "due_date": _data(task.due_date),
        "tags": task.tag_list,
    }


def full(task):
    """Formato completo, com estado derivado e nomes das relações."""
    return {
        **basic(task),
        "overdue": task.is_overdue(),
        "user_name": task.user.name if task.user else None,
        "category_name": task.category.name if task.category else None,
    }


def resumo(task):
    """Subconjunto usado em `GET /users/<id>/tasks`."""
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "created_at": _data(task.created_at),
        "due_date": _data(task.due_date),
        "overdue": task.is_overdue(),
    }


def many_full(tasks):
    return [full(task) for task in tasks]


def many_basic(tasks):
    return [basic(task) for task in tasks]


def many_resumo(tasks):
    return [resumo(task) for task in tasks]
