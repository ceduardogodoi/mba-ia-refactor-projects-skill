"""Queries de User, na API 2.0 do SQLAlchemy."""
from sqlalchemy import func

from src.infra.database import db
from src.models.task import Task
from src.models.user import User


class UserRepository:
    def listar_com_contagem(self):
        """Usuário + total de tasks em uma query.

        Antes, `len(u.tasks)` dentro do for disparava um lazy load por usuário.
        """
        linhas = db.session.execute(
            db.select(User, func.count(Task.id))
            .select_from(User)
            .outerjoin(Task, Task.user_id == User.id)
            .group_by(User.id)
            .order_by(User.id)
        ).all()
        return [(usuario, total) for usuario, total in linhas]

    def buscar(self, user_id):
        return db.session.get(User, user_id)

    def buscar_por_email(self, email):
        return db.session.scalar(db.select(User).where(User.email == email))

    def contar(self):
        return db.session.scalar(db.select(func.count()).select_from(User))

    def criar(self, name, email, password, role):
        usuario = User()
        usuario.name = name
        usuario.email = email
        usuario.set_password(password)
        usuario.role = role
        db.session.add(usuario)
        db.session.commit()
        return usuario

    def atualizar(self, usuario, dados):
        for campo, valor in dados.items():
            if campo == "password":
                usuario.set_password(valor)
            else:
                setattr(usuario, campo, valor)
        db.session.commit()
        return usuario

    def deletar(self, usuario):
        """As tasks vão junto por ON DELETE CASCADE, não por um loop na rota."""
        db.session.delete(usuario)
        db.session.commit()
