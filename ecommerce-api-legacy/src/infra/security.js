'use strict';

const crypto = require('node:crypto');

/**
 * Hashing de senha com scrypt do node:crypto — sem dependência nova.
 *
 * Substitui `badCrypto`, cuja saída dependia apenas do primeiro byte e meio da
 * senha: badCrypto('senhaforte') === badCrypto('sen'), e 200.000 senhas
 * distintas produziam um único hash.
 */

const KEY_LENGTH = 64;
const SALT_BYTES = 16;

function scrypt(password, salt) {
  return new Promise((resolve, reject) => {
    crypto.scrypt(password, salt, KEY_LENGTH, (err, derived) =>
      err ? reject(err) : resolve(derived)
    );
  });
}

async function hashPassword(password) {
  const salt = crypto.randomBytes(SALT_BYTES).toString('hex');
  const derived = await scrypt(password, salt);
  return `scrypt$${salt}$${derived.toString('hex')}`;
}

async function verifyPassword(password, stored) {
  if (typeof stored !== 'string') return false;

  const [scheme, salt, expected] = stored.split('$');
  if (scheme !== 'scrypt' || !salt || !expected) {
    // Hashes gravados por badCrypto caem aqui e simplesmente não autenticam.
    return false;
  }

  const derived = await scrypt(password, salt);
  const expectedBuffer = Buffer.from(expected, 'hex');
  if (expectedBuffer.length !== derived.length) return false;

  return crypto.timingSafeEqual(expectedBuffer, derived);
}

/** Deixa apenas os últimos quatro dígitos — o máximo que PCI-DSS permite registrar. */
function maskCardNumber(cardNumber) {
  const digits = String(cardNumber ?? '');
  if (digits.length <= 4) return '****';
  return `${'*'.repeat(digits.length - 4)}${digits.slice(-4)}`;
}

module.exports = { hashPassword, verifyPassword, maskCardNumber };
