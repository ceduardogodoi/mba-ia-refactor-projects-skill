"""Composition root.

Único lugar que sabe como as peças se encaixam. Não define rota, não contém
regra de negócio e não acessa banco — apenas constrói e liga.

O `db.create_all()` era executado no escopo de módulo do antigo `app.py`, como
efeito colateral do import. Agora é uma etapa nomeada da criação da aplicação.
"""
from flask import Flask
from flask_cors import CORS

from src.controllers.category_controller import CategoryController
from src.controllers.report_controller import ReportController
from src.controllers.system_controller import SystemController
from src.controllers.task_controller import TaskController
from src.controllers.user_controller import UserController
from src.infra import database
from src.infra.database import create_schema, db
from src.middlewares import error_handler, security
from src.middlewares.logging import build_logger
from src.repositories.category_repository import CategoryRepository
from src.repositories.task_repository import TaskRepository
from src.repositories.user_repository import UserRepository
from src.services.notification_service import (
    NotificationService,
    NullMailer,
    SmtpMailer,
)
from src.views.routes import build_blueprints

# Import necessário para que o SQLAlchemy registre os models antes do create_all.
from src import models  # noqa: F401


def create_app(settings):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["DEBUG"] = settings.debug
    app.config["MAX_CONTENT_LENGTH"] = settings.max_content_length

    logger = build_logger(settings)

    # Origens restritas por configuração — antes era CORS(app), que libera todas.
    CORS(app, origins=settings.cors_origins)
    security.register(app)

    database.init_app(app, settings)
    create_schema(app)

    tasks = TaskRepository()
    users = UserRepository()
    categories = CategoryRepository()

    mailer = SmtpMailer(settings, logger) if settings.notifications_enabled else NullMailer()
    notifications = NotificationService(mailer, logger, settings.notifications_enabled)

    blueprints = build_blueprints(
        task=TaskController(tasks, users, categories, notifications),
        user=UserController(users, tasks, logger),
        category=CategoryController(categories),
        report=ReportController(tasks, users, categories),
        system=SystemController(),
    )
    for blueprint in blueprints:
        app.register_blueprint(blueprint)

    error_handler.register(app, logger)

    logger.info("aplicação inicializada", extra={"database": settings.database_uri})
    return app


__all__ = ["create_app", "db"]
