# ARCHITECTURE AUDIT REPORT

Project:   task-manager-api
Stack:     Python 3.12.13 + Flask 3.0.0 / Flask-SQLAlchemy 3.1.1 (SQLAlchemy 2.0.51)
Files:     15 analyzed | ~1.158 lines of code (1.059 de aplicação + 99 seed)
Database:  SQLite (tasks.db) via SQLAlchemy — 3 tables
Routes:    22 endpoints
Date:      2026-08-08
Skill:     refactor-arch

---

## Summary

| Severity | Count |
| --- | --- |
| CRITICAL | 2 |
| HIGH | 4 |
| MEDIUM | 7 |
| LOW | 3 |
| **Total** | **16** |

Este projeto é o mais enganoso dos três. Ele tem `models/`, `routes/`, `services/` e `utils/` — a
aparência de uma aplicação em camadas. O que as pastas não contam é que `routes/` faz o trabalho de
controller, model e serializer ao mesmo tempo, e que `services/` e `utils/` não são chamados por
ninguém: `NotificationService` nunca é instanciado, e as nove funções de `utils/helpers.py` têm zero
chamadas fora do próprio arquivo. São 164 linhas de código que existem, são mantidas e não executam.

O sintoma mais claro dessa separação nominal é o `is_overdue()`. Ele está definido em
`models/task.py`, onde deveria estar — e é reimplementado inline, com o mesmo `if` de três níveis, em
**seis** lugares diferentes das rotas. A regra tem um dono e sete implementações.

A gravidade absoluta é menor que a dos projetos anteriores: não há SQL Injection, não há endpoint de
execução arbitrária e não há God Class. Em compensação, dois achados são graves e verificados em
execução: `GET /users/1` devolve o hash MD5 da senha no payload — `81dc9bdb52d04dc20036dbd8313ed055`
é o MD5 de `1234`, resolvível por rainbow table em tempo nulo — e o login entrega
`fake-jwt-token-1`, que é adivinhável a partir do id do usuário.

---

## Findings

### #1 [CRITICAL] Insecure Credential Handling & Sensitive Data Exposure (AP-05)

**File:** `models/user.py:29`

**Description:** Senhas são hasheadas com MD5 sem salt, o hash é incluído no payload de resposta pelo
`to_dict()`, e a autenticação devolve um token construído por concatenação do id do usuário.

**Evidence:**
```python
def set_password(self, pwd):
    self.password = hashlib.md5(pwd.encode()).hexdigest()
```

**Occurrences:** `models/user.py:29` (MD5 na gravação), `models/user.py:32` (MD5 na verificação),
`models/user.py:21` (`'password': self.password` no `to_dict`), `routes/user_routes.py:33`
(`GET /users/<id>` devolve o `to_dict` completo), `routes/user_routes.py:86` (a criação devolve o
hash), `routes/user_routes.py:209` (o login devolve o hash),
`routes/user_routes.py:210` (`'token': 'fake-jwt-token-' + str(user.id)`)

**Impact:** Verificado em execução:

```text
GET /users/1  ->  "password": "81dc9bdb52d04dc20036dbd8313ed055"
md5("1234")   =   81dc9bdb52d04dc20036dbd8313ed055
POST /login   ->  "token": "fake-jwt-token-1"
```

MD5 sem salt é reversível por rainbow table para qualquer senha comum, e o endpoint que entrega o
hash é público. Não é preciso invadir o banco: basta um `GET`. O token, por sua vez, é derivado do id
— quem souber que existe o usuário 1 se autentica como ele, se algum dia o token passar a ser
verificado.

**Recommendation:** Trocar MD5 por `werkzeug.security.generate_password_hash` (pbkdf2 com salt, já
disponível via Flask), remover `password` do payload por allowlist no serializer, e substituir o token
falso por JWT assinado ou remover o campo enquanto não houver autenticação real. → `RP-05` + `RP-14`

---

### #2 [CRITICAL] Hardcoded Secrets & Credentials (AP-01)

**File:** `app.py:13`

**Description:** A `SECRET_KEY` do Flask é um literal no código, e o `NotificationService` carrega
host, porta, usuário e senha de SMTP hardcoded no próprio construtor.

**Evidence:**
```python
app.config['SECRET_KEY'] = 'super-secret-key-123'
```
```python
self.email_user = 'taskmanager@gmail.com'
self.email_password = 'senha123'
```

**Occurrences:** `app.py:13` (`SECRET_KEY`), `services/notification_service.py:7-10` (host, porta,
usuário e senha de SMTP), `app.py:11` (URI do banco fixa), `app.py:34` (`debug=True` e bind em
`0.0.0.0`)

**Impact:** A `SECRET_KEY` assina sessões e qualquer token derivado; conhecida, permite forjá-los. As
credenciais de SMTP permitiriam enviar email em nome da aplicação. Todas estão no histórico do git
desde o commit inicial, então removê-las do código não as revoga.

**Recommendation:** Extrair para um módulo `config/` lendo variáveis de ambiente, com falha explícita
na ausência de `SECRET_KEY`, e `.env.example` commitado. As credenciais precisam ser **revogadas**. →
`RP-01`

