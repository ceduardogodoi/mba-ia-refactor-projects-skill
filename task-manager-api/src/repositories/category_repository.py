"""Queries de Category, na API 2.0 do SQLAlchemy."""
from sqlalchemy import func

from src.infra.database import db
from src.models.category import Category
from src.models.task import Task


class CategoryRepository:
    def listar_com_contagem(self):
        """Categoria + total de tasks em uma query, no lugar de um count() por categoria."""
        linhas = db.session.execute(
            db.select(Category, func.count(Task.id))
            .select_from(Category)
            .outerjoin(Task, Task.category_id == Category.id)
            .group_by(Category.id)
            .order_by(Category.id)
        ).all()
        return [(categoria, total) for categoria, total in linhas]

    def buscar(self, category_id):
        return db.session.get(Category, category_id)

    def contar(self):
        return db.session.scalar(db.select(func.count()).select_from(Category))

    def criar(self, name, description, color):
        categoria = Category()
        categoria.name = name
        categoria.description = description
        categoria.color = color
        db.session.add(categoria)
        db.session.commit()
        return categoria

    def atualizar(self, categoria, dados):
        for campo, valor in dados.items():
            setattr(categoria, campo, valor)
        db.session.commit()
        return categoria

    def deletar(self, categoria):
        """As tasks associadas têm category_id anulado por ON DELETE SET NULL.

        Antes elas ficavam apontando para um id que não existia mais.
        """
        db.session.delete(categoria)
        db.session.commit()
