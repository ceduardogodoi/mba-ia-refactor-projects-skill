'use strict';

const sqlite3 = require('sqlite3');

/**
 * Fronteira de infraestrutura do banco.
 *
 * O driver de callback é promisificado aqui, uma única vez. Nenhuma camada
 * acima desta vê callback — é o que permite que controllers sejam escritos com
 * async/await e que exceções voltem para a pilha do Express, onde o middleware
 * de erro consegue tratá-las.
 *
 * `verbose()` foi removido: ele adiciona stack trace a toda operação e só faz
 * sentido em depuração local.
 */
function connect(databaseFile) {
  const db = new sqlite3.Database(databaseFile);

  const api = {
    get(sql, params = []) {
      return new Promise((resolve, reject) => {
        db.get(sql, params, (err, row) => (err ? reject(err) : resolve(row)));
      });
    },

    all(sql, params = []) {
      return new Promise((resolve, reject) => {
        db.all(sql, params, (err, rows) => (err ? reject(err) : resolve(rows)));
      });
    },

    // `function` e não arrow: lastID e changes vivem no `this` do callback.
    run(sql, params = []) {
      return new Promise((resolve, reject) => {
        db.run(sql, params, function onDone(err) {
          if (err) return reject(err);
          resolve({ lastID: this.lastID, changes: this.changes });
        });
      });
    },

    exec(sql) {
      return new Promise((resolve, reject) => {
        db.exec(sql, (err) => (err ? reject(err) : resolve()));
      });
    },

    /** Envolve o callback em uma transação, com rollback em qualquer falha. */
    async transaction(work) {
      await api.run('BEGIN');
      try {
        const result = await work(api);
        await api.run('COMMIT');
        return result;
      } catch (err) {
        await api.run('ROLLBACK').catch(() => {});
        throw err;
      }
    },

    close() {
      return new Promise((resolve) => db.close(() => resolve()));
    },
  };

  return api;
}

/** SQLite ignora foreign keys por padrão — precisa ser ligado por conexão. */
async function enableForeignKeys(db) {
  await db.run('PRAGMA foreign_keys = ON');
}

module.exports = { connect, enableForeignKeys };
