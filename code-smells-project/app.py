"""Entry point da aplicação.

Mantém `python app.py` funcionando. A composição vive em `src/app.py`; este
arquivo apenas carrega a configuração e expõe `app` para servidores WSGI.
"""
from src.app import create_app
from src.config.settings import Settings, load_dotenv

load_dotenv()
settings = Settings()
app = create_app(settings)

if __name__ == "__main__":
    app.run(host=settings.host, port=settings.port, debug=settings.debug)