---

### #3 [HIGH] Route Handlers Acting as Controllers, Models and Serializers (AP-06)

**File:** `routes/task_routes.py:11-63`

**Description:** É o achado estrutural do projeto. As pastas sugerem camadas, mas cada handler de rota
faz tudo: consulta o banco, aplica regra de negócio, monta o payload campo a campo e escolhe o status
code. `get_tasks` tem 53 linhas e contém quatro responsabilidades distintas; `summary_report` tem 90
linhas e nove blocos de agregação. Nenhuma dessas regras pode ser exercitada sem um request context.

**Evidence:**
```python
tasks = Task.query.all()
for t in tasks:
    task_data = {}
    task_data['id'] = t.id
    ...
    if t.due_date:
        if t.due_date < datetime.utcnow():
            if t.status != 'done' and t.status != 'cancelled':
                task_data['overdue'] = True
    ...
    user = User.query.get(t.user_id)
```

**Occurrences:** `routes/task_routes.py:11-63` (`get_tasks`), `routes/task_routes.py:85-154`
(`create_task`, 70 linhas), `routes/task_routes.py:156-223` (`update_task`, 68 linhas),
`routes/task_routes.py:273-299` (`task_stats`), `routes/user_routes.py:153-183`
(`get_user_tasks`), `routes/report_routes.py:12-101` (`summary_report`, 90 linhas),
`routes/report_routes.py:103-155` (`user_report`)

**Impact:** Testar a regra de "task atrasada" exige subir o Flask e o banco. Mudar o formato de saída
de uma task exige editar cinco funções em três arquivos. E como a mesma regra foi copiada em vez de
chamada, as cópias já podem divergir sem que nada acuse — ver finding #5.

**Recommendation:** Introduzir `controllers/` por domínio, mover as regras para os models que já
existem, extrair `serializers/` para o payload, e reduzir `routes/` a binding de método e path. →
`RP-06`

---

### #4 [HIGH] Swallowed Exceptions (AP-10)

**File:** `routes/task_routes.py:62`

**Description:** Doze blocos `except:` sem tipo, a maioria devolvendo uma mensagem genérica sem log.
O `except:` sem tipo captura inclusive `KeyboardInterrupt` e `SystemExit`. Não há handler de erro
centralizado, e o mesmo bloco `try/except → 500` está copiado por vários handlers.

**Evidence:**
```python
    except:
        return jsonify({'error': 'Erro interno'}), 500
```

**Occurrences:** `routes/task_routes.py:62`, `:137`, `:204`, `:236`; `routes/user_routes.py:130`,
`:149`; `routes/report_routes.py:186`, `:207`, `:221`; `utils/helpers.py:46`, `:49`, `:88`

**Impact:** `GET /tasks` responde `{'error': 'Erro interno'}` para qualquer falha — banco fora do ar,
bug de serialização ou dado corrompido produzem a mesma resposta, e nenhuma delas é registrada. Em
`utils/helpers.py:46-50`, o `except:` aninhado transforma data inválida em `None` silenciosamente, que
depois vira `NULL` no banco.

**Recommendation:** Tipos de erro de domínio levantados pelas camadas internas e um `errorhandler`
central que mapeia para status code, registra a stack e devolve mensagem genérica ao cliente. Remover
os doze blocos. → `RP-09`

---

### #5 [HIGH] Duplicated Business Rule (AP-13)

**File:** `models/task.py:50-59`

**Description:** `Task.is_overdue()` está implementado no model — o lugar certo — e é reimplementado
inline, com o mesmo `if` de três níveis, em seis handlers de rota. O método existe e nunca é chamado.
O mesmo vale para `Task.validate_status()` e `Task.validate_priority()`, também definidos no model e
também reimplementados inline nas rotas.

**Evidence:**
```python
def is_overdue(self):
    if self.due_date:
        if self.due_date < datetime.utcnow():
            if self.status != 'done' and self.status != 'cancelled':
                return True
```

**Occurrences:** definição em `models/task.py:50-59`; cópias inline em `routes/task_routes.py:30-39`,
`routes/task_routes.py:71-80`, `routes/task_routes.py:284-287`, `routes/user_routes.py:171-180`,
`routes/report_routes.py:34-43`, `routes/report_routes.py:132-135`. Métodos de validação:
`models/task.py:38-48` (definidos), `routes/task_routes.py:110-114` e `:177-184` (reimplementados)

**Impact:** Sete implementações da mesma regra. Uma mudança no critério de atraso — incluir o status
`in_progress`, por exemplo — precisa ser aplicada em sete lugares, e esquecer um faz `/tasks` e
`/tasks/<id>` discordarem sobre a mesma task. É exatamente o tipo de divergência que passa despercebida
porque cada endpoint parece correto isoladamente.

**Recommendation:** Usar o método que já existe. Deletar as seis cópias e chamar `task.is_overdue()`
a partir do serializer. → `RP-12`

---

### #6 [HIGH] Missing Referential Integrity & Manual Cascade (AP-11)

**File:** `routes/user_routes.py:140-142`

