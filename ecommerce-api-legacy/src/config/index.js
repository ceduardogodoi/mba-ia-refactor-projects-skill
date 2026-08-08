'use strict';

/**
 * Única porta de entrada de configuração.
 *
 * Nenhum outro módulo lê process.env. Secrets falham na inicialização quando
 * ausentes — um default para chave de gateway seria a mesma vulnerabilidade com
 * passos a mais.
 */

const TRUE = new Set(['1', 'true', 'yes', 'on']);

function required(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Variável de ambiente obrigatória ausente: ${name}. ` +
      'Copie .env.example para .env e defina um valor.'
    );
  }
  return value;
}

function flag(name, fallback = false) {
  const raw = process.env[name];
  return raw === undefined ? fallback : TRUE.has(raw.trim().toLowerCase());
}

const config = Object.freeze({
  env: process.env.NODE_ENV || 'development',
  host: process.env.HOST || '127.0.0.1',
  port: Number(process.env.PORT || 3000),

  databaseFile: process.env.DATABASE_FILE || ':memory:',
  seedOnBoot: flag('SEED_ON_BOOT', true),

  paymentGatewayKey: required('PAYMENT_GATEWAY_KEY'),

  logLevel: process.env.LOG_LEVEL || 'info',
  maxBodySize: process.env.MAX_BODY_SIZE || '100kb',
  cacheMaxEntries: Number(process.env.CACHE_MAX_ENTRIES || 1000),
});

module.exports = { config };
