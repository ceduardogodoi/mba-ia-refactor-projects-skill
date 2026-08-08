'use strict';

/**
 * Logger com níveis, sem dependência nova.
 *
 * Substitui os console.log espalhados, que não tinham nível, timestamp nem
 * contexto — e que foram o mecanismo pelo qual número de cartão e chave de
 * gateway acabaram em stdout.
 */

const LEVELS = { error: 0, warn: 1, info: 2, debug: 3 };

function buildLogger({ level = 'info', stream = process.stdout } = {}) {
  const threshold = LEVELS[level] ?? LEVELS.info;

  function emit(levelName, message, context) {
    if (LEVELS[levelName] > threshold) return;
    const entry = {
      ts: new Date().toISOString(),
      level: levelName,
      message,
      ...(context ? { context } : {}),
    };
    stream.write(`${JSON.stringify(entry)}\n`);
  }

  return {
    error: (message, context) => emit('error', message, context),
    warn: (message, context) => emit('warn', message, context),
    info: (message, context) => emit('info', message, context),
    debug: (message, context) => emit('debug', message, context),
  };
}

module.exports = { buildLogger };
