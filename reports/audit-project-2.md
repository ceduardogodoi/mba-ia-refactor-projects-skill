# ARCHITECTURE AUDIT REPORT

Project:   ecommerce-api-legacy
Stack:     JavaScript (Node.js v24.16.0) + Express 4.22.1
Files:     3 analyzed | ~180 lines of code
Database:  SQLite em memória (`:memory:`) — 5 tables
Routes:    3 endpoints
Date:      2026-08-08
Skill:     refactor-arch

---

## Summary

| Severity | Count |
| --- | --- |
| CRITICAL | 6 |
| HIGH | 5 |
| MEDIUM | 4 |
| LOW | 3 |
| **Total** | **18** |

180 linhas conseguem concentrar mais risco que os 780 do projeto anterior. `AppManager` é uma God
Class no sentido literal: o construtor abre o banco, `initDb` cria o schema e insere seeds,
`setupRoutes` define três rotas e dentro delas processa pagamento, cria usuário, grava auditoria e
monta relatório. `utils.js` completa o quadro sendo simultaneamente módulo de configuração, cache
global mutável e biblioteca de criptografia — as três coisas que menos deveriam coabitar.

Três achados elevam este projeto acima do anterior em gravidade. Primeiro, a chave de gateway de
pagamento é uma `pk_live_` real em código e é impressa em log junto com o número de cartão completo a
cada checkout. Segundo, `badCrypto` não é um hash fraco — é um hash com espaço efetivo de 12 bits, que
descarta tudo além do primeiro byte e meio da senha. Terceiro, e verificado empiricamente, uma única
requisição não autenticada com `card` numérico derruba o processo inteiro; como o banco é `:memory:`,
todos os dados morrem junto.

---

## Findings

### #1 [CRITICAL] Hardcoded Secrets & Credentials (AP-01)

**File:** `src/utils.js:1-7`

**Description:** O objeto `config` carrega credencial de banco, chave de gateway de pagamento e
usuário de SMTP como literais. A chave usa o prefixo `pk_live_`, que por convenção indica ambiente de
produção — e o nome da senha de banco (`senha_super_secreta_prod_123`) confirma a intenção.

**Evidence:**
```js
const config = {
    dbUser: "admin_master",
    dbPass: "senha_super_secreta_prod_123", 
    paymentGatewayKey: "pk_live_1234567890abcdef",
```

**Impact:** Qualquer pessoa com acesso de leitura ao repositório — incluindo forks e logs de CI — tem
a chave de produção do gateway de pagamento. Nenhuma dessas credenciais é lida de ambiente, então não
há como rotacioná-las sem alterar código.

**Recommendation:** Mover tudo para `process.env` através de um módulo `config/` com validação na
inicialização, e commitar `.env.example`. As três credenciais precisam ser **revogadas**, não apenas
removidas. → `RP-01`

---

### #2 [CRITICAL] Secrets and Card Number Written to Logs (AP-01)

**File:** `src/AppManager.js:45`

**Description:** A cada checkout, o número completo do cartão e a chave do gateway são impressos em
stdout. Confirmado em execução: `Processando cartão 4111222233334444 na chave pk_live_1234567890abcdef`.

**Evidence:**
```js
console.log(`Processando cartão ${cc} na chave ${config.paymentGatewayKey}`);
```

**Impact:** O PAN completo em log é violação direta de PCI-DSS, que só permite os últimos quatro
dígitos. Como stdout normalmente é coletado por agregadores de log, o dado sai do servidor e passa a
existir em sistemas de terceiros, com retenção própria e controle de acesso mais frouxo. A chave de
produção viaja junto, no mesmo registro.

**Recommendation:** Nunca registrar PAN nem secret. Mascarar para os últimos quatro dígitos e remover
a chave do log. → `RP-15`

---

### #3 [CRITICAL] Insecure Credential Handling (AP-05)

**File:** `src/utils.js:17-23`

**Description:** `badCrypto` concatena os dois primeiros caracteres de `base64(senha)` dez mil vezes e
devolve os dez primeiros caracteres do resultado. Como os dois primeiros caracteres de base64 codificam
apenas 12 bits — o primeiro byte inteiro e o nibble alto do segundo —, todo o restante da senha é
descartado. Não há salt, e a função é determinística.

**Evidence:**
```js
function badCrypto(pwd) {
    let hash = "";
    for(let i = 0; i < 10000; i++) {
        hash += Buffer.from(pwd).toString('base64').substring(0, 2);
    }
    return hash.substring(0, 10);
}
```

**Occurrences:** `src/utils.js:17-23` (a função), `src/AppManager.js:68` (uso, com senha default
`"123456"` quando `pwd` não vem no request), `src/AppManager.js:18` (seed grava a senha `'123'` em
plaintext, sem passar sequer por `badCrypto`)

