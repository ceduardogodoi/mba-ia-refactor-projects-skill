"""Erros de domínio.

As camadas internas levantam estes tipos; só o middleware decide status code.
Substitui os doze blocos `except:` que devolviam 'Erro interno' sem registrar
nada.
"""


class DomainError(Exception):
    status = 400

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class ValidationError(DomainError):
    status = 400


class NotFoundError(DomainError):
    status = 404


class UnauthorizedError(DomainError):
    status = 401


class ForbiddenError(DomainError):
    status = 403


class ConflictError(DomainError):
    status = 409
