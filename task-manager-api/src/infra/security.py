"""Hashing de senha.

Substitui `hashlib.md5(pwd.encode()).hexdigest()`, que é sem salt e reversível
por rainbow table — o hash exposto por `GET /users/1` era
`81dc9bdb52d04dc20036dbd8313ed055`, o MD5 de `1234`.

Usa `werkzeug.security`, que já vem com o Flask: pbkdf2-sha256 com salt por
usuário. Nenhuma dependência nova.
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
        # Hashes MD5 gravados antes da refatoração caem aqui e não autenticam.
        return False