**Impact:** Medido empiricamente:

```text
badCrypto("123")        === badCrypto("124")         -> "MTMTMTMTMT"
badCrypto("senhaforte") === badCrypto("sen")         -> "c2c2c2c2c2"
200.000 senhas distintas iniciadas por "p"  ->  1 hash distinto
```

O espaço de saída é de no máximo 4.096 valores. Na prática o hash **revela o primeiro caractere da
senha**, e duas senhas quaisquer que compartilhem o primeiro byte colidem. Se um endpoint de login for
adicionado — hoje não existe —, ele aceitará quase qualquer senha que comece com a letra certa.
Adicionalmente, a função custa 0,75 ms de CPU por chamada no request path, gastos para produzir um
resultado de 12 bits.

**Recommendation:** Substituir por `scrypt` do `node:crypto`, com salt por usuário e comparação em
tempo constante — sem dependência nova. Re-gerar o seed com hash. Todas as senhas existentes devem ser
consideradas comprometidas. → `RP-05`

---

### #4 [CRITICAL] Unvalidated Input Crashes the Process (AP-14)

**File:** `src/AppManager.js:29-35`

**Description:** A validação do checkout testa apenas presença (`!u || !e || !cid || !cc`), nunca
tipo. Um `card` enviado como número JSON passa pela guarda e chega em `cc.startsWith("4")` na linha 46,
onde `Number.prototype` não tem `startsWith`. A exceção é lançada dentro de um callback do `sqlite3`,
fora da pilha do Express — nenhum handler pode interceptá-la, e o Node encerra o processo.

**Evidence:**
```js
if (!u || !e || !cid || !cc) return res.status(400).send("Bad Request");
```

**Occurrences:** `src/AppManager.js:35` (guarda insuficiente), `src/AppManager.js:46` (ponto do
crash), `src/AppManager.js:29-33` (nenhum campo tem validação de tipo ou formato)

**Impact:** Verificado em execução. `POST /api/checkout` com `"card": 4111222233334444` (número, não
string) produz:

```text
TypeError: cc.startsWith is not a function
    at processPaymentAndEnroll (src/AppManager.js:46:41)
Node.js v24.16.0     <- processo encerrado
```

É negação de serviço remota, sem autenticação, com uma requisição. E como o banco é `:memory:`, o
processo levar consigo todas as matrículas e pagamentos registrados desde o último boot. Pior: o
usuário já foi inserido na linha 69 antes do crash, deixando escrita parcial — que neste caso
desaparece com o banco, mas não desapareceria com banco persistente.

**Recommendation:** Validação de schema na fronteira, com coerção e checagem de tipo antes de qualquer
uso, e um handler de erro centralizado. Depois de `RP-08`, o `await` traz a exceção de volta para a
pilha do Express, onde o middleware consegue tratá-la. → `RP-12` + `RP-08` + `RP-09`

---

### #5 [CRITICAL] God Class (AP-04)

**File:** `src/AppManager.js:4-141`

**Description:** Uma classe acumula responsabilidades de cinco camadas: abre a conexão (linha 7), cria
o schema e insere seeds (10-23), define rotas (25-138), processa pagamento (45-48), grava auditoria
(57) e monta o relatório financeiro (80-129). `utils.js` é o complemento — configuração, cache global
e criptografia no mesmo arquivo de 25 linhas.

**Evidence:**
```js
class AppManager {
    constructor() { this.db = new sqlite3.Database(':memory:'); }
    initDb() { /* CREATE TABLE x5 + INSERT seeds */ }
    setupRoutes(app) { /* 3 rotas, com pagamento e regra de negócio inline */ }
}
```

**Occurrences:** `src/AppManager.js:4-141` (a classe), `src/utils.js:1-25` (módulo-depósito)

**Impact:** Nada é testável isoladamente: exercitar a regra de pagamento exige instanciar a classe,
que abre um banco e registra rotas. O método `setupRoutes(app)` inverte a arquitetura — é a classe que
detém o banco quem decide o roteamento. E o nome não descreve nada: `AppManager` poderia conter
qualquer coisa, e contém.

**Recommendation:** Separar em `infra/` (conexão e schema), `models/` por entidade, `services/`
(gateway de pagamento), `controllers/` (use cases) e `routes/` (binding). → `RP-04`

---

### #6 [CRITICAL] Payment Approved by Card Prefix (AP-06, escalado)

**File:** `src/AppManager.js:46`

**Description:** A aprovação do pagamento é decidida por um ternário sobre o primeiro dígito do
cartão. Não há chamada a gateway algum — a `paymentGatewayKey` da config é apenas impressa no log,
nunca usada. Mesmo assim, o registro em `payments` é gravado com status `PAID` e a matrícula é
efetivada.

