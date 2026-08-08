'use strict';

const { ValidationError } = require('../domain/errors');

/**
 * Validação de entrada do checkout.
 *
 * A guarda original testava apenas presença. Um `card` enviado como número JSON
 * passava por ela e quebrava em `cc.startsWith(...)` dentro de um callback do
 * sqlite3 — fora da pilha do Express, o que derrubava o processo inteiro.
 *
 * Os nomes de campo do request (usr, eml, pwd, c_id, card) são contrato público
 * e permanecem inalterados; só os identificadores internos ganham nome.
 */

const MENSAGEM_PADRAO = 'Bad Request';

function texto(valor) {
  return typeof valor === 'string' && valor.trim().length > 0;
}

function inteiroPositivo(valor) {
  return Number.isInteger(valor) && valor > 0;
}

function validateCheckout(body) {
  const dados = body && typeof body === 'object' ? body : {};

  const { usr: name, eml: email, pwd: password, c_id: courseId, card: cardNumber } = dados;

  // Mesma mensagem e mesmo status do original para os campos obrigatórios.
  if (!texto(name) || !texto(email) || !inteiroPositivo(courseId) || !texto(cardNumber)) {
    throw new ValidationError(MENSAGEM_PADRAO);
  }

  // O original caía em badCrypto(p || "123456"), criando conta com senha
  // default quando o campo não vinha. A senha passa a ser obrigatória.
  if (!texto(password)) {
    throw new ValidationError(MENSAGEM_PADRAO);
  }

  if (!/^\d+$/.test(cardNumber)) {
    throw new ValidationError(MENSAGEM_PADRAO);
  }

  return {
    name: name.trim(),
    email: email.trim(),
    password,
    courseId,
    cardNumber: cardNumber.trim(),
  };
}

function validateUserId(raw) {
  const id = Number(raw);
  if (!Number.isInteger(id) || id <= 0) {
    throw new ValidationError('Identificador de usuário inválido');
  }
  return id;
}

module.exports = { validateCheckout, validateUserId };
