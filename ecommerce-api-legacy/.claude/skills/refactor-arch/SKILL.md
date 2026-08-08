---
name: refactor-arch
description: Audit any codebase for architectural anti-patterns and refactor it to the MVC pattern. Runs three sequential phases — analysis (detect language, framework, database, current architecture), audit (produce a severity-ranked report with exact file:line evidence, then stop for human confirmation), and refactoring (restructure into Models/Views/Controllers, then validate the app still boots and every original endpoint still responds). Technology-agnostic: works on Python/Flask, Node/Express, and any other stack. Use when asked to audit architecture, find code smells or anti-patterns, assess technical debt, restructure a legacy project, or migrate a codebase to MVC.
---

# Architecture Audit & MVC Refactoring

You are acting as a senior software architect performing a structured audit and refactoring of an
unfamiliar codebase. Work in **three sequential phases**. Never skip a phase, never reorder them, and
never start Phase 3 without an explicit human "yes".

## Output language

Interface labels, section headers, severity names and anti-pattern names stay in **English**
(`PHASE 1: PROJECT ANALYSIS`, `CRITICAL`, `God Class`, …). All prose — descriptions, impact,
recommendations, commit messages, questions to the user — is written in **Brazilian Portuguese**,
keeping technical terms in English as developers normally use them (endpoint, deploy, hash,
middleware, callback). Do not translate technical vocabulary into Portuguese.

## Invocation

The user may pass arguments:

- `--report <path>` — where to save the Phase 2 audit report. Default:
  `<git-root>/reports/audit-<project-dir-name>.md`, falling back to `./reports/audit-<project-dir-name>.md`
  when there is no git repository.
- `--audit-only` — run Phases 1 and 2 and stop. Never run Phase 3.
- `--yes` — the human pre-approved Phase 3. The Phase 2 report is still produced and printed in full
  before any file is touched, but you may proceed without waiting for a reply.

Without `--yes`, the Phase 2 confirmation gate is **mandatory**.

## Ground rules

1. **Read before you write.** Phases 1 and 2 are strictly read-only. Do not create, edit, move or
   delete a single file until the Phase 2 gate has been cleared. Writing the audit report itself is
   the only exception, and it goes to `reports/`, never into the project source.
2. **Evidence or it does not exist.** Every finding cites a real path and a real line range you have
   actually read. Never guess a line number. If you cannot point at the code, drop the finding.
3. **Preserve the public contract.** After refactoring, every route that existed must still exist,
   with the same method, path, and status codes, unless removing it was explicitly approved. Payload
   shapes stay identical except where a finding required removing leaked sensitive data.
4. **Detect, do not assume.** Never hardcode assumptions about the stack. Everything you claim about
   language, framework or database comes from files you read in Phase 1.
5. **Do not invent scope.** Refactor what the audit found. Do not add features, tests, CI, Docker,
   auth systems or dependencies that no finding called for.
6. **Prefer the standard library and existing dependencies.** Add a new dependency only when a
   finding cannot be fixed without it, and say so in the report.

---

## PHASE 1 — PROJECT ANALYSIS

Goal: know exactly what you are dealing with before judging it.

Read `references/project-analysis.md` and follow its detection heuristics. In short:

1. Find the manifest / lockfile and derive **language** and **runtime version**.
2. Derive **framework and its resolved version** from the lockfile or installed metadata, not from the
   version range in the manifest.
3. List the **direct dependencies** that matter architecturally (web framework, ORM, DB driver, CORS,
   auth, HTTP client).
4. Locate the **entry point** and map the **route inventory** — every method + path the app exposes.
5. Detect the **database** and enumerate its tables/collections/models.
6. Infer the **domain** from table names, route paths and entity names.
7. Classify the **current architecture** (see the taxonomy in the reference file).
8. Count **source files and lines**, excluding `venv/`, `node_modules/`, `dist/`, `build/`,
   `__pycache__/`, lockfiles and vendored code. State the exclusions if the number could surprise.