**Evidence:**
```js
let status = cc.startsWith("4") ? "PAID" : "DENIED";
```

**Impact:** Qualquer número começando com `4` — inclusive `"4"` — resulta em matrícula concedida e
registro financeiro marcado como pago, sem que dinheiro nenhum tenha sido movimentado. O relatório
financeiro em `/api/admin/financial-report` soma esses valores e apresenta receita que não existe.

**Escalonamento:** AP-06 é HIGH por definição no catálogo. Elevado a CRITICAL pelo critério de
desempate 2 — o sistema produz dado errado silenciosamente, e o dado errado é financeiro.

**Recommendation:** Extrair um `paymentService` com interface explícita, injetado no controller, para
que a integração real possa substituir o stub sem tocar em regra de negócio. Enquanto for stub, deve
declarar-se como tal e não gravar `PAID`. → `RP-06` + `RP-07`

---

### #7 [HIGH] Callback Hell & Hand-Rolled Async Counters (AP-09)

**File:** `src/AppManager.js:37-78`

**Description:** O checkout aninha cinco níveis de callback. O relatório financeiro coordena fan-out
assíncrono com contadores manuais (`coursesPending`, `enrPending`) decrementados dentro de callbacks
aninhados em três níveis. A linha 26 (`const self = this`) existe só para escapar do escopo perdido.

**Evidence:**
```js
let coursesPending = courses.length;
...
enrPending--;
if (enrPending === 0) {
    report.push(courseData);
    coursesPending--;
    if (coursesPending === 0) res.json(report);
}
```

**Occurrences:** `src/AppManager.js:37-78` (checkout, 5 níveis), `src/AppManager.js:83-128`
(relatório, contadores manuais), `src/AppManager.js:26` (`self = this`)

**Impact:** Os contadores são a parte perigosa. Qualquer caminho de erro que retorne sem decrementar
deixa `res.json` sem ser chamado e a requisição pendura até o timeout do cliente. Inversamente, um
decremento a mais dispara `res.json` duas vezes e o Express lança `ERR_HTTP_HEADERS_SENT`. As linhas
92-93 já contêm esse defeito: se a query de enrollments falhar, `enrollments` vem `undefined` e
`enrollments.length` derruba o processo pelo mesmo mecanismo do finding #4.

**Recommendation:** Promisificar o driver na fronteira de infra e reescrever com `async/await`;
`Promise.all` substitui os contadores inteiramente. → `RP-08`

---

### #8 [HIGH] Ignored Errors (AP-10)

**File:** `src/AppManager.js:133`

**Description:** Vários callbacks recebem `err` e não o consultam. O `DELETE /api/users/:id` é o caso
extremo: recebe `err`, ignora, e responde sucesso incondicionalmente. Não há middleware de erro
registrado em lugar nenhum da aplicação, e as respostas de erro que existem são strings de texto puro
sem contexto.

**Evidence:**
```js
this.db.run("DELETE FROM users WHERE id = ?", [id], (err) => {
    res.send("Usuário deletado, mas as matrículas e pagamentos ficaram sujos no banco.");
});
```

**Occurrences:** `src/AppManager.js:133-136` (err ignorado, sucesso incondicional),
`src/AppManager.js:57` (err do audit log ignorado), `src/AppManager.js:92-93` (err ignorado e
`enrollments.length` acessado em seguida), `src/AppManager.js:104` e `:106` (err ignorado nos gets do
relatório)

**Impact:** Um `DELETE` que falha responde `200`. O cliente registra o usuário como removido, o banco
discorda, e ninguém fica sabendo — não há log de erro. Nos callbacks do relatório, um erro de query
produz `undefined` que é usado imediatamente, transformando falha de banco em queda de processo.

**Recommendation:** Tipos de erro de domínio, `next(err)` em todos os caminhos assíncronos e um
middleware de erro registrado por último. → `RP-09`

---

### #9 [HIGH] No Transaction Boundary & Missing Referential Integrity (AP-11)

**File:** `src/AppManager.js:50-63`

**Description:** O checkout faz três escritas encadeadas — `enrollments`, `payments`, `audit_logs` —
sem transação. Uma falha na segunda deixa matrícula sem pagamento. Nenhuma das cinco tabelas declara
`FOREIGN KEY`, e o `DELETE` de usuário não remove nem bloqueia os registros dependentes — a própria
mensagem de resposta admite isso textualmente.

**Evidence:**
```js
this.db.run("CREATE TABLE enrollments (id INTEGER PRIMARY KEY, user_id INTEGER, course_id INTEGER)");
```

**Occurrences:** `src/AppManager.js:12-16` (schema sem FKs), `src/AppManager.js:50-63` (três escritas
sem transação), `src/AppManager.js:131-137` (delete deixando órfãos)

