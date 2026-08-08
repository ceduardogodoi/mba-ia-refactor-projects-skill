"""Rate limit para endpoints de autenticação.

`/login` sem limite permite força bruta ilimitada contra a base de usuários.

Implementação em memória, deliberadamente. `Flask-Limiter` seria dependência
nova, e a regra da skill é só adicionar dependência quando o finding não puder
ser resolvido sem ela. Duas limitações que essa escolha impõe, e que estão
registradas no relatório em vez de escondidas:

1. O estado vive no processo. Com mais de um worker, cada um conta
   separadamente, e o limite efetivo é `limite x nº de workers`. Para valer em
   produção o contador precisa ser compartilhado (Redis) ou aplicado na borda.
2. A identidade do cliente é `request.remote_addr`. Atrás de proxy reverso isso
   é o IP do proxy, e confiar em `X-Forwarded-For` sem validar a cadeia permite
   forjar a identidade. Por isso o header não é lido aqui.
"""
import time
from collections import defaultdict, deque

from flask import request

from src.domain.errors import TooManyRequestsError


class SlidingWindowLimiter:
    """Janela deslizante: mantém os timestamps das tentativas dentro da janela."""

    def __init__(self, limite, janela_segundos, clock=time.monotonic):
        self._limite = limite
        self._janela = janela_segundos
        self._clock = clock
        self._tentativas = defaultdict(deque)

    def permitir(self, chave):
        agora = self._clock()
        registros = self._tentativas[chave]

        while registros and agora - registros[0] >= self._janela:
            registros.popleft()

        if len(registros) >= self._limite:
            return False

        registros.append(agora)
        return True

    def segundos_para_liberar(self, chave):
        registros = self._tentativas.get(chave)
        if not registros:
            return 0
        return max(0, int(self._janela - (self._clock() - registros[0])) + 1)


def register(app, settings, logger, endpoints=("usuarios.login",)):
    limiter = SlidingWindowLimiter(settings.login_rate_limit, settings.login_rate_window)
    protegidos = set(endpoints)

    @app.before_request
    def _limitar():
        if request.endpoint not in protegidos:
            return None

        chave = f"{request.endpoint}:{request.remote_addr}"
        if limiter.permitir(chave):
            return None

        espera = limiter.segundos_para_liberar(chave)
        # Sem o IP no log: registrar tentativa de força bruta não deve criar um
        # segundo problema de dado pessoal.
        logger.warning("rate limit atingido", extra={"endpoint": request.endpoint})
        raise TooManyRequestsError(
            f"Muitas tentativas. Tente novamente em {espera} segundos."
        )

    return limiter
