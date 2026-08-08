'use strict';

const { NotFoundError, PaymentDeclinedError } = require('../domain/errors');
const { validateCheckout } = require('../schemas/checkoutSchema');

/**
 * Use case de checkout.
 *
 * Era um aninhamento de cinco níveis de callback dentro de `setupRoutes`. Agora
 * é o caminho feliz em linha reta: validar, buscar, cobrar, matricular.
 */
class CheckoutController {
  constructor({ users, courses, enrollments, payments, cache }) {
    this._users = users;
    this._courses = courses;
    this._enrollments = enrollments;
    this._payments = payments;
    this._cache = cache;
  }

  async checkout(req, res) {
    const input = validateCheckout(req.body);

    const course = await this._courses.findActiveById(input.courseId);
    if (!course) throw new NotFoundError('Curso não encontrado');

    const existingUser = await this._users.findByEmail(input.email);

    // A cobrança acontece antes de qualquer escrita. No original o usuário era
    // criado primeiro, então um pagamento recusado deixava a conta órfã.
    const payment = await this._payments.charge({
      cardNumber: input.cardNumber,
      amount: course.price,
      courseId: course.id,
    });
    if (!payment.approved) throw new PaymentDeclinedError('Pagamento recusado');

    const enrollment = await this._enrollments.enroll({
      user: existingUser,
      course,
      payment,
      createUser: existingUser ? null : (tx) => this._users.create(input, tx),
    });

    this._cache.set(`last_checkout_${enrollment.user.id}`, course.title);

    res.status(200).json({ msg: 'Sucesso', enrollment_id: enrollment.id });
  }
}

module.exports = { CheckoutController };