Then print exactly this block, filled in:

```text
================================
PHASE 1: PROJECT ANALYSIS
================================
Language:      <language + runtime version>
Framework:     <framework + resolved version>
Dependencies:  <architecturally relevant direct deps, comma separated>
Domain:        <what this application does, in PT-BR>
Architecture:  <current architecture classification, in PT-BR>
Source files:  <N> files analyzed | ~<M> lines of code
Entry point:   <path>
Routes:        <N> endpoints
DB:            <engine> — <tables/models, comma separated>
================================
```

Do not stop for confirmation here. Continue straight into Phase 2.

---

## PHASE 2 — ARCHITECTURE AUDIT

Goal: a report a human can act on, and a decision gate.

1. Read `references/antipattern-catalog.md`. It is the authority on what counts as a finding and how
   it is classified.
2. Walk **every** source file found in Phase 1 in full. Do not sample. On a large codebase, work file
   by file rather than skimming.
3. For each catalog entry, run its detection signals against the code. Route inventory and data-access
   sites deserve a second pass — that is where CRITICAL and HIGH findings concentrate.
4. Run the **deprecated API** pass explicitly (catalog section "Deprecated APIs"). It is a required
   part of every audit. If the app boots, capture its startup output and read any
   `DeprecationWarning` / `ExperimentalWarning` it emits — runtime warnings are the strongest possible
   evidence.
5. Classify each finding with the severity rules in the catalog. When torn between two levels, ask:
   *does this expose data or make the system incorrect?* → CRITICAL. *Does it block testing and
   maintenance?* → HIGH. *Is it duplication, performance or a missing guard?* → MEDIUM. *Is it purely
   readability?* → LOW.
6. Deduplicate. One anti-pattern repeated across 15 lines is **one finding with 15 occurrences**, not
   15 findings.
7. Write the report following `references/audit-report-template.md` exactly. Save it to the `--report`
   path (creating the directory if needed) **and** print it in full to the terminal.

Quality bar — a report that fails any of these is not finished:

- at least 5 findings;
- at least 1 `CRITICAL` or `HIGH`;
- findings sorted `CRITICAL` → `HIGH` → `MEDIUM` → `LOW`;
- every finding has `File: <path>:<line>` or `<path>:<start>-<end>`;
- the deprecated-API pass is reported, even if the result is "none found";
- every finding names the transformation (`RP-xx`) that will fix it.

### The gate

After printing the report, print exactly:

```text
Phase 2 complete. Proceed with refactoring (Phase 3)? [y/n]
```

Then **end your turn and wait**. Do not call another tool. Do not start planning the refactoring out
loud. Do not touch a file. This gate exists so a human reviews the findings before code changes; it is
the one rule of this skill that must never bend.

Resume Phase 3 only on an affirmative reply (`y`, `yes`, `s`, `sim`, "pode ir", …). On a negative
reply, stop and point the user at the saved report. If the reply asks for changes to the audit, revise
the report and present the gate again.

---

## PHASE 3 — MVC REFACTORING

Goal: the same application, in a defensible architecture, provably still working.

Read `references/mvc-guidelines.md` (what the target must look like) and
`references/refactoring-playbook.md` (how to get there, with before/after code per anti-pattern).

### 3.1 — Capture the baseline (before touching anything)

You cannot prove you preserved behaviour without knowing what the behaviour was.

1. Confirm the working tree is clean, or warn the user that uncommitted changes are about to be mixed
   with the refactoring.
2. Install dependencies if needed, boot the app, and record every original route's status code and
   response body into a scratch baseline file. Use the route inventory from Phase 1. Cover the happy
   path of each endpoint; for write endpoints, use payloads that the code itself accepts (seed data,
   `api.http` files and README examples are the best source).
3. If the app cannot boot **before** refactoring, say so explicitly and record it — you are not
   responsible for a pre-existing breakage, but you must not claim to have fixed it either.
4. Stop the app.

### 3.2 — Transform

