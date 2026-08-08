'use strict';

/** Log de acesso, com nível e duração. Sem corpo de request — ele carrega PAN. */
function buildRequestLogger(logger) {
  return function requestLogger(req, res, next) {
    const start = process.hrtime.bigint();

    res.on('finish', () => {
      const ms = Number(process.hrtime.bigint() - start) / 1e6;
      const level = res.statusCode >= 500 ? 'error' : res.statusCode >= 400 ? 'warn' : 'info';
      logger[level]('request', {
        method: req.method,
        path: req.originalUrl,
        status: res.statusCode,
        durationMs: Number(ms.toFixed(1)),
      });
    });

    next();
  };
}

module.exports = { buildRequestLogger };
