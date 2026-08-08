"""Contrato externo de Category."""

CAMPOS_PUBLICOS = ("id", "name", "description", "color")


def publico(category):
    dados = {campo: getattr(category, campo) for campo in CAMPOS_PUBLICOS}
    dados["created_at"] = str(category.created_at) if category.created_at else None
    return dados


def com_contagem(category, total_tasks):
    return {**publico(category), "task_count": total_tasks}


def many_com_contagem(pares):
    return [com_contagem(category, total) for category, total in pares]
