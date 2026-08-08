"""Notificações de pedido.

Antes eram `print` inline no controller, o que fazia o sistema parecer que
notificava sem notificar. A implementação continua sendo apenas registro em log —
mas agora existe uma interface explícita para substituir por email/SMS/push reais
sem tocar no controller.
"""


class NotificationService:
    def __init__(self, logger):
        self._logger = logger

    def pedido_criado(self, pedido_id, usuario_id):
        self._logger.info(
            "notificação de pedido criado", extra={"pedido_id": pedido_id, "usuario_id": usuario_id}
        )

    def status_alterado(self, pedido_id, novo_status):
        self._logger.info(
            "notificação de mudança de status",
            extra={"pedido_id": pedido_id, "status": str(novo_status)},
        )
