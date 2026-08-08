"""Constantes de domínio.

Substituem os literais espalhados por routes/ e o conjunto paralelo que existia
em utils/helpers.py — definido, exportado e nunca usado. Os valores de string
são exatamente os que trafegam na API e são persistidos, então mudá-los é
mudança de contrato.
"""
from enum import StrEnum


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"

    @classmethod
    def values(cls):
        return tuple(str(status) for status in cls)


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    MANAGER = "manager"

    @classmethod
    def values(cls):
        return tuple(str(role) for role in cls)


# Status em que um prazo vencido não conta como atraso: a task já terminou.
STATUS_ENCERRADOS = (TaskStatus.DONE, TaskStatus.CANCELLED)

TITULO_MIN = 3
TITULO_MAX = 200

PRIORIDADE_MIN = 1
PRIORIDADE_MAX = 5
PRIORIDADE_PADRAO = 3
PRIORIDADE_ALTA_ATE = 2  # prioridade <= 2 conta como "alta" nos relatórios

SENHA_MIN = 4

COR_PADRAO = "#000000"

FORMATO_DATA = "%Y-%m-%d"

DIAS_ATIVIDADE_RECENTE = 7

# Rótulos de prioridade usados no relatório de resumo.
ROTULOS_PRIORIDADE = {
    1: "critical",
    2: "high",
    3: "medium",
    4: "low",
    5: "minimal",
}
