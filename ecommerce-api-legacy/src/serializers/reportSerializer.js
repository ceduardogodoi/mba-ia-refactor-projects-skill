'use strict';

const { STATUS_PAID } = require('../services/paymentService');

const ALUNO_DESCONHECIDO = 'Unknown';

/**
 * Agrupa as linhas achatadas do JOIN no formato do relatório financeiro.
 *
 * Único lugar que define a forma externa do relatório. A ordem passa a ser
 * determinística (id do curso), enquanto no original dependia da ordem de
 * conclusão dos callbacks.
 */
function financialReport(rows) {
  const porCurso = new Map();

  for (const row of rows) {
    if (!porCurso.has(row.course_id)) {
      porCurso.set(row.course_id, { course: row.course_title, revenue: 0, students: [] });
    }
    const curso = porCurso.get(row.course_id);

    // LEFT JOIN: curso sem matrícula traz enrollment_id nulo.
    if (row.enrollment_id === null) continue;

    if (row.payment_status === STATUS_PAID) {
      curso.revenue += row.payment_amount;
    }

    curso.students.push({
      student: row.student_name ?? ALUNO_DESCONHECIDO,
      paid: row.payment_amount ?? 0,
    });
  }

  return [...porCurso.values()];
}

module.exports = { financialReport };