**Impact:** Matrículas órfãs apontando para usuários inexistentes, e pagamentos órfãos apontando para
matrículas que podem ter sumido. O relatório financeiro percorre justamente essas tabelas e resolve o
usuário faltante como `'Unknown'` (linha 113), o que faz a corrupção passar despercebida em vez de
falhar visivelmente.

**Recommendation:** Envolver o use case em transação com rollback, declarar as foreign keys com
política de `ON DELETE` explícita e habilitar `PRAGMA foreign_keys = ON` por conexão. → `RP-10`

---

### #10 [HIGH] Mutable Global State (AP-07)

**File:** `src/utils.js:9-10`

**Description:** `globalCache` e `totalRevenue` são estado mutável de módulo, exportados por
referência. `logAndCache` escreve em `globalCache` a cada checkout, sem limite de tamanho, sem TTL e
sem qualquer política de remoção. `totalRevenue` é exportado como número primitivo — quem importa
recebe uma cópia que nunca é atualizada.

**Evidence:**
```js
let globalCache = {};
let totalRevenue = 0;
```

**Occurrences:** `src/utils.js:9-10` (declaração), `src/utils.js:14` (escrita sem limite),
`src/utils.js:25` (exportação por referência), `src/AppManager.js:7` (a conexão também é estado
compartilhado, presa ao ciclo de vida da God Class)

**Impact:** `globalCache` cresce indefinidamente com o número de checkouts — é um vazamento de memória
com prazo, não com se. E `totalRevenue` é a armadilha clássica do primitivo exportado: qualquer
reatribuição em `utils.js` seria invisível para `AppManager.js`, que capturou o valor no momento do
`require`. O nome sugere que alguém pretendia acumular receita ali.

**Recommendation:** Cache como objeto injetado, com limite e ciclo de vida explícito; conexão obtida
de uma factory, não de um atributo de instância compartilhado. → `RP-07`

---

### #11 [HIGH] Hardcoded Dependencies / No Dependency Injection (AP-08)

**File:** `src/AppManager.js:2`

**Description:** `AppManager` importa `config`, `logAndCache` e `badCrypto` diretamente e instancia a
conexão no próprio construtor. Não há nenhum ponto de substituição: nem parâmetro de construtor, nem
factory, nem interface. `app.js` reforça o acoplamento chamando `new AppManager()` e `initDb()` no
escopo de módulo, o que dispara criação de schema e seed como efeito colateral do `require`.

**Evidence:**
```js
const { config, logAndCache, badCrypto, totalRevenue } = require('./utils');
...
this.db = new sqlite3.Database(':memory:');
```

**Occurrences:** `src/AppManager.js:2` (colaboradores importados), `src/AppManager.js:7` (conexão
instanciada internamente), `src/app.js:8-10` (composição com efeito colateral no require)

**Impact:** Nenhum teste consegue rodar sem abrir banco e registrar rotas, e trocar o cache ou o
gateway de pagamento exige editar a classe que contém as regras de negócio. A direção de dependência
aponta do domínio para a infraestrutura — o inverso do que a arquitetura pede.

**Recommendation:** Colaboradores recebidos por construtor, conexão vinda de factory, e composição
concentrada em `app.js` separada do `listen()` para que a app seja testável. → `RP-07`

---

### #12 [MEDIUM] N+1 Queries (AP-12)

**File:** `src/AppManager.js:83-128`

**Description:** O relatório financeiro busca todos os cursos, depois uma query de enrollments por
curso, depois duas queries por enrollment — uma para o usuário e outra para o pagamento. São
1 + N + 2×N×M idas ao banco para um relatório que um único `JOIN` com `GROUP BY` resolve.

**Evidence:**
```js
enrollments.forEach(enr => {
    this.db.get("SELECT name, email FROM users WHERE id = ?", [enr.user_id], (err, user) => {
        this.db.get("SELECT amount, status FROM payments WHERE enrollment_id = ?", [enr.id], (err, payment) => {
```

**Impact:** Com os 2 cursos e 1 matrícula do seed são 6 queries e o problema é invisível. Com 50 cursos
de 200 alunos são mais de 20.000 idas ao banco em uma requisição — e como cada uma abre um nível de
callback, multiplica também a superfície de corrida descrita no finding #7.

**Recommendation:** Uma query com `LEFT JOIN` entre `courses`, `enrollments`, `users` e `payments`,
agrupando em memória. → `RP-11`

---

### #13 [MEDIUM] Insecure Middleware & Framework Configuration (AP-23)

**File:** `src/app.js:6`

**Description:** `express.json()` é registrado sem `limit`, aceitando corpo de qualquer tamanho.
Não há security headers, nem `helmet` nem equivalente manual. `app.listen(config.port)` é chamado sem
host, o que faz o Express escutar em todas as interfaces (`::`) numa API sem autenticação alguma. Não
há rate limit no `/api/checkout`, que é o endpoint de pagamento.

