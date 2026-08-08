"""Model de Task: dados e as regras que dependem apenas de uma task.

`is_overdue()` já existia aqui — e era reimplementado inline em seis handlers de
rota. Agora existe uma implementação e um chamador por caso de uso.
"""
from src.domain.constants import (
    PRIORIDADE_MAX,
    PRIORIDADE_MIN,
    STATUS_ENCERRADOS,
    TaskStatus,
)
from src.infra.database import db, utc_now


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default=str(TaskStatus.PENDING))
    priority = db.Column(db.Integer, default=3)

    # ondelete explícito: apagar um usuário leva as tasks dele; apagar uma
    # categoria apenas desassocia. Antes o primeiro caso era resolvido por um
    # loop na rota e o segundo deixava tasks apontando para um id inexistente.
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    due_date = db.Column(db.DateTime, nullable=True)
    tags = db.Column(db.String(500), nullable=True)

    user = db.relationship("User", back_populates="tasks", passive_deletes=True)
    category = db.relationship("Category", back_populates="tasks", passive_deletes=True)

    # ------------------------------------------------------------------ regras

    def is_overdue(self):
        """Prazo vencido e a task ainda não terminou.

        Dono único desta regra. Chamada pelo serializer e pelos repositórios de
        relatório — nunca reescrita no chamador.
        """
        if self.due_date is None:
            return False
        if self.due_date >= utc_now():
            return False
        return self.status not in STATUS_ENCERRADOS

    @classmethod
    def criterio_atrasada(cls):
        """A mesma regra de `is_overdue()`, expressa como predicado SQL.

        Filtrar no banco exige uma segunda forma da regra — não dá para levar um
        método Python para dentro do WHERE. Ela fica aqui, ao lado da primeira,
        para que as duas mudem juntas; espalhá-la pelos repositórios seria
        reintroduzir a duplicação que a refatoração removeu.
        """
        from sqlalchemy import and_

        return and_(
            cls.due_date.is_not(None),
            cls.due_date < utc_now(),
            cls.status.not_in([str(status) for status in STATUS_ENCERRADOS]),
        )

    def days_overdue(self):
        if not self.is_overdue():
            return 0
        return (utc_now() - self.due_date).days

    def is_high_priority(self):
        from src.domain.constants import PRIORIDADE_ALTA_ATE

        return self.priority is not None and self.priority <= PRIORIDADE_ALTA_ATE

    @property
    def tag_list(self):
        return self.tags.split(",") if self.tags else []

    @tag_list.setter
    def tag_list(self, valores):
        self.tags = ",".join(valores) if isinstance(valores, list) else valores

    @staticmethod
    def status_valido(status):
        return status in TaskStatus.values()

    @staticmethod
    def prioridade_valida(prioridade):
        return PRIORIDADE_MIN <= prioridade <= PRIORIDADE_MAX
