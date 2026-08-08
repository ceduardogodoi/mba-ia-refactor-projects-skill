"""Constantes de domínio.

Substituem os literais que estavam espalhados por controllers.py, models.py e
database.py. Os valores de string são exatamente os que trafegam na API e são
persistidos no banco — mudá-los é mudança de contrato.
"""
from enum import StrEnum


class StatusPedido(StrEnum):
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    ENVIADO = "enviado"
    ENTREGUE = "entregue"
    CANCELADO = "cancelado"


class TipoUsuario(StrEnum):
    CLIENTE = "cliente"
    ADMIN = "admin"


# Tupla de str puras: a mensagem de erro de categoria inválida expõe esta lista
# no payload, e o formato precisa continuar idêntico ao original.
CATEGORIAS_VALIDAS = (
    "informatica",
    "moveis",
    "vestuario",
    "geral",
    "eletronicos",
    "livros",
)

CATEGORIA_PADRAO = "geral"

NOME_PRODUTO_MIN = 2
NOME_PRODUTO_MAX = 200

# (faturamento mínimo, percentual de desconto) — avaliado de cima para baixo.
FAIXAS_DESCONTO = (
    (10_000, 0.10),
    (5_000, 0.05),
    (1_000, 0.02),
)

PRODUTO_DESCONHECIDO = "Desconhecido"