**Evidence:**
```js
app.use(express.json());
```

**Occurrences:** `src/app.js:6` (body sem limite), `src/app.js:12` (bind em todas as interfaces),
ausência de headers e de rate limit em toda a aplicação

**Impact:** Um corpo JSON grande o suficiente esgota memória do processo — que, combinado ao finding
#4, significa que este serviço tem dois caminhos independentes para ser derrubado remotamente sem
autenticação. O bind em todas as interfaces expõe na rede local uma API onde `DELETE /api/users/:id`
não pede credencial.

**Recommendation:** `express.json({ limit })` vindo da config, host explícito, headers de segurança e
rate limit no endpoint de pagamento. → `RP-18`

---

### #14 [MEDIUM] Deprecated & Superseded APIs (AP-15)

**File:** `src/AppManager.js:1`

**Description:** Nenhuma API do registry Node aparece no código, e o boot não emite
`DeprecationWarning`. O que existe são APIs superadas e dependências atrasadas em major.

| API / dependência | Localização | Estado | Substituto |
| --- | --- | --- | --- |
| `require('sqlite3').verbose()` | `src/AppManager.js:1` | superado; `verbose()` adiciona stack trace a cada chamada | `node:sqlite` (nativo desde o Node 22), `better-sqlite3`, ou wrapper de promise |
| API de callback do `sqlite3` | `src/AppManager.js` inteiro | superado por interfaces baseadas em promise | ver `RP-08` |
| `sqlite3@5.1.7` | `package.json:11` | um major atrás (`6.0.1` disponível) | atualizar |
| `express@4.22.1` | `package.json:10` | Express 4 em manutenção; `5.2.1` é a linha atual | migrar em trabalho próprio |

**Runtime warnings capturadas no boot:**
```text
nenhuma  (node --pending-deprecation --trace-deprecation --trace-warnings src/app.js)
```

**Impact:** `verbose()` cobra custo de stack trace em toda operação de banco, o que em produção é
desperdício puro. A distância de um major em `sqlite3` acumula correções de segurança não aplicadas.

**Recommendation:** Remover `verbose()` do caminho de produção e promisificar o driver na camada de
infra, o que já é exigido pelo `RP-08`. A migração para Express 5 fica como trabalho separado. →
`RP-13` + `RP-08`

---

### #15 [MEDIUM] Ad-hoc Logging (AP-17)

**File:** `src/utils.js:13`

**Description:** Não há biblioteca nem configuração de logging. Tudo sai por `console.log`, sem nível,
sem timestamp e sem contexto estruturado. Um evento de rotina e um dado de cartão de crédito são
impressos da mesma forma.

**Evidence:**
```js
console.log(`[LOG] Salvando no cache: ${key}`);
```

**Occurrences:** `src/utils.js:13`, `src/AppManager.js:45`, `src/app.js:13`

**Impact:** Impossível reduzir verbosidade em produção ou elevar durante incidente, e impossível
filtrar por severidade. É também o mecanismo pelo qual o finding #2 acontece: sem níveis nem política,
nada impede que um `console.log` de depuração com PAN chegue à produção.

**Recommendation:** Logger configurado no composition root, com nível vindo da config e mascaramento
de campos sensíveis. → `RP-15`

---

### #16 [LOW] Poor Naming (AP-20)

**File:** `src/AppManager.js:29-33`

**Description:** Identificadores de uma letra para dados de negócio, e nomes de módulo que não
descrevem o conteúdo.

**Evidence:**
```js
let u = req.body.usr;
let e = req.body.eml;
let p = req.body.pwd;
let cid = req.body.c_id;
let cc = req.body.card;
```

**Occurrences:** `src/AppManager.js:29-33` (`u`, `e`, `p`, `cid`, `cc`), `src/AppManager.js:89-106`
(`c`, `enr`), `src/AppManager.js:4` (`AppManager` não descreve nada), `src/utils.js` (nome genérico
para config + cache + crypto), `src/utils.js:17` (`badCrypto` batizada com o próprio defeito)

**Impact:** `e` é o email, mas em JavaScript `e` é convencionalmente o erro — a leitura do checkout
exige memorizar cinco abreviações. Os campos do request (`usr`, `eml`, `pwd`, `c_id`) são contrato
público e não podem ser renomeados sem quebrar clientes.

**Recommendation:** Renomear os identificadores internos por desestruturação com alias, preservando os
nomes do wire. A correção do contrato fica registrada como ação posterior. → `RP-17`

---

### #17 [LOW] Dead Code & Unused Exports (AP-21)

**File:** `src/utils.js:10`

**Description:** `totalRevenue` é declarado, exportado, importado em `AppManager.js` e nunca usado.
`globalCache` é exportado mas nunca lido por ninguém — só escrito. `smtpUser` está na config sem que
exista qualquer código de envio de email.