**Description:** As foreign keys estão declaradas no ORM, mas o SQLite não as aplica sem
`PRAGMA foreign_keys = ON`, que o projeto nunca emite. O `delete_user` compensa deletando as tasks à
mão, em um loop, antes de remover o usuário. O `delete_category` não compensa nada: apaga a categoria
e deixa as tasks apontando para um id inexistente.

**Evidence:**
```python
tasks = Task.query.filter_by(user_id=user_id).all()
for t in tasks:
    db.session.delete(t)
```

**Occurrences:** `routes/user_routes.py:140-142` (cascade manual), `routes/report_routes.py:211-223`
(`delete_category` sem tratar as tasks), `models/task.py:13-14` (FKs declaradas sem `ondelete`),
`database.py:1-3` (nenhum `PRAGMA foreign_keys`)

**Impact:** Apagar uma categoria deixa tasks com `category_id` órfão. O `GET /tasks` então resolve
`Category.query.get(t.category_id)` como `None` e devolve `category_name: null`, o que faz a
inconsistência parecer um campo opcional em vez de corrupção. Além disso, a cascade manual do usuário
apaga tasks silenciosamente — não há aviso de que remover um usuário destrói o histórico dele.

**Recommendation:** Declarar `ondelete` explícito nas FKs, habilitar `PRAGMA foreign_keys = ON` por
conexão, e substituir a cascade manual pela do banco. Para categoria, decidir entre `SET NULL` e
`RESTRICT` — e o comportamento passa a ser explícito em qualquer um dos casos. → `RP-10`

---

### #7 [MEDIUM] Deprecated API Usage (AP-15)

**File:** `routes/task_routes.py:31`

**Description:** Duas famílias de API deprecated, ambas confirmadas por warning em runtime.

**Evidence:** capturado ao exercitar os endpoints com `PYTHONWARNINGS=always`:
```text
[27x] DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for
      removal in a future version. Use timezone-aware objects...
[10x] LegacyAPIWarning: The Query.get() method is considered legacy as of the 1.x series
      of SQLAlchemy and becomes a legacy construct in 2.0 | routes/task_routes.py:42
```

| API | Ocorrências | Estado | Substituto |
| --- | --- | --- | --- |
| `datetime.utcnow()` | 18, em 7 arquivos | deprecated no Python 3.12 | `datetime.now(timezone.utc)` |
| `Model.query` (Legacy Query API) | 56 | legacy no SQLAlchemy 2.0 | `db.session.execute(db.select(Model))` |
| `Model.query.get()` | 16 | deprecated desde 2.0 | `db.session.get(Model, id)` |
| `SQLALCHEMY_TRACK_MODIFICATIONS` | `app.py:12` | vestigial | remover a linha |

**Impact:** `utcnow()` devolve datetime *naive*, e `now(timezone.utc)` devolve *aware* — comparar os
dois levanta `TypeError`. Como as 18 ocorrências participam das comparações de prazo, a migração
precisa ser feita de uma vez, em todos os pontos, incluindo o tipo das colunas. A Legacy Query API
não quebra hoje, mas é o principal obstáculo a uma futura atualização de major do SQLAlchemy.

**Recommendation:** Substituir as 18 chamadas de `utcnow()` e migrar os 56 usos de `Model.query` para
a API 2.0 na mesma passagem, verificando com warnings ligados ao final. Remover
`SQLALCHEMY_TRACK_MODIFICATIONS`. → `RP-13`

---

### #8 [MEDIUM] N+1 Queries (AP-12)

**File:** `routes/report_routes.py:55-68`

**Description:** Cinco padrões N+1 distintos, todos no caminho de leitura mais usado da API.

**Evidence:**
```python
for u in users:
    user_tasks = Task.query.filter_by(user_id=u.id).all()
```

**Occurrences:** `routes/report_routes.py:55-68` (uma query por usuário no relatório),
`routes/report_routes.py:24-28` (cinco `count()` sequenciais onde um `GROUP BY` resolve),
`routes/report_routes.py:163` (um `count()` por categoria), `routes/task_routes.py:42` e `:51`
(um `User.query.get` e um `Category.query.get` por task, sem eager loading),
`routes/user_routes.py:22` (`len(u.tasks)` dispara lazy load por usuário)

**Impact:** `GET /tasks` com 500 tasks dispara 1.001 queries. `GET /reports/summary` cresce
linearmente com o número de usuários. Com as 10 tasks e 3 usuários do seed o problema é invisível —
ele aparece exatamente quando a aplicação passa a ter uso real.

**Recommendation:** `joinedload`/`selectinload` para as relações acessadas em loop, `GROUP BY` para os
contadores, e uma query agregada para o relatório por usuário. → `RP-11`

---

### #9 [MEDIUM] Missing Input Validation (AP-14)

**File:** `routes/task_routes.py:113`

**Description:** A validação testa faixa antes de garantir tipo. `priority` vindo do JSON como string
chega a `priority < 1` e levanta `TypeError`, fora de qualquer `try` — o Flask converte em 500.

**Evidence:**
```python
if priority < 1 or priority > 5:
    return jsonify({'error': 'Prioridade deve ser entre 1 e 5'}), 400
```