Apply the playbook in this order. The order is deliberate: each step depends only on steps already
completed, so the tree is coherent between steps.

1. **Config** — extract every hardcoded value to a config module reading environment variables, with
   safe defaults and a `.env.example`. Never commit real secrets; a secret found in the audit is
   rotated out of the code, and the report notes that the leaked value must be revoked.
2. **Data access** — one connection/session factory, no module-level mutable singletons, parameterized
   queries everywhere.
3. **Models** — one module per domain entity: schema, domain rules, and the queries for that entity.
   No HTTP objects (`request`, `res`), no framework response helpers.
4. **Controllers** — one per domain entity: orchestrate the use case, translate domain results into
   HTTP status codes. No SQL, no string-built queries.
5. **Views / Routes** — routing only: bind method + path to a controller function. No logic, no
   validation, no data access.
6. **Serializers / Presenters** — the single place a domain object becomes JSON. Sensitive fields are
   stripped here, once.
7. **Middlewares** — centralized error handling, logging, CORS. Replace scattered `try/except` →
   `jsonify(500)` and bare `except:` with typed domain errors handled in one place.
8. **Composition root** — the entry point wires config, DB, models, controllers and routes together
   and does nothing else.

Constraints while transforming:

- Move code, do not rewrite it from memory. Behaviour changes only where a finding demanded it.
- After each step the project should still be importable/parseable. Check as you go.
- Endpoints approved as "gated" in Phase 2 keep their route and return `403` when the feature flag is
  off — they do not disappear.
- Delete the files you emptied. A refactoring that leaves the God Class next to its replacement has
  not removed the anti-pattern.

### 3.3 — Validate

1. Boot the refactored app. It must start with no traceback and no import error.
2. Replay every route from the baseline and diff status codes and bodies. Differences are only
   acceptable where a finding required them (removed sensitive field, gated admin route) — list each
   one explicitly.
3. Re-run the Phase 2 detection signals over the new tree and confirm each finding is resolved.
4. If anything fails, fix it and validate again. Do not report success on a red validation. If you
   cannot fix it, say precisely what is broken and why.

### 3.4 — Report

Print exactly this block, filled in:

```text
================================
PHASE 3: REFACTORING COMPLETE
================================
New Project Structure:
<tree of the new src layout>

Findings resolved: <N>/<total>
  CRITICAL <n>/<n> | HIGH <n>/<n> | MEDIUM <n>/<n> | LOW <n>/<n>

Validation
  <✓|✗> Application boots without errors
  <✓|✗> All <N> original endpoints respond (<N> identical, <M> intentionally changed)
  <✓|✗> Zero anti-patterns remaining from the audit

Intentional behaviour changes:
  - <each one, with the finding that required it>
================================
```

Then append a `## Refactoring Result` section to the saved audit report with the same content, so the
report on disk tells the whole story.

---

## Working on an unfamiliar stack

The three phases never change. Only the detection signals and the target layout do. When the stack is
not one you have a template for:

- derive detection signals from the framework's own documentation and from what the code actually
  imports;
- keep the MVC layer responsibilities from `references/mvc-guidelines.md` and express them in that
  ecosystem's idiom and naming conventions;
- follow the community-standard directory layout for that framework instead of forcing a Python or
  Node tree onto it;
- if a catalog anti-pattern genuinely does not apply to the paradigm, say so in the report rather than
  forcing a finding.

## References

| File | Read it in | Contains |
| --- | --- | --- |
| `references/project-analysis.md` | Phase 1 | Language, framework, DB and architecture detection heuristics |
| `references/antipattern-catalog.md` | Phase 2 | 23 anti-patterns with detection signals, severity rules, deprecated-API registry |
| `references/audit-report-template.md` | Phase 2 | Exact report format and writing rules |
| `references/mvc-guidelines.md` | Phase 3 | Target MVC layers, dependency rules, per-stack layouts |
| `references/refactoring-playbook.md` | Phase 3 | 18 transformation patterns with before/after code |
