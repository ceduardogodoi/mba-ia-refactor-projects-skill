"""Fábrica de conexões com escopo de requisição.

Substitui o singleton global de módulo. Cada requisição recebe sua própria
conexão, fechada no teardown do app context — sem `check_same_thread=False` e
sem estado compartilhado entre threads.
"""
import sqlite3

from flask import current_app, g

_CONN_KEY = "db_conn"


class Database:
    def __init__(self, path):
        self.path = path

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        # SQLite ignora foreign keys por padrão, e por conexão.
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def init_app(app, database):
    app.extensions["database"] = database
    app.teardown_appcontext(close_connection)


def get_connection():
    """Conexão da requisição corrente. É esta função que os models recebem."""
    if _CONN_KEY not in g:
        g.db_conn = current_app.extensions["database"].connect()
    return g.db_conn


def close_connection(exception=None):
    conn = g.pop(_CONN_KEY, None)
    if conn is not None:
        conn.close()
