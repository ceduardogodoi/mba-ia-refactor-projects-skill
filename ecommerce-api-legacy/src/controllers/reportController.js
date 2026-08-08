'use strict';

const { financialReport } = require('../serializers/reportSerializer');

/** Use case de relatório financeiro. */
class ReportController {
  constructor({ enrollments }) {
    this._enrollments = enrollments;
  }

  async financial(req, res) {
    const rows = await this._enrollments.findReportRows();
    res.status(200).json(financialReport(rows));
  }
}

module.exports = { ReportController };
