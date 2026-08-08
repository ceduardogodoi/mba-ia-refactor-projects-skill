# Refactoring Playbook (Phase 3)

One transformation per anti-pattern, with before/after code. Examples alternate between Python and
JavaScript; the transformation is the same in any language — translate the idiom, keep the shape.

**Apply in the order listed in `SKILL.md` §3.2.** Config first, composition root last. Each pattern
assumes the ones before it are done.

| Pattern | Fixes | Name |
| --- | --- | --- |
| RP-01 | AP-01 | Extract Configuration |
| RP-02 | AP-02 | Parameterize Queries |
| RP-03 | AP-03 | Gate the Dangerous Endpoint |
| RP-04 | AP-04 | Split the God Class |
| RP-05 | AP-05 | Real Password Hashing |
| RP-06 | AP-06, AP-18 | Thin the Controller |
| RP-07 | AP-07, AP-08 | Factory + Injection instead of Globals |
| RP-08 | AP-09 | Flatten Callbacks with async/await |
| RP-09 | AP-10, AP-22 | Centralized Error Handling |
| RP-10 | AP-11 | Transaction Boundary & Referential Integrity |
| RP-11 | AP-12 | Eliminate N+1 |
| RP-12 | AP-13, AP-14 | Consolidate Validation |
| RP-13 | AP-15 | Replace Deprecated APIs |
| RP-14 | AP-16, AP-05 | Extract the Serializer |
| RP-15 | AP-17 | Structured Logging |
| RP-16 | AP-19 | Named Constants |
| RP-17 | AP-20, AP-21 | Rename & Remove Dead Code |

---

## RP-01 — Extract Configuration

**Before**
```python
app.config["SECRET_KEY"] = "minha-chave-super-secreta-123"
app.config["DEBUG"] = True
db_path = "loja.db"
```

**After** — `src/config/settings.py`
```python
import os

class Settings:
    def __init__(self, env=None):
        env = env or os.environ
        self.secret_key = env.get("SECRET_KEY") or self._required("SECRET_KEY")
        self.debug = env.get("DEBUG", "false").lower() == "true"
        self.db_path = env.get("DB_PATH", "loja.db")
        self.port = int(env.get("PORT", "5000"))
        self.admin_query_enabled = env.get("ADMIN_QUERY_ENABLED", "false").lower() == "true"

    @staticmethod
    def _required(name):
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {name}")
```

`.env.example` — committed; `.env` — gitignored.
```bash
SECRET_KEY=troque-por-um-valor-aleatorio
DEBUG=false
DB_PATH=loja.db
ADMIN_QUERY_ENABLED=false
```

**Rules**
- Secrets **fail fast** when missing. A default secret key is the same vulnerability with extra steps.
- Non-secrets get sensible defaults so the app runs out of the box.
- Config is read **once**, at startup, in one module. No `os.environ` anywhere else.
- `DEBUG` defaults to `false`. Debug mode in Flask exposes an interactive shell on tracebacks.
- Add `.env` to `.gitignore` in the same change.
- The report must say the leaked secret needs **rotation** — deleting the line does not scrub git history.

---

## RP-02 — Parameterize Queries

**Before**
```python
cursor.execute("SELECT * FROM produtos WHERE id = " + str(id))
cursor.execute("SELECT * FROM usuarios WHERE email = '" + email + "' AND senha = '" + senha + "'")
```

**After**
```python
cursor.execute("SELECT * FROM produtos WHERE id = ?", (id,))
cursor.execute("SELECT * FROM usuarios WHERE email = ?", (email,))
```

Dynamic filters keep parameters too — build the *structure*, never the *values*:
```python
def buscar(self, termo=None, categoria=None, preco_min=None, preco_max=None):
    sql = ["SELECT * FROM produtos WHERE 1=1"]
    params = []
    if termo:
        sql.append("AND (nome LIKE ? OR descricao LIKE ?)")
        params += [f"%{termo}%", f"%{termo}%"]
    if categoria:
        sql.append("AND categoria = ?")
        params.append(categoria)
    if preco_min is not None:
        sql.append("AND preco >= ?")
        params.append(preco_min)
    return self._cursor().execute(" ".join(sql), params).fetchall()
```

**Rules**
- The `%` wildcards for `LIKE` go in the **parameter**, never in the SQL string.
- Identifiers (table/column names) cannot be parameterized — validate them against a literal allowlist.
- ORM projects: prefer the query builder; if `raw`/`text` is unavoidable, bind parameters
  (`text("… WHERE id = :id"), {"id": id}`).
