# Project Analysis Heuristics (Phase 1)

Everything you report in Phase 1 must come from a file you actually read. This document tells you
which files to read, in what order, and what to conclude from them.

---

## 1. Language and runtime

Look for the manifest first — it is the cheapest, most reliable signal. Search the project root, then
one level down (`src/`, `app/`, `backend/`, `api/`).

| Manifest / marker | Language | Runtime version comes from |
| --- | --- | --- |
| `requirements.txt`, `pyproject.toml`, `Pipfile`, `setup.py`, `environment.yml` | Python | `pyproject.toml` `requires-python`, `venv/pyvenv.cfg`, `.python-version`, `runtime.txt`, or `python3 --version` |
| `package.json` | JavaScript / TypeScript | `engines.node`, `.nvmrc`, or `node --version`; TypeScript if `tsconfig.json` or `.ts` sources exist |
| `go.mod` | Go | `go` directive in `go.mod` |
| `composer.json` | PHP | `require.php` constraint |
| `Gemfile` | Ruby | `.ruby-version`, `Gemfile` `ruby` directive |
| `pom.xml`, `build.gradle(.kts)` | Java / Kotlin | `maven.compiler.release`, `sourceCompatibility` |
| `*.csproj`, `*.sln` | C# | `TargetFramework` |
| `Cargo.toml` | Rust | `rust-version`, `rust-toolchain.toml` |
| `mix.exs` | Elixir | `elixir` requirement |

If several manifests coexist, the language of the **entry point** wins; mention the others as
secondary. A `package.json` next to a Python API is usually tooling, not the application.

**Do not** guess the language from file extensions alone when a manifest exists — a repo with three
`.js` config files and forty `.py` sources is a Python project.

---

## 2. Framework and resolved version

The manifest gives you a *range* (`^4.18.2`, `flask==3.0.0`, `>=2.0`). Report the **resolved** version:

- Node: `package-lock.json` → the `node_modules/<pkg>` entry's `version`, or read
  `node_modules/<pkg>/package.json`. `npm ls <pkg> --depth=0` also works.
- Python: `venv/lib/python*/site-packages/<dist>-<version>.dist-info/`, or `pip show <pkg>`, or
  `<pkg>/__init__.py` `__version__`.
- Other ecosystems: the lockfile (`go.sum`, `Gemfile.lock`, `composer.lock`, `Cargo.lock`, …).

If nothing is installed, report the manifest constraint and mark it: `Flask ~3.0.0 (declared, not installed)`.

Framework identification by dependency name plus import signature:

| Dependency | Framework | Import / usage signature |
| --- | --- | --- |
| `flask` | Flask | `from flask import Flask`, `@app.route`, `Blueprint` |
| `fastapi` | FastAPI | `FastAPI()`, `@app.get`, `APIRouter` |
| `django` | Django | `manage.py`, `settings.py`, `urls.py` |
| `express` | Express | `require('express')`, `app.get/post`, `express.Router()` |
| `@nestjs/core` | NestJS | `@Controller()`, `@Module()` decorators |
| `fastify` | Fastify | `fastify()`, `server.route()` |
| `koa` | Koa | `new Koa()`, `ctx` handlers |
| `gin-gonic/gin` | Gin | `gin.Default()`, `r.GET` |
| `rails` | Rails | `config/routes.rb`, `app/controllers/` |
| `laravel/framework` | Laravel | `routes/web.php`, `artisan` |
| `spring-boot-starter-web` | Spring Boot | `@RestController`, `@RequestMapping` |

Also record architecturally relevant companions: ORM (`sqlalchemy`, `prisma`, `sequelize`,
`typeorm`, `mongoose`, `flask-sqlalchemy`), DB driver (`sqlite3`, `psycopg2`, `pg`, `mysql2`),
`cors`, auth (`jsonwebtoken`, `flask-jwt-extended`, `passport`), validation (`marshmallow`, `zod`,
`joi`, `pydantic`), HTTP client. Skip test and lint tooling — it is not architecture.

Flag dependencies that are **declared but never imported**: that is a LOW finding (AP-19 family) and a
useful signal that the project is not what its manifest claims.

---

## 3. Entry point

In order of confidence:

1. Manifest declaration: `package.json` `main` / `scripts.start`, `pyproject.toml` `[project.scripts]`,
   `Procfile`, `Dockerfile` `CMD`.
2. Framework convention: `app.py`, `main.py`, `wsgi.py`, `manage.py`, `src/app.js`, `index.js`,
   `server.js`, `src/main.ts`, `cmd/*/main.go`.
3. The file that instantiates the application object and calls `listen`/`run`.

Also note **how the app is started** and on which port — Phase 3 validation needs both.

---

## 4. Route inventory

You need every `METHOD /path` the application exposes. This list is the contract that Phase 3 must
preserve, so build it exhaustively.

Search patterns by framework:

