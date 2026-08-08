'use strict';

const express = require('express');

const { BoundedCache } = require('./infra/cache');
const { buildLogger } = require('./infra/logger');
const { connect, enableForeignKeys } = require('./infra/database');
const { createSchema, seedIfEmpty } = require('./infra/schema');

const { UserModel } = require('./models/userModel');
const { CourseModel } = require('./models/courseModel');
const { EnrollmentModel } = require('./models/enrollmentModel');

const { StubPaymentService } = require('./services/paymentService');

const { CheckoutController } = require('./controllers/checkoutController');
const { ReportController } = require('./controllers/reportController');
const { UserController } = require('./controllers/userController');

const { buildRoutes } = require('./routes');
const { securityHeaders } = require('./middlewares/security');
const { buildRequestLogger } = require('./middlewares/requestLogger');
const { buildErrorHandler, notFoundHandler } = require('./middlewares/errorHandler');

/**
 * Composition root.
 *
 * Único lugar que sabe como as peças se encaixam. Não define rota, não contém
 * regra de negócio e não abre banco por conta própria — apenas constrói e liga.
 *
 * Exporta a app sem chamar listen(): quem escuta é `server.js`. Essa separação
 * é o que torna a aplicação testável sem subir porta.
 */
async function createApp(config, { logger = buildLogger({ level: config.logLevel }) } = {}) {
  const db = connect(config.databaseFile);
  await enableForeignKeys(db);
  await createSchema(db);
  if (config.seedOnBoot && (await seedIfEmpty(db))) {
    logger.info('dados iniciais carregados');
  }

  const users = new UserModel(db);
  const courses = new CourseModel(db);
  const enrollments = new EnrollmentModel(db);
  const payments = new StubPaymentService(logger);
  const cache = new BoundedCache(config.cacheMaxEntries);

  const app = express();
  app.disable('x-powered-by');

  app.use(securityHeaders);
  app.use(buildRequestLogger(logger));
  app.use(express.json({ limit: config.maxBodySize }));

  app.use(buildRoutes({
    checkout: new CheckoutController({ users, courses, enrollments, payments, cache }),
    report: new ReportController({ enrollments }),
    user: new UserController({ users, logger }),
  }));

  app.use(notFoundHandler);
  app.use(buildErrorHandler(logger)); // sempre por último

  app.locals.db = db;
  app.locals.logger = logger;
  return app;
}

module.exports = { createApp };