**Evidence:**
```js
const { config, logAndCache, badCrypto, totalRevenue } = require('./utils');
```

**Occurrences:** `src/utils.js:10` e `:25` (`totalRevenue`), `src/AppManager.js:2` (import não usado),
`src/utils.js:9` e `:25` (`globalCache` exportado sem leitor), `src/utils.js:5` (`smtpUser` sem uso)

**Recommendation:** Remover. → `RP-17`

---

### #18 [LOW] Inconsistent Response Shape & Status Codes (AP-22)

**File:** `src/AppManager.js:35`

**Description:** Três rotas, três formatos. O checkout responde JSON no sucesso e texto puro no erro;
o relatório responde array cru sem envelope; o delete responde texto puro com `200`. As mensagens
misturam português e inglês.

**Evidence:**
```js
if (!u || !e || !cid || !cc) return res.status(400).send("Bad Request");
```

**Occurrences:** `src/AppManager.js:35` (`"Bad Request"` em texto), `src/AppManager.js:38`
(`"Curso não encontrado"`), `src/AppManager.js:60` (JSON), `src/AppManager.js:121` (array cru),
`src/AppManager.js:135` (texto com `200` descrevendo uma falha)

**Impact:** Um cliente não consegue tratar erro genericamente — precisa saber, por rota, se a resposta
é JSON ou texto. E a mensagem do delete descreve corrupção de dados com status de sucesso, o que
impede qualquer monitoração automática de detectar o problema.

**Recommendation:** Envelope único de erro vindo do middleware central e envelope único de sucesso no
serializer. → `RP-09` + `RP-14`

---

## Deprecated APIs

Coberto integralmente no finding #14. Resumo do pass de quatro frentes:

1. **Boot com warnings habilitados** — `node --pending-deprecation --trace-deprecation
   --trace-warnings src/app.js`: nenhum warning emitido.
2. **Grep do registry Node** — `new Buffer`, `url.parse`, `createCipher`, `util.isArray`,
   `util._extend`, `fs.exists`, `body-parser`, `.substr(`, `app.del(`, `res.send(<status>,`,
   `domain`: nenhuma ocorrência. O código usa `Buffer.from`, `.substring` e `express.json()`, que são
   as formas corretas.
3. **Versões resolvidas vs. changelog** — `express@4.22.1` (linha 4 em manutenção; 5.2.1 é a atual),
   `sqlite3@5.1.7` (um major atrás de 6.0.1). `npm outdated` confirma ambos.
4. **Dependências deprecated** — `util-deprecate@1.0.2` aparece apenas como dependência transitiva do
   `sqlite3`, não é uso direto do projeto.

Vale registrar o contraste com o projeto 1, onde o pass resultou vazio: aqui ele produziu achado real,
o que confirma que a verificação não é decorativa.

---

## Refactoring Plan Preview

```text
ecommerce-api-legacy/
├── .env.example
├── src/
│   ├── app.js                    # composition root, exporta a app
│   ├── server.js                 # listen() — separado para tornar app testável
│   ├── config/index.js           # process.env com validação
│   ├── infra/
│   │   ├── database.js           # factory + driver promisificado
│   │   ├── schema.js             # DDL com FKs + seed explícito
│   │   └── security.js           # scrypt (node:crypto)
│   ├── models/
│   │   ├── userModel.js
│   │   ├── courseModel.js
│   │   └── enrollmentModel.js    # matrícula + pagamento em uma transação
│   ├── services/
│   │   └── paymentService.js     # gateway injetado, com interface explícita
│   ├── controllers/
│   │   ├── checkoutController.js
│   │   ├── reportController.js
│   │   └── userController.js
│   ├── routes/index.js
│   ├── serializers/reportSerializer.js
│   ├── schemas/checkoutSchema.js
│   └── middlewares/
│       ├── errorHandler.js       # (err, req, res, next) — registrado por último
│       ├── requestLogger.js
│       └── security.js           # headers, body limit, rate limit
```

| # | Step | Findings resolvidos |
| --- | --- | --- |
| 1 | Config por ambiente + `.env.example` | #1, #13 |
| 2 | Infra: driver promisificado, schema com FKs, scrypt | #3, #9, #14 |
| 3 | Models por entidade, transação no checkout | #5, #9, #12 |
| 4 | `paymentService` com interface explícita | #6, #11 |
| 5 | Controllers com `async/await` | #5, #7 |
| 6 | Routes: binding puro | #5 |
| 7 | Validação de schema na fronteira | #4 |
| 8 | Middlewares: erro central, logging, security | #2, #8, #13, #15, #18 |
| 9 | Composition root + limpeza | #10, #16, #17 |

