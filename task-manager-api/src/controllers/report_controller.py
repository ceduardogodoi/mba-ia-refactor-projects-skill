"""Use cases de relatório.

`summary_report` tinha 90 linhas e nove blocos de agregação inline, cada um com
sua própria query. A agregação passou para o repositório; aqui resta a montagem
do relatório.
"""
from flask import jsonify

from src.domain.constants import DIAS_ATIVIDADE_RECENTE, ROTULOS_PRIORIDADE, TaskStatus
from src.domain.errors import NotFoundError
from src.serializers import user_serializer


class ReportController:
    def __init__(self, tasks, users, categories):
        self._tasks = tasks
        self._users = users
        self._categories = categories

    def resumo(self):
        por_status = self._tasks.contar_por_status()
        por_prioridade = self._tasks.contar_por_prioridade()
        atrasadas = self._tasks.listar_atrasadas()

        from src.infra.database import utc_now

        return jsonify({
            "generated_at": str(utc_now()),
            "overview": {
                "total_tasks": self._tasks.contar(),
                "total_users": self._users.contar(),
                "total_categories": self._categories.contar(),
            },
            "tasks_by_status": {
                status: por_status.get(status, 0) for status in TaskStatus.values()
            },
            "tasks_by_priority": {
                rotulo: por_prioridade.get(nivel, 0)
                for nivel, rotulo in ROTULOS_PRIORIDADE.items()
            },
            "overdue": {
                "count": len(atrasadas),
                "tasks": [
                    {
                        "id": task.id,
                        "title": task.title,
                        "due_date": str(task.due_date),
                        "days_overdue": task.days_overdue(),
                    }
                    for task in atrasadas
                ],
            },
            "recent_activity": {
                "tasks_created_last_7_days": self._tasks.contar_criadas_desde(
                    DIAS_ATIVIDADE_RECENTE
                ),
                "tasks_completed_last_7_days": self._tasks.contar_concluidas_desde(
                    DIAS_ATIVIDADE_RECENTE
                ),
            },
            "user_productivity": [
                {
                    "user_id": linha["user_id"],
                    "user_name": linha["user_name"],
                    "total_tasks": linha["total"],
                    "completed_tasks": linha["concluidas"],
                    "completion_rate": _percentual(linha["concluidas"], linha["total"]),
                }
                for linha in self._tasks.produtividade_por_usuario()
            ],
        }), 200

    def por_usuario(self, user_id):
        usuario = self._users.buscar(user_id)
        if usuario is None:
            raise NotFoundError("Usuário não encontrado")

        stats = self._tasks.estatisticas_do_usuario(user_id)
        total = len(stats["tasks"])
        concluidas = stats["por_status"][str(TaskStatus.DONE)]

        return jsonify({
            "user": {
                "id": usuario.id,
                "name": usuario.name,
                "email": usuario.email,
            },
            "statistics": {
                "total_tasks": total,
                "done": concluidas,
                "pending": stats["por_status"][str(TaskStatus.PENDING)],
                "in_progress": stats["por_status"][str(TaskStatus.IN_PROGRESS)],
                "cancelled": stats["por_status"][str(TaskStatus.CANCELLED)],
                "overdue": stats["atrasadas"],
                "high_priority": stats["alta_prioridade"],
                "completion_rate": _percentual(concluidas, total),
            },
        }), 200


def _percentual(parte, total):
    return round((parte / total) * 100, 2) if total > 0 else 0
