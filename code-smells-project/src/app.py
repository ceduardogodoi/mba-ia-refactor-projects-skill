"""Composition root.

Único lugar que sabe como as peças se encaixam. Não define rota, não contém
regra de negócio e não acessa banco — apenas constrói e conecta.
"""
from flask import Flask
from flask_cors import CORS

from src.controllers.admin_controller import AdminController
from src.controllers.pedido_controller import PedidoController
from src.controllers.produto_controller import ProdutoController
from src.controllers.relatorio_controller import RelatorioController
from src.controllers.sistema_controller import SistemaController
from src.controllers.usuario_controller import UsuarioController
from src.infra import database as db
from src.infra.database import Database, get_connection
from src.infra.schema import criar_schema, popular_se_vazio
from src.middlewares import error_handler, rate_limit, security
from src.middlewares.logging import build_logger
from src.models.admin_model import AdminModel
from src.models.pedido_model import PedidoModel
from src.models.produto_model import ProdutoModel
from src.models.usuario_model import UsuarioModel
from src.services.notification_service import NotificationService
from src.views.routes import build_blueprints


def create_app(settings):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["DEBUG"] = settings.debug
    app.config["MAX_CONTENT_LENGTH"] = settings.max_content_length

    logger = build_logger(settings)

    # Origens restritas por configuração — antes era CORS(app), que libera todas.
    CORS(app, origins=settings.cors_origins)
    security.register(app)

    database = Database(settings.db_path)
    db.init_app(app, database)
    _bootstrap(database, settings, logger)

    produto_model = ProdutoModel(get_connection)
    usuario_model = UsuarioModel(get_connection)
    pedido_model = PedidoModel(get_connection)
    admin_model = AdminModel(get_connection)

    notificacoes = NotificationService(logger)

    blueprints = build_blueprints(
        produto=ProdutoController(produto_model),
        usuario=UsuarioController(usuario_model, logger),
        pedido=PedidoController(pedido_model, notificacoes),
        relatorio=RelatorioController(pedido_model),
        admin=AdminController(admin_model, settings, logger),
        sistema=SistemaController(produto_model, usuario_model, pedido_model),
    )
    for blueprint in blueprints:
        app.register_blueprint(blueprint)

    # Depois dos blueprints: o limiter identifica a rota por `request.endpoint`,
    # que só existe depois que as rotas estão registradas.
    rate_limit.register(app, settings, logger)

    error_handler.register(app, logger)

    logger.info("aplicação inicializada", extra={"db_path": settings.db_path})
    return app


def _bootstrap(database, settings, logger):
    """Cria schema e popula dados iniciais.

    Antes isto acontecia como efeito colateral de obter uma conexão. Agora é uma
    etapa explícita da composição, com conexão própria e de vida curta.
    """
    conn = database.connect()
    try:
        criar_schema(conn)
        if settings.seed_on_boot and popular_se_vazio(conn):
            logger.info("dados iniciais carregados")
    finally:
        conn.close()
