"""Endpoints de sistema: índice e health check."""
from flask import jsonify

from src.infra.database import utc_now

VERSAO = "1.0"


class SystemController:
    def index(self):
        return jsonify({"message": "Task Manager API", "version": VERSAO}), 200

    def health(self):
        return jsonify({"status": "ok", "timestamp": str(utc_now())}), 200
