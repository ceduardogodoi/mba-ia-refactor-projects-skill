"""Security headers.

`flask-talisman` cobriria isto, mas é dependência nova — a regra é só adicionar
dependência quando o finding não puder ser resolvido sem ela.
"""


def register(app):
    @app.after_request
    def _headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response
