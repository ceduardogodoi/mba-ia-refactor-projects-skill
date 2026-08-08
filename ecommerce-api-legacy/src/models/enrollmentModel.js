'use strict';

/** Matrícula, pagamento e trilha de auditoria — sempre juntos, sempre atômicos. */
class EnrollmentModel {
  constructor(db) {
    this._db = db;
  }

  /**
   * Cria matrícula, registro de pagamento e log de auditoria em uma única
   * transação. Antes eram três escritas encadeadas por callback, sem BEGIN:
   * uma falha na segunda deixava matrícula sem pagamento.
   *
   * `createUser` é opcional e roda dentro da mesma transação, para que um
   * checkout que falha no pagamento não deixe o usuário criado para trás.
   */
  async enroll({ user, course, payment, createUser }) {
    return this._db.transaction(async (tx) => {
      const enrolledUser = createUser ? await createUser(tx) : user;

      const enrollment = await tx.run(
        'INSERT INTO enrollments (user_id, course_id) VALUES (?, ?)',
        [enrolledUser.id, course.id]
      );

      await tx.run(
        'INSERT INTO payments (enrollment_id, amount, status) VALUES (?, ?, ?)',
        [enrollment.lastID, course.price, payment.status]
      );

      await tx.run(
        "INSERT INTO audit_logs (action, created_at) VALUES (?, datetime('now'))",
        [`Checkout curso ${course.id} por ${enrolledUser.id}`]
      );

      return { id: enrollment.lastID, user: enrolledUser, course };
    });
  }

  /**
   * Relatório financeiro em uma única query.
   *
   * Antes eram 1 + N + 2*N*M idas ao banco, coordenadas por contadores
   * decrementados à mão dentro de callbacks aninhados em três níveis.
   */
  findReportRows() {
    return this._db.all(`
      SELECT c.id    AS course_id,
             c.title AS course_title,
             e.id    AS enrollment_id,
             u.name  AS student_name,
             p.amount AS payment_amount,
             p.status AS payment_status
      FROM courses c
      LEFT JOIN enrollments e ON e.course_id = c.id
      LEFT JOIN users       u ON u.id = e.user_id
      LEFT JOIN payments    p ON p.enrollment_id = e.id
      ORDER BY c.id, e.id
    `);
  }
}

module.exports = { EnrollmentModel };
