"""Única porta de entrada de configuração.

Nenhum outro módulo lê variáveis de ambiente. Secrets falham na inicialização
quando ausentes — um default para SECRET_KEY seria a mesma vulnerabilidade com
passos a mais.
"""
import os
from pathlib import Path

_TRUE = {"1", "true", "yes", "on"}


def load_dotenv(path=".env"):
    """Carrega um .env simples, sem sobrescrever o que já existe no ambiente.

    `python-dotenv` está declarado em requirements.txt e nunca foi importado.
    Em vez de passar a depender dele por causa de doze linhas, o parser fica
    aqui — e a dependência não usada sai do requirements.
    """
    env_file = Path(path)
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class Settings:
    def __init__(self, env=None):
        env = os.environ if env is None else env

        self.secret_key = self._required(env, "SECRET_KEY")
        self.debug = self._flag(env, "DEBUG", default=False)
        self.database_uri = env.get("DATABASE_URI", "sqlite:///tasks.db")

        self.host = env.get("HOST", "127.0.0.1")
        self.port = int(env.get("PORT", "5000"))
        self.log_level = env.get("LOG_LEVEL", "INFO").upper()

        self.cors_origins = self._list(env, "CORS_ORIGINS", default="http://localhost:3000")
        self.max_content_length = int(env.get("MAX_CONTENT_LENGTH_BYTES", str(1024 * 1024)))

        # Notificações por email. Desligadas por padrão: o serviço nunca foi
        # ligado no projeto original e enviar email de verdade a partir de um
        # handler HTTP precisa de decisão consciente.
        self.notifications_enabled = self._flag(env, "NOTIFICATIONS_ENABLED", default=False)
        self.smtp_host = env.get("SMTP_HOST", "")
        self.smtp_port = int(env.get("SMTP_PORT", "587"))
        self.smtp_user = env.get("SMTP_USER", "")
        self.smtp_password = env.get("SMTP_PASSWORD", "")
        self.smtp_timeout = int(env.get("SMTP_TIMEOUT_SECONDS", "10"))

    @staticmethod
    def _required(env, name):
        value = env.get(name)
        if not value:
            raise RuntimeError(
                f"Variável de ambiente obrigatória ausente: {name}. "
                f"Copie .env.example para .env e defina um valor."
            )
        return value

    @staticmethod
    def _flag(env, name, default=False):
        raw = env.get(name)
        return default if raw is None else raw.strip().lower() in _TRUE

    @staticmethod
    def _list(env, name, default=""):
        return [item.strip() for item in env.get(name, default).split(",") if item.strip()]
