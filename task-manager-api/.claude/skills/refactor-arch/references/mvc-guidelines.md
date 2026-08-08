# Target Architecture — MVC Guidelines (Phase 3)

What the refactored project must look like when Phase 3 finishes. The layer contract below is
language-agnostic; the layouts at the end show how it materializes per stack.

---

## The layers

### Model — *owns the data and the rules about the data*

**May:** define the schema; read and write persistence; enforce invariants that are true regardless of
who is asking (a price cannot be negative, a task's status is one of four values); expose queries
expressed in domain terms (`find_overdue()`, not `SELECT * WHERE due_date < ?`); compute derived
domain values (`is_overdue()`, `order_total()`).

**May not:** import the HTTP framework; touch `request` / `req` / `res` / session / headers; return
HTTP status codes; build API response payloads; decide which fields a client may see; call other
layers upward.

**Test:** instantiable and callable without an HTTP server.

### View / Routes — *owns the mapping between URLs and the application*

**May:** declare `METHOD /path → controller function`; group routes by domain (blueprint, router,
module); apply route-level middleware (auth guard, rate limit); own path prefixes.

**May not:** contain business rules, validation logic, data access, or any `if` about domain state. A
route file should read as a table of contents. If a route body is longer than one line, it is doing
someone else's job.

> In a JSON API the "View" is the routing + response-shaping layer. Where a project renders templates,
> templates belong here too. Serializers/presenters — the code that turns a domain object into JSON —
> are part of this layer's responsibility, kept in their own module.

### Controller — *owns the use case*

**May:** parse and validate the request; call models/services in the right order; translate a domain
result into an HTTP status code and a serialized body; raise typed domain errors for the error
middleware to handle.

**May not:** contain SQL or query-builder calls; recompute a rule a model already owns; format dates
or build payloads by hand (delegate to the serializer); catch every exception into a generic 500 (the
middleware does that once, centrally).

**Size:** a controller function that is more than ~30 lines is hiding business logic. Extract it.

### Supporting modules

| Module | Responsibility |
| --- | --- |
| `config/` | Every environment-dependent value, read from env vars, with safe non-secret defaults and fail-fast validation for required secrets. The only module that reads the environment. |
| `middlewares/` | Cross-cutting concerns: centralized error handler, request logging, CORS, auth. One place, applied once. |
| `serializers/` (or `schemas/`, `presenters/`) | The single definition of what each entity looks like on the wire, and which fields are public. |
| `services/` | Use-case orchestration that spans multiple models, or integration with the outside world (mailer, payment gateway). Optional — introduce one only when a controller would otherwise coordinate three or more models, or when an external system needs a seam for testing. |
| `<entry point>` | The composition root: build config, open the DB, wire models/controllers/routes/middlewares, start the server. Nothing else. |

---

## Dependency direction

```
Routes ──▶ Middlewares ──▶ Controllers ──▶ Services ──▶ Models ──▶ Data access
                                │                                      │
                                └──▶ Serializers                    Config
```

Dependencies point **one way only**. Rules that follow from this and that you must verify before
declaring Phase 3 done:

- No model imports a controller, a route, or the HTTP framework.
- No route imports a model directly — it goes through its controller.
- No layer imports the entry point (that is a circular import waiting to happen).
- Config is imported by everyone and imports nobody.
- If two modules import each other, the shared thing belongs in a third module below both.

---

## Naming and file organization

- **One file per domain entity, per layer:** `models/produto.py` ↔ `controllers/produto_controller.py`
  ↔ `routes/produto_routes.py`. Finding the code for a feature must be a mechanical operation.
- **Suffix by layer** (`*_controller`, `*_routes`, `*_model`) *or* rely on the directory — pick one
  convention and apply it everywhere. Do not mix.
- **Name after the domain, never after the mechanism.** `produto_controller`, not `data_handler`;
  `pagamento_service`, not `utils`.
- **No `utils` / `helpers` / `common` / `misc` dumping grounds.** If a helper has a home, put it there.
  A date formatter used by three serializers belongs in the serializer layer.
- **Keep the codebase's existing language.** A Portuguese-named domain stays Portuguese; do not
  translate `produtos` to `products` mid-refactoring — that is churn, not improvement.

---

## Preserving the contract

The refactoring is a restructuring, not a rewrite. Non-negotiable:

- Every original `METHOD + path` still exists and still resolves.
- Status codes for the happy path and for known error paths are unchanged.
- Response body keys are unchanged, **except** where a finding required removing a leaked field or
  fixing a genuinely wrong status code. Every such change is listed in "Intentional behaviour changes".
- Request payload keys are unchanged — even bad ones (`usr`, `eml`, `c_id`). Renaming them breaks every
  client. Rename the *internal* variables and document the API-level fix as a follow-up.
- Routes classified as dangerous in the audit keep their path and method, and return `403` when their
  feature flag is off. A gated route is still a route.

---

## Definition of done

- [ ] Each layer's "may not" list holds — verified by grep, not by intent.
- [ ] The entry point only composes; it declares no route bodies and no business rules.
- [ ] No hardcoded secret anywhere; `.env.example` documents every variable.
- [ ] Data access happens in exactly one layer, with parameterized queries only.
- [ ] Error handling is centralized; no bare `except:` / empty `catch` remains.
- [ ] Every file emptied by the refactoring has been deleted.
- [ ] The app boots, and every baseline route replays with the expected status and body.
- [ ] Every audit finding maps to a change you can point at.

---

## Reference layouts

### Python / Flask

```text
src/
├── config/
│   ├── __init__.py
│   └── settings.py           # env vars, fail-fast on missing secrets
├── infra/
│   ├── __init__.py
│   └── database.py           # connection/session factory, schema bootstrap
├── models/
│   ├── __init__.py
│   ├── produto_model.py
│   ├── usuario_model.py
│   └── pedido_model.py
├── controllers/
│   ├── __init__.py
│   ├── produto_controller.py
│   ├── usuario_controller.py
│   └── pedido_controller.py
├── views/
│   ├── __init__.py
│   └── routes.py             # blueprints: METHOD /path → controller
├── serializers/
│   ├── __init__.py
│   └── produto_serializer.py
├── middlewares/
│   ├── __init__.py
│   ├── error_handler.py      # @app.errorhandler + domain error types
│   └── logging.py
└── app.py                    # composition root: create_app() factory
```

Flask specifics: use an application factory (`create_app(config)`) so the app can be built in tests
with a different config; register one blueprint per domain; put shared request-scoped resources on
`flask.g` with a `teardown_appcontext`, never on a module global; register error handlers for your
domain exception types, not for bare `Exception`.

### Node / Express

```text
src/
├── config/
│   └── index.js              # process.env, with validation
├── infra/
│   └── database.js           # connection factory, promisified driver
├── models/
│   ├── userModel.js
│   ├── courseModel.js
│   └── enrollmentModel.js
├── controllers/
│   ├── checkoutController.js
│   └── reportController.js
├── routes/
│   ├── index.js              # mounts the routers
│   └── checkoutRoutes.js
├── serializers/
│   └── reportSerializer.js
├── middlewares/
│   ├── errorHandler.js       # (err, req, res, next) — must be registered last
│   └── requestLogger.js
├── services/
│   └── paymentService.js     # external gateway, injected
└── app.js                    # composition root
```

Express specifics: the error middleware takes four arguments and is registered **after** all routes;
async handlers must forward rejections (`next(err)` or an `asyncHandler` wrapper) or the centralized
handler never sees them; export the app separately from `listen()` so it is testable; promisify
callback-based drivers at the `infra` boundary so no callback style leaks upward.

### Other stacks

Keep the layer contract, adopt the ecosystem's conventions:

- **Django** — `models.py` / `views.py` / `urls.py` per app; serializers via DRF; settings split by
  environment.
- **NestJS** — module per domain, `*.controller.ts` / `*.service.ts` / `*.entity.ts`; DI is built in,
  so AP-08 is fixed by using the container rather than `new`.
- **Rails / Laravel** — the framework already prescribes MVC; the work is moving logic out of
  controllers into models and service objects, not inventing a tree.
- **Go** — `internal/handler`, `internal/service`, `internal/repository`, `cmd/<app>/main.go` as
  composition root; interfaces defined by the consumer.

Never impose a Python or Node tree on a framework that has its own convention. Matching the ecosystem
is part of the deliverable.
