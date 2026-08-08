"""Validação de entrada na fronteira da aplicação.

Regra única por entidade, com modo `parcial` para update — antes o mesmo bloco
estava copiado em `criar_produto` e `atualizar_produto`, e as cópias já haviam
divergido. Tudo levanta `ValidationError`; o middleware traduz para 400.
"""
import re

from src.domain.constants import (
    CATEGORIAS_VALIDAS,
    CATEGORIA_PADRAO,
    NOME_PRODUTO_MAX,
    NOME_PRODUTO_MIN,
    StatusPedido,
)
from src.domain.errors import ValidationError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _corpo(dados):
    if not dados:
        raise ValidationError("Dados inválidos")
    return dados


def _numero(valor, rotulo):
    """Coage antes de comparar. Comparar string com int era um 500 disfarçado."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            raise ValidationError(f"{rotulo} deve ser um número") from None
    return valor


def validar_produto(dados, parcial=False):
    dados = _corpo(dados)

    for campo, rotulo in (("nome", "Nome"), ("preco", "Preço"), ("estoque", "Estoque")):
        if campo not in dados:
            raise ValidationError(f"{rotulo} é obrigatório")

    nome = dados["nome"]
    preco = _numero(dados["preco"], "Preço")
    estoque = _numero(dados["estoque"], "Estoque")
    categoria = dados.get("categoria", CATEGORIA_PADRAO)

    if preco < 0:
        raise ValidationError("Preço não pode ser negativo")
    if estoque < 0:
        raise ValidationError("Estoque não pode ser negativo")

    if not isinstance(nome, str):
        raise ValidationError("Nome deve ser um texto")
    if len(nome) < NOME_PRODUTO_MIN:
        raise ValidationError("Nome muito curto")
    if len(nome) > NOME_PRODUTO_MAX:
        raise ValidationError("Nome muito longo")

    if categoria not in CATEGORIAS_VALIDAS:
        raise ValidationError(
            "Categoria inválida. Válidas: " + str(list(CATEGORIAS_VALIDAS))
        )

    return {
        "nome": nome,
        "descricao": dados.get("descricao", ""),
        "preco": preco,
        "estoque": estoque,
        "categoria": categoria,
    }


def validar_usuario(dados):
    dados = _corpo(dados)

    nome = dados.get("nome", "")
    email = dados.get("email", "")
    senha = dados.get("senha", "")

    if not nome or not email or not senha:
        raise ValidationError("Nome, email e senha são obrigatórios")
    if not isinstance(email, str) or not _EMAIL_RE.match(email):
        raise ValidationError("Email inválido")

    return {"nome": nome, "email": email, "senha": senha}


def validar_login(dados):
    dados = _corpo(dados)

    email = dados.get("email", "")
    senha = dados.get("senha", "")
    if not email or not senha:
        raise ValidationError("Email e senha são obrigatórios")

    return {"email": email, "senha": senha}


def validar_pedido(dados):
    dados = _corpo(dados)

    usuario_id = dados.get("usuario_id")
    itens = dados.get("itens", [])

    if not usuario_id:
        raise ValidationError("Usuario ID é obrigatório")
    if not itens or len(itens) == 0:
        raise ValidationError("Pedido deve ter pelo menos 1 item")

    normalizados = []
    for item in itens:
        if not isinstance(item, dict) or "produto_id" not in item or "quantidade" not in item:
            raise ValidationError("Item inválido: informe produto_id e quantidade")
        quantidade = _numero(item["quantidade"], "Quantidade")
        if quantidade <= 0:
            raise ValidationError("Quantidade deve ser maior que zero")
        normalizados.append({
            "produto_id": item["produto_id"],
            "quantidade": int(quantidade),
        })

    return {"usuario_id": usuario_id, "itens": normalizados}


def validar_status_pedido(dados):
    dados = _corpo(dados)

    novo_status = dados.get("status", "")
    if novo_status not in tuple(str(s) for s in StatusPedido):
        raise ValidationError("Status inválido")

    return novo_status


def validar_filtros_busca(args):
    """`args` é o MultiDict de query string. Coerção antes de qualquer uso."""
    preco_min = args.get("preco_min")
    preco_max = args.get("preco_max")

    return {
        "termo": args.get("q", ""),
        "categoria": args.get("categoria"),
        "preco_min": _numero(preco_min, "preco_min") if preco_min else None,
        "preco_max": _numero(preco_max, "preco_max") if preco_max else None,
    }
