'use strict';

/**
 * Security headers.
 *
 * `helmet` cobriria isto, mas é dependência nova — a regra da skill é só
 * adicionar dependência quando o finding não puder ser resolvido sem ela, e
 * quatro headers não justificam. Registrado antes das rotas.
 */
function securityHeaders(req, res, next) {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('X-Permitted-Cross-Domain-Policies', 'none');
  res.removeHeader('X-Powered-By');
  next();
}

module.exports = { securityHeaders };
