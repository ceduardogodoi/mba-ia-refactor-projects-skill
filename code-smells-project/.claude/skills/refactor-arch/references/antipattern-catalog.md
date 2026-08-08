# Anti-Pattern Catalog (Phase 2)

The authority on what counts as a finding, how it is detected, and how it is classified.

Each entry gives you **detection signals** that are concrete enough to grep for or point at. "Bad
code" is not a signal; *"SQL query built with `+` on a value coming from `request`"* is. Each entry
also gives you a **not a finding when** clause — respect it, false positives destroy a report's
credibility.

---

## Severity rules

| Severity | Rule | Typical examples |
| --- | --- | --- |
| `CRITICAL` | Exposes sensitive data, allows unauthorized action, corrupts data, or so completely destroys separation of concerns that the system cannot be reasoned about. | Hardcoded credentials, SQL Injection, arbitrary-query endpoint, God Class holding schema + routing + business rules, passwords in plaintext. |
| `HIGH` | Strong MVC/SOLID violation that makes the code untestable or unchangeable in isolation. | Business logic inside controllers, mutable global state, hardcoded dependencies with no injection, callback pyramids, swallowed exceptions, missing transaction boundaries. |
| `MEDIUM` | Duplication, moderate performance problems, missing guards, deprecated APIs, standardization gaps. | N+1 queries, copy-pasted validation, unvalidated input, `datetime.utcnow()`, manual serialization, `print` as logging. |
| `LOW` | Readability and consistency only. Nothing breaks, nothing leaks. | Magic numbers, `usr`/`eml`/`c_id` naming, unused imports, inconsistent response envelopes. |

Tie-breakers, in order:

1. Does it leak data or allow an unauthorized action? → `CRITICAL`.
2. Does it make the system produce wrong data? → `CRITICAL` if silent, `HIGH` if visible.
3. Does it make a unit test impossible without booting the whole app? → `HIGH`.
4. Does it cost performance or repeat itself? → `MEDIUM`.
5. Is a reader merely slowed down? → `LOW`.

**Escalation:** an individually-MEDIUM pattern becomes `HIGH` when it is systemic (present in every
handler) and load-bearing. Say so in the finding: *"MEDIUM isoladamente, elevado a HIGH por ocorrer em
todos os 14 handlers"*.

---

## CRITICAL

### AP-01 — Hardcoded Secrets & Credentials

**Definition:** Secrets embedded in source instead of being read from the environment.

**Detection signals**
- Assignments to identifiers matching `secret|password|passwd|pwd|pass|token|api_?key|apikey|private_?key|credential|salt|dsn|conn(ection)?_?string` with a string literal on the right.
- Known key prefixes: `pk_live_`, `sk_live_`, `sk-`, `AKIA`, `ghp_`, `xoxb-`, `-----BEGIN * PRIVATE KEY-----`.
- Framework config lines: `app.config['SECRET_KEY'] = '...'`, `JWT_SECRET = '...'`, `django SECRET_KEY`.
- Connection strings with inline credentials: `postgres://user:pass@host`, `mongodb+srv://…:…@`.
- SMTP/service blocks: `email_password`, `smtp_pass`, `self.email_user = '...'`.
- A secret **echoed in a response body** (a `/health` endpoint returning `secret_key`) — that is a second, separate finding at CRITICAL.

**Not a finding when:** the value comes from `os.environ` / `process.env` with a non-secret default
(`port`, `host`, `LOG_LEVEL`), or the file is clearly a `.env.example` / fixture with obviously fake
values.

**Impact:** anyone with repository read access (including CI logs and forks) owns production. Git
history keeps the value forever, so rotation is mandatory, not optional.

**Fix:** `RP-01`. Always state in the report that the leaked value **must be revoked**, because
removing it from the code does not remove it from history.

---

### AP-02 — SQL Injection via String-Built Queries

**Definition:** Query text assembled by concatenation or interpolation with values that reach the
application from outside.

