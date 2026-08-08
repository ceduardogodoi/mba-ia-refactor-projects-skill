'use strict';

const { NotFoundError } = require('../domain/errors');
const { validateUserId } = require('../schemas/checkoutSchema');

/** Use case de remoção de usuário. */
class UserController {
  constructor({ users, logger }) {
    this._users = users;
    this._logger = logger;
  }

  /**
   * O original ignorava o erro do driver e respondia 200 com uma mensagem que
   * descrevia a própria corrupção que estava causando. Agora a foreign key
   * bloqueia a remoção (409), a ausência do usuário é 404, e uma falha real
   * chega ao middleware de erro.
   */
  async remove(req, res) {
    const id = validateUserId(req.params.id);

    const removed = await this._users.remove(id);
    if (removed === 0) throw new NotFoundError('Usuário não encontrado');

    this._logger.info('usuário removido', { userId: id });
    res.status(200).json({ msg: 'Usuário removido', user_id: id });
  }
}

module.exports = { UserController };
