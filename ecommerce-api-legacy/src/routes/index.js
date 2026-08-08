'use strict';

const express = require('express');

const { asyncHandler } = require('../middlewares/errorHandler');

/**
 * Camada de roteamento: método + path -> controller.
 *
 * Nenhuma regra, nenhuma validação, nenhum acesso a dados. Os 3 endpoints
 * originais, com os mesmos métodos e paths.
 */
function buildRoutes({ checkout, report, user }) {
  const router = express.Router();

  router.post('/api/checkout', asyncHandler(checkout.checkout.bind(checkout)));
  router.get('/api/admin/financial-report', asyncHandler(report.financial.bind(report)));
  router.delete('/api/users/:id', asyncHandler(user.remove.bind(user)));

  return router;
}

module.exports = { buildRoutes };
