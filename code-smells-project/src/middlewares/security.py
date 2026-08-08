"""Security headers.

`flask-talisman` cobriria isto, mas é dependência nova — a regra da skill é só
adicionar dependência quando o finding não puder ser resolvido sem ela, e quatro
headers não justificam.

A verificação correta é pelo wire (`curl -I`), não pelo código: um header que se
acredita estar setado e não está é pior que um ausente.
"""


def register(app):
    @app.after_request
    def _headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        response.headers.pop("Server", None)
        return response
