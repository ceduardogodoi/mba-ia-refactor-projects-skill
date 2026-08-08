"""Erros de domínio.

As camadas internas levantam estes tipos; só o middleware de erro decide status
code. Nenhuma camada abaixo do controller devolve tupla (payload, status).
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
    """Violação de regra de integridade — ex.: apagar registro ainda referenciado."""
    status = 409


class TooManyRequestsError(DomainError):
    status = 429
