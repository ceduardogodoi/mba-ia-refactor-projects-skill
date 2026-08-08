"""Model de User.

O `to_dict()` que existia aqui incluía o campo `password` e era a razão pela
qual o hash vazava em cinco endpoints. A decisão sobre o que é público passou
para o serializer, com allowlist.
"""
from src.domain.constants import UserRole
from src.infra.database import db, utc_now
from src.infra.security import hash_senha, senha_confere


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default=str(UserRole.USER))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)

    tasks = db.relationship(
        "Task", back_populates="user", passive_deletes=True
    )

    def set_password(self, senha_em_claro):
        self.password = hash_senha(senha_em_claro)

    def check_password(self, senha_em_claro):
        return senha_confere(senha_em_claro, self.password)

    def is_admin(self):
        return self.role == UserRole.ADMIN
