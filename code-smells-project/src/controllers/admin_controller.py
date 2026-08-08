"""Rotas administrativas, atrás de feature flag.

As rotas continuam existindo e mantendo método e path — mas respondem 403
enquanto `ADMIN_ENDPOINTS_ENABLED` estiver desligada, que é o default. Ligar é
uma decisão explícita de quem opera o serviço.
"""
from flask import jsonify, request

from src.domain.errors import ForbiddenError, ValidationError
from src.serializers.response import ok


class AdminController:
    def __init__(self, admin_model, settings, logger):
        self._admin = admin_model
        self._settings = settings
        self._logger = logger

    def _garantir_habilitado(self, operacao):
        if not self._settings.admin_endpoints_enabled:
            self._logger.warning("acesso negado a rota administrativa",
                                 extra={"operacao": operacao})
            raise ForbiddenError(
                "Endpoint administrativo desabilitado. "
                "Defina ADMIN_ENDPOINTS_ENABLED=true para habilitar."
            )

    def resetar_banco(self):
        self._garantir_habilitado("reset-db")
        self._admin.limpar_dados()
        self._logger.warning("banco de dados resetado via rota administrativa")
        return jsonify({"mensagem": "Banco de dados resetado", "sucesso": True}), 200

    def executar_query(self):
        self._garantir_habilitado("query")

        dados = request.get_json(silent=True) or {}
        query = dados.get("sql", "")
        if not query:
            raise ValidationError("Query não informada")

        self._logger.warning("execução de SQL arbitrário via rota administrativa")
        resultado = self._admin.executar_sql(query)

        if resultado is None:
            return jsonify({"mensagem": "Query executada", "sucesso": True}), 200
        return jsonify(ok(resultado)), 200
