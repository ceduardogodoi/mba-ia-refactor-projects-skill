"""Contrato externo de pedido, incluindo os itens aninhados."""

CAMPOS_PEDIDO = ("id", "usuario_id", "status", "total", "criado_em")
CAMPOS_ITEM = ("produto_id", "produto_nome", "quantidade", "preco_unitario")


def one(pedido):
    payload = {campo: pedido[campo] for campo in CAMPOS_PEDIDO}
    payload["itens"] = [
        {campo: item[campo] for campo in CAMPOS_ITEM} for item in pedido["itens"]
    ]
    return payload


def many(pedidos):
    return [one(pedido) for pedido in pedidos]


def criacao(resultado):
    return {"pedido_id": resultado["pedido_id"], "total": resultado["total"]}