**Occurrences:** `routes/task_routes.py:113` (create), `routes/task_routes.py:182` (update, mesma
falha), `routes/task_routes.py:261` (`int(priority)` sobre query string, sem guarda),
`routes/task_routes.py:264` (`int(user_id)` idem), `routes/user_routes.py:115`
(`len(data['password'])` sem checar que é string)

**Impact:** Verificado em execução — `POST /tasks` com `{"title":"Teste valido","priority":"alta"}`
responde `500 Internal Server Error` com `TypeError` no log, quando deveria responder `400`. O mesmo
vale para `GET /tasks/search?priority=alta`. É erro de cliente sendo reportado como falha de servidor,
o que polui métrica de erro e esconde problema real.

**Recommendation:** Coerção e checagem de tipo antes de qualquer comparação, em um validador por
entidade. O projeto já declara `marshmallow` no `requirements.txt` sem usá-lo — é o candidato natural,
sem custo de dependência nova. → `RP-12`

---

### #10 [MEDIUM] Insecure Middleware & Framework Configuration (AP-23)

**File:** `app.py:15`

**Description:** `CORS(app)` sem argumentos libera todas as origens para todas as rotas, incluindo
`/login` e `/users`. `debug=True` está fixo na chamada de `app.run`, junto com bind em `0.0.0.0`. Não
há limite de tamanho de corpo, nem security headers. E `db.create_all()` roda no escopo de módulo,
como efeito colateral do import.

**Evidence:**
```python
CORS(app)
```
```python
app.run(debug=True, host='0.0.0.0', port=5000)
```

**Occurrences:** `app.py:15` (CORS irrestrito), `app.py:34` (`debug=True` e `0.0.0.0`),
`app.py:30-31` (`db.create_all()` no import), ausência de `MAX_CONTENT_LENGTH` e de security headers

**Impact:** O modo debug do Werkzeug expõe um console interativo na página de traceback — execução
remota de código a partir de qualquer exceção não tratada, e o finding #9 mostra que elas existem.
Combinado ao CORS aberto e ao bind em todas as interfaces, qualquer site aberto no browser da vítima
consegue ler a resposta de `GET /users`, que traz os hashes de senha do finding #1.

**Recommendation:** Origens e `DEBUG` vindos da config, com defaults restritivos; `MAX_CONTENT_LENGTH`
definido; security headers em middleware; e `create_all()` movido para uma etapa explícita de
inicialização. → `RP-18` + `RP-01`

---

### #11 [MEDIUM] Manual Serialization (AP-16)

**File:** `routes/task_routes.py:17-27`

**Description:** A conversão de objeto para payload é feita campo a campo, à mão, em quatro lugares —
e o resultado difere entre eles. `GET /tasks` inclui `user_name` e `category_name`; `GET /tasks/<id>`,
que usa `to_dict()`, não inclui. `GET /users/<id>/tasks` produz um terceiro formato, com menos campos.

**Evidence:**
```python
task_data = {}
task_data['id'] = t.id
task_data['title'] = t.title
task_data['description'] = t.description
```

**Occurrences:** `routes/task_routes.py:17-27`, `routes/user_routes.py:15-23`,
`routes/user_routes.py:162-169`, `models/task.py:23-36` (`to_dict`), `models/user.py:16-25`
(`to_dict`, que também decide expor a senha), `models/category.py:13-21`

**Impact:** Não existe um lugar único que defina o contrato da API, e ele já divergiu: a mesma task
tem três formatos diferentes conforme o endpoint que a devolve. É também a razão pela qual a senha
vaza — o `to_dict` do usuário decide o que é público, e ninguém revisa essa decisão.

**Recommendation:** Uma camada `serializers/` por entidade, com allowlist de campos, usada por todos
os controllers. Models deixam de ter `to_dict`. → `RP-14`

---

### #12 [MEDIUM] Ad-hoc Logging (AP-17)

**File:** `routes/task_routes.py:149`

**Description:** Não há configuração de logging. Eventos de negócio e erros saem por `print`, no mesmo
nível, sem timestamp e sem contexto. `utils/helpers.py` até define um `log_action`, que nunca é
chamado.

**Evidence:**
```python
print(f"Task criada: {task.id} - {task.title}")
```

**Occurrences:** `routes/task_routes.py:149`, `:153`, `:219`, `:234`; `routes/user_routes.py:83`,
`:89`, `:147`; `services/notification_service.py:21`, `:24`; `utils/helpers.py:39-41`
(`log_action`, definido e nunca usado)

**Impact:** Impossível ajustar verbosidade em produção ou filtrar por severidade. Combinado ao finding
#4, um erro engolido por `except:` não deixa rastro nenhum — nem exceção, nem log.

**Recommendation:** Logger configurado na inicialização, com nível vindo da config, e
`logger.exception` dentro do handler de erro central. → `RP-15`

---

### #13 [MEDIUM] Hardcoded Dependencies / Unused Service Layer (AP-08)

**File:** `services/notification_service.py:5-10`

