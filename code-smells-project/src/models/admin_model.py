"""Operações administrativas de manutenção.

Isoladas em um model próprio para que o controller não escreva SQL. O acesso a
estas operações é controlado por feature flag na camada de controller.
"""
from src.infra.schema import limpar


class AdminModel:
    def __init__(self, connection_provider):
        self._conn = connection_provider

    def limpar_dados(self):
        limpar(self._conn())
        return True

    def executar_sql(self, query):
        """Executa SQL cru. Só alcançável com ADMIN_ENDPOINTS_ENABLED=true."""
        conn = self._conn()
        cursor = conn.execute(query)
        if query.strip().upper().startswith("SELECT"):
            return [dict(row) for row in cursor.fetchall()]
        conn.commit()
        return None