**Detection signals**
- `cursor.execute("… " + var)`, `"SELECT … WHERE id = " + str(id)`.
- f-strings / template literals inside query text: `f"… WHERE email = '{email}'"`, `` `… WHERE id = ${id}` ``.
- `%` formatting: `"… WHERE nome LIKE '%%%s%%'" % termo`.
- Incremental query building: `query += " AND categoria = '" + categoria + "'"`.
- ORM raw escape hatches carrying interpolation: `db.session.execute(f"…")`, `sequelize.query(\`…\`)`, `knex.raw(\`…\`)`, `Model.objects.raw(f"…")`.
- Trace the variable back: if it originates in `request.args`, `request.get_json()`, `req.body`,
  `req.params`, `req.query`, headers, or a file/queue payload, it is **exploitable** — not merely
  bad style.

**Not a finding when:** the query uses placeholders (`?`, `%s`, `$1`, `:name`) with a parameter
sequence, or the interpolated value is a code-controlled constant (a table name from a literal
allowlist). Interpolating a code-controlled value is still `LOW`/`MEDIUM` style, not CRITICAL.

**Impact:** full read/write of the database, authentication bypass (`' OR '1'='1`), data destruction.

**Fix:** `RP-02`.

---

### AP-03 — Arbitrary Query / Command Execution Endpoint

**Definition:** A route that takes code — SQL, shell, or an expression — from the request and runs it.

**Detection signals**
- A handler passing a request field straight to an executor: `cursor.execute(dados.get("sql"))`, `db.run(req.body.query)`.
- `eval(`, `exec(`, `Function(`, `child_process.exec(`, `os.system(`, `subprocess.*(shell=True)` with request-derived input.
- Destructive admin routes with no authentication: `/admin/reset-db`, `/admin/query`, `/debug/*`, mass `DELETE FROM`.
- Deserialization of request data with `pickle.loads`, `yaml.load` (unsafe loader), `unserialize`.

**Not a finding when:** the route is behind real authentication *and* authorization *and* the input is
restricted to a fixed allowlist. Being "internal only" is not a mitigation unless enforced in code.

**Impact:** total compromise. This is not a code smell, it is a backdoor.

**Fix:** `RP-03`.

---

### AP-04 — God Class / God Module

**Definition:** One class or module owning responsibilities that belong to three or more layers.

**Detection signals**
- A single file combining ≥3 of: schema creation, seed data, routing, business rules, data access, serialization, notifications, config.
- A class with a method like `setupRoutes(app)` — routing defined inside a class that also owns the DB handle.
- Module length far beyond the project's median (>300 lines is a smell; >500 is the pattern), or a file that changes for unrelated reasons.
- A `Manager`, `Helper`, `Util`, `Handler`, `Service` or `Core` class with no cohesive noun in its name and >8 public methods.
- Imports spanning every concern: DB driver + HTTP framework + crypto + mailer in one file.

**Not a finding when:** the file is long but cohesive — 400 lines of one entity's queries is a big
model, not a God Class. Cohesion, not length, decides.

**Impact:** nothing can be tested in isolation; any change risks everything; parallel work guarantees
conflicts.

**Fix:** `RP-04`.

---

### AP-05 — Insecure Credential Handling & Sensitive Data Exposure

**Definition:** Passwords stored recoverably or with an unsuitable hash, and/or sensitive fields
returned in responses.

**Detection signals**
- Plaintext storage: a `password`/`senha` column written straight from the request; a login query comparing `senha = '<input>'`.
- Unsuitable hashes: `hashlib.md5`, `hashlib.sha1`, `crypto.createHash('md5'|'sha1')`, plain `sha256` with no salt or KDF, any homemade function (`badCrypto`, base64, XOR, `substring` of a digest).
- Missing a real KDF: no `bcrypt`, `argon2`, `scrypt`, `pbkdf2`, `werkzeug.security.generate_password_hash`.
- Serializers exposing secrets: `to_dict()` / `toJSON()` including `password`, `senha`, `pass`, `token`, `cpf`, `card`; `SELECT *` piped directly into a response.
- Secrets in logs: `console.log(\`… cartão ${cc} … ${config.paymentGatewayKey}\`)`, `print("senha: " + senha)`.
- Predictable or fake tokens: `'fake-jwt-token-' + user.id`, sequential session ids.

