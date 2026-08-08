"""Configuração de logging.

Substitui os 14 `print` espalhados pelo código. Nível vem da config; nenhum dado
sensível é registrado.
"""
import logging
import sys

FORMATO = "%(asctime)s %(levelname)-8s %(name)s %(message)s"


def build_logger(settings, nome="loja"):
    logger = logging.getLogger(nome)
    logger.setLevel(settings.log_level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(FORMATO))
        logger.addHandler(handler)

    logger.propagate = False
    return logger
