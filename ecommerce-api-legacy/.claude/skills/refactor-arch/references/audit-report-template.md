# Audit Report Template (Phase 2)

The report is the deliverable a human reviews before approving any code change. It must be readable
top to bottom, and every claim in it must be checkable against the repository.

Save it to the `--report` path and print the same content to the terminal.

---

## Writing rules

1. **Labels in English, prose in PT-BR.** Section headers, field names, severity and anti-pattern names
   are English. `Description`, `Impact` and `Recommendation` are written in Brazilian Portuguese with
   technical terms kept in English.
2. **Exact locations, always.** `File: models.py:28` or `File: models.py:28-49`. Never a bare filename,
   never "várias linhas", never an approximate range. Paths are relative to the project root.
3. **Sorted by severity**, `CRITICAL` → `HIGH` → `MEDIUM` → `LOW`. Within a severity, most impactful
   first. Number findings sequentially across the whole report (`#1`, `#2`, …) so they can be
   referenced in conversation.
4. **One anti-pattern per finding.** Repeated occurrences of the same pattern go in the `Occurrences`
   list of a single finding.
5. **Evidence is a real quote.** The snippet must be copied from the file, not paraphrased. Keep it to
   the 1–6 lines that prove the point.
6. **Impact is concrete.** Not "dificulta a manutenção" but "qualquer usuário pode ler a tabela
   `usuarios` inteira, incluindo senhas, com uma requisição HTTP".
7. **Recommendation names the transformation.** Every finding ends with the `RP-xx` that will fix it, so
   Phase 3 is a mechanical consequence of Phase 2.
8. **No finding without a file read.** If it is not in the code you read, it is not in the report.

---

## Template

````markdown
# ARCHITECTURE AUDIT REPORT

Project:   <project directory name>
Stack:     <language> + <framework version>
Files:     <N> analyzed | ~<M> lines of code
Database:  <engine> — <N> tables
Routes:    <N> endpoints
Date:      <YYYY-MM-DD>
Skill:     refactor-arch

---

## Summary

| Severity | Count |
| --- | --- |
| CRITICAL | <n> |
| HIGH | <n> |
| MEDIUM | <n> |
| LOW | <n> |
| **Total** | **<n>** |

<Um parágrafo em PT-BR: o veredito arquitetural. O que este projeto é hoje, qual é o problema
estrutural dominante, e o que a refatoração vai mudar. Três a cinco frases.>

---

## Findings

### #<n> [<SEVERITY>] <Anti-pattern name> (<AP-xx>)

**File:** `<path>:<line>` ou `<path>:<start>-<end>`

**Description:** <O que está errado, em PT-BR, descrevendo o código concreto — não a categoria.>

**Evidence:**
```<lang>
<trecho real do arquivo, 1-6 linhas>
```

**Occurrences:** `<path>:<line>`, `<path>:<line>`, … *(omitir a linha inteira quando houver só uma)*

**Impact:** <Consequência concreta e verificável, em PT-BR.>

**Recommendation:** <O que fazer, em PT-BR.> → `RP-xx`

---

<repetir para cada finding, em ordem de severidade>

---

## Deprecated APIs

<Obrigatório. Se nada foi encontrado, escrever: "Nenhuma API deprecated detectada para
<framework> <versão> / <runtime> <versão>." e descrever como foi verificado.>

| API | Location | Status | Replacement |
| --- | --- | --- | --- |
| `<api>` | `<path>:<lines>` | deprecated desde <versão> / removida em <versão> | `<substituto>` |

**Runtime warnings capturadas no boot:**
```text
<saída literal de stderr, ou "nenhuma">
```

---

## Refactoring Plan Preview

O que a Fase 3 vai fazer, se aprovada:

```text
<árvore da estrutura MVC alvo>
```

| # | Step | Findings resolvidos |
| --- | --- | --- |
| 1 | Config extraction | #<n>, #<n> |
| 2 | Data access layer | #<n> |
| … | … | … |

**Contract preservation:** os <N> endpoints originais continuam existindo, com os mesmos métodos,
paths e status codes.

**Intentional behaviour changes** *(cada uma exigida por um finding — sem isso o finding não é
resolvido)*:

- `<METHOD /path>` — <o que muda e por quê> (finding #<n>)

---

## Accepted / Out of Scope

<O que foi visto e deliberadamente não virou finding, e por quê. Ex.: scripts de seed, arquivos de
teste, código gerado, decisões legadas intencionais. Uma lista curta aumenta a confiança no relatório.>

---

## Post-Refactoring Actions (fora do escopo da skill)

<Ações que a refatoração não pode executar, mas que os findings exigem. Ex.: revogar e rotacionar os
secrets vazados — removê-los do código não os remove do histórico do git; forçar reset de senha dos
usuários cujos hashes eram MD5.>

---

Total: <n> findings
````

---

## Terminal output

The terminal gets the same content, wrapped in the banner so it reads like the tool it is:

```text
================================
ARCHITECTURE AUDIT REPORT
================================
Project: <name>
Stack:   <stack>
Files:   <N> analyzed | ~<M> lines of code

Summary
CRITICAL: <n> | HIGH: <n> | MEDIUM: <n> | LOW: <n>

Findings

[CRITICAL] <Anti-pattern name>
File: <path>:<lines>
Description: <PT-BR>
Impact: <PT-BR>
Recommendation: <PT-BR>

<...>

================================
Total: <n> findings
Report saved to: <path>
================================

Phase 2 complete. Proceed with refactoring (Phase 3)? [y/n]
```

Then stop and wait. Nothing after the gate line — no tool calls, no planning, no file writes.

---

## Worked example of a single finding

Use this as the calibration point for tone and specificity.

````markdown
### #2 [CRITICAL] SQL Injection via String-Built Queries (AP-02)

**File:** `models.py:28`

**Description:** Todas as queries do módulo são montadas por concatenação de string com valores que
vêm direto do request. Em `get_produto_por_id` o `id` é interpolado sem qualquer sanitização; em
`login_usuario` o mesmo acontece com `email` e `senha`, o que permite bypass de autenticação com um
payload como `' OR '1'='1' --`.

**Evidence:**
```python
cursor.execute("SELECT * FROM produtos WHERE id = " + str(id))
```

**Occurrences:** `models.py:28`, `models.py:47-50`, `models.py:57-61`, `models.py:68`,
`models.py:92`, `models.py:109-111`, `models.py:126-129`, `models.py:140`, `models.py:148-151`,
`models.py:157-161`, `models.py:163-166`, `models.py:174`, `models.py:188`, `models.py:192`,
`models.py:220`, `models.py:224`, `models.py:279-281`, `models.py:289-297`

**Impact:** Qualquer cliente HTTP consegue ler, alterar ou apagar toda a base — incluindo a tabela
`usuarios`, que guarda senhas em plaintext — e autenticar-se como qualquer usuário sem conhecer a
senha. Não é um risco teórico: `GET /produtos/busca?q=' OR 1=1 --` já é suficiente.

**Recommendation:** Substituir toda concatenação por queries parametrizadas (`?` + tupla de
parâmetros) e mover o acesso a dados para repositórios por entidade, de forma que exista um único
ponto onde SQL é escrito. → `RP-02`
````