**Not a finding when:** the field is genuinely public, or the "password" is a per-request opaque value
never persisted.

**Impact:** one leaked dump exposes every user's credentials, and password reuse spreads it across
other services. Fake tokens mean there is no authentication at all.

**Fix:** `RP-05` (hashing) and `RP-14` (serializer stripping).

---

## HIGH

### AP-06 — Business Logic in the Controller / Route Handler (Fat Controller)

**Definition:** Domain rules, calculations, orchestration and data access living in the HTTP handler.

**Detection signals**
- Money, discount, tax, score, aggregate or state-machine computation inside a handler.
- Data access called directly from the route function (`Task.query.filter(...)`, `db.get(...)`, raw SQL).
- Handlers longer than ~40 lines, or nesting depth ≥4.
- The same domain rule reimplemented in several handlers (the overdue check duplicated across list, detail, stats and report endpoints).
- Side effects — email, SMS, push, audit log — fired inline from the handler.
- The handler is impossible to call without a request context, so the rule cannot be unit-tested.

**Not a finding when:** the handler only parses input, calls one collaborator, and maps the result to a
status code. That is exactly what a controller should be.

**Impact:** business rules cannot be tested, reused or changed in one place; they drift between
endpoints and start disagreeing with each other.

**Fix:** `RP-06`.

---

### AP-07 — Mutable Global State / Module-Level Singleton

**Definition:** Shared mutable state at module scope, most often a connection or a cache.

**Detection signals**
- `global <name>` reassigned inside a function; a module-level `db_connection = None` lazily filled.
- `let globalCache = {}`, `let totalRevenue = 0` exported and mutated from elsewhere.
- A single connection shared across requests, especially with thread-safety escape hatches: `sqlite3.connect(..., check_same_thread=False)`.
- Mutable default arguments (`def f(items=[])`), class attributes mutated per instance.
- A value exported by reference then reassigned in another module (the importer keeps the stale copy — a silent correctness bug).

**Not a finding when:** the module-level object is immutable configuration, or a properly
request-scoped factory (`flask.g`, an app-scoped connection pool, a DI container).

**Impact:** cross-request contamination, race conditions under concurrency, tests that pass alone and
fail together, and state that cannot be reset.

**Fix:** `RP-07`.

---

### AP-08 — Hardcoded Dependencies / No Dependency Injection

**Definition:** A component instantiates or imports its collaborators directly, so it cannot be
substituted.

