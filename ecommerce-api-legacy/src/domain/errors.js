'use strict';

/**
 * Erros de domínio.
 *
 * As camadas internas lançam estes tipos; só o middleware de erro decide status
 * code. Nenhuma camada abaixo do controller monta resposta HTTP.
 */

class DomainError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.name = new.target.name;
    this.status = status;
  }
}

class ValidationError extends DomainError {
  constructor(message) { super(message, 400); }
}

class NotFoundError extends DomainError {
  constructor(message) { super(message, 404); }
}

class PaymentDeclinedError extends DomainError {
  constructor(message) { super(message, 400); }
}

class ConflictError extends DomainError {
  constructor(message) { super(message, 409); }
}

module.exports = {
  DomainError,
  ValidationError,
  NotFoundError,
  PaymentDeclinedError,
  ConflictError,
};