**Description:** `NotificationService` lê a própria configuração no construtor, instancia a conexão
SMTP dentro do método que a usa, e não recebe nenhum colaborador. Não há ponto de substituição — um
teste que exercite `notify_task_assigned` tentaria abrir conexão com `smtp.gmail.com`. O detalhe que
fecha o quadro: a classe **nunca é instanciada** em lugar nenhum do projeto.

**Evidence:**
```python
def __init__(self):
    self.notifications = []
    self.email_host = 'smtp.gmail.com'
    self.email_port = 587
    self.email_user = 'taskmanager@gmail.com'
    self.email_password = 'senha123'
```

**Occurrences:** `services/notification_service.py:5-10` (config no construtor),
`services/notification_service.py:15` (`smtplib.SMTP` instanciado inline, sem timeout), e zero
instanciações da classe em todo o projeto

**Impact:** A camada de serviço existe como pasta e como arquivo, mas não participa da aplicação. Isso
é pior que não existir: dá a impressão de que notificações são um recurso implementado. Se algum dia
for ligada como está, cada `notify_task_assigned` abrirá uma conexão SMTP síncrona, sem timeout,
dentro do request path.

**Recommendation:** Injetar mailer e configuração pelo construtor, definir timeout explícito, e
decidir conscientemente entre ligar o serviço ou removê-lo. → `RP-07`

---

### #14 [LOW] Dead Code & Unused Dependencies (AP-21)

**File:** `utils/helpers.py:1-116`

**Description:** `utils/helpers.py` tem 116 linhas e nove funções. Nenhuma delas é chamada fora do
próprio arquivo — `format_date` e `calculate_percentage` chegam a ser importadas em
`routes/report_routes.py:7`, mas nunca invocadas. Somando o `NotificationService` do finding #13, são
164 linhas de código mantido e nunca executado. Há ainda imports não usados em cinco arquivos e três
dependências declaradas que ninguém importa.

**Evidence:**
```python
import json, os, sys, time
```

**Occurrences:** `utils/helpers.py:9-108` (nove funções, zero chamadas externas),
`utils/helpers.py:3-7` (`os`, `json`, `sys`, `math`, `hashlib` não usados),
`routes/task_routes.py:7` (`json`, `os`, `sys`, `time` não usados), `app.py:7` (`os`, `sys`, `json`
não usados), `routes/user_routes.py:6` (`hashlib`, `json` não usados),
`routes/report_routes.py:8` (`json` não usado), `models/task.py:3` (`json` não usado),
`requirements.txt:4-6` (`marshmallow`, `requests`, `python-dotenv` declarados e nunca importados)

**Impact:** Cada dependência declarada é peso de deploy e superfície de vulnerabilidade sem benefício.
E o código morto ativamente engana: `process_task_data` implementa a validação que os handlers
reimplementam à mão, o que sugere uma refatoração que foi começada e abandonada.

**Recommendation:** Remover. As funções que forem realmente úteis (`process_task_data`) devem ser
adotadas pelo validador do finding #9 em vez de reescritas. → `RP-17`

---

### #15 [LOW] Magic Numbers & Magic Strings (AP-19)

**File:** `routes/task_routes.py:110`

**Description:** A lista de status válidos aparece literal em quatro lugares, as faixas de prioridade
e os limites de título em outros tantos. O irônico é que `utils/helpers.py:110-116` já define
`VALID_STATUSES`, `VALID_ROLES`, `MAX_TITLE_LENGTH`, `MIN_TITLE_LENGTH`, `MIN_PASSWORD_LENGTH`,
`DEFAULT_PRIORITY` e `DEFAULT_COLOR` — e nenhuma dessas constantes é usada.

**Evidence:**
```python
if status not in ['pending', 'in_progress', 'done', 'cancelled']:
```

**Occurrences:** `routes/task_routes.py:110`, `:177` (lista de status),
`models/task.py:39` (a mesma lista, de novo), `routes/task_routes.py:96-100`, `:167-170`
(limites de título), `routes/task_routes.py:113`, `:182` (faixa de prioridade),
`routes/user_routes.py:71`, `:120` (lista de roles), `routes/user_routes.py:64`, `:115`
(tamanho mínimo de senha), `utils/helpers.py:110-116` (as constantes que existem e não são usadas)

**Impact:** A lista de status vive em quatro cópias mais uma constante ignorada. Adicionar um status
exige encontrar todas as cinco.

**Recommendation:** `StrEnum` para status e roles, constantes nomeadas para limites, e adotar as que
já existem em vez de criar um conjunto paralelo. → `RP-16`

---

### #16 [LOW] Inconsistent Response Shape & Status Codes (AP-22)

**File:** `routes/task_routes.py:61`

**Description:** A API não tem envelope. Alguns endpoints devolvem array cru, outros objeto, outros
`{'message': ...}`, e os erros usam `{'error': ...}` — em português, enquanto as chaves de dados são
em inglês. O `DELETE /users/<id>` devolve `{'message': ...}`, e o `DELETE /categories/<id>` devolve
outra mensagem com formato próprio.

**Evidence:**
```python
return jsonify(result), 200
```

