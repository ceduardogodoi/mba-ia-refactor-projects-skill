'use strict';

/** Dados de curso. */
class CourseModel {
  constructor(db) {
    this._db = db;
  }

  findActiveById(id) {
    return this._db.get(
      'SELECT id, title, price FROM courses WHERE id = ? AND active = 1',
      [id]
    );
  }
}

module.exports = { CourseModel };
