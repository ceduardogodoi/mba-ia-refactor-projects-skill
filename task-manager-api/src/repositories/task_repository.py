"""Queries de Task, na API 2.0 do SQLAlchemy.

Substitui os 56 usos de `Model.query` (Legacy Query API) e os 16 de
`Model.query.get()`, ambos emitindo warning em runtime sob SQLAlchemy 2.0.
Também é onde os padrões N+1 são resolvidos: eager loading para as relações
acessadas em loop e agregação no banco para os contadores.
"""
from datetime import timedelta

from sqlalchemy import case, func, or_
from sqlalchemy.orm import joinedload

from src.domain.constants import STATUS_ENCERRADOS, TaskStatus
from src.infra.database import db, utc_now
from src.models.category import Category
from src.models.task import Task
from src.models.user import User


def _com_relacoes(stmt):
    """Carrega user e category junto — antes eram duas queries por task."""
    return stmt.options(joinedload(Task.user), joinedload(Task.category))


class TaskRepository:
    # --------------------------------------------------------------- leitura

    def listar(self):
        return db.session.scalars(_com_relacoes(db.select(Task))).unique().all()

    def buscar(self, task_id):
        return db.session.get(Task, task_id)

    def listar_por_usuario(self, user_id):
        return db.session.scalars(
            _com_relacoes(db.select(Task).where(Task.user_id == user_id))
        ).unique().all()

    def buscar_filtrado(self, termo=None, status=None, prioridade=None, user_id=None):
        stmt = _com_relacoes(db.select(Task))
        if termo:
            stmt = stmt.where(
                or_(Task.title.like(f"%{termo}%"), Task.description.like(f"%{termo}%"))
            )
        if status:
            stmt = stmt.where(Task.status == status)
        if prioridade is not None:
            stmt = stmt.where(Task.priority == prioridade)
        if user_id is not None:
            stmt = stmt.where(Task.user_id == user_id)
        return db.session.scalars(stmt).unique().all()

    # ------------------------------------------------------------- agregação

    def contar(self):
        return db.session.scalar(db.select(func.count()).select_from(Task))

    def contar_por_status(self):
        """Um GROUP BY no lugar de quatro count() sequenciais."""
        linhas = db.session.execute(
            db.select(Task.status, func.count()).group_by(Task.status)
        ).all()
        return {status: total for status, total in linhas}

    def contar_por_prioridade(self):
        """Um GROUP BY no lugar de cinco count() sequenciais."""
        linhas = db.session.execute(
            db.select(Task.priority, func.count()).group_by(Task.priority)
        ).all()
        return {prioridade: total for prioridade, total in linhas}

    def listar_atrasadas(self):
        """Filtra no banco em vez de carregar tudo e testar em Python.

        O critério vem do model — este repositório não reescreve a regra.
        """
        stmt = db.select(Task).where(Task.criterio_atrasada()).order_by(Task.id)
        return db.session.scalars(stmt).all()

    def contar_atrasadas(self):
        return len(self.listar_atrasadas())

    def contar_criadas_desde(self, dias):
        limite = utc_now() - timedelta(days=dias)
        return db.session.scalar(
            db.select(func.count()).select_from(Task).where(Task.created_at >= limite)
        )

    def contar_concluidas_desde(self, dias):
        limite = utc_now() - timedelta(days=dias)
        return db.session.scalar(
            db.select(func.count())
            .select_from(Task)
            .where(Task.status == str(TaskStatus.DONE))
            .where(Task.updated_at >= limite)
        )

    def produtividade_por_usuario(self):
        """Total e concluídas por usuário em uma query.

        Antes era uma query por usuário, dentro de um for.
        """
        concluida = case((Task.status == str(TaskStatus.DONE), 1), else_=0)
        linhas = db.session.execute(
            db.select(
                User.id,
                User.name,
                func.count(Task.id),
                func.coalesce(func.sum(concluida), 0),
            )
            .select_from(User)
            .outerjoin(Task, Task.user_id == User.id)
            .group_by(User.id, User.name)
            .order_by(User.id)
        ).all()
        return [
            {"user_id": uid, "user_name": nome, "total": total, "concluidas": concluidas}
            for uid, nome, total, concluidas in linhas
        ]

    def estatisticas_do_usuario(self, user_id):
        tasks = self.listar_por_usuario(user_id)
        contagem = {status: 0 for status in TaskStatus.values()}
        for task in tasks:
            if task.status in contagem:
                contagem[task.status] += 1
        return {
            "tasks": tasks,
            "por_status": contagem,
            "atrasadas": sum(1 for t in tasks if t.is_overdue()),
            "alta_prioridade": sum(1 for t in tasks if t.is_high_priority()),
        }

    # --------------------------------------------------------------- escrita

    def criar(self, dados):
        task = Task()
        self._aplicar(task, dados)
        db.session.add(task)
        db.session.commit()
        return task

    def atualizar(self, task, dados):
        self._aplicar(task, dados)
        task.updated_at = utc_now()
        db.session.commit()
        return task

    def deletar(self, task):
        db.session.delete(task)
        db.session.commit()

    @staticmethod
    def _aplicar(task, dados):
        for campo, valor in dados.items():
            if campo == "tags":
                task.tag_list = valor
            else:
                setattr(task, campo, valor)


class CategoriaLookup:
    """Consultas auxiliares usadas na validação de task."""

    def existe(self, category_id):
        return db.session.get(Category, category_id) is not None