**Occurrences:** `routes/task_routes.py:61` (array cru), `routes/task_routes.py:150` (objeto),
`routes/task_routes.py:235` (`{'message': ...}`), `routes/user_routes.py:148`,
`routes/report_routes.py:220`, `app.py:24` e `:28` (formatos próprios para `/health` e `/`)

**Impact:** Cliente precisa saber, por endpoint, se a resposta é array, objeto de dados ou mensagem.
Não há como tratar respostas genericamente.

**Recommendation:** Envelope único definido no serializer e formato único de erro vindo do handler
central. Qualquer mudança aqui é mudança de contrato e deve ser listada. → `RP-14` + `RP-09`

---

## Deprecated APIs

Coberto integralmente no finding #7. Este foi o projeto onde o pass produziu o resultado mais forte
dos três, e por evidência direta de runtime.

Verificação de quatro frentes:

1. **Boot com warnings habilitados** — `PYTHONWARNINGS=always python -W always`, importando a app,
   rodando o seed e exercitando os 12 endpoints de leitura pelo test client. Resultado: **69 warnings
   capturadas**, de dois tipos, com arquivo e linha.
2. **Grep do registry Python** — confirmou 18 `datetime.utcnow()`, 56 usos de `Model.query`, 16
   `Model.query.get()` e `SQLALCHEMY_TRACK_MODIFICATIONS`.
3. **Versões resolvidas vs. changelog** — Flask 3.0.0, Flask-SQLAlchemy 3.1.1 e SQLAlchemy 2.0.51.
   A Legacy Query API é legado justamente a partir da 2.0, que é a instalada.
4. **Dependências deprecated** — nenhuma abandonada; `marshmallow`, `requests` e `python-dotenv` estão
   declaradas mas não importadas, o que é o finding #14 e não deprecação.

Contraste entre os três projetos, usando a mesma verificação: vazio no projeto 1, achado por
comparação de versão no projeto 2, e achado por warning de runtime no projeto 3. O pass discrimina.

---

## Refactoring Plan Preview

```text
task-manager-api/
├── .env.example
├── app.py                          # entry point — mantém `python app.py`
└── src/
    ├── app.py                      # composition root: create_app()
    ├── config/settings.py
    ├── domain/
    │   ├── constants.py            # StrEnum de status e roles, limites
    │   └── errors.py
    ├── infra/
    │   ├── database.py             # sessão + PRAGMA foreign_keys
    │   └── security.py             # hash de senha (werkzeug)
    ├── models/
    │   ├── task.py                 # is_overdue() com um único dono
    │   ├── user.py
    │   └── category.py
    ├── repositories/               # queries por entidade, API 2.0 do SQLAlchemy
    │   ├── task_repository.py
    │   ├── user_repository.py
    │   └── category_repository.py
    ├── controllers/
    │   ├── task_controller.py
    │   ├── user_controller.py
    │   ├── category_controller.py
    │   └── report_controller.py
    ├── views/routes.py             # 22 endpoints: método + path -> controller
    ├── serializers/
    │   ├── task_serializer.py
    │   ├── user_serializer.py      # allowlist — sem `password`
    │   └── category_serializer.py
    ├── schemas/validators.py
    ├── services/notification_service.py   # colaboradores injetados
    └── middlewares/
        ├── error_handler.py
        └── logging.py
```

| # | Step | Findings resolvidos |
| --- | --- | --- |
| 1 | Config por ambiente + `.env.example` | #2, #10 |
| 2 | Infra: sessão, PRAGMA foreign_keys, hash de senha | #1, #6 |
| 3 | Migração da Legacy Query API e de `utcnow()` | #7 |
| 4 | Repositories por entidade, com eager loading | #3, #8 |
| 5 | Models como donos das regras; remoção das cópias inline | #5 |
| 6 | Controllers finos | #3 |
| 7 | Views/routes: binding puro | #3 |
| 8 | Serializers com allowlist | #1, #11, #16 |
| 9 | Validação consolidada | #9, #15 |
| 10 | Middlewares: erro central + logging | #4, #12, #16 |
| 11 | Service de notificação com injeção | #13 |
| 12 | Composition root + limpeza de código morto | #14 |

**Contract preservation:** os 22 endpoints originais continuam existindo, com os mesmos métodos,
paths e status codes.

**Intentional behaviour changes:**

