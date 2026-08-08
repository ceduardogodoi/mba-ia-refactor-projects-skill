'use strict';

const { config } = require('./config');
const { createApp } = require('./app');

/**
 * Entry point. Só sobe o servidor — a composição vive em `app.js`.
 *
 * O host passa a ser explícito e default 127.0.0.1. Antes o `listen(port)` sem
 * host escutava em todas as interfaces, expondo na rede local uma API sem
 * autenticação.
 */
async function main() {
  const app = await createApp(config);
  const logger = app.locals.logger;

  const server = app.listen(config.port, config.host, () => {
    logger.info('servidor iniciado', {
      host: config.host,
      port: config.port,
      env: config.env,
    });
  });

  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.on(signal, () => {
      logger.info('encerrando', { signal });
      server.close(() => process.exit(0));
    });
  }
}

main().catch((err) => {
  process.stderr.write(`Falha ao iniciar: ${err.message}\n`);
  process.exit(1);
});
