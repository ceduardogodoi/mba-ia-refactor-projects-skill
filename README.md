# Skill de Auditoria e Refatoração Arquitetural

Uma Custom Skill do Claude Code que analisa, audita e refatora qualquer projeto para o padrão MVC,
independente da linguagem ou framework. Executada de ponta a ponta em três projetos legados: dois
Python/Flask e um Node.js/Express.

```text
.claude/skills/refactor-arch/
├── SKILL.md                          # as 3 fases, os ground rules e o gate
└── references/
    ├── project-analysis.md           # heurísticas de detecção por stack
    ├── antipattern-catalog.md        # 23 anti-patterns com detection signals
    ├── audit-report-template.md      # formato do relatório da Fase 2
    ├── mvc-guidelines.md             # camadas alvo e direção de dependência
    └── refactoring-playbook.md       # 18 transformações com código antes/depois
```

| | code-smells-project | ecommerce-api-legacy | task-manager-api |
| --- | --- | --- | --- |
| Stack | Python 3.12 + Flask 3.1.1 | Node 24 + Express 4.22.1 | Python 3.12 + Flask 3.0 / SQLAlchemy 2.0 |
| Findings | 19 | 18 | 16 |
| Severidade | 6C / 4H / 6M / 3L | 6C / 5H / 4M / 3L | 2C / 4H / 7M / 3L |
| Endpoints | 19 | 3 | 22 |
| Antes | 780 linhas / 4 arquivos | 180 linhas / 3 arquivos | 1.158 linhas / 15 arquivos |
| Depois | 1.357 / 38 arquivos | 964 / 22 arquivos | 1.746 / 40 arquivos |
| Probes de validação | 38 (19 idênticos) | 10 + crash probe (2 idênticos) | 51 (42 idênticos) |
| Relatório | [audit-project-1.md](reports/audit-project-1.md) | [audit-project-2.md](reports/audit-project-2.md) | [audit-project-3.md](reports/audit-project-3.md) |

---

## A) Análise Manual

Leitura dos três projetos feita à mão, antes de escrever a skill. É esta análise que calibrou o
catálogo: cada problema encontrado aqui virou um detection signal, e a distribuição de severidade que
observei virou a régua do catálogo.

### `code-smells-project` — Python/Flask, API de E-commerce

| # | Problema | Severidade | Local |
| --- | --- | --- | --- |
| 1 | `POST /admin/query` executa SQL arbitrário do body, sem autenticação | `CRITICAL` | `app.py:59-78` |
| 2 | SQL montado por concatenação em 18 pontos | `CRITICAL` | `models.py` |
| 3 | Senhas em plaintext, gravadas, comparadas em SQL e devolvidas por `GET /usuarios` | `CRITICAL` | `models.py:105-131` |
| 4 | `SECRET_KEY` hardcoded e ecoada no `/health` | `CRITICAL` | `app.py:7`, `controllers.py:289` |
| 5 | `models.py` acumula acesso a dados, regra de negócio e formatação para 4 domínios | `CRITICAL` | `models.py:1-314` |
| 6 | Conexão SQLite global com `check_same_thread=False` | `HIGH` | `database.py:4-10` |
| 7 | Notificações disparadas como `print` dentro do controller | `HIGH` | `controllers.py:208-210` |
| 8 | Queries N+1 na listagem de pedidos | `MEDIUM` | `models.py:171-233` |
| 9 | Validação duplicada e já divergente entre criar e atualizar produto | `MEDIUM` | `controllers.py:28-54` vs `:72-90` |
| 10 | Magic numbers nas faixas de desconto | `LOW` | `models.py:256-262` |
| 11 | `import sqlite3` e `import os` não usados | `LOW` | `models.py:2`, `database.py:2` |

