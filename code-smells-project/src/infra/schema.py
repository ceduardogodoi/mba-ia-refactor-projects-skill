"""DDL e seed, executados explicitamente na composição da aplicação.

Antes isto vivia dentro de `get_db()`: obter uma conexão criava tabelas e
inseria dados. Agora bootstrap e obtenção de conexão são operações distintas.
"""
from src.domain.constants import StatusPedido, TipoUsuario
from src.infra.security import hash_senha

DDL = (
    """
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        descricao TEXT,
        preco REAL,
        estoque INTEGER,
        categoria TEXT,
        ativo INTEGER DEFAULT 1,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        email TEXT,
        senha TEXT,
        tipo TEXT DEFAULT 'cliente',
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER REFERENCES usuarios(id) ON DELETE RESTRICT,
        status TEXT DEFAULT 'pendente',
        total REAL,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS itens_pedido (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER REFERENCES pedidos(id) ON DELETE CASCADE,
        produto_id INTEGER REFERENCES produtos(id) ON DELETE RESTRICT,
        quantidade INTEGER,
        preco_unitario REAL
    )
    """,
)

PRODUTOS_INICIAIS = (
    ("Notebook Gamer", "Notebook potente para jogos", 5999.99, 10, "informatica"),
    ("Mouse Wireless", "Mouse sem fio ergonômico", 89.90, 50, "informatica"),
    ("Teclado Mecânico", "Teclado mecânico RGB", 299.90, 30, "informatica"),
    ("Monitor 27''", "Monitor 27 polegadas 144hz", 1899.90, 15, "informatica"),
    ("Headset Gamer", "Headset com microfone", 199.90, 25, "informatica"),
    ("Cadeira Gamer", "Cadeira ergonômica", 1299.90, 8, "moveis"),
    ("Webcam HD", "Webcam 1080p", 249.90, 20, "informatica"),
    ("Hub USB", "Hub USB 3.0 7 portas", 79.90, 40, "informatica"),
    ("SSD 1TB", "SSD NVMe 1TB", 449.90, 35, "informatica"),
    ("Camiseta Dev", "Camiseta estampa código", 59.90, 100, "vestuario"),
)

# As senhas de seed permanecem as mesmas do projeto original para não quebrar
# quem usa estas credenciais, mas agora são gravadas com hash.
USUARIOS_INICIAIS = (
    ("Admin", "admin@loja.com", "admin123", TipoUsuario.ADMIN),
    ("João Silva", "joao@email.com", "123456", TipoUsuario.CLIENTE),
    ("Maria Santos", "maria@email.com", "senha123", TipoUsuario.CLIENTE),
)


def criar_schema(conn):
    for statement in DDL:
        conn.execute(statement)
    conn.commit()


def popular_se_vazio(conn):
    if conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] > 0:
        return False

    conn.executemany(
        "INSERT INTO produtos (nome, descricao, preco, estoque, categoria) "
        "VALUES (?, ?, ?, ?, ?)",
        PRODUTOS_INICIAIS,
    )
    conn.executemany(
        "INSERT INTO usuarios (nome, email, senha, tipo) VALUES (?, ?, ?, ?)",
        [(nome, email, hash_senha(senha), str(tipo)) for nome, email, senha, tipo in USUARIOS_INICIAIS],
    )
    conn.commit()
    return True


def limpar(conn):
    """Apaga os dados de todas as tabelas, respeitando a ordem de dependência."""
    for tabela in ("itens_pedido", "pedidos", "produtos", "usuarios"):
        conn.execute(f"DELETE FROM {tabela}")
    conn.commit()


__all__ = ["criar_schema", "popular_se_vazio", "limpar", "StatusPedido"]