- `GET /users`, `GET /users/<id>`, `POST /users`, `PUT /users/<id>` e `POST /login` deixam de retornar
  o campo `password` (finding #1).
- `POST /login` — o campo `token` deixa de ser `fake-jwt-token-<id>`. Enquanto não houver
  autenticação real, o campo é removido em vez de manter um valor que finge ser um token (finding #1).
- Senhas passam a usar pbkdf2 com salt. Os hashes MD5 existentes deixam de autenticar; o seed é
  regerado (finding #1).
- `POST /tasks` e `PUT /tasks/<id>` com `priority` não numérico passam a responder `400` em vez de
  `500` (finding #9).
- `GET /tasks/search` com `priority` ou `user_id` não numérico passa a responder `400` (finding #9).
- `DELETE /categories/<id>` passa a ter comportamento explícito para tasks associadas, em vez de
  deixá-las órfãs (finding #6).
- Respostas de erro passam a ter forma única e não expõem detalhe de exceção (findings #4, #16).
- `GET /tasks/<id>` passa a incluir `user_name` e `category_name`, alinhando-se a `GET /tasks` — hoje
  os dois endpoints devolvem formatos diferentes para a mesma entidade (finding #11).
- O servidor passa a escutar em `127.0.0.1` por default, e `DEBUG` passa a vir da config com default
  `false` (finding #10).

---

## Accepted / Out of Scope

- **`seed.py`** — script de desenvolvimento. Será atualizado para gerar hashes com o novo algoritmo,
  mas não é auditado como código de aplicação.
- **Ausência de autenticação e autorização** — todos os 22 endpoints são públicos, incluindo
  `DELETE /users/<id>`. Introduzir auth é feature nova, não refatoração. O finding #1 resolve o
  vazamento de credencial, não a ausência de controle de acesso.
- **Nomenclatura do domínio em inglês** (`task`, `user`, `category`) — preservada.
- **`users.email` sem constraint `UNIQUE`** — a unicidade é verificada em aplicação
  (`routes/user_routes.py:67`). Adicionar a constraint exige migração de dados e fica registrado
  abaixo.

---

## Post-Refactoring Actions (fora do escopo da skill)

1. **Revogar a `SECRET_KEY` e as credenciais de SMTP.** Estão no histórico do git desde o commit
   inicial; removê-las do código não as revoga.
2. **Forçar reset de senha de todos os usuários.** MD5 sem salt deve ser tratado como equivalente a
   plaintext, e os hashes foram expostos publicamente por `GET /users`.
3. **Implementar autenticação real.** O campo `token` sai da resposta na refatoração; um JWT assinado
   com verificação nos endpoints é o passo seguinte.
4. **Adicionar `UNIQUE` em `users.email`** com migração dos dados existentes.
5. **Decidir o destino do `NotificationService`** — ligá-lo com mailer injetado e envio assíncrono, ou
   removê-lo. Mantê-lo desligado como está é a pior das três opções.
6. **Cobrir com testes.** A refatoração torna `is_overdue`, as validações e os cálculos de relatório
   testáveis pela primeira vez.
7. **Planejar a atualização de major do SQLAlchemy**, agora que a Legacy Query API foi removida.

---

Total: 16 findings

---

## Correção ao finding #6

A execução da Fase 3 mostrou que parte do finding #6 estava errada, e a correção fica registrada aqui
em vez de reescrever o achado original.

**O que eu afirmei:** que `delete_category` apagava a categoria e deixava as tasks apontando para um
id inexistente.

**O que acontece de fato:** o SQLAlchemy desassocia os filhos ao apagar o pai. Ao remover uma
categoria pela API, o ORM carrega as tasks relacionadas e zera `category_id`. Medido no baseline: após
`DELETE /categories/5`, a task associada já vinha com `category_id: null`. Pelo caminho da API, o
órfão que descrevi não ocorria.

**O que permanece verdadeiro, e foi verificado:**

```text
ORIGINAL     PRAGMA foreign_keys = 0
             INSERT INTO tasks (title, category_id, user_id)
                    VALUES ('orfa', 999, 999)      ->  ACEITO, órfão criado

REFATORADO   PRAGMA foreign_keys = 1
             mesmo INSERT                          ->  IntegrityError
```

O banco não aplicava integridade referencial nenhuma. Qualquer escrita fora do ORM — SQL cru, outro
processo, um script de importação, o próprio `seed.py` — podia criar órfãos livremente, e nada
reclamaria. A política de exclusão também não era declarada: o comportamento vinha como efeito
colateral do ORM, não como decisão registrada no schema. E o `delete_user` compensava à mão, com um
loop de `db.session.delete(t)` dentro do handler, o que era redundante com o próprio ORM.

**Severidade após a correção:** o finding continua HIGH, mas por um motivo diferente do que escrevi.
Não é "a API cria órfãos"; é "o banco não impede que sejam criados, e a política de exclusão é
implícita". A recomendação original — declarar `ondelete`, ligar o `PRAGMA` e remover a cascade manual
— continua sendo exatamente a correção certa.

---

## Refactoring Result

Fase 3 executada e aprovada pelo gate humano em 2026-08-08.

### Estrutura resultante

```text
task-manager-api/
├── .env.example
├── app.py                            # entry point — mantém `python app.py`
├── seed.py                           # senhas agora com pbkdf2
└── src/
    ├── app.py                        # composition root: create_app()
    ├── config/settings.py
    ├── domain/
    │   ├── constants.py              # StrEnum de status e roles, limites, rótulos
    │   └── errors.py
    ├── infra/
    │   ├── database.py               # sessão, utc_now(), PRAGMA foreign_keys
    │   └── security.py               # hash de senha (werkzeug)
    ├── models/
    │   ├── task.py                   # is_overdue() e criterio_atrasada()
    │   ├── user.py
    │   └── category.py
    ├── repositories/
    │   ├── task_repository.py        # API 2.0 + eager loading + agregação
    │   ├── user_repository.py
    │   └── category_repository.py
    ├── controllers/
    │   ├── task_controller.py
    │   ├── user_controller.py
    │   ├── category_controller.py
    │   ├── report_controller.py
    │   └── system_controller.py
    ├── views/routes.py               # 22 endpoints: método + path -> controller
    ├── serializers/
    │   ├── task_serializer.py
    │   ├── user_serializer.py        # allowlist — sem `password`
    │   └── category_serializer.py
    ├── schemas/validators.py
    ├── services/notification_service.py
    └── middlewares/
        ├── error_handler.py
        ├── logging.py
        └── security.py
```

Removidos: `database.py`, `models/`, `routes/`, `services/`, `utils/` na raiz. As 116 linhas de
`utils/helpers.py` — nove funções, zero chamadas — saíram inteiras. `requirements.txt` passou de seis
para três dependências, com `marshmallow`, `requests` e `python-dotenv` removidas por nunca terem sido
importadas.

### Findings resolvidos: 15 completos, 1 parcial

| Severidade | Resolvidos |
| --- | --- |
| CRITICAL | 2/2 |
| HIGH | 4/4 |
| MEDIUM | 7/7 |
| LOW | 2/3 (+1 parcial) |

O finding #16 (envelope de resposta inconsistente) ficou parcial, pela mesma razão do projeto 1: a
forma de erro foi unificada e erros inesperados deixaram de virar página HTML, mas as respostas de
sucesso mantêm mais de um formato — array cru para listas, objeto para item, `{'message': ...}` para
comandos. Unificá-las quebraria o contrato de todos os 22 endpoints e exige versionar a API.

### Verificação dos detection signals na árvore refatorada

| Signal | Resultado |
| --- | --- |
| Secrets hardcoded | limpo |
| MD5 / `password` em serializer | limpo |
| `except:` sem tipo | limpo |
| `datetime.utcnow()` | limpo (18 → 0) |
| Legacy Query API (`Model.query.*`) | limpo (56 → 0) |
| `SQLALCHEMY_TRACK_MODIFICATIONS` | limpo |
| `print()` como log | limpo em `src/` |
| Lista de status literal | limpo |
| `CORS(app)` irrestrito | limpo |
| Models/repositories/serializers importando Flask | limpo |
| Routes acessando repository | limpo |
| Controllers escrevendo query | limpo |
| Implementações da regra de prazo fora do model | 0 (era 6) |

Os `print()` remanescentes estão em `seed.py`, que é script de linha de comando — o catálogo isenta
explicitamente o caso em que a saída *é* a interface.

### Validação de comportamento

Baseline capturado **antes** da primeira edição, com 51 probes cobrindo os 22 endpoints e seus
caminhos de erro.

```text
✓ Application boots without errors
✓ 22/22 endpoints originais respondem (mesmos métodos e paths)
✓ 42/51 probes com status e body idênticos
✓ 9/51 probes alterados — todos rastreados a um finding
✓ Warnings de deprecação: 69 -> 0
✓ Zero anti-patterns remanescentes da auditoria (exceto o parcial #16)
```

| Mudança | Probes | Finding |
| --- | --- | --- |
| Campo `password` removido do payload | 3 | #1 |
| Campo `token` removido do login | 1 | #1 |
| Tipo inválido: 500 → 400 | 4 | #9 |
| `GET /tasks/<id>` passa a incluir `user_name` e `category_name` | 1 | #11 |

Verificações adicionais fora do conjunto de probes:

```text
✓ PRAGMA foreign_keys: 0 -> 1; INSERT com FK inexistente passou de aceito a IntegrityError
✓ DELETE /users/1 remove as 4 tasks do usuário via CASCADE do banco, não por loop na rota
✓ Boot com PYTHONWARNINGS=always e 12 endpoints exercitados: nenhuma warning
✓ Regra de prazo com implementação única no model, em duas formas (Python e SQL)
```

### Nota de método — duas regressões encontradas pelo baseline

O primeiro diff após a refatoração acusou `POST /categories` e `POST /users` devolvendo `500`, e o
efeito cascateou: sem categoria e sem usuário criados, mais cinco probes falharam em sequência. A
causa era trivial e teria passado despercebida em uma revisão visual — os repositórios declaravam
parâmetros em português (`criar(self, nome, descricao, cor)`) enquanto o payload validado usa as
chaves em inglês do contrato (`name`, `description`, `color`), produzindo
`TypeError: unexpected keyword argument 'name'`.

Vale registrar porque é o argumento a favor do método: a refatoração parecia pronta, compilava, subia
sem erro e servia a maioria dos endpoints. Foram os probes de `POST` que a reprovaram. Sem o baseline,
o commit teria saído com dois endpoints de escrita quebrados.

### Contraste entre os três projetos

Este era o projeto "parcialmente organizado", e a auditoria confirmou que a organização era nominal:
`services/` e `utils/` somavam 164 linhas mantidas e nunca executadas, e a regra de negócio mais
reutilizada do domínio tinha um dono e sete implementações.

O pass de deprecated APIs fechou os três casos possíveis com a mesma verificação de quatro frentes:
vazio no projeto 1, achado por comparação de versão no projeto 2, e achado por warning de runtime no
projeto 3 — 69 delas, com arquivo e linha.
