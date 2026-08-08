"""Única porta de entrada de configuração da aplicação.

Nenhum outro módulo lê variáveis de ambiente. Secrets falham na inicialização
quando ausentes — um default para SECRET_KEY seria a mesma vulnerabilidade com
passos a mais.
"""
import os
from pathlib import Path

_TRUE = {"1", "true", "yes", "on"}


def load_dotenv(path=".env"):
    """Carrega um .env simples para o ambiente, sem sobrescrever o que já existe.

    Evita uma dependência só para isso. Variáveis já definidas no ambiente têm
    precedência, que é o comportamento esperado em container e CI.
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
        self.db_path = env.get("DB_PATH", "loja.db")
        self.host = env.get("HOST", "127.0.0.1")
        self.port = int(env.get("PORT", "5000"))
        self.log_level = env.get("LOG_LEVEL", "INFO").upper()
        self.cors_origins = self._list(env, "CORS_ORIGINS", default="http://localhost:3000")

        # Rotas administrativas executam SQL arbitrário e destroem dados.
        # Default negado: ligar exige decisão explícita de quem opera.
        self.admin_endpoints_enabled = self._flag(env, "ADMIN_ENDPOINTS_ENABLED", default=False)

        self.seed_on_boot = self._flag(env, "SEED_ON_BOOT", default=True)

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
        if raw is None:
            return default
        return raw.strip().lower() in _TRUE

    @staticmethod
    def _list(env, name, default=""):
        raw = env.get(name, default)
        return [item.strip() for item in raw.split(",") if item.strip()]
