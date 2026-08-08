"""Acesso a dados e regras de pedido.

Concentra o que estava espalhado entre `models.py` e `controllers.py`: cálculo do
total, reserva de estoque, transação do use case e as faixas de desconto do
relatório de vendas.
"""
from src.domain.constants import (
    FAIXAS_DESCONTO,
    PRODUTO_DESCONHECIDO,
    StatusPedido,
)
from src.domain.errors import ValidationError

_SQL_PEDIDOS_COM_ITENS = """
SELECT p.id, p.usuario_id, p.status, p.total, p.criado_em,
       ip.produto_id, ip.quantidade, ip.preco_unitario,
       pr.nome AS produto_nome
FROM pedidos p
LEFT JOIN itens_pedido ip ON ip.pedido_id = p.id
LEFT JOIN produtos pr ON pr.id = ip.produto_id
{where}
ORDER BY p.id, ip.id
"""


class PedidoModel:
    def __init__(self, connection_provider):
        self._conn = connection_provider

    # ------------------------------------------------------------------ leitura

    def contar(self):
        return self._conn().execute("SELECT COUNT(*) FROM pedidos").fetchone()[0]

    def listar_todos(self):
        rows = self._conn().execute(_SQL_PEDIDOS_COM_ITENS.format(where="")).fetchall()
        return _agrupar_por_pedido(rows)

    def listar_por_usuario(self, usuario_id):
        rows = self._conn().execute(
            _SQL_PEDIDOS_COM_ITENS.format(where="WHERE p.usuario_id = ?"), (usuario_id,)
        ).fetchall()
        return _agrupar_por_pedido(rows)

    # ------------------------------------------------------------------- escrita

    def criar(self, usuario_id, itens):
        """Cria pedido, itens e baixa de estoque em uma única transação.

        A baixa é condicional (`WHERE estoque >= ?`): se outra requisição consumiu
        o estoque entre a validação e a escrita, o UPDATE não afeta linha nenhuma
        e a transação inteira é desfeita.
        """
        conn = self._conn()

        produtos = {}
        total = 0
        for item in itens:
            produto_id = item["produto_id"]
            quantidade = item["quantidade"]
            produto = conn.execute(
                "SELECT id, nome, preco, estoque FROM produtos WHERE id = ?", (produto_id,)
            ).fetchone()
            if produto is None:
                raise ValidationError(f"Produto {produto_id} não encontrado")
            if produto["estoque"] < quantidade:
                raise ValidationError(f"Estoque insuficiente para {produto['nome']}")
            produtos[produto_id] = produto
            total = total + (produto["preco"] * quantidade)

        try:
            cursor = conn.execute(
                "INSERT INTO pedidos (usuario_id, status, total) VALUES (?, ?, ?)",
                (usuario_id, str(StatusPedido.PENDENTE), total),
            )
            pedido_id = cursor.lastrowid

            for item in itens:
                produto = produtos[item["produto_id"]]
                quantidade = item["quantidade"]

                conn.execute(
                    "INSERT INTO itens_pedido "
                    "(pedido_id, produto_id, quantidade, preco_unitario) VALUES (?, ?, ?, ?)",
                    (pedido_id, produto["id"], quantidade, produto["preco"]),
                )

                baixa = conn.execute(
                    "UPDATE produtos SET estoque = estoque - ? WHERE id = ? AND estoque >= ?",
                    (quantidade, produto["id"], quantidade),
                )
                if baixa.rowcount == 0:
                    raise ValidationError(f"Estoque insuficiente para {produto['nome']}")

            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return {"pedido_id": pedido_id, "total": total}

    def atualizar_status(self, pedido_id, novo_status):
        conn = self._conn()
        conn.execute(
            "UPDATE pedidos SET status = ? WHERE id = ?", (str(novo_status), pedido_id)
        )
        conn.commit()
        return True

    # ---------------------------------------------------------------- relatório

    def relatorio_vendas(self):
        conn = self._conn()

        totais = conn.execute(
            "SELECT COUNT(*) AS quantidade, COALESCE(SUM(total), 0) AS faturamento FROM pedidos"
        ).fetchone()
        total_pedidos = totais["quantidade"]
        faturamento = totais["faturamento"]

        por_status = {
            row["status"]: row["quantidade"]
            for row in conn.execute(
                "SELECT status, COUNT(*) AS quantidade FROM pedidos GROUP BY status"
            ).fetchall()
        }

        desconto = calcular_desconto(faturamento)

        return {
            "total_pedidos": total_pedidos,
            "faturamento_bruto": round(faturamento, 2),
            "desconto_aplicavel": round(desconto, 2),
            "faturamento_liquido": round(faturamento - desconto, 2),
            "pedidos_pendentes": por_status.get(str(StatusPedido.PENDENTE), 0),
            "pedidos_aprovados": por_status.get(str(StatusPedido.APROVADO), 0),
            "pedidos_cancelados": por_status.get(str(StatusPedido.CANCELADO), 0),
            "ticket_medio": round(faturamento / total_pedidos, 2) if total_pedidos > 0 else 0,
        }


def calcular_desconto(faturamento):
    """Faixa de desconto sobre o faturamento bruto. Regra de negócio, testável isolada."""
    for minimo, percentual in FAIXAS_DESCONTO:
        if faturamento > minimo:
            return faturamento * percentual
    return 0


def _agrupar_por_pedido(rows):
    """Converte o resultado achatado do JOIN em agregados de pedido.

    Substitui o padrão 1 + N + N×M de queries por uma única ida ao banco.
    """
    pedidos = {}
    ordem = []
    for row in rows:
        pedido_id = row["id"]
        if pedido_id not in pedidos:
            pedidos[pedido_id] = {
                "id": pedido_id,
                "usuario_id": row["usuario_id"],
                "status": row["status"],
                "total": row["total"],
                "criado_em": row["criado_em"],
                "itens": [],
            }
            ordem.append(pedido_id)
        # LEFT JOIN: pedido sem itens traz produto_id nulo.
        if row["produto_id"] is not None:
            pedidos[pedido_id]["itens"].append({
                "produto_id": row["produto_id"],
                "produto_nome": row["produto_nome"] or PRODUTO_DESCONHECIDO,
                "quantidade": row["quantidade"],
                "preco_unitario": row["preco_unitario"],
            })
    return [pedidos[pedido_id] for pedido_id in ordem]