- Placeholder syntax varies: `?` (SQLite), `%s` (psycopg2/MySQL), `$1` (node-postgres), `:name`
  (SQLAlchemy). Use the driver's.
- Fix **every** occurrence. One missed concatenation keeps the vulnerability open.

---

## RP-03 — Gate the Dangerous Endpoint

Keep the contract, remove the weapon.

**Before**
```python
@app.route("/admin/query", methods=["POST"])
def executar_query():
    query = request.get_json().get("sql", "")
    cursor.execute(query)          # executa SQL arbitrário do request
```

**After** — `controllers/admin_controller.py`
```python
def executar_query():
    if not settings.admin_query_enabled:
        raise ForbiddenError("Endpoint desabilitado por configuração")
    ...
```

**Rules**
- Route and method survive; the behaviour becomes `403` while the flag is off (default: off).
- Default-deny. A flag that defaults to on is not a mitigation.
- Destructive routes (`/admin/reset-db`) get the same treatment.
- Record it under "Intentional behaviour changes": *"`POST /admin/query` responde 403 enquanto
  `ADMIN_QUERY_ENABLED=false`"*.
- If the audit approved outright removal instead, delete the route and say so — do not leave a stub.

---

## RP-04 — Split the God Class

**Before** — `AppManager.js`: schema + seed + routing + payment + audit log, all in one class.
```js
class AppManager {
    constructor() { this.db = new sqlite3.Database(':memory:'); }
    initDb() { /* CREATE TABLE ×5 + INSERT seeds */ }
    setupRoutes(app) { /* 3 rotas, com pagamento e regra de negócio inline */ }
}
```

**After** — responsibilities separated by layer
```text
infra/database.js        → connection factory + schema bootstrap (promisified)
infra/seed.js            → seed data, run explicitly, not on import
models/userModel.js      → users table: findByEmail, create
models/courseModel.js    → courses table: findActiveById
models/enrollmentModel.js→ enrollments + payments, inside one transaction
services/paymentService.js → gateway call, injected
controllers/checkoutController.js → the use case
routes/checkoutRoutes.js → POST /api/checkout → controller
app.js                   → composition root
```

**Method**
1. List the class's responsibilities. Each one names a future module.
2. Move, do not rewrite. Cut a method into its new home and adjust imports; behaviour stays byte-identical
   until a *different* pattern deliberately changes it.
3. Break the coupling: the God Class usually holds a shared `this.db`. Replace it with a connection
   injected into each model (see RP-07).
4. Delete the original file once empty. A God Class left beside its replacement is not a refactoring.
5. Re-check the routes after each move — this is where endpoints get silently lost.

---

## RP-05 — Real Password Hashing

**Before**
```python
self.password = hashlib.md5(pwd.encode()).hexdigest()          # projeto 3
```
```js
function badCrypto(pwd) {                                       // projeto 2
    let hash = "";
    for (let i = 0; i < 10000; i++) hash += Buffer.from(pwd).toString('base64').substring(0, 2);
    return hash.substring(0, 10);
}
```

**After**
```python
from werkzeug.security import generate_password_hash, check_password_hash

def set_password(self, raw):
    self.password_hash = generate_password_hash(raw)   # pbkdf2-sha256 com salt

def check_password(self, raw):
    return check_password_hash(self.password_hash, raw)
```
```js
const crypto = require('node:crypto');

function hashPassword(raw) {
    const salt = crypto.randomBytes(16).toString('hex');
    const derived = crypto.scryptSync(raw, salt, 64).toString('hex');
    return `scrypt$${salt}$${derived}`;
}

function verifyPassword(raw, stored) {
    const [, salt, expected] = stored.split('$');
    const actual = crypto.scryptSync(raw, salt, 64);
    return crypto.timingSafeEqual(Buffer.from(expected, 'hex'), actual);
}
```