**Contract preservation:** os 3 endpoints originais continuam existindo, com os mesmos métodos e
paths. Os nomes de campo do request (`usr`, `eml`, `pwd`, `c_id`, `card`) são preservados.

**Intentional behaviour changes:**

- `POST /api/checkout` com `card` não string — passa a responder `400` em vez de derrubar o processo
  (finding #4).
- `POST /api/checkout` — a senha passa a ser gravada com `scrypt`. Os hashes de `badCrypto` existentes
  deixam de ser válidos (finding #3).
- `POST /api/checkout` — o log deixa de conter o número do cartão e a chave do gateway (finding #2).
- `DELETE /api/users/:id` — passa a responder `409` quando o usuário tem matrículas, e `500` quando a
  operação falha, em vez de `200` incondicional com mensagem descrevendo a corrupção (findings #8, #9).
- Respostas de erro passam a ser JSON com forma única, em vez de texto puro (finding #18).
- O servidor passa a escutar em `127.0.0.1` por default, configurável por `HOST` (finding #13).

---

## Accepted / Out of Scope

- **Banco em memória (`:memory:`)** — é escolha deliberada do boilerplate, documentada no README do
  projeto, e o seed automático depende dela. Mantida. A consequência para durabilidade está registrada
  no finding #4 como agravante, não como finding próprio.
- **Ausência de autenticação e autorização** — `DELETE /api/users/:id` e
  `GET /api/admin/financial-report` são públicos, sendo o segundo explicitamente administrativo.
  Introduzir auth é feature nova, não refatoração. Registrado abaixo.
- **`paymentService` continuará sendo stub** — implementar integração real com gateway está fora do
  escopo. A refatoração cria a interface e o ponto de substituição; o finding #6 é resolvido no que diz
  respeito à arquitetura, e o stub passará a declarar-se como tal.
- **Nomes de campo do request** (`usr`, `eml`, `c_id`) — contrato público, preservados.

---

## Post-Refactoring Actions (fora do escopo da skill)

1. **Revogar as três credenciais vazadas** — a chave `pk_live_` do gateway, a senha do banco e o
   usuário de SMTP estão no histórico do git desde o commit inicial.
2. **Considerar todas as senhas comprometidas.** O `badCrypto` tem espaço efetivo de 12 bits; os
   hashes armazenados revelam o primeiro caractere da senha. Reset obrigatório.
3. **Auditar os logs já coletados.** Todo checkout executado até aqui gravou o PAN completo em stdout;
   se houve agregador de logs, o dado saiu do servidor e precisa ser expurgado.
4. **Adicionar autenticação e autorização**, especialmente em `/api/admin/financial-report` e
   `DELETE /api/users/:id`.
5. **Implementar a integração real de pagamento**, substituindo o stub pela interface criada.
6. **Cobrir com testes** — checkout, cálculo de receita e integridade referencial são os pontos de
   partida.
7. **Atualizar `sqlite3` para 6.x** e planejar a migração para Express 5.

---

Total: 18 findings

---

## Refactoring Result

Fase 3 executada e aprovada pelo gate humano em 2026-08-08.

### Estrutura resultante

```text
ecommerce-api-legacy/
├── .env.example
└── src/
    ├── server.js                  # entry point — só o listen()
    ├── app.js                     # composition root: createApp()
    ├── config/index.js
    ├── domain/errors.js
    ├── infra/
    │   ├── database.js            # driver promisificado + transaction()
    │   ├── schema.js              # DDL com FKs + seed explícito
    │   ├── security.js            # scrypt + máscara de PAN
    │   ├── cache.js               # BoundedCache com limite
    │   └── logger.js
    ├── models/
    │   ├── userModel.js
    │   ├── courseModel.js
    │   └── enrollmentModel.js     # matrícula + pagamento + auditoria em transação
    ├── services/paymentService.js # interface de cobrança (stub declarado)
    ├── controllers/
    │   ├── checkoutController.js
    │   ├── reportController.js
    │   └── userController.js
    ├── routes/index.js
    ├── serializers/reportSerializer.js
    ├── schemas/checkoutSchema.js
    └── middlewares/
        ├── errorHandler.js        # asyncHandler + handler central
        ├── requestLogger.js
        └── security.js
```

Arquivos removidos: `src/AppManager.js`, `src/utils.js`. 180 linhas em 3 arquivos deram lugar a 964
linhas em 22 arquivos.

### Findings resolvidos: 17 completos, 1 parcial

| Severidade | Resolvidos |
| --- | --- |
| CRITICAL | 6/6 |
| HIGH | 5/5 |
| MEDIUM | 3/4 (+1 parcial) |
| LOW | 3/3 |

O finding #13 (AP-23) ficou parcial: security headers, limite de corpo e host explícito foram
aplicados e verificados pelo wire, mas **não há rate limit** em `/api/checkout`. Implementá-lo exige
uma dependência nova ou um limitador em memória com semântica de janela — decisão que não cabia
dentro desta refatoração.

O finding #6 está resolvido no escopo declarado na auditoria: a decisão de pagamento saiu do handler
e passou a viver atrás de uma interface injetada. A implementação continua sendo stub, mas agora se
declara como tal (`provider: 'stub'`), e substituí-la por um gateway real não toca em regra de negócio.

### Verificação dos detection signals na árvore refatorada

| Signal | Resultado |
| --- | --- |
| Secrets hardcoded | limpo |
| SQL por interpolação de template literal | limpo |
| `badCrypto` / hash caseiro | limpo |
| Estado global mutável | limpo |
| Callback aninhado / `self = this` | limpo |
| Registry Node (`new Buffer`, `url.parse`, `verbose()`, …) | limpo |
| `console.log` | limpo |
| `express.json()` sem `limit` | limpo |
| Models/serializers importando express | limpo |
| Routes acessando models | limpo |
| Controllers escrevendo SQL | limpo |
| Error middleware registrado por último | limpo |

### Validação de comportamento

Baseline capturado **antes** da primeira edição, com 10 probes cobrindo os 3 endpoints e seus
caminhos de erro, mais uma sonda de crash executada à parte.

```text
✓ Application boots without errors
✓ 3/3 endpoints originais respondem (mesmos métodos e paths)
✓ 2/10 probes com status e body idênticos
✓ 8/10 probes alterados — todos rastreados a um finding
✓ Sonda de crash: HTTP 000 / servidor MORREU  ->  HTTP 400 / servidor VIVO
✓ Zero anti-patterns remanescentes da auditoria (exceto o parcial #13)
```

| Mudança | Probes | Finding |
| --- | --- | --- |
| Corpo de erro passou de texto puro para JSON `{"error": ...}` | 4 | #18 |
| `DELETE /api/users/1` (com matrícula): 200 → 409 | 1 | #8, #9 |
| `DELETE /api/users/9999` (inexistente): 200 → 404 | 1 | #8 |
| Relatório pós-delete preserva `"Leonan"` em vez de `"Unknown"` | 1 | #9 (consequência) |
| Ordem dos alunos dentro do curso | 1 | #7, #12 (consequência) |

Sobre a ordem dos alunos: no original ela era determinada pela ordem de conclusão dos callbacks
aninhados, que não é especificada; no refatorado é `ORDER BY e.id`. Três execuções limpas de cada
versão mostraram ordem **estável em ambas** nesta máquina — `['Leonan','Guilherme']` no original e
`['Guilherme','Leonan']` no refatorado. Ou seja: não foi observado não-determinismo no original, mas
a ordem dele também não era garantida por nada; a versão nova passa a ter ordenação explícita.

Verificações adicionais fora do conjunto de probes:

```text
✓ DELETE de usuário sem matrícula responde 200 (caminho feliz alcançável)
✓ DELETE do mesmo id em seguida responde 404
✓ Corpo acima de MAX_BODY_SIZE responde 413 em vez de esgotar memória
✓ Headers verificados no wire: X-Content-Type-Options, X-Frame-Options, Referrer-Policy
✓ Log do checkout registra "card":"************4444"
✓ Zero ocorrências do PAN completo ou da chave do gateway no log
✓ Checkout recusado não cria mais usuário órfão (a cobrança acontece antes da escrita)
```

### Nota de método — um experimento contaminado

Vale registrar, porque afeta a confiança nos números. A primeira tentativa de medir determinismo da
ordem dos alunos produziu listas que **cresciam** a cada execução, o que é impossível com banco
`:memory:` recriado a cada boot. A causa era o harness, não a aplicação: o runner usava `eval` para
subir o servidor, então `$!` capturava o PID do subshell e não o do node, e o `kill` deixava o
processo órfão escutando na porta. As execuções seguintes bateram no servidor antigo.

O runner foi corrigido para encerrar por porta (`lsof -ti`) em vez de por PID, e **os dois baselines
foram recapturados do zero** com o harness consertado. Os números desta seção vêm da captura
corrigida. A conclusão inicial — de que o original era não-determinístico — estava errada e foi
refeita.

### Contraste com o projeto 1

O `AP-23`, criado depois da execução do projeto 1 justamente porque um achado escapou do catálogo,
produziu finding aqui já a partir dos detection signals — `express.json()` sem `limit`, ausência de
headers e bind em todas as interfaces. A entrada se pagou na primeira execução seguinte.

O pass de deprecated APIs também se comportou de forma diferente: vazio no projeto 1, com achado real
no projeto 2. Nos dois casos o resultado veio da mesma verificação de quatro frentes, o que sugere que
o pass discrimina em vez de sempre confirmar.
