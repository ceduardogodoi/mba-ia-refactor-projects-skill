"""Contrato externo de User.

Allowlist, nunca denylist. O antigo `User.to_dict()` incluía `password`, e era
por isso que o hash MD5 vazava em cinco endpoints — inclusive no `GET /users/<id>`,
que é público. Um campo novo na tabela não vira público por omissão.
"""
from src.serializers import task_serializer

CAMPOS_PUBLICOS = ("id", "name", "email", "role", "active")


def publico(user):
    dados = {campo: getattr(user, campo) for campo in CAMPOS_PUBLICOS}
    dados["created_at"] = str(user.created_at) if user.created_at else None
    return dados


def com_contagem(user, total_tasks):
    return {**publico(user), "task_count": total_tasks}


def com_tasks(user, tasks):
    return {**publico(user), "tasks": task_serializer.many_basic(tasks)}


def many_com_contagem(pares):
    return [com_contagem(user, total) for user, total in pares]
