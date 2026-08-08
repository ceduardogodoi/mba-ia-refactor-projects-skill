"""Acesso a dados e regras de usuário.

A senha nunca sai deste módulo em claro, e a verificação é feita em Python com
comparação de hash — não dentro da query, como antes.
"""
from src.domain.constants import TipoUsuario
from src.infra.security import hash_senha, senha_confere

CAMPOS = "id, nome, email, tipo, criado_em"


class UsuarioModel:
    def __init__(self, connection_provider):
        self._conn = connection_provider

    def listar(self):
        return self._conn().execute(f"SELECT {CAMPOS} FROM usuarios").fetchall()

    def contar(self):
        return self._conn().execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]

    def buscar_por_id(self, usuario_id):
        return self._conn().execute(
            f"SELECT {CAMPOS} FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()

    def buscar_por_email(self, email):
        return self._conn().execute(
            "SELECT id, nome, email, senha, tipo, criado_em FROM usuarios WHERE email = ?",
            (email,),
        ).fetchone()

    def criar(self, nome, email, senha, tipo=TipoUsuario.CLIENTE):
        conn = self._conn()
        cursor = conn.execute(
            "INSERT INTO usuarios (nome, email, senha, tipo) VALUES (?, ?, ?, ?)",
            (nome, email, hash_senha(senha), str(tipo)),
        )
        conn.commit()
        return cursor.lastrowid

    def autenticar(self, email, senha):
        """Devolve a linha do usuário ou None.

        Não distingue email inexistente de senha errada: o custo do hash é pago
        nos dois caminhos e o chamador recebe a mesma resposta.
        """
        usuario = self.buscar_por_email(email)
        if usuario is None:
            senha_confere(senha, None)
            return None
        if not senha_confere(senha, usuario["senha"]):
            return None
        return usuario
