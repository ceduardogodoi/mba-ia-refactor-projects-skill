"""Validação de entrada na fronteira.

Regra única por entidade, com modo parcial para update. A mudança de substância
em relação ao original é a ordem das operações: o tipo é coagido **antes** de
qualquer comparação. Era isso que faltava em `if priority < 1`, onde um valor
string levantava TypeError e virava 500 em vez de 400.

As mensagens são idênticas às do projeto original — elas fazem parte do contrato.
"""
import re

from src.domain.constants import (
    FORMATO_DATA,
    PRIORIDADE_MAX,
    PRIORIDADE_MIN,
    SENHA_MIN,
    TITULO_MAX,
    TITULO_MIN,
    TaskStatus,
    UserRole,
)
from src.domain.errors import ValidationError
from datetime import datetime

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+$")


def _corpo(dados):
    if not dados:
        raise ValidationError("Dados inválidos")
    return dados


def _inteiro(valor, mensagem):
    if isinstance(valor, bool) or not isinstance(valor, int):
        try:
            valor = int(valor)
        except (TypeError, ValueError):
            raise ValidationError(mensagem) from None
    return valor


def _titulo(valor):
    if not isinstance(valor, str):
        raise ValidationError("Título muito curto")
    if len(valor) < TITULO_MIN:
        raise ValidationError("Título muito curto")
    if len(valor) > TITULO_MAX:
        raise ValidationError("Título muito longo")
    return valor


def _status(valor):
    if valor not in TaskStatus.values():
        raise ValidationError("Status inválido")
    return valor


def _prioridade(valor):
    mensagem = f"Prioridade deve ser entre {PRIORIDADE_MIN} e {PRIORIDADE_MAX}"
    prioridade = _inteiro(valor, mensagem)
    if not PRIORIDADE_MIN <= prioridade <= PRIORIDADE_MAX:
        raise ValidationError(mensagem)
    return prioridade


def _data(valor):
    try:
        return datetime.strptime(valor, FORMATO_DATA)
    except (TypeError, ValueError):
        raise ValidationError("Formato de data inválido. Use YYYY-MM-DD") from None


def _email(valor):
    if not isinstance(valor, str) or not _EMAIL_RE.match(valor):
        raise ValidationError("Email inválido")
    return valor


def _role(valor):
    if valor not in UserRole.values():
        raise ValidationError("Role inválido")
    return valor


# ------------------------------------------------------------------------ task


def validar_task_criacao(dados):
    """A ordem de validação reproduz a do projeto original."""
    dados = _corpo(dados)

    titulo = dados.get("title")
    if not titulo:
        raise ValidationError("Título é obrigatório")

    validado = {
        "title": _titulo(titulo),
        "description": dados.get("description", ""),
        "status": _status(dados.get("status", str(TaskStatus.PENDING))),
        "priority": _prioridade(dados.get("priority", 3)),
        "user_id": dados.get("user_id"),
        "category_id": dados.get("category_id"),
    }

    if dados.get("due_date"):
        validado["due_date"] = _data(dados["due_date"])
    if dados.get("tags"):
        validado["tags"] = dados["tags"]

    return validado


def validar_task_atualizacao(dados):
    dados = _corpo(dados)
    validado = {}

    if "title" in dados:
        validado["title"] = _titulo(dados["title"])
    if "description" in dados:
        validado["description"] = dados["description"]
    if "status" in dados:
        validado["status"] = _status(dados["status"])
    if "priority" in dados:
        validado["priority"] = _prioridade(dados["priority"])
    if "user_id" in dados:
        validado["user_id"] = dados["user_id"]
    if "category_id" in dados:
        validado["category_id"] = dados["category_id"]
    if "due_date" in dados:
        validado["due_date"] = _data(dados["due_date"]) if dados["due_date"] else None
    if "tags" in dados:
        validado["tags"] = dados["tags"]

    return validado


def validar_filtros_task(args):
    prioridade = args.get("priority")
    user_id = args.get("user_id")
    return {
        "termo": args.get("q", ""),
        "status": args.get("status") or None,
        "prioridade": _prioridade(prioridade) if prioridade else None,
        "user_id": _inteiro(user_id, "Parâmetro user_id inválido") if user_id else None,
    }


# ------------------------------------------------------------------------ user


def validar_usuario_criacao(dados):
    dados = _corpo(dados)

    nome = dados.get("name")
    email = dados.get("email")
    senha = dados.get("password")

    if not nome:
        raise ValidationError("Nome é obrigatório")
    if not email:
        raise ValidationError("Email é obrigatório")
    if not senha:
        raise ValidationError("Senha é obrigatória")

    _email(email)
    if not isinstance(senha, str) or len(senha) < SENHA_MIN:
        raise ValidationError(f"Senha deve ter no mínimo {SENHA_MIN} caracteres")

    return {
        "name": nome,
        "email": email,
        "password": senha,
        "role": _role(dados.get("role", str(UserRole.USER))),
    }


def validar_usuario_atualizacao(dados):
    dados = _corpo(dados)
    validado = {}

    if "name" in dados:
        validado["name"] = dados["name"]
    if "email" in dados:
        validado["email"] = _email(dados["email"])
    if "password" in dados:
        senha = dados["password"]
        if not isinstance(senha, str) or len(senha) < SENHA_MIN:
            raise ValidationError("Senha muito curta")
        validado["password"] = senha
    if "role" in dados:
        validado["role"] = _role(dados["role"])
    if "active" in dados:
        validado["active"] = bool(dados["active"])

    return validado


def validar_login(dados):
    dados = _corpo(dados)
    email = dados.get("email")
    senha = dados.get("password")
    if not email or not senha:
        raise ValidationError("Email e senha são obrigatórios")
    return {"email": email, "password": senha}


# -------------------------------------------------------------------- category


def validar_categoria_criacao(dados):
    dados = _corpo(dados)
    nome = dados.get("name")
    if not nome:
        raise ValidationError("Nome é obrigatório")
    return {
        "name": nome,
        "description": dados.get("description", ""),
        "color": dados.get("color", "#000000"),
    }


def validar_categoria_atualizacao(dados):
    dados = _corpo(dados)
    validado = {}
    for campo in ("name", "description", "color"):
        if campo in dados:
            validado[campo] = dados[campo]
    return validado
