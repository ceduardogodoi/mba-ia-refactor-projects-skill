'use strict';

/**
 * Cache com limite explícito.
 *
 * Substitui o `globalCache = {}` de módulo, que crescia indefinidamente e era
 * exportado por referência. Agora é um objeto injetado, com tamanho máximo e
 * política de remoção — o que torna o vazamento de memória impossível por
 * construção em vez de improvável por sorte.
 */
class BoundedCache {
  constructor(maxEntries = 1000) {
    this._maxEntries = maxEntries;
    this._entries = new Map();
  }

  set(key, value) {
    if (this._entries.has(key)) this._entries.delete(key);
    this._entries.set(key, value);

    while (this._entries.size > this._maxEntries) {
      // Map preserva ordem de inserção: o primeiro é o mais antigo.
      this._entries.delete(this._entries.keys().next().value);
    }
  }

  get(key) {
    return this._entries.get(key);
  }

  get size() {
    return this._entries.size;
  }
}

module.exports = { BoundedCache };
