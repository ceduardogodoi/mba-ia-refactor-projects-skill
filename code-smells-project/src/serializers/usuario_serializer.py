"""Contrato externo de usuário.

Allowlist, nunca denylist: um campo novo na tabela não vaza por omissão. É por
isso que `senha` não pode voltar a aparecer no payload por acidente.
"""

CAMPOS_PUBLICOS = ("id", "nome", "email", "tipo", "criado_em")

# O login devolve um subconjunto — sem `criado_em`, como no contrato original.
CAMPOS_SESSAO = ("id", "nome", "email", "tipo")


def one(row):
    return {campo: row[campo] for campo in CAMPOS_PUBLICOS}


def many(rows):
    return [one(row) for row in rows]


def sessao(row):
    return {campo: row[campo] for campo in CAMPOS_SESSAO}