**Rules**
- Use a KDF: `bcrypt`, `argon2`, `scrypt`, `pbkdf2`. Never a bare digest, never something homemade.
- Salt per user, stored with the hash.
- Compare in constant time (`timingSafeEqual`, `hmac.compare_digest`, or the library's `check_*`).
- Prefer the framework's helper (`werkzeug.security`) or the stdlib (`node:crypto`) over a new dependency.
- Existing plaintext/MD5 rows cannot be converted. Either re-seed the dev database, or verify against the
  legacy scheme once and re-hash on next successful login. Whichever you choose, put it in
  "Post-Refactoring Actions": **users must reset their passwords**.
- Login must not distinguish "email inexistente" from "senha errada".

---

## RP-06 — Thin the Controller

**Before** — route handler doing everything
```python
def criar_pedido():
    dados = request.get_json()
    resultado = models.criar_pedido(dados.get("usuario_id"), dados.get("itens", []))
    if "erro" in resultado:
        return jsonify({"erro": resultado["erro"]}), 400
    print("ENVIANDO EMAIL: Pedido " + str(resultado["pedido_id"]) + " criado")
    print("ENVIANDO SMS: Seu pedido foi recebido!")
    return jsonify({"dados": resultado, "sucesso": True}), 201
```

**After**
```python
# controllers/pedido_controller.py
def criar_pedido():
    dados = PedidoSchema.validate(request.get_json())          # RP-12
    pedido = pedido_model.criar(dados["usuario_id"], dados["itens"])
    notification_service.pedido_criado(pedido)                 # RP-07: injetado
    return jsonify(PedidoSerializer.one(pedido)), 201          # RP-14
```

The domain rules (stock check, total calculation) move into `models/pedido_model.py`; the
notifications move into a service; error translation moves into the middleware (RP-09).

**Rules**
- A controller does four things and nothing else: validate input, call collaborators, choose a status
  code, serialize the result.
- Any `if` about *domain state* ("estoque insuficiente", "pedido já aprovado") belongs to the model.
  An `if` about *HTTP* ("resource missing → 404") belongs to the controller.
- A domain function returning `{"erro": "..."}` is an exception in disguise. Raise a typed error and let
  RP-09 map it.
- Side effects (email, SMS, audit) are services called by the controller, or events — never inline
  `print`s.
- Slow external calls (AP-18) get an explicit timeout; if the client does not need the result, do not
  block the response on them.

---

## RP-07 — Factory + Injection instead of Globals

**Before**
```python
db_connection = None                                    # global mutável

def get_db():
    global db_connection
    if db_connection is None:
        db_connection = sqlite3.connect(db_path, check_same_thread=False)
    return db_connection
```

**After** — `src/infra/database.py`
```python
import sqlite3
from flask import g

class Database:
    def __init__(self, path):
        self._path = path

    def connect(self):
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

def init_app(app, database):
    app.extensions["database"] = database
    app.teardown_appcontext(_close)

def get_conn():
    if "db_conn" not in g:
        g.db_conn = current_app.extensions["database"].connect()
    return g.db_conn

def _close(exc):
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()
```

Models receive what they need instead of reaching for a global:
```python
class ProdutoModel:
    def __init__(self, conn_provider):
        self._conn = conn_provider

    def buscar_por_id(self, produto_id):
        return self._conn().execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
```

The same for external collaborators — configuration comes **in**, it is not read inside:
```python
class NotificationService:
    def __init__(self, mailer, settings):     # antes: smtplib + credenciais no __init__
        self._mailer = mailer
        self._settings = settings
```

**Rules**
- Connections are **request-scoped**, not process-scoped. `check_same_thread=False` on a shared
  connection is a race condition, not a configuration.
- Nothing mutable at module level. Caches become an injected object with an explicit lifetime.
- Every collaborator that does I/O arrives through the constructor, so a test can pass a fake.
- Wiring happens once, in the composition root.
- Watch for stale-copy bugs: a module-level counter exported and reassigned elsewhere never updates for
  its importers. Delete it or make it a real store.

---

## RP-08 — Flatten Callbacks with async/await

**Before** — five levels deep, plus manual counters
```js
this.db.get("SELECT * FROM courses WHERE id = ?", [cid], (err, course) => {
    this.db.get("SELECT id FROM users WHERE email = ?", [e], (err, user) => {
        this.db.run("INSERT INTO enrollments …", [userId, cid], function (err) {
            self.db.run("INSERT INTO payments …", [enrId, course.price, status], function (err) {
                self.db.run("INSERT INTO audit_logs …", [...], (err) => {
                    res.status(200).json({ msg: "Sucesso", enrollment_id: enrId });
                });
            });
        });
    });
});
```

**After** — promisify at the infra boundary, then write straight-line code
```js
// infra/database.js
const { promisify } = require('node:util');

function wrap(db) {
    return {
        get: promisify(db.get.bind(db)),
        all: promisify(db.all.bind(db)),
        run: (sql, params = []) => new Promise((resolve, reject) =>
            db.run(sql, params, function (err) {
                err ? reject(err) : resolve({ lastID: this.lastID, changes: this.changes });
            })),
    };
}
```
```js
// controllers/checkoutController.js
async function checkout(req, res, next) {
    const input = validateCheckout(req.body);
    const course = await courseModel.findActiveById(input.courseId);
    if (!course) throw new NotFoundError('Curso não encontrado');

    const user = await userModel.findOrCreateByEmail(input);
    const payment = await paymentService.charge(input.card, course.price);
    if (!payment.approved) throw new PaymentDeniedError('Pagamento recusado');

    const enrollment = await enrollmentModel.enroll(user.id, course.id, payment);
    res.status(200).json({ msg: 'Sucesso', enrollment_id: enrollment.id });
}
```

Fan-out replaces the hand-rolled counter entirely:
```js
const report = await Promise.all(courses.map(buildCourseReport));   // era coursesPending--
```

**Rules**
- Promisify **once**, at the infra boundary. No callback style above it.
- `sqlite3`'s `run` needs a manual wrapper — `this.lastID` is only available on a `function` callback,
  which an arrow function or `promisify` would lose.
- Delete the `self = this` aliases; `async` methods and arrows keep `this`.
- Every async handler must forward rejections to the error middleware — wrap it or `try/catch → next(err)`.
  An unhandled rejection in Express 4 hangs the request forever.
- Deleting the counters removes the double-`res.send` and the never-responds bugs along with them.

---

## RP-09 — Centralized Error Handling

**Before** — the same block copy-pasted into every handler, plus silent swallows
```python
try:
    ...
except Exception as e:
    return jsonify({"erro": str(e)}), 500      # vaza SQL e paths
```
```python
except:
    return jsonify({'error': 'Erro interno'}), 500    # engole tudo, inclusive 404
```

**After** — typed domain errors + one handler
```python
# middlewares/errors.py
class DomainError(Exception):
    status = 400
    def __init__(self, message, details=None):
        super().__init__(message)
        self.message, self.details = message, details

class NotFoundError(DomainError):    status = 404
class ValidationError(DomainError):  status = 400
class UnauthorizedError(DomainError):status = 401
class ForbiddenError(DomainError):   status = 403
class ConflictError(DomainError):    status = 409

def register(app, logger):
    @app.errorhandler(DomainError)
    def _domain(err):
        return jsonify({"erro": err.message, "detalhes": err.details, "sucesso": False}), err.status

    @app.errorhandler(Exception)
    def _unexpected(err):
        logger.exception("Erro não tratado")                 # stack completa no log
        return jsonify({"erro": "Erro interno", "sucesso": False}), 500   # genérica para o cliente
```

Express equivalent — four arguments, registered **after** all routes:
```js
app.use((err, req, res, _next) => {
    if (err instanceof DomainError) {
        return res.status(err.status).json({ error: err.message });
    }
    logger.error({ err }, 'Erro não tratado');
    res.status(500).json({ error: 'Erro interno' });
});
```

**Rules**
- Domain code **raises**; only the middleware decides status codes.
- Delete every per-handler `try/except → 500`. That is the point of the pattern.
- The client gets a stable, generic message; the log gets the stack trace. Never `str(e)` in a response.
- Bare `except:` also catches `KeyboardInterrupt` and `SystemExit` — it must not survive the refactoring.
- One error envelope for the whole API (AP-22). Changing it is a contract change: list it.

---

## RP-10 — Transaction Boundary & Referential Integrity

**Before** — multi-step write with no atomicity
```python
cursor.execute("INSERT INTO pedidos …")
for item in itens:
    cursor.execute("INSERT INTO itens_pedido …")
    cursor.execute("UPDATE produtos SET estoque = estoque - … ")
db.commit()          # falha no meio → pedido criado, estoque inconsistente
```

**After**
```python
def criar(self, usuario_id, itens):
    conn = self._conn()
    try:
        conn.execute("BEGIN")
        total = self._calcular_total_e_reservar(conn, itens)   # valida estoque e reserva
        cur = conn.execute(
            "INSERT INTO pedidos (usuario_id, status, total) VALUES (?, ?, ?)",
            (usuario_id, STATUS_PENDENTE, total))
        pedido_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario) "
            "VALUES (?, ?, ?, ?)",
            [(pedido_id, i["produto_id"], i["quantidade"], i["preco"]) for i in itens])
        conn.commit()
        return pedido_id
    except Exception:
        conn.rollback()
        raise
```

The stock decrement becomes conditional, so it cannot go negative under concurrency:
```sql
UPDATE produtos SET estoque = estoque - ? WHERE id = ? AND estoque >= ?
-- rowcount == 0 → estoque insuficiente, aborta a transação
```

Referential integrity in the schema, not in prose:
```sql
CREATE TABLE enrollments (
    id        INTEGER PRIMARY KEY,
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE RESTRICT
);
PRAGMA foreign_keys = ON;   -- SQLite: desligado por padrão em cada conexão
```

**Rules**
- One use case = one transaction. Commit once, at the end.
- Never `commit()` inside a loop.
- Read-then-write on a contended value is a TOCTOU race: use a conditional `UPDATE … WHERE` and check
  the affected row count.
- Declare foreign keys with an explicit `ON DELETE` policy, and enable enforcement (SQLite needs
  `PRAGMA foreign_keys = ON` **per connection**).
- A delete that leaves orphans is a bug even when the response says `200`.

---

## RP-11 — Eliminate N+1

**Before** — 1 + N + N×M queries
```python
for row in pedidos:                                            # N pedidos
    itens = cursor2.execute("SELECT * FROM itens_pedido WHERE pedido_id = " + str(row["id"]))
    for item in itens:                                         # M itens cada
        prod = cursor3.execute("SELECT nome FROM produtos WHERE id = " + str(item["produto_id"]))
```

**After** — one query, grouped in memory
```python
SQL = """
SELECT p.id, p.usuario_id, p.status, p.total, p.criado_em,
       ip.produto_id, ip.quantidade, ip.preco_unitario, pr.nome AS produto_nome
FROM pedidos p
LEFT JOIN itens_pedido ip ON ip.pedido_id = p.id
LEFT JOIN produtos    pr ON pr.id = ip.produto_id
WHERE p.usuario_id = ?
ORDER BY p.id
"""

def listar_por_usuario(self, usuario_id):
    rows = self._conn().execute(SQL, (usuario_id,)).fetchall()
    return agrupar_por_pedido(rows)
```

ORM version — declare the eager load instead of touching lazy relations in a loop:
```python
tasks = db.session.scalars(
    db.select(Task).options(joinedload(Task.user), joinedload(Task.category))
).unique().all()
```

Repeated aggregate counts collapse into one grouped query:
```python
# antes: 5 chamadas .filter_by(priority=n).count()
rows = db.session.execute(
    db.select(Task.priority, func.count()).group_by(Task.priority)).all()
```

**Rules**
- No query call inside a loop over the result of another query. Ever.
- One aggregate query beats five counters.
- `joinedload` / `selectinload` / `include` / `populate` are the ORM's answer — use the framework's,
  do not hand-roll a join if the ORM offers one.
- Grouping rows into a nested structure in application code is fine and cheap; the round trips are what cost.
- In async/callback code this also removes the fan-out that RP-08 was coordinating by hand.

---

## RP-12 — Consolidate Validation

**Before** — the same block in `create` and `update`, plus a rule reimplemented five times
```python
if len(title) < 3:   return jsonify({'error': 'Título muito curto'}), 400
if len(title) > 200: return jsonify({'error': 'Título muito longo'}), 400
if status not in ['pending', 'in_progress', 'done', 'cancelled']: ...
```

**After** — one schema, used by every entry point
```python
# schemas/task_schema.py
from middlewares.errors import ValidationError
from constants import VALID_STATUSES, MIN_TITLE_LENGTH, MAX_TITLE_LENGTH, PRIORITY_RANGE

def validate_task(data, partial=False):
    out = {}
    if "title" in data or not partial:
        title = (data.get("title") or "").strip()
        if not MIN_TITLE_LENGTH <= len(title) <= MAX_TITLE_LENGTH:
            raise ValidationError(
                f"Título deve ter entre {MIN_TITLE_LENGTH} e {MAX_TITLE_LENGTH} caracteres")
        out["title"] = title
    if "status" in data:
        if data["status"] not in VALID_STATUSES:
            raise ValidationError(f"Status inválido. Válidos: {', '.join(VALID_STATUSES)}")
        out["status"] = data["status"]
    if "priority" in data:
        try:
            priority = int(data["priority"])
        except (TypeError, ValueError):
            raise ValidationError("Prioridade deve ser um número inteiro")
        if priority not in PRIORITY_RANGE:
            raise ValidationError("Prioridade deve ser entre 1 e 5")
        out["priority"] = priority
    return out
```

Domain rules duplicated inline collapse into the model method that already exists:
```python
# antes: este if de três níveis, repetido em 5 endpoints
task_data['overdue'] = task.is_overdue()
```

**Rules**
- `partial=True` handles `PATCH`/`PUT` semantics without a second copy of the rules.
- Coerce types *before* comparing. `data['priority'] < 1` on a string is a 500, not a 400.
- Validation raises `ValidationError`; RP-09 turns it into a `400`. Handlers stop returning tuples.
- If a helper implementing the rule already exists but is unused, use it — do not write a third copy.
- Only extract duplication that is genuinely the same rule. Two rules that merely look alike must stay apart.
- A schema library (marshmallow, pydantic, zod, joi) is a fine target when it is already a dependency;
  do not add one for a handful of fields.

---

## RP-13 — Replace Deprecated APIs

**Before / After** — mechanical substitutions
```python
datetime.utcnow()                  → datetime.now(timezone.utc)
datetime.utcfromtimestamp(ts)      → datetime.fromtimestamp(ts, timezone.utc)
Task.query.get(task_id)            → db.session.get(Task, task_id)
Task.query.filter_by(status=s).all() → db.session.scalars(db.select(Task).filter_by(status=s)).all()
Task.query.count()                 → db.session.scalar(db.select(func.count()).select_from(Task))
hashlib.md5(pwd.encode())          → generate_password_hash(pwd)          # ver RP-05
type(tags) == list                 → isinstance(tags, list)
```
```js
new Buffer(str)                    → Buffer.from(str)
url.parse(u)                       → new URL(u)
crypto.createCipher(...)           → crypto.createCipheriv(...)
res.send(404, 'x')                 → res.status(404).send('x')
app.del(...)                       → app.delete(...)
require('body-parser').json()      → express.json()
str.substr(0, 2)                   → str.slice(0, 2)
```

**Rules**
- Timezone change is behavioural: `utcnow()` returns naive, `now(timezone.utc)` returns aware. Comparing
  the two raises `TypeError`. Migrate **every** comparison site in the same change, and check what the
  ORM columns store (`DateTime` vs `DateTime(timezone=True)`).
- Verify after substituting: boot with warnings enabled (`python -W all`, `node --pending-deprecation`)
  and confirm the warning is gone.
- Do not bundle a major framework upgrade into this refactoring. Replace the deprecated call within the
  version in use, and list the upgrade under "Post-Refactoring Actions".
- Removing `SQLALCHEMY_TRACK_MODIFICATIONS` is safe — it only ever silenced a warning about a feature
  that defaults to off.

---

## RP-14 — Extract the Serializer

**Before** — hand-built dicts, duplicated and leaking
```python
def to_dict(self):
    return {'id': self.id, 'name': self.name, 'email': self.email,
            'password': self.password,          # ← senha no payload
            'role': self.role, 'created_at': str(self.created_at)}
```

**After** — one module decides what is public
```python
# serializers/user_serializer.py
PUBLIC_FIELDS = ("id", "name", "email", "role", "active")

def one(user, include_tasks=False):
    data = {f: getattr(user, f) for f in PUBLIC_FIELDS}
    data["created_at"] = _iso(user.created_at)
    if include_tasks:
        data["tasks"] = [task_serializer.one(t) for t in user.tasks]
    return data

def many(users):
    return [one(u) for u in users]

def _iso(value):
    return value.isoformat() if value else None
```

Computed presentation flags move here too, sourced from the model's rule:
```python
def one(task):
    return {**base(task), "overdue": task.is_overdue()}     # regra no model, exibição no serializer
```

**Rules**
- **Allowlist, never denylist.** A new sensitive column must not become public by default.
- The serializer is the only place a domain object becomes JSON. Models stop having `to_dict`.
- Date formatting lives here, once. Prefer ISO-8601 over `str(datetime)`.
- Keep the existing key names and envelope unless a finding required a change — this is the API contract.
- Removing `password` from a response **is** a contract change. It is required by AP-05, and it goes in
  "Intentional behaviour changes".

---

## RP-15 — Structured Logging

**Before**
```python
print("Produto criado com ID: " + str(id))
print("ERRO ao criar produto: " + str(e))
```
```js
console.log(`Processando cartão ${cc} na chave ${config.paymentGatewayKey}`);   // vaza segredos
```

**After**
```python
# middlewares/logging.py
import logging, sys

def build_logger(settings):
    logger = logging.getLogger("app")
    logger.setLevel(settings.log_level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s %(message)s"))
    logger.addHandler(handler)
    return logger
```
```python
logger.info("produto criado", extra={"produto_id": produto_id})
logger.exception("falha ao criar produto")     # inclui a stack automaticamente
```

**Rules**
- Levels carry meaning: `DEBUG` diagnostics, `INFO` business events, `WARNING` recoverable, `ERROR`
  failed operation, `CRITICAL` app-level failure.
- Level comes from config, defaulting to `INFO`.
- **Never log secrets, passwords, tokens or card numbers.** Mask them (`**** **** **** 4444`).
- `logger.exception` inside an `except` block; it captures the traceback for free.
- Business side effects disguised as logs (`print("ENVIANDO EMAIL: …")`) are not a logging problem —
  they belong to a service (RP-06). Do not "fix" them by converting the `print` to a `logger.info`.

---

## RP-16 — Named Constants

**Before**
```python
if faturamento > 10000:  desconto = faturamento * 0.1
elif faturamento > 5000: desconto = faturamento * 0.05
if status not in ["pendente", "aprovado", "enviado", "entregue", "cancelado"]: ...
```

**After**
```python
# constants.py
from enum import StrEnum

class StatusPedido(StrEnum):
    PENDENTE  = "pendente"
    APROVADO  = "aprovado"
    ENVIADO   = "enviado"
    ENTREGUE  = "entregue"
    CANCELADO = "cancelado"

FAIXAS_DESCONTO = (          # (faturamento mínimo, percentual)
    (10_000, 0.10),
    ( 5_000, 0.05),
    ( 1_000, 0.02),
)
```
```python
def calcular_desconto(faturamento):
    for minimo, percentual in FAIXAS_DESCONTO:
        if faturamento > minimo:
            return faturamento * percentual
    return 0.0
```

**Rules**
- Enums for closed sets of values — they make the invalid state unrepresentable and give you the
  validation list for free.
- Business thresholds become named data, so the rule can be changed without editing control flow.
- The constant lives where the rule lives (domain constants near the model), not in a global `utils`.
- If constants already exist and are unused, adopt them instead of adding a parallel set.
- Values crossing the wire keep their exact string (`StrEnum` serializes as the string it wraps).

---

## RP-17 — Rename & Remove Dead Code

**Before**
```js
let u = req.body.usr, e = req.body.eml, p = req.body.pwd, cid = req.body.c_id, cc = req.body.card;
```

**After** — internal names become meaningful; the wire contract is untouched
```js
const { usr: name, eml: email, pwd: password, c_id: courseId, card: cardNumber } = req.body;
```

Deletions in the same pass:
```python
import json, os, sys, time     # nenhum é usado → remover
def generate_id():             # nunca chamado → remover
    import uuid
    return str(uuid.uuid4())
```

**Rules**
- Rename **internal** identifiers freely; the request/response field names are the public contract and
  must not change silently. Note the desired API-level rename under "Post-Refactoring Actions".
- Rename modules that lie about their contents: `utils.js` holding config + cache + crypto becomes
  `config/`, `infra/cache.js` and `security/password.js`. `report_routes.py` owning categories CRUD
  gets a `category_routes.py`.
- Delete unused imports, unused functions, unreachable branches and commented-out code. Git remembers.
- Remove declared-but-unimported dependencies from the manifest, and say so — fewer packages, smaller
  attack surface.
- Verify before deleting: a "dead" function may be referenced dynamically (`getattr`, string dispatch,
  a route name). Grep the whole tree, including config and templates.

---

## Verification after each pattern

- The project still imports/parses. Check as you go, not once at the end.
- The finding this pattern targets no longer matches its detection signal.
- No route disappeared. Diff the route inventory against Phase 1's.
- Nothing new was introduced that a catalog signal would flag.
