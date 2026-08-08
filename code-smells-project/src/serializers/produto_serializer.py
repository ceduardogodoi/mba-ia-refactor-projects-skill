"""Contrato externo de produto — allowlist explícita de campos públicos."""

CAMPOS_PUBLICOS = (
    "id",
    "nome",
    "descricao",
    "preco",
    "estoque",
    "categoria",
    "ativo",
    "criado_em",
)


def one(row):
    return {campo: row[campo] for campo in CAMPOS_PUBLICOS}


def many(rows):
    return [one(row) for row in rows]
