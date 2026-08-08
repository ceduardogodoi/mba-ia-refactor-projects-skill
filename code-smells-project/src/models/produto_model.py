"""Acesso a dados e regras de produto.

Não conhece Flask, `request` nem status code — devolve linhas do banco e levanta
erros de domínio.
"""
import sqlite3

from src.domain.errors import ConflictError

CAMPOS = "id, nome, descricao, preco, estoque, categoria, ativo, criado_em"


class ProdutoModel:
    def __init__(self, connection_provider):
        self._conn = connection_provider

    def listar(self):
        return self._conn().execute(f"SELECT {CAMPOS} FROM produtos").fetchall()

    def contar(self):
        return self._conn().execute("SELECT COUNT(*) FROM produtos").fetchone()[0]

    def buscar_por_id(self, produto_id):
        return self._conn().execute(
            f"SELECT {CAMPOS} FROM produtos WHERE id = ?", (produto_id,)
        ).fetchone()

    def buscar(self, termo=None, categoria=None, preco_min=None, preco_max=None):
        """Filtros dinâmicos: a estrutura da query é montada, os valores nunca."""
        sql = [f"SELECT {CAMPOS} FROM produtos WHERE 1=1"]
        params = []

        if termo:
            sql.append("AND (nome LIKE ? OR descricao LIKE ?)")
            params.extend([f"%{termo}%", f"%{termo}%"])
        if categoria:
            sql.append("AND categoria = ?")
            params.append(categoria)
        if preco_min is not None:
            sql.append("AND preco >= ?")
            params.append(preco_min)
        if preco_max is not None:
            sql.append("AND preco <= ?")
            params.append(preco_max)

        return self._conn().execute(" ".join(sql), params).fetchall()

    def criar(self, nome, descricao, preco, estoque, categoria):
        conn = self._conn()
        cursor = conn.execute(
            "INSERT INTO produtos (nome, descricao, preco, estoque, categoria) "
            "VALUES (?, ?, ?, ?, ?)",
            (nome, descricao, preco, estoque, categoria),
        )
        conn.commit()
        return cursor.lastrowid

    def atualizar(self, produto_id, nome, descricao, preco, estoque, categoria):
        conn = self._conn()
        conn.execute(
            "UPDATE produtos SET nome = ?, descricao = ?, preco = ?, estoque = ?, "
            "categoria = ? WHERE id = ?",
            (nome, descricao, preco, estoque, categoria, produto_id),
        )
        conn.commit()
        return True

    def deletar(self, produto_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise ConflictError(
                "Produto não pode ser removido: existem pedidos que o referenciam"
            ) from exc
        return True