| Framework | Patterns to search |
| --- | --- |
| Flask | `@app.route`, `@<bp>.route`, `app.add_url_rule(`, `Blueprint(`, `MethodView` |
| FastAPI | `@app.<method>`, `@router.<method>`, `include_router(` |
| Django | `urls.py` → `path(`, `re_path(`, `include(` |
| Express | `app.<method>(`, `router.<method>(`, `app.use('<prefix>'`, `.route('<path>')` |
| NestJS | `@Get/@Post/@Put/@Delete/@Patch`, `@Controller('<prefix>')` |
| Koa / Fastify | `router.<method>(`, `fastify.route({` |
| Rails | `config/routes.rb` |
| Laravel | `routes/*.php` → `Route::<method>` |
| Spring | `@GetMapping`, `@PostMapping`, `@RequestMapping` |

Record, per route: method, full path (prefix + suffix), the handler function, and the file:line of the
binding. Watch for:

- routes registered **outside** the routing file (a route defined inside a class method, as
  `setupRoutes(app)` does, is itself a finding — see AP-04);
- duplicated `method + path` pairs, where the second registration silently wins or errors;
- prefixes applied at registration (`app.use('/api', router)`, `register_blueprint(bp, url_prefix=...)`).

---

## 5. Database

Detect the engine from, in order: DB driver dependency → connection string / DSN → ORM configuration →
raw `CREATE TABLE` statements → migration files.

| Signal | Engine |
| --- | --- |
| `sqlite3`, `:memory:`, `*.db`, `sqlite:///` | SQLite |
| `psycopg2`, `pg`, `postgres://`, `postgresql+psycopg` | PostgreSQL |
| `mysql2`, `pymysql`, `mysql://` | MySQL / MariaDB |
| `mongoose`, `pymongo`, `mongodb://` | MongoDB |
| `redis`, `ioredis` | Redis (cache/session, usually secondary) |

Enumerate the schema:

- **Raw SQL projects** — grep `CREATE TABLE`; the column list is right there.
- **ORM projects** — every class inheriting the ORM base (`db.Model`, `Base`, `Model`,
  `mongoose.Schema`, `@Entity`) is a table; read `__tablename__` / `tableName` for the real name.
- **Migration-based projects** — the migrations directory is the source of truth.

Also note: where the schema is created (a `CREATE TABLE` inside a request-time function is a finding),
whether seeds run automatically at boot, and whether foreign keys are declared or only implied — an
`user_id` column with no `FOREIGN KEY` and no `ON DELETE` is the seed of AP-11.

---

## 6. Domain inference

Combine three sources and describe the application in one sentence, in PT-BR:

- **Table/model names** — `produtos, pedidos, itens_pedido` → e-commerce; `courses, enrollments, payments` → LMS/education; `tasks, categories` → productivity.
- **Route paths** — `/checkout`, `/reports/vendas`, `/login`.
- **Naming language** — the codebase's own vocabulary tells you the business it models.

Say what it *does*, not what it *is built with*: "API de E-commerce (produtos, pedidos, usuários e
relatório de vendas)" — not "uma API REST em Flask".

---

## 7. Architecture classification

Pick the closest label and justify it in one clause.

| Label | Recognized by |
| --- | --- |
| **Monolítica de arquivo único** | One file holds routing, business rules and data access |
| **Monolítica por camada técnica, sem separação real** | Files named `models.py`/`controllers.py` exist, but `models` runs SQL *and* formats output, or controllers hold business rules |
| **God Class / God Module** | One class or module concentrates schema, seed, routing and use cases |
| **Camadas por tipo (layered by type)** | Real `models/`, `routes/`, `services/` directories — but check whether responsibilities actually match the folder names |
| **MVC** | Routing binds only; controllers orchestrate; models own data and domain rules |
| **Camadas + serviços (service layer)** | MVC plus a use-case layer between controllers and models |
| **Hexagonal / Clean** | Domain isolated behind ports; adapters at the edges |

The most common and most important verdict is *"the folders say layered, the code says monolith"*.
State it plainly: **"Camadas por tipo, mas com responsabilidades vazadas — as rotas atuam como
controllers e contêm regra de negócio, serialização e acesso a dados."**

---

## 8. Counting files and lines

Count only project source. Exclude, and be ready to name the exclusions:

`venv/`, `.venv/`, `env/`, `node_modules/`, `vendor/`, `dist/`, `build/`, `target/`, `__pycache__/`,
`.git/`, `.pytest_cache/`, coverage output, minified bundles, lockfiles, and any generated code.

Count separately and label them: application source, seed/fixture scripts, tests, config files. When
the number could surprise the reader, show the split:
`Source files: 8 files analyzed | ~1.000 lines (7 de aplicação + 1 seed)`.

---

## 9. Output

Fill the Phase 1 block in `SKILL.md` exactly as specified. If a field genuinely does not apply — no
database, no routes — write `n/a` rather than deleting the line, so the shape of the report stays
stable across projects.
