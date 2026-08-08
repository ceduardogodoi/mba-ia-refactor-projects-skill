'use strict';

const { DomainError } = require('../domain/errors');

/**
 * Envolve um handler assíncrono para que rejeições cheguem ao middleware de erro.
 *
 * Express 4 não captura rejeição de Promise: sem isto, um `await` que falha
 * deixa a requisição pendurada até o timeout do cliente.
 */
function asyncHandler(handler) {
  return (req, res, next) => Promise.resolve(handler(req, res, next)).catch(next);
}

/**
 * Tratamento de erro centralizado. Deve ser registrado por último, e precisa
 * dos quatro argumentos para que o Express o reconheça como error middleware.
 */
function buildErrorHandler(logger) {
  return function errorHandler(err, req, res, _next) {
    if (err instanceof DomainError) {
      return res.status(err.status).json({ error: err.message });
    }

    // Corpo JSON malformado ou grande demais, levantado por express.json().
    if (err.type === 'entity.parse.failed') {
      return res.status(400).json({ error: 'Bad Request' });
    }
    if (err.type === 'entity.too.large') {
      return res.status(413).json({ error: 'Payload muito grande' });
    }

    logger.error('erro não tratado', {
      method: req.method,
      path: req.originalUrl,
      error: err.message,
      stack: err.stack,
    });
    res.status(500).json({ error: 'Erro interno' });
  };
}

function notFoundHandler(req, res) {
  res.status(404).json({ error: 'Recurso não encontrado' });
}

module.exports = { asyncHandler, buildErrorHandler, notFoundHandler };
