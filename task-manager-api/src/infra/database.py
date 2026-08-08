"""Sessão do SQLAlchemy e utilitários de tempo.

O `utc_now()` daqui substitui as 18 chamadas de `datetime.utcnow()`, que o
Python 3.12 marcou como deprecated.

Sobre a escolha de manter datetimes *naive*: a substituição canônica é
`datetime.now(timezone.utc)`, que devolve um datetime *aware*. Em SQLite isso
não funciona de ponta a ponta — o banco não tem tipo com timezone, então mesmo
com `DateTime(timezone=True)` os valores voltam naive na leitura, e comparar
naive com aware levanta TypeError. Manter UTC naive preserva exatamente a
semântica anterior e elimina o warning. Migrar para aware exige um banco com
suporte real a timezone e está registrado como ação posterior.
"""
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utc_now():
    """Agora em UTC, naive — equivalente a `datetime.utcnow()`, sem a deprecação."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def init_app(app, settings):
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_uri
    db.init_app(app)

    if settings.database_uri.startswith("sqlite"):
        _enable_sqlite_foreign_keys()


def _enable_sqlite_foreign_keys():
    """SQLite ignora foreign keys por padrão, e por conexão.

    Sem isto, os `ondelete` declarados nos models são documentação e não
    restrição — foi assim que apagar uma categoria deixava tasks órfãs.
    """
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "connect")
    def _set_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()


def create_schema(app):
    with app.app_context():
        db.create_all()
