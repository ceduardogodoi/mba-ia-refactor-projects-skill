'use strict';

const { maskCardNumber } = require('../infra/security');

/**
 * Interface de cobrança.
 *
 * A implementação real ainda não existe. O que existe é o ponto de substituição:
 * o controller depende desta interface, não de um ternário embutido no handler,
 * então trocar o stub por um gateway de verdade não toca em regra de negócio.
 */

const STATUS_PAID = 'PAID';
const STATUS_DENIED = 'DENIED';

/**
 * STUB — não realiza cobrança alguma.
 *
 * Reproduz a decisão do código original (aprova cartões iniciados em 4) para
 * preservar o comportamento observável, mas declara-se explicitamente como stub
 * em `provider`, para que nenhum consumidor confunda isto com cobrança real.
 */
class StubPaymentService {
  constructor(logger) {
    this._logger = logger;
  }

  async charge({ cardNumber, amount, courseId }) {
    // O número do cartão nunca é registrado por inteiro, e a chave do gateway
    // nunca é registrada — era isso que o console.log original fazia.
    this._logger.info('processando cobrança', {
      card: maskCardNumber(cardNumber),
      amount,
      courseId,
      provider: 'stub',
    });

    const approved = cardNumber.startsWith('4');

    return {
      approved,
      status: approved ? STATUS_PAID : STATUS_DENIED,
      provider: 'stub',
    };
  }
}

module.exports = { StubPaymentService, STATUS_PAID, STATUS_DENIED };
