"""Hashing de senha.

Usa `werkzeug.security`, que já vem com o Flask — pbkdf2-sha256 com salt por
usuário. Nenhuma dependência nova é introduzida.
"""
from werkzeug.security import check_password_hash, generate_password_hash


def hash_senha(senha_em_claro):
    return generate_password_hash(senha_em_claro)


def senha_confere(senha_em_claro, hash_armazenado):
    if not hash_armazenado:
        return False
    try:
        return check_password_hash(hash_armazenado, senha_em_claro)
    except ValueError:
        # Hash em formato desconhecido — registros gravados em plaintext antes da
        # refatoração caem aqui e simplesmente não autenticam.
        return False
