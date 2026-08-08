'use strict';

const { hashPassword } = require('./security');

/**
 * DDL e seed, executados explicitamente na composição.
 *
 * Antes o schema era criado no construtor da God Class e o seed vinha junto,
 * como efeito colateral do require. Agora são etapas nomeadas.
 *
 * As foreign keys que faltavam estão declaradas aqui, com política de ON DELETE
 * explícita: remover um usuário com matrículas passa a ser bloqueado em vez de
 * deixar matrículas e pagamentos órfãos.
 */

const DDL = [
  `CREATE TABLE IF NOT EXISTS users (
     id INTEGER PRIMARY KEY,
     name TEXT NOT NULL,
     email TEXT NOT NULL,
     pass TEXT NOT NULL
   )`,
  `CREATE TABLE IF NOT EXISTS courses (
     id INTEGER PRIMARY KEY,
     title TEXT NOT NULL,
     price REAL NOT NULL,
     active INTEGER NOT NULL DEFAULT 1
   )`,
  `CREATE TABLE IF NOT EXISTS enrollments (
     id INTEGER PRIMARY KEY,
     user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
     course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE RESTRICT
   )`,
  `CREATE TABLE IF NOT EXISTS payments (
     id INTEGER PRIMARY KEY,
     enrollment_id INTEGER NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
     amount REAL NOT NULL,
     status TEXT NOT NULL
   )`,
  `CREATE TABLE IF NOT EXISTS audit_logs (
     id INTEGER PRIMARY KEY,
     action TEXT NOT NULL,
     created_at DATETIME NOT NULL
   )`,
];

const SEED_COURSES = [
  ['Clean Architecture', 997.0, 1],
  ['Docker', 497.0, 1],
];

// A senha do seed continua sendo '123' para não quebrar quem usa esta
// credencial, mas agora é gravada com hash.
const SEED_USER = { name: 'Leonan', email: 'leonan@fullcycle.com.br', password: '123' };

async function createSchema(db) {
  for (const statement of DDL) {
    await db.run(statement);
  }
}

async function seedIfEmpty(db) {
  const { total } = await db.get('SELECT COUNT(*) AS total FROM users');
  if (total > 0) return false;

  const passwordHash = await hashPassword(SEED_USER.password);
  const user = await db.run(
    'INSERT INTO users (name, email, pass) VALUES (?, ?, ?)',
    [SEED_USER.name, SEED_USER.email, passwordHash]
  );

  for (const course of SEED_COURSES) {
    await db.run('INSERT INTO courses (title, price, active) VALUES (?, ?, ?)', course);
  }

  const enrollment = await db.run(
    'INSERT INTO enrollments (user_id, course_id) VALUES (?, ?)',
    [user.lastID, 1]
  );
  await db.run(
    'INSERT INTO payments (enrollment_id, amount, status) VALUES (?, ?, ?)',
    [enrollment.lastID, 997.0, 'PAID']
  );

  return true;
}

module.exports = { createSchema, seedIfEmpty };
