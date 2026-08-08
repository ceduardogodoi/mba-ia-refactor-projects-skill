'use strict';

const { hashPassword } = require('../infra/security');
const { ConflictError } = require('../domain/errors');

/** Dados e regras de usuário. Não conhece Express, req nem res. */
class UserModel {
  constructor(db) {
    this._db = db;
  }

  findByEmail(email) {
    return this._db.get('SELECT id, name, email FROM users WHERE email = ?', [email]);
  }

  findById(id) {
    return this._db.get('SELECT id, name, email FROM users WHERE id = ?', [id]);
  }

  async create({ name, email, password }, executor = this._db) {
    const passwordHash = await hashPassword(password);
    const { lastID } = await executor.run(
      'INSERT INTO users (name, email, pass) VALUES (?, ?, ?)',
      [name, email, passwordHash]
    );
    return { id: lastID, name, email };
  }

  /**
   * Remove o usuário. A foreign key com ON DELETE RESTRICT impede a remoção
   * quando existem matrículas — antes a operação seguia em frente e deixava
   * matrículas e pagamentos órfãos.
   */
  async remove(id) {
    try {
      const { changes } = await this._db.run('DELETE FROM users WHERE id = ?', [id]);
      return changes;
    } catch (err) {
      if (String(err.code).includes('SQLITE_CONSTRAINT')) {
        throw new ConflictError(
          'Usuário não pode ser removido: existem matrículas que o referenciam'
        );
      }
      throw err;
    }
  }
}

module.exports = { UserModel };
