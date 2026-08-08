"""Script para popular o banco com dados iniciais.

As senhas continuam sendo as mesmas, mas agora são gravadas com pbkdf2 e salt
em vez de MD5.
"""
from datetime import timedelta

from app import app
from src.domain.constants import TaskStatus, UserRole
from src.infra.database import db, utc_now
from src.models import Category, Task, User

USUARIOS = [
    ("João Silva", "joao@email.com", "1234", UserRole.ADMIN),
    ("Maria Santos", "maria@email.com", "abcd", UserRole.USER),
    ("Pedro Oliveira", "pedro@email.com", "pass", UserRole.MANAGER),
]

CATEGORIAS = [
    ("Backend", "Tarefas de backend", "#3498db"),
    ("Frontend", "Tarefas de frontend", "#2ecc71"),
    ("DevOps", "Tarefas de infraestrutura", "#e74c3c"),
    ("Bug", "Correção de bugs", "#e67e22"),
]


def _tasks(agora):
    return [
        {"title": "Implementar autenticação JWT", "description": "Adicionar autenticação real com JWT",
         "status": TaskStatus.PENDING, "priority": 1, "user_id": 1, "category_id": 1,
         "due_date": agora - timedelta(days=3)},
        {"title": "Criar tela de login", "description": "Tela de login responsiva",
         "status": TaskStatus.IN_PROGRESS, "priority": 2, "user_id": 2, "category_id": 2,
         "due_date": agora + timedelta(days=5)},
        {"title": "Configurar CI/CD", "description": "Pipeline com GitHub Actions",
         "status": TaskStatus.DONE, "priority": 2, "user_id": 3, "category_id": 3,
         "tags": "devops,ci,github"},
        {"title": "Corrigir bug no filtro de busca", "description": "Filtro não funciona com caracteres especiais",
         "status": TaskStatus.PENDING, "priority": 1, "user_id": 1, "category_id": 4,
         "due_date": agora - timedelta(days=1)},
        {"title": "Adicionar paginação na API", "description": "Endpoints retornam todos os registros",
         "status": TaskStatus.PENDING, "priority": 3, "user_id": 1, "category_id": 1,
         "due_date": agora + timedelta(days=10)},
        {"title": "Escrever testes unitários", "description": "Cobertura mínima de 80%",
         "status": TaskStatus.PENDING, "priority": 2, "user_id": 2, "category_id": 1},
        {"title": "Documentar API com Swagger", "description": "Gerar documentação automática",
         "status": TaskStatus.CANCELLED, "priority": 4, "user_id": 3, "category_id": 1},
        {"title": "Refatorar models", "description": "Melhorar organização dos models",
         "status": TaskStatus.IN_PROGRESS, "priority": 3, "user_id": 2, "category_id": 1,
         "tags": "refactor,tech-debt"},
        {"title": "Configurar monitoramento", "description": "Prometheus + Grafana",
         "status": TaskStatus.PENDING, "priority": 4, "user_id": 3, "category_id": 3,
         "due_date": agora + timedelta(days=20)},
        {"title": "Melhorar validações de input", "description": "Usar marshmallow ou pydantic",
         "status": TaskStatus.PENDING, "priority": 3, "user_id": 1, "category_id": 1,
         "tags": "improvement,validation"},
    ]


def seed_data():
    with app.app_context():
        db.session.execute(db.delete(Task))
        db.session.execute(db.delete(User))
        db.session.execute(db.delete(Category))
        db.session.commit()

        for nome, email, senha, role in USUARIOS:
            usuario = User()
            usuario.name = nome
            usuario.email = email
            usuario.set_password(senha)
            usuario.role = str(role)
            db.session.add(usuario)

        for nome, descricao, cor in CATEGORIAS:
            categoria = Category()
            categoria.name = nome
            categoria.description = descricao
            categoria.color = cor
            db.session.add(categoria)

        db.session.commit()

        for dados in _tasks(utc_now()):
            task = Task()
            task.title = dados["title"]
            task.description = dados["description"]
            task.status = str(dados["status"])
            task.priority = dados["priority"]
            task.user_id = dados["user_id"]
            task.category_id = dados["category_id"]
            if "due_date" in dados:
                task.due_date = dados["due_date"]
            if "tags" in dados:
                task.tags = dados["tags"]
            db.session.add(task)

        db.session.commit()

        print("Seed concluído com sucesso!")
        print(f"  {db.session.scalar(db.select(db.func.count()).select_from(User))} usuários")
        print(f"  {db.session.scalar(db.select(db.func.count()).select_from(Category))} categorias")
        print(f"  {db.session.scalar(db.select(db.func.count()).select_from(Task))} tasks")


if __name__ == "__main__":
    seed_data()
