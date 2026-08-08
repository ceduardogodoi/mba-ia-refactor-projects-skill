"""Configuração de logging.

Substitui os `print` espalhados por rotas e serviços. `utils/helpers.py` chegava
a definir um `log_action`, que nunca foi chamado.
"""
import logging
import sys

FORMATO = "%(asctime)s %(levelname)-8s %(name)s %(message)s"


def build_logger(settings, nome="taskmanager"):
    logger = logging.getLogger(nome)
    logger.setLevel(settings.log_level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(FORMATO))
        logger.addHandler(handler)

    logger.propagate = False
    return logger