**Detection signals**
- `new SmtpClient()`, `NotificationService()`, `PaymentGateway()` constructed inside the consumer.
- Concrete infrastructure imported into domain code (`import smtplib` inside a service that also holds business rules; a DB driver imported by a model that also formats output).
- Configuration read from within a low-level component (`self.email_host = 'smtp.gmail.com'` in the notifier's constructor) instead of being handed in.
- No seam: no constructor parameter, factory, registry or interface to swap the collaborator.

**Not a finding when:** the collaborator is a pure function or a stdlib value with no I/O.

**Impact:** every test touches the network; swapping a provider means editing business code; the
dependency direction points from domain to infrastructure, inverting the architecture.

**Fix:** `RP-07`.

---

### AP-09 — Callback Hell / Deep Nesting

**Definition:** Control flow expressed through nested callbacks or nested conditionals deep enough
that the happy path cannot be read.

**Detection signals**
- Callback nesting ≥3 levels; closing sequences like `});\n});\n});\n});`.
- Async work coordinated by hand-rolled counters: `let pending = items.length; … pending--; if (pending === 0) res.json(...)`.
- `self = this` / `that = this` aliasing to escape scope.
- Error handling repeated at every level, or an `err` parameter declared and never checked.
- `if` nesting ≥4, or arrow-shaped code where the same condition is re-tested at several depths.
- A response sent from inside several branches, with no guarantee it is sent exactly once.

**Not a finding when:** two levels of nesting on a genuinely sequential flow.

**Impact:** the manual counter approach is a race condition waiting to happen — one error path skips a
decrement and the request hangs forever, or `res` is sent twice and Express throws
`ERR_HTTP_HEADERS_SENT`. It is also untestable.

**Fix:** `RP-08`.

---

### AP-10 — Swallowed Exceptions & Generic Error Handling

**Definition:** Errors caught and discarded, or every error collapsed into the same opaque response.

**Detection signals**
- `except:` / `except Exception: pass`, `catch (e) {}`, `catch { }`.
- `try/except` returning a generic `{'error': 'Erro interno'}, 500` with no logging and no
  distinction between a 404, a validation error and a bug.
- The same `try/except Exception → jsonify(500)` block copy-pasted into every handler — error handling
  belongs in one middleware, not in twenty handlers.
- A callback's `err` argument ignored: `db.run(..., (err) => { res.send("ok") })`.
- Exception detail leaked to the client: `jsonify({"erro": str(e)})` exposes SQL and paths.
- `except` used for control flow where a check would do.

**Not a finding when:** the exception is caught, logged with context, and deliberately converted to a
domain-specific result.

**Impact:** failures become invisible; the client cannot tell "not found" from "database is down";
debugging in production is guesswork; stack details leak to attackers.

**Fix:** `RP-09`.

---

### AP-11 — Missing Transaction Boundary & Orphaned Records

**Definition:** A multi-step write with no atomicity, or a delete that leaves dangling references.

**Detection signals**
- Several `INSERT`/`UPDATE` in one use case with no `BEGIN`/`COMMIT`/`ROLLBACK` and no unit of work — a failure halfway leaves the database inconsistent (order created, stock not decremented).
- Commit inside a loop instead of once at the end.
- `DELETE FROM parent` with no `ON DELETE CASCADE`, no FK constraint, and no manual child cleanup.
- Foreign-key columns declared as plain integers with no `FOREIGN KEY` clause.
- Read-then-write with no locking or conditional update (`SELECT estoque` … later … `UPDATE estoque = estoque - n`) — a TOCTOU race that oversells stock.
- Code (or a comment, or a response message) that admits the inconsistency: *"as matrículas e pagamentos ficaram sujos no banco"*.

**Not a finding when:** the operation is a single statement, or soft deletes with intentional retention.

**Impact:** silent data corruption that grows over time and is expensive to reconcile later.

**Fix:** `RP-10`.

---

## MEDIUM

### AP-12 — N+1 Queries

**Definition:** One query per row of a previous result instead of a single set-based query.

**Detection signals**
- A query call inside a `for` / `forEach` / list comprehension whose iterable came from another query.
- Nested loops each issuing a query (products → enrollments → user → payment: 1 + N + N×M queries).
- ORM lazy relations accessed inside a loop with no `joinedload` / `selectinload` / `include` / `populate`.
- Repeated counters: `Task.query.filter_by(priority=1).count()` five times in a row, where one `GROUP BY` answers all of them.
- Re-fetching a row already in hand (`SELECT preco FROM produtos WHERE id = ?` for a product loaded moments earlier).

**Not a finding when:** the outer set is provably bounded and tiny (a fixed enum), and the join would
hurt readability for no measurable gain.

**Impact:** latency grows linearly (or quadratically) with data; fine with 10 seed rows, fatal with
10.000. Under async callbacks it also multiplies AP-09's race surface.

**Fix:** `RP-11`.

---

### AP-13 — Duplicated Logic

**Definition:** The same rule expressed in more than one place.

**Detection signals**
- Identical validation blocks in `create` and `update` handlers.
- The same computation inlined repeatedly (the "is it overdue" three-level `if` reimplemented in list, detail, per-user, stats and report endpoints).
- The same serialization dictionary rebuilt by hand in several functions.
- A helper that already implements the rule (`Task.is_overdue()`, `utils.process_task_data()`) sitting **unused** next to five inline copies — duplication *plus* dead code.
- Regex literals repeated across files (`r'^[a-zA-Z0-9+_.-]+@…'` in the route and in `utils/helpers.py`).

**Not a finding when:** the similarity is coincidental — two rules that look alike today but change for
different reasons. Do not merge those.

**Impact:** a rule change is applied to three of five copies, and the endpoints start disagreeing.
This is how "the list says overdue, the detail says it is not" bugs are born.

**Fix:** `RP-12`.

---

### AP-14 — Missing or Misplaced Input Validation

**Definition:** External input reaching domain or persistence without being validated, or validated in
the wrong layer.

**Detection signals**
- `request.get_json()` / `req.body` fields used with no presence, type or range check.
- Type coercion with no guard: `int(request.args.get('priority'))`, `float(preco_min)` — a non-numeric query string yields a 500.
- Comparisons that assume a type: `if data['priority'] < 1` when `priority` may be a string.
- No length/format limits on strings persisted to sized columns.
- Path params used directly in queries with no existence check.
- Validation living in the route while the same entity is also created elsewhere without it (seeds, other endpoints) — the rule is not enforced by the model.
- No 405/404 handling; unknown fields silently accepted.

**Not a finding when:** a schema library (marshmallow, pydantic, zod, joi) already validates at the
boundary.

**Impact:** 500s instead of 400s, invalid rows in the database, and validation that can be bypassed
through any path that skips that specific handler.

**Fix:** `RP-12`.

---

### AP-15 — Deprecated API Usage  *(mandatory audit pass)*

**Definition:** Use of APIs the platform or framework has deprecated, scheduled for removal, or
already removed in a newer major version.

**How to run the pass — do all four:**

1. Boot the app (or import it) and capture stderr. `DeprecationWarning`, `RemovedInX Warning`,
   `LegacyAPIWarning`, `ExperimentalWarning` and `npm WARN deprecated` are direct evidence — quote them.
   Python needs `-W all` (or `PYTHONWARNINGS=always`) to show them.
2. Grep the registry below for the detected language/framework.
3. Compare the **resolved** framework version (Phase 1) against its changelog/migration guide, and
   check whether any *dependency* is itself deprecated or unmaintained (`npm ls`, `pip list --outdated`,
   `npm audit`).
4. Report the replacement API, not just the problem.

**Registry — Python**

| Deprecated | Since / removed | Replacement |
| --- | --- | --- |
| `datetime.utcnow()`, `datetime.utcfromtimestamp()` | deprecated 3.12 | `datetime.now(timezone.utc)`, `datetime.fromtimestamp(ts, timezone.utc)` |
| `Model.query` / `Query.get()` (Flask-SQLAlchemy legacy) | legacy in SQLAlchemy 2.0 | `db.session.execute(db.select(Model))`, `db.session.get(Model, id)` |
| `@app.before_first_request` | removed in Flask 2.3 | app factory setup or `with app.app_context()` |
| `flask.escape`, `flask.Markup`, `flask.json.JSONEncoder` | removed in Flask 2.4 | `markupsafe.escape`, `markupsafe.Markup`, custom `app.json` provider |
| `werkzeug.urls.url_quote`, `url_encode` | removed in Werkzeug 2.4 | `urllib.parse.quote`, `urlencode` |
| `distutils` | removed in 3.12 | `setuptools`, `packaging` |
| `imp` | removed in 3.12 | `importlib` |
| `pkg_resources` | deprecated | `importlib.metadata`, `importlib.resources` |
| `hashlib.md5` / `sha1` for passwords | never appropriate | `bcrypt`, `argon2`, `scrypt`, `werkzeug.security` |
| `asyncio.get_event_loop()` outside a loop | deprecated 3.10+ | `asyncio.run`, `get_running_loop` |
| `SQLALCHEMY_TRACK_MODIFICATIONS` | vestigial, always `False` | remove the setting entirely |
| bare `type(x) == list` | style, not deprecation | `isinstance(x, list)` |

**Registry — Node / JavaScript**

| Deprecated | Since / removed | Replacement |
| --- | --- | --- |
| `new Buffer(...)`, `Buffer(...)` | deprecated Node 6, runtime warning | `Buffer.from`, `Buffer.alloc` |
| `url.parse()`, `url.resolve()` | legacy | `new URL()` |
| `crypto.createCipher` / `createDecipher` | deprecated Node 10 | `createCipheriv` / `createDecipheriv` |
| `util.isArray`, `util.isDate`, `util._extend` | deprecated | `Array.isArray`, `instanceof`, spread |
| `domain` module | deprecated | `AsyncLocalStorage` |
| `fs.exists` | deprecated | `fs.access`, `fs.existsSync` |
| `res.send(status, body)`, `res.json(status, obj)`, `app.del()` | removed in Express 4 | `res.status(s).send(body)`, `app.delete()` |
| standalone `body-parser` | bundled since Express 4.16 | `express.json()`, `express.urlencoded()` |
| `String.prototype.substr` | Annex B, discouraged | `slice` / `substring` |
| `sqlite3` callback API + `.verbose()` in production | not removed, but superseded | `node:sqlite`, `better-sqlite3`, or a promise wrapper |
| `require('request')`, `moment` | unmaintained | `fetch`/`undici`, `Temporal`/`date-fns`/`dayjs` |
| `process.on('uncaughtException')` as flow control | discouraged | domain errors + centralized handler |

For any other stack, derive the list from the framework's own migration guide; do not invent
deprecations.

**Severity:** `MEDIUM` by default. Raise to `HIGH` when the API is already **removed** in the version
declared in the manifest (the app is one `npm install`/`pip install -U` away from not booting), and to
`CRITICAL` when the deprecated API is the security control itself (`createCipher`, MD5 for passwords).

**Fix:** `RP-13`.

---

### AP-16 — Manual Serialization / Presentation Logic Leak

**Definition:** Domain objects converted to the wire format by hand, in the layer that should not care
about the wire format.

**Detection signals**
- Field-by-field dictionary building repeated across functions: `d = {}; d['id'] = t.id; d['title'] = t.title; …`.
- `str(datetime)` / manual date formatting scattered through data access or domain code.
- A model's `to_dict()` that decides API concerns (which fields the client may see, computed display flags like `overdue`).
- Response-shaping done inside the data layer (`models.py` returning ready-made API payloads).
- The same object serialized differently by different endpoints — `/tasks` returns `user_name`, `/tasks/<id>` does not.

**Not a finding when:** a dedicated serializer/schema/DTO layer owns this and is used consistently.

**Impact:** the API contract has no single definition, so it drifts; adding a field means editing five
functions; sensitive fields leak because there is no one place that decides what is public.

**Fix:** `RP-14`.

---

### AP-17 — Ad-hoc Logging

**Definition:** `print` / `console.log` used as the observability strategy.

**Detection signals**
- `print("…")` / `console.log(...)` in handlers, models or services.
- No `logging` / `winston` / `pino` configuration anywhere.
- No severity levels — an error and a routine event are printed identically.
- Business side effects faked as logs: `print("ENVIANDO EMAIL: …")` standing in for an actual
  notification (that is also AP-06 — the side effect belongs in a service).
- Sensitive data printed (cross-reference AP-05).
- `debug=True` / verbose mode wired on in what is presented as production config.

**Not a finding when:** it is a CLI whose output *is* the interface, or a one-shot script.

**Impact:** nothing is filterable, routable or structured; logs cannot be turned down in production or
up during an incident.

**Fix:** `RP-15`.

---

### AP-18 — Blocking / Unreliable I/O in the Request Path

**Definition:** Slow or failure-prone external calls made synchronously while the client waits.

**Detection signals**
- SMTP, HTTP, or payment-gateway calls inside a request handler with no timeout and no retry.
- `smtplib.SMTP(...)` / `requests.get(...)` / `fetch` awaited inline in a route.
- No timeout argument on any outbound call.
- An external failure turning a successful business operation into a 500 (the order was created, the
  email failed, the client sees an error and retries — creating a second order).
- A CPU-heavy loop in the request path (`for i = 0; i < 10000` doing string concatenation).

**Not a finding when:** the call is genuinely part of the synchronous contract (a payment
authorization the response depends on) *and* has a timeout and error handling.

**Impact:** p99 latency is hostage to a third party; connection pools exhaust; partial failures produce
duplicate business records.

**Fix:** `RP-06` (extract to a service) plus explicit timeouts; queue it if the client does not need
the result.

---

## LOW

### AP-19 — Magic Numbers & Magic Strings

**Detection signals**
- Numeric literals with business meaning inline: `if faturamento > 10000: desconto = faturamento * 0.1`.
- Status/role/priority literals repeated as bare strings: `'pending'`, `'done'`, `'admin'`, `'PAID'`, `status != 'cancelled'`.
- Length and range limits inline: `len(title) < 3`, `priority > 5`, `len(password) < 4`.
- Ports, timeouts, page sizes as literals.
- Constants that **exist** (`VALID_STATUSES`, `MAX_TITLE_LENGTH` in `utils/helpers.py`) while the code
  keeps using literals — worth calling out by name.

**Not a finding when:** the literal is self-evident (`0`, `1`, `''`) or used once in an obvious place.

**Fix:** `RP-16`.

---

### AP-20 — Poor Naming

**Detection signals**
- Single-letter or truncated identifiers outside tight loops: `u`, `e`, `p`, `cid`, `cc`, `t`, `c`, `enr`.
- Abbreviated API field names: `usr`, `eml`, `pwd`, `c_id`, `card` — these are the **public contract**,
  so renaming them is a breaking change; recommend an internal rename plus a documented contract fix.
- Names that lie: `AppManager` (routing + DB + payments), `utils.js` (config + cache + crypto),
  `report_routes.py` (also owns categories CRUD), `badCrypto` (named after its own defect).
- Meaningless containers: `data`, `data2`, `result`, `temp`, `stuff`, `process()`, `handle()`.
- Mixed-language identifiers in one module (`criar_produto` next to `get_todos_produtos`).
- Booleans that do not read as questions (`self.active` vs `is_active`), negated flags (`notDisabled`).

**Fix:** `RP-17`.

---

### AP-21 — Dead Code & Unused Imports

**Detection signals**
- Imports never referenced: `import json, os, sys, time` at the top of a route module that uses none of them.
- Local imports inside functions with no cycle-breaking reason (`def generate_id(): import uuid`).
- Functions defined and never called (`utils.process_task_data`, `Task.validate_status`, `totalRevenue`).
- Exported values that are never imported.
- Commented-out code blocks; unreachable branches after `return`.
- Declared dependencies that are never imported (`marshmallow`, `requests`, `python-dotenv` in a
  `requirements.txt` where nothing imports them) — a deployment weight and a security surface for no benefit.

**Fix:** delete it. Version control remembers.

---

### AP-22 — Inconsistent Response Shape & Status Codes

**Detection signals**
- Envelope used in some endpoints and not others: `{"dados": …, "sucesso": true}` here, a bare array there.
- Error shape varying: `{"erro": …}` vs `{"error": …}` vs a plain string body (`res.send("Bad Request")`).
- Wrong or arbitrary status codes: `200` for a creation, `400` for "not found", `500` for a validation
  failure, `200` on a delete that failed.
- A success message that describes a failure (*"Usuário deletado, mas as matrículas e pagamentos
  ficaram sujos no banco"*).
- Mixed key languages in one API (`dados`/`sucesso` alongside `error`/`message`).

**Not a finding when:** the divergence is documented and intentional (a health endpoint may legitimately
differ).

**Fix:** `RP-09` (one error shape from the centralized handler) plus `RP-14` (one success shape from the
serializer). Any change here is a contract change — list it under "Intentional behaviour changes".

---

## Reporting rules

- **Group, do not spam.** 15 concatenated queries in one file = one AP-02 finding listing all 15 lines.
- **Never report a rule you did not check.** No placeholder findings.
- **A finding on a file you did not read is a fabrication.** Read it or drop it.
- **Cross-reference.** A single line can carry two findings (a hardcoded secret printed to a log is
  AP-01 + AP-17). Report the strongest one and mention the other in its description.
- **Note what you deliberately did not flag.** A short "Accepted / Out of Scope" section (test files,
  seed scripts, intentional legacy shims) makes the report more trustworthy, not less.