**Por que importam.** Os quatro primeiros não são estilo: qualquer cliente HTTP lê a base inteira,
autentica-se como admin com `' OR '1'='1' --` e recebe as senhas de todos por um `GET`. O quinto é o
que impede qualquer correção segura — a regra de desconto, que é a mais volátil do sistema, está
soterrada entre `cursor.execute` e montagem de payload. A divergência da validação (#9) é o caso mais
instrutivo: `POST /produtos` recusa categoria inválida e `PUT /produtos/<id>` aceita, porque a cópia
foi feita e depois só uma evoluiu.

### `ecommerce-api-legacy` — Node.js/Express, LMS com checkout

| # | Problema | Severidade | Local |
| --- | --- | --- | --- |
| 1 | Chave `pk_live_` de gateway de pagamento e senha de banco hardcoded | `CRITICAL` | `src/utils.js:1-7` |
| 2 | Número do cartão e chave do gateway impressos em log a cada checkout | `CRITICAL` | `src/AppManager.js:45` |
| 3 | `badCrypto` como hash de senha | `CRITICAL` | `src/utils.js:17-23` |
| 4 | `card` numérico derruba o processo inteiro | `CRITICAL` | `src/AppManager.js:29-35`, `:46` |
| 5 | `AppManager` concentra conexão, schema, seed, roteamento, pagamento e auditoria | `CRITICAL` | `src/AppManager.js:4-141` |
| 6 | Aprovação de pagamento decidida por prefixo do cartão, sem gateway | `CRITICAL` | `src/AppManager.js:46` |
| 7 | Callback hell de 5 níveis e contadores assíncronos manuais | `HIGH` | `src/AppManager.js:37-78`, `:83-128` |
| 8 | `DELETE /api/users/:id` ignora o erro e responde sucesso incondicional | `HIGH` | `src/AppManager.js:131-137` |
| 9 | Três escritas encadeadas sem transação; nenhuma FK no schema | `HIGH` | `src/AppManager.js:12-16`, `:50-63` |
| 10 | `globalCache` cresce sem limite; `totalRevenue` exportado por valor | `HIGH` | `src/utils.js:9-10` |
| 11 | N+1 no relatório financeiro: 1 + N + 2×N×M queries | `MEDIUM` | `src/AppManager.js:83-128` |
| 12 | Identificadores de uma letra para dados de negócio | `LOW` | `src/AppManager.js:29-33` |
| 13 | Três rotas, três formatos de resposta | `LOW` | `src/AppManager.js:35`, `:60`, `:135` |

**Por que importam.** 180 linhas concentram mais risco que as 780 do projeto anterior. O `badCrypto`
parece só ruim até você medir: ele guarda apenas os dois primeiros caracteres do base64 da senha, ou
seja 12 bits, e descarta o resto — `badCrypto("senhaforte")` é igual a `badCrypto("sen")`, e 200 mil
senhas distintas produzem **um único hash**. O #4 é negação de serviço remota com uma requisição, e
como o banco é `:memory:`, tudo morre junto. O #6 registra receita que não existe: nenhum dinheiro é
movimentado, mas `payments` recebe `PAID` e o relatório financeiro soma.

### `task-manager-api` — Python/Flask, Task Manager

| # | Problema | Severidade | Local |
| --- | --- | --- | --- |
| 1 | Senhas com MD5 sem salt, hash no payload de 5 endpoints, token falso no login | `CRITICAL` | `models/user.py:21,29`, `routes/user_routes.py:210` |
| 2 | `SECRET_KEY` e credenciais SMTP hardcoded | `CRITICAL` | `app.py:13`, `services/notification_service.py:7-10` |
| 3 | Rotas fazem o trabalho de controller, model e serializer ao mesmo tempo | `HIGH` | `routes/task_routes.py:11-63`, `routes/report_routes.py:12-101` |
| 4 | Doze `except:` sem tipo, sem log | `HIGH` | 12 ocorrências em 4 arquivos |
| 5 | `is_overdue()` definido no model e reimplementado inline seis vezes | `HIGH` | `models/task.py:50-59` + 6 cópias |
| 6 | Foreign keys declaradas mas nunca aplicadas pelo banco | `HIGH` | `database.py`, `models/task.py:13-14` |
| 7 | 18 `datetime.utcnow()` e 56 usos da Legacy Query API | `MEDIUM` | 7 arquivos |
| 8 | Cinco padrões N+1 distintos | `MEDIUM` | `routes/report_routes.py:55-68` e outros |
| 9 | `priority` como string derruba a validação para 500 | `MEDIUM` | `routes/task_routes.py:113` |
| 10 | `utils/helpers.py`: 9 funções, zero chamadas externas | `LOW` | `utils/helpers.py:1-116` |
| 11 | Constantes definidas em `helpers.py` e ignoradas; literais repetidos | `LOW` | `utils/helpers.py:110-116` |

**Por que importam.** Este é o projeto enganoso: ele *parece* organizado. O #5 é o sintoma que
desmascara — a regra mais reutilizada do domínio tem um dono e sete implementações, e mudar o critério
de atraso exigiria acertar sete lugares. O #1 é o mais grave: `81dc9bdb52d04dc20036dbd8313ed055` é o
MD5 de `1234`, e sai por um `GET` público. O #10 mostra o custo do abandono: `process_task_data`
implementa exatamente a validação que os handlers reescrevem à mão.

---

## B) Construção da Skill

### As três fases e o que separa uma da outra

O `SKILL.md` é o prompt; os cinco arquivos de referência são o conhecimento de domínio. A separação
importa: o prompt fica pequeno e sempre carregado, o conhecimento é lido sob demanda na fase que
precisa dele.

- **Fase 1 — Análise.** Estritamente read-only. Detecta linguagem, framework, banco, rotas e
  arquitetura a partir de manifests e lockfiles.
- **Fase 2 — Auditoria.** Também read-only, exceto pelo relatório. Cruza o código contra o catálogo,
  produz o relatório e **para**.
- **Fase 3 — Refatoração.** A única fase que escreve.

### Decisões de design

**Todo finding aponta um `RP-xx`.** Esta é a decisão mais estruturante. Cada achado do relatório
termina nomeando a transformação que o corrige, o que faz a Fase 3 ser consequência mecânica da Fase 2
em vez de uma segunda rodada de julgamento onde o agente pode divergir do que ele mesmo auditou.

**O gate é escrito de forma dura.** "Imprima a linha, **encerre o turno e espere**. Não chame outra
tool. Não comece a planejar em voz alta. Não toque em arquivo." O comportamento mais fácil de um
agente atropelar é justamente a pausa, então a instrução é explícita sobre o que *não* fazer, não só
sobre o que fazer.

**Baseline antes da primeira edição.** A Fase 3 começa subindo a aplicação *original* e gravando
status e corpo de cada rota do inventário da Fase 1. Sem isso, "os endpoints continuam respondendo" é
afirmação, não verificação. Esta decisão se pagou: ela reprovou a primeira tentativa de refatoração do
projeto 3, que compilava, subia sem erro e servia a maioria dos endpoints — mas tinha dois endpoints
de escrita quebrados por incompatibilidade de nome de parâmetro.

**Toda entrada do catálogo tem uma cláusula "not a finding when".** Falso positivo destrói a
credibilidade de um relatório mais rápido que um falso negativo. É por isso que o relatório do projeto
1 distingue os 10 pontos de SQL Injection realmente exploráveis dos 5 que recebem `<int:id>` já coagido
pelo Flask — ambos são erro, mas só os primeiros são vulnerabilidade.

**Contract preservation é ground rule, não sugestão.** Rotas perigosas são neutralizadas por feature
flag em vez de removidas: `POST /admin/query` continua existindo e responde `403` enquanto
`ADMIN_ENDPOINTS_ENABLED=false`. Isso satisfaz "os endpoints originais respondem" sem manter o vetor
de ataque, e a decisão fica documentada em vez de silenciosa.

### Quais anti-patterns entraram, e por quê

23 anti-patterns — 5 `CRITICAL`, 6 `HIGH`, 8 `MEDIUM`, 4 `LOW`. O mínimo exigido era 8.

A seleção veio da análise manual: cada problema que eu encontrei lendo os três projetos precisava ter
uma entrada que o detectasse por sinal, não por intuição. `AP-02` (SQL Injection) nasceu do projeto 1,
`AP-09` (callback hell) do projeto 2, `AP-13` (lógica duplicada) do `is_overdue` do projeto 3.

Entradas que existem por decisão explícita:

- **`AP-15 — Deprecated API Usage`**, exigido pelo desafio, com um registry de ~24 entradas
  Python/Node e um pass de quatro frentes: capturar warnings de runtime no boot, grepar o registry,
  comparar versões resolvidas contra o changelog, e checar dependências abandonadas. A primeira frente
  é a mais forte porque produz evidência que não depende do meu julgamento.
- **`AP-03` separado de `AP-02`.** Injeção de SQL e um endpoint que executa SQL do request são
  problemas diferentes com correções diferentes — parametrizar não resolve um backdoor.
- **`AP-23 — Insecure Middleware Configuration`** foi acrescentado *depois* da primeira execução, e a
  história está nos commits (ver "Desafios encontrados").

### Como garanti que a skill é agnóstica de tecnologia

Quatro mecanismos, todos verificáveis:

1. **Detecção por manifest, nunca por suposição.** O `project-analysis.md` mapeia dez ecossistemas por
   arquivo de manifest, e o `SKILL.md` proíbe explicitamente afirmar qualquer coisa sobre a stack que
   não venha de um arquivo lido na Fase 1.
2. **Detection signals com variantes por linguagem.** `AP-02` lista concatenação Python, template
   literal JS, `%`-format e escape hatches de ORM. `AP-15` tem registries separados para Python e Node.
3. **O playbook alterna Python e JavaScript.** Nove transformações têm exemplo em cada linguagem, e as
   regras abaixo do código são escritas na forma "faça X", não "use a função Y do Flask".
4. **Layouts por ecossistema no `mvc-guidelines.md`.** Flask e Express têm árvore de referência;
   Django, NestJS, Rails, Laravel e Go têm instrução de seguir a convenção do próprio framework. A
   regra final é explícita: *"nunca imponha uma árvore Python ou Node a um framework que tem convenção
   própria"*.

O teste real foi o projeto 2. Ele é a única stack não-Python e o único paradigma assíncrono, e exigiu
transformações que os outros dois não tocaram: promisificação na fronteira de infra, `asyncHandler`
para que rejeições cheguem ao middleware, e substituição de contadores manuais por `Promise.all`.

### Desafios encontrados

**Uma lacuna que só apareceu executando.** No projeto 1 identifiquei `CORS(app)` sem restrição de
origem — por julgamento, não por detection signal. O catálogo não cobria misconfiguração de segurança
em middleware, e numa sessão limpa o achado provavelmente escaparia. Registrei a lacuna no relatório,
commitei essa observação, e só então criei `AP-23` e `RP-18`. A entrada se pagou na execução seguinte:
no projeto 2 ela produziu finding direto dos sinais — `express.json()` sem `limit`, headers ausentes,
bind em todas as interfaces.

**Ampliar o catálogo criou dívida retroativa.** `AP-23` é mais largo que o achado que o motivou, e os
sinais novos não foram aplicados ao projeto 1, que já tinha rodado. Três ficaram pendentes lá
(security headers, `MAX_CONTENT_LENGTH`, rate limit em `/login`). Está registrado como tabela de delta
residual no relatório — decisão consciente, não omissão.

**Um finding meu estava errado.** No projeto 3 afirmei que apagar uma categoria deixava tasks órfãs. O
baseline provou o contrário: o SQLAlchemy desassocia os filhos no nível do ORM. O que era verdade —
e verifiquei nos dois sentidos — é que o banco rodava com `PRAGMA foreign_keys = 0` e aceitava
qualquer FK inexistente vinda de escrita fora do ORM. O finding continua `HIGH`, por outro motivo. A
correção está em seção própria do relatório, em vez de reescrever o achado original como se nada
tivesse acontecido.

**Um experimento contaminado.** Ao medir determinismo no projeto 2, obtive listas que cresciam a cada
execução — impossível com banco `:memory:`. A causa era o meu harness: `eval` cria subshell, `$!`
capturava o PID errado e o servidor ficava órfão na porta. Corrigi para encerrar por porta e
recapturei os dois baselines do zero. A conclusão que eu havia tirado estava errada e foi refeita.

**A refatoração pode introduzir a duplicação que acabou de remover.** Ao consolidar o `is_overdue()`
no projeto 3, o repositório passou a expressar a mesma regra como predicado SQL — inevitável quando o
filtro roda no banco, mas eram duas formas em dois arquivos. Movi o predicado para
`Task.criterio_atrasada()`, no model. A regra que tinha um dono e sete implementações passou a ter um
dono e duas formas, ambas no mesmo arquivo.

### Onde a skill mora

O desafio exige a skill dentro dos três projetos, e é o que está entregue — as três cópias são
byte-idênticas (`shasum` do conteúdo concatenado: `2c4deda17240`). A redundância é intencional: é ela
que prova que a skill é copiável e não acoplada a um projeto.

Considerei promover uma cópia à raiz para conveniência, e decidi não fazê-lo. Durante esta sessão o
próprio Claude Code registrou a skill como *directory-scoped* ao encontrá-la em
`task-manager-api/.claude/skills`, aplicando-a a arquivos sob aquele diretório. Ou seja: rodando da
raiz, as três cópias já são alcançáveis, e uma quarta só criaria mais um lugar para divergir.

Para propagar alterações durante a iteração, `code-smells-project` é a cópia canônica e o sync é em
mão única:

```bash
for p in ecommerce-api-legacy task-manager-api; do
  rsync -a --delete code-smells-project/.claude/skills/refactor-arch/ "$p/.claude/skills/refactor-arch/"
done
```

---

## C) Resultados

### Resumo dos três relatórios

**53 findings** no total, com evidência de arquivo e linha em cada um.

| Severidade | Projeto 1 | Projeto 2 | Projeto 3 | Total |
| --- | --- | --- | --- | --- |
| `CRITICAL` | 6 | 6 | 2 | 14 |
| `HIGH` | 4 | 5 | 4 | 13 |
| `MEDIUM` | 6 | 4 | 7 | 17 |
| `LOW` | 3 | 3 | 3 | 9 |
| **Total** | **19** | **18** | **16** | **53** |

O pass de deprecated APIs fechou os três resultados possíveis com a mesma verificação de quatro
frentes, o que sugere que ele discrimina em vez de sempre confirmar:

| Projeto | Resultado | Como foi obtido |
| --- | --- | --- |
| 1 | nenhuma | Boot com `-W all` sem warnings; grep do registry sem ocorrência; versões instaladas conferidas |
| 2 | 4 achados | Nenhum warning e nenhum grep — achados por comparação de versão (`sqlite3.verbose()`, API de callback, `sqlite3` um major atrás, Express 4 em manutenção) |
| 3 | 74 ocorrências | **69 warnings de runtime capturadas**, com arquivo e linha: 18 `datetime.utcnow()` e 56 usos da Legacy Query API |

### Antes e depois

**`code-smells-project`** — 4 arquivos viram 38; o SQL sai de 18 concatenações para zero.

```text
antes                              depois
app.py          88 linhas          src/{config,infra,models,controllers,
controllers.py 292                      views,serializers,schemas,services,
models.py      314                      middlewares}/ + app.py
database.py     86                 38 arquivos, 1.357 linhas
```

**`ecommerce-api-legacy`** — a God Class de 141 linhas vira 22 arquivos; cinco níveis de callback
viram `async/await`.

```text
antes                              depois
src/app.js       14 linhas         src/{config,infra,models,services,
src/AppManager.js 141                   controllers,routes,serializers,
src/utils.js      25                    schemas,middlewares}/ + app.js + server.js
                                   22 arquivos, 964 linhas
```

**`task-manager-api`** — as pastas continuam, mas passam a significar o que dizem; `utils/` inteiro
sai, e `requirements.txt` cai de 6 para 3 dependências.

```text
antes                              depois
models/  routes/  services/        src/{config,domain,infra,models,repositories,
utils/   database.py  app.py            controllers,views,serializers,schemas,
15 arquivos, 1.158 linhas               services,middlewares}/ + app.py + seed.py
                                   40 arquivos, 1.746 linhas
```

Três números que resumem a mudança de qualidade:

```text
                                    antes    depois
SQL por concatenação (projeto 1)       18         0
Warnings de deprecação (projeto 3)     69         0
Implementações de is_overdue (proj 3)   7         1 (em duas formas, no model)
```

### Checklist de validação

**Fase 1 — Análise**

- [x] Linguagem detectada corretamente — Python 3.12.13, Node v24.16.0, Python 3.12.13
- [x] Framework detectado corretamente — versões **resolvidas** do lockfile/venv, não o range do manifest
- [x] Domínio descrito corretamente — E-commerce, LMS com checkout, Task Manager
- [x] Número de arquivos condiz — 4, 3 e 15, conferidos por `find` com exclusões declaradas

**Fase 2 — Auditoria**

- [x] Relatório segue o template de `audit-report-template.md`
- [x] Cada finding tem arquivo e linhas exatos
- [x] Findings ordenados `CRITICAL` → `LOW`
- [x] Mínimo de 5 findings — 19, 18 e 16
- [x] Detecção de APIs deprecated incluída — nos três, com o método documentado
- [x] Skill pausa e pede confirmação antes da Fase 3 — nas três execuções

**Fase 3 — Refatoração**

- [x] Estrutura de diretórios segue padrão MVC
- [x] Configuração extraída para módulo de config, sem hardcoded — `.env.example` nos três
- [x] Models criados para abstrair dados
- [x] Views/Routes separadas para roteamento
- [x] Controllers concentram o fluxo
- [x] Error handling centralizado — 16, 0 e 12 blocos duplicados removidos
- [x] Entry point claro — `app.py` / `server.js`, com a composição em módulo separado
- [x] Aplicação inicia sem erros
- [x] Endpoints originais respondem corretamente — 19/19, 3/3 e 22/22

**Critérios de aceite**

| Critério | P1 | P2 | P3 |
| --- | --- | --- | --- |
| Fase 1 detecta stack corretamente | ✓ | ✓ | ✓ |
| Fase 2 encontra ≥ 5 findings | ✓ 19 | ✓ 18 | ✓ 16 |
| Fase 2 inclui ≥ 1 `CRITICAL` ou `HIGH` | ✓ 10 | ✓ 11 | ✓ 6 |
| Fase 3 aplicação funciona após refatoração | ✓ | ✓ | ✓ |

### Validação por baseline

Em cada projeto o baseline foi capturado **antes da primeira edição**, e cada divergência foi
rastreada até um finding. Nenhuma mudança não intencional sobreviveu.

| | probes | idênticos | alterados | todos rastreados? |
| --- | --- | --- | --- | --- |
| Projeto 1 | 38 | 19 | 19 | sim |
| Projeto 2 | 10 + crash probe | 2 | 8 | sim |
| Projeto 3 | 51 | 42 | 9 | sim |

O projeto 2 tem a evidência mais direta. Uma requisição não autenticada com `card` numérico:

```text
ANTES                                    DEPOIS
crash probe -> HTTP 000                  crash probe -> HTTP 400
servidor    -> MORREU                    servidor    -> VIVO

TypeError: cc.startsWith is not a function
    at processPaymentAndEnroll (src/AppManager.js:46:41)
Node.js v24.16.0     <- processo encerrado
```

### Logs das aplicações após a refatoração

```text
$ cd code-smells-project && python app.py
2026-08-08 12:07:31 INFO  loja dados iniciais carregados
2026-08-08 12:07:31 INFO  loja aplicação inicializada
BOOT OK — rotas: 19
```

```text
$ cd ecommerce-api-legacy && npm start
{"ts":"2026-08-08T...","level":"info","message":"dados iniciais carregados"}
{"ts":"2026-08-08T...","level":"info","message":"servidor iniciado",
 "context":{"host":"127.0.0.1","port":3000,"env":"development"}}

# checkout — note o cartão mascarado e a ausência da chave do gateway
{"level":"info","message":"processando cobrança",
 "context":{"card":"************4444","amount":497,"courseId":2,"provider":"stub"}}
```

```text
$ cd task-manager-api && python app.py
2026-08-08 14:30:08 INFO  taskmanager aplicação inicializada
BOOT OK — rotas: 22

WARNINGS: nenhuma      # eram 69
```

Verificações complementares, medidas no wire e não no código:

```text
projeto 2   $ curl -sD - localhost:3000/api/admin/financial-report | grep -i x-
            X-Content-Type-Options: nosniff
            X-Frame-Options: DENY
            Referrer-Policy: no-referrer

projeto 2   corpo acima do limite            -> HTTP 413
projeto 2   DELETE de usuário sem matrícula  -> HTTP 200
projeto 3   PRAGMA foreign_keys              -> 0 antes, 1 depois
projeto 3   INSERT com FK inexistente        -> aceito antes, IntegrityError depois
projeto 3   DELETE /users/1                  -> 200; tasks do usuário 4 -> 0
```

---

## D) Como Executar

### Pré-requisitos

- **Claude Code** instalado e autenticado
- **Python 3.12+** para `code-smells-project` e `task-manager-api`
- **Node.js 20+** para `ecommerce-api-legacy`

A skill já está em `.claude/skills/refactor-arch/` dentro dos três projetos. Não é preciso copiar nada.

### Executando a skill

```bash
cd code-smells-project
claude "/refactor-arch"
```

```bash
cd ../ecommerce-api-legacy
claude "/refactor-arch"
```

```bash
cd ../task-manager-api
claude "/refactor-arch"
```

A skill imprime o bloco da Fase 1, o relatório da Fase 2 e então **para**, aguardando `y` ou `n` antes
de tocar em qualquer arquivo.

Argumentos disponíveis:

| Argumento | Efeito |
| --- | --- |
| `--report <path>` | Onde salvar o relatório. Default: `<git-root>/reports/audit-<projeto>.md` |
| `--audit-only` | Roda Fases 1 e 2 e para. Nunca executa a Fase 3 |
| `--yes` | Pré-aprova a Fase 3. O relatório ainda é impresso por inteiro antes de qualquer escrita |

```bash
claude "/refactor-arch --report reports/audit-project-1.md"
claude "/refactor-arch --audit-only"
```

### Rodando os projetos refatorados

```bash
cd code-smells-project
pip install -r requirements.txt
cp .env.example .env          # obrigatório: não sobe sem SECRET_KEY
python app.py                 # http://127.0.0.1:5000
```

```bash
cd ecommerce-api-legacy
npm install
cp .env.example .env          # obrigatório: não sobe sem PAYMENT_GATEWAY_KEY
npm start                     # http://127.0.0.1:3000
```

```bash
cd task-manager-api
pip install -r requirements.txt
cp .env.example .env          # obrigatório: não sobe sem SECRET_KEY
python seed.py                # popula o banco — rode antes do primeiro boot
python app.py                 # http://127.0.0.1:5000
```

Os três falham na inicialização com mensagem explícita se a variável obrigatória estiver ausente. É
intencional: um default para secret é a mesma vulnerabilidade com passos a mais.

### Como validar que a refatoração funcionou

**1. A aplicação sobe sem erro e expõe o mesmo número de rotas.**

```bash
# projeto 1 — 19 rotas
cd code-smells-project && SECRET_KEY=x python -c "
import app; print(len([r for r in app.app.url_map.iter_rules() if r.endpoint!='static']))"

# projeto 3 — 22 rotas, e zero warnings de deprecação
cd task-manager-api && SECRET_KEY=x PYTHONWARNINGS=always python -W always -c "
import app; print(len([r for r in app.app.url_map.iter_rules() if r.endpoint!='static']))"
```

**2. Os endpoints respondem.** Cada projeto tem exemplos prontos:

```bash
curl localhost:5000/produtos                        # projeto 1
curl localhost:3000/api/admin/financial-report      # projeto 2 (ou use api.http)
curl localhost:5000/tasks                           # projeto 3
```

**3. Os anti-patterns sumiram.** Os detection signals do catálogo são grepáveis por construção. O
filtro abaixo descarta comentários e menções entre crases — o código refatorado documenta o que
substituiu, então os nomes antigos aparecem em docstrings de propósito:

```bash
nocomment(){ grep -vE '`' | grep -vE '^[^:]+:[0-9]+: *(\*|//|#)'; }

grep -rn "execute(.*+"           code-smells-project/src/   | nocomment   # SQL concatenado
grep -rn "utcnow()\|\.query\."   task-manager-api/src/      | nocomment   # deprecated
grep -rn "badCrypto\|pk_live"    ecommerce-api-legacy/src/  | nocomment   # hash caseiro e secret
grep -rn "senha"                 code-smells-project/src/serializers/ | nocomment
grep -rn "md5\|'password'"       task-manager-api/src/      | nocomment
```

Os cinco retornam vazio.

**4. Os dados sensíveis não vazam mais.**

```bash
curl -s localhost:5000/usuarios | grep -c senha      # projeto 1 -> 0
curl -s localhost:5000/health   | grep -c secret_key # projeto 1 -> 0
curl -s localhost:5000/users/1  | grep -c password   # projeto 3 -> 0
```

**5. As rotas perigosas continuam existindo, mas desarmadas.**

```bash
curl -s -X POST localhost:5000/admin/query \
  -H 'Content-Type: application/json' -d '{"sql":"SELECT 1"}'
# -> 403 enquanto ADMIN_ENDPOINTS_ENABLED=false
```

---

## Estrutura do repositório

```text
mba-ia-refactor-projects-skill/
├── README.md
├── reports/
│   ├── audit-project-1.md
│   ├── audit-project-2.md
│   └── audit-project-3.md
├── code-smells-project/          # Python/Flask — API de E-commerce
│   ├── .claude/skills/refactor-arch/
│   ├── app.py  .env.example  requirements.txt
│   └── src/
├── ecommerce-api-legacy/         # Node/Express — LMS com checkout
│   ├── .claude/skills/refactor-arch/
│   ├── package.json  api.http  .env.example
│   └── src/
└── task-manager-api/             # Python/Flask — Task Manager
    ├── .claude/skills/refactor-arch/
    ├── app.py  seed.py  .env.example  requirements.txt
    └── src/
```

## Ações posteriores

A refatoração corrige arquitetura e código; não corrige o que já vazou. Os três relatórios trazem uma
seção de ações posteriores, e três itens valem repetir aqui:

1. **Revogar todos os secrets.** `SECRET_KEY` nos projetos 1 e 3, chave `pk_live_` de gateway e
   credenciais de banco e SMTP no projeto 2. Estão no histórico do git desde o commit inicial —
   removê-los do código não os revoga.
2. **Considerar todas as senhas comprometidas.** Plaintext no projeto 1, `badCrypto` de 12 bits no
   projeto 2, MD5 sem salt exposto publicamente no projeto 3. Reset obrigatório nos três.
3. **Nenhum dos três tem autenticação.** A refatoração fecha o vazamento de credenciais e desarma as
   rotas administrativas, mas endpoints como `GET /usuarios` e `GET /api/admin/financial-report`
   continuam públicos. Introduzir auth é feature, não refatoração.
