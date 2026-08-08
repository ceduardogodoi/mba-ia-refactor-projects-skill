# ARCHITECTURE AUDIT REPORT

Project:   code-smells-project
Stack:     Python 3.12.13 + Flask 3.1.1
Files:     4 analyzed | ~780 lines of code
Database:  SQLite (loja.db) — 4 tables
Routes:    19 endpoints
Date:      2026-08-08
Skill:     refactor-arch

---

## Summary

| Severity | Count |
| --- | --- |
| CRITICAL | 6 |
| HIGH | 4 |
| MEDIUM | 6 |
| LOW | 3 |
| **Total** | **19** |

O projeto tem os nomes de arquivo de uma aplicação em camadas e o comportamento de um script único.
`models.py` não é uma camada de dados: ele monta SQL por concatenação, decide regra de negócio
(faixas de desconto, validação de estoque, cálculo de total) e devolve dicionários já formatados para
a API — três responsabilidades de três camadas diferentes em um arquivo. `app.py`, que deveria ser
apenas composição e roteamento, define dois handlers que abrem cursor e executam SQL diretamente, um
deles aceitando SQL arbitrário do request. O resultado é que nenhuma regra pode ser testada sem subir
o Flask, e a superfície de ataque é total: um cliente HTTP não autenticado consegue ler a tabela de
usuários — que guarda senhas em plaintext —, autenticar-se como qualquer pessoa, ou apagar a base
inteira. A refatoração precisa separar as camadas, mas o trabalho urgente é fechar os quatro vetores
de acesso irrestrito ao banco.

---

## Findings

### #1 [CRITICAL] Arbitrary Query / Command Execution Endpoint (AP-03)

**File:** `app.py:59-78`

**Description:** `POST /admin/query` recebe uma string SQL no campo `sql` do body e a executa sem
qualquer autenticação, autorização ou allowlist. Não é um code smell — é um backdoor com rota
pública. `POST /admin/reset-db` complementa: apaga as quatro tabelas sem confirmação e sem auth.

**Evidence:**
```python
dados = request.get_json()
query = dados.get("sql", "")
...
cursor.execute(query)
```

**Occurrences:** `app.py:59-78` (`/admin/query`), `app.py:47-57` (`/admin/reset-db`)

**Impact:** Qualquer pessoa com acesso de rede à aplicação tem controle total do banco —
`{"sql": "SELECT * FROM usuarios"}` devolve todas as senhas em plaintext, e `DROP TABLE` é aceito
igualmente. `POST /admin/reset-db` destrói a base com uma requisição vazia, sem body.

**Recommendation:** Manter as duas rotas atrás de feature flag desabilitada por padrão
(`ADMIN_QUERY_ENABLED`), respondendo `403` enquanto desligada, e mover os handlers para um
`admin_controller`. → `RP-03`

---

### #2 [CRITICAL] SQL Injection via String-Built Queries (AP-02)

**File:** `models.py:28`

**Description:** As 18 queries de `models.py` são montadas por concatenação de string. Onde o valor
concatenado vem de path param tipado (`<int:id>`) o Flask já coage para inteiro e não há
exploração possível; mas onde vem de body ou query string, a injeção é direta. Os casos exploráveis
são: `login_usuario` (`email`, `senha`), `criar_usuario` e `criar_produto`/`atualizar_produto`
(`nome`, `descricao` — só o comprimento é checado), `criar_pedido` (`usuario_id` e `produto_id`
vindos do JSON, sem coerção) e `buscar_produtos` (`termo` e `categoria`, ambos direto da query
string, sem validação).

**Evidence:**
```python
cursor.execute(
    "SELECT * FROM usuarios WHERE email = '" + email + "' AND senha = '" + senha + "'"
)
```

**Occurrences:** exploráveis — `models.py:47-50`, `models.py:57-61`, `models.py:109-111`,
`models.py:126-129`, `models.py:140`, `models.py:148-151`, `models.py:155`, `models.py:157-161`,
`models.py:163-166`, `models.py:289-297`. Segunda ordem (valor vindo do banco, gravado por um
insert anterior) — `models.py:188`, `models.py:192`, `models.py:220`, `models.py:224`. Não
exploráveis mas igualmente incorretos — `models.py:28`, `models.py:68`, `models.py:92`,
`models.py:174`, `models.py:279-281`.

**Impact:** `POST /login` com `{"email": "' OR '1'='1' --", "senha": "x"}` autentica como o primeiro
usuário da tabela, que é o `admin`. `GET /produtos/busca?q=' OR 1=1 --` já vaza o catálogo inteiro e
serve de ponto de partida para `UNION SELECT` sobre `usuarios`. Não requer credencial nenhuma.

**Recommendation:** Substituir toda concatenação por placeholders `?` com tupla de parâmetros,
inclusive nos filtros dinâmicos de `buscar_produtos` (montar a estrutura, nunca os valores), e
concentrar o SQL em repositórios por entidade. → `RP-02`

---

### #3 [CRITICAL] Insecure Credential Storage & Exposure (AP-05)

**File:** `models.py:105-131`

**Description:** Senhas são gravadas e comparadas em plaintext. Não há hash em lugar nenhum do
projeto: o seed insere `admin123` literal, o cadastro grava o que veio do request, e o login compara
string com string dentro do próprio SQL. Pior, a senha faz parte do payload de resposta —
`get_todos_usuarios` e `get_usuario_por_id` incluem o campo `senha`, e `GET /usuarios` é público.

**Evidence:**
```python
cursor.execute(
    "SELECT * FROM usuarios WHERE email = '" + email + "' AND senha = '" + senha + "'"
)
```

**Occurrences:** `models.py:110` (login compara plaintext), `models.py:126-129` (grava plaintext),
`models.py:84` e `models.py:99` (`senha` no dicionário de retorno), `controllers.py:128-134`
(`GET /usuarios` devolve a lista com senhas), `database.py:75-79` (seeds em plaintext)

**Impact:** `GET /usuarios`, sem autenticação, devolve nome, email e senha de todos os usuários —
incluindo o admin. Como reúso de senha é a norma, o vazamento não se limita a esta aplicação.

**Recommendation:** Hash com KDF (`werkzeug.security.generate_password_hash`, já disponível via
Flask), comparação com `check_password_hash`, e remoção do campo `senha` do serializer por
allowlist. Login deixa de distinguir "email inexistente" de "senha errada". → `RP-05` + `RP-14`

---

### #4 [CRITICAL] Hardcoded Secrets (AP-01)

**File:** `app.py:7-8`

**Description:** `SECRET_KEY` está literal no código e `DEBUG` está fixo em `True`, inclusive na
chamada `app.run(debug=True)`. Com debug ligado, o Werkzeug expõe um console interativo na página de
traceback — execução remota de código a partir de qualquer exceção não tratada.

**Evidence:**
```python
app.config["SECRET_KEY"] = "minha-chave-super-secreta-123"
app.config["DEBUG"] = True
```

**Occurrences:** `app.py:7`, `app.py:8`, `app.py:88` (`debug=True` no `app.run`), `database.py:5`
(`db_path` fixo — não é secret, mas é config no lugar errado)

**Impact:** A `SECRET_KEY` assina sessões e qualquer token derivado; conhecida, permite forjá-los. O
valor está no histórico do git desde o commit inicial, então removê-lo do código não o revoga.

**Recommendation:** Extrair para um módulo `config/settings.py` lendo variáveis de ambiente, com
falha explícita na ausência de `SECRET_KEY` e `DEBUG` default `false`. Commitar `.env.example`. →
`RP-01`

---

### #5 [CRITICAL] Secret Exposed in API Response (AP-01)

**File:** `controllers.py:285-289`

**Description:** O endpoint `GET /health`, público e sem autenticação, devolve no corpo da resposta a
`secret_key`, o flag de debug, o caminho do banco e um campo `ambiente: "producao"`.

**Evidence:**
```python
"ambiente": "producao",
"db_path": "loja.db",
"debug": True,
"secret_key": "minha-chave-super-secreta-123"
```

**Impact:** Um health check é justamente o endpoint que monitoração externa consulta sem credencial e
que costuma ser exposto publicamente. Ele entrega a chave de assinatura da aplicação em uma requisição
`GET`.

**Recommendation:** Reduzir `/health` a status e conectividade do banco. Nenhum dado de configuração
no payload. → `RP-14`

---

### #6 [CRITICAL] God Module (AP-04)

**File:** `models.py:1-314`

**Description:** `models.py` concentra responsabilidades de três camadas para quatro domínios
distintos (produtos, usuários, pedidos, relatórios): acesso a dados (as 18 queries), regra de negócio
(cálculo de total do pedido, validação de estoque, faixas de desconto do relatório) e formatação de
resposta da API (oito dicionários montados campo a campo). `app.py` reforça o padrão ao definir dois
handlers com cursor próprio, em vez de apenas compor a aplicação.

**Evidence:**
```python
desconto = 0
if faturamento > 10000:
    desconto = faturamento * 0.1
elif faturamento > 5000:
    desconto = faturamento * 0.05
```

**Occurrences:** `models.py:1-314` (módulo inteiro), `models.py:235-273` (regra de desconto na camada
de dados), `models.py:133-169` (regra de pedido), `app.py:47-78` (handlers com acesso direto ao banco
no entry point)

**Impact:** Nenhuma regra de negócio pode ser exercitada sem banco e sem Flask. A faixa de desconto,
que é a regra mais volátil do sistema, está soterrada entre `cursor.execute` e montagem de payload —
mudá-la exige tocar no arquivo que também contém autenticação e criação de pedidos.

**Recommendation:** Separar em `models/` por entidade (só dados), `controllers/` por domínio
(orquestração), `serializers/` (payload) e mover a regra de desconto para o model de pedidos. →
`RP-04` + `RP-06`

---

### #7 [HIGH] Business Logic & Side Effects in the Controller (AP-06)

**File:** `controllers.py:208-210`

**Description:** `criar_pedido` dispara três notificações (email, SMS, push) inline no handler, como
`print`. `atualizar_status_pedido` faz o mesmo condicionalmente por status. São efeitos colaterais de
negócio codificados no controller, sem serviço, sem tratamento de falha e sem possibilidade de
desligar.

**Evidence:**
```python
print("ENVIANDO EMAIL: Pedido " + str(resultado["pedido_id"]) + " criado para usuario " + str(usuario_id))
print("ENVIANDO SMS: Seu pedido foi recebido!")
print("ENVIANDO PUSH: Novo pedido recebido pelo sistema")
```

**Occurrences:** `controllers.py:208-210`, `controllers.py:247-250`

**Impact:** A notificação de pedido — requisito de negócio — não existe de fato, e o `print` esconde
isso: o sistema parece notificar e não notifica. Quando for implementada de verdade, será dentro do
handler HTTP, sem retry e bloqueando a resposta.

**Recommendation:** Extrair para um `NotificationService` injetado no controller, com interface
explícita. O controller chama; o serviço decide como entregar. → `RP-06`

---

### #8 [HIGH] Mutable Global Connection (AP-07)

**File:** `database.py:4-10`

**Description:** A conexão SQLite é um global de módulo, preenchido preguiçosamente e compartilhado
por todas as requisições, com `check_same_thread=False` para silenciar a proteção do driver. O
`get_db()` também cria schema e insere seeds na primeira chamada, misturando bootstrap com obtenção
de conexão.

**Evidence:**
```python
db_connection = None
db_path = "loja.db"

def get_db():
    global db_connection
    if db_connection is None:
        db_connection = sqlite3.connect(db_path, check_same_thread=False)
```

**Occurrences:** `database.py:4-10` (global + flag), `database.py:12-84` (schema e seed dentro do
getter)

**Impact:** `check_same_thread=False` não torna a conexão thread-safe — apenas remove o aviso. O
servidor Flask atende requisições em threads, então cursores concorrentes compartilham a mesma
conexão e a mesma transação implícita: um `commit` de uma requisição persiste o trabalho parcial de
outra. Não há como resetar o estado entre testes.

**Recommendation:** Factory de conexão por requisição via `flask.g` com `teardown_appcontext`, e
bootstrap de schema movido para fora do getter, executado explicitamente na composição. → `RP-07`

---

### #9 [HIGH] No Transaction Boundary & Missing Referential Integrity (AP-11)

**File:** `models.py:133-169`

**Description:** `criar_pedido` faz de 3 a 3+2N escritas (pedido, itens, baixa de estoque) sem
`BEGIN`/`ROLLBACK`, com um único `commit` no fim — mas uma exceção no meio deixa o que já foi
executado pendente na conexão global, que outra requisição pode commitar. A validação de estoque
acontece em um loop separado, antes das escritas: entre a leitura e o `UPDATE ... estoque - N` existe
uma janela de corrida que permite vender estoque inexistente. O schema não declara nenhuma foreign
key.

**Evidence:**
```python
cursor.execute(
    "UPDATE produtos SET estoque = estoque - " + str(item["quantidade"]) +
    " WHERE id = " + str(item["produto_id"])
)
```

**Occurrences:** `models.py:133-169` (use case sem transação), `models.py:139-146` (leitura de
estoque separada da escrita), `database.py:14-53` (schema sem `FOREIGN KEY` e sem
`PRAGMA foreign_keys`)

**Impact:** Estoque fica negativo sob concorrência, e pedidos podem ficar sem itens ou com baixa de
estoque parcial. Como `itens_pedido.produto_id` não é FK, apagar um produto deixa itens órfãos
apontando para nada — e `DELETE /produtos/<id>` faz exatamente isso, sem checagem.

**Recommendation:** Envolver o use case em transação explícita com rollback, trocar a baixa de estoque
por `UPDATE ... WHERE id = ? AND estoque >= ?` verificando `rowcount`, e declarar as foreign keys com
política de `ON DELETE`. → `RP-10`

---

### #10 [HIGH] Swallowed Exceptions & Duplicated Error Handling (AP-10)

**File:** `controllers.py:10-12`

**Description:** Os 14 handlers de `controllers.py` repetem o mesmo bloco
`try / except Exception as e: return jsonify({"erro": str(e)}), 500`. Não há distinção entre erro de
validação, recurso inexistente e falha de infraestrutura, não há log estruturado, e a mensagem da
exceção vai para o cliente.

**Evidence:**
```python
except Exception as e:
    print("ERRO: " + str(e))
    return jsonify({"erro": str(e)}), 500
```

**Occurrences:** `controllers.py:10`, `:21`, `:60`, `:95`, `:108`, `:125`, `:133`, `:143`, `:164`,
`:185`, `:218`, `:226`, `:234`, `:254`, `:261`, `:291`

**Impact:** `str(e)` de um erro de SQLite devolve o texto da query ao cliente, o que entrega a
estrutura do banco a um atacante e complementa o vetor de injeção do finding #2. Do lado da operação,
um banco fora do ar e um campo malformado produzem a mesma resposta, tornando o diagnóstico
impossível.

**Recommendation:** Tipos de erro de domínio (`NotFoundError`, `ValidationError`, …) levantados pelas
camadas internas e um `errorhandler` central que mapeia para status code, loga a stack e devolve
mensagem genérica ao cliente. Remover os 16 blocos. → `RP-09`

---

### #11 [MEDIUM] N+1 Queries (AP-12)

**File:** `models.py:171-201`

**Description:** `get_pedidos_usuario` e `get_todos_pedidos` executam uma query para listar pedidos,
outra por pedido para buscar os itens, e mais uma por item para buscar o nome do produto — 1 + N + N×M
round trips para dados que um único `JOIN` resolve. `relatorio_vendas` faz cinco `COUNT` separados
onde um `GROUP BY` bastaria.

**Evidence:**
```python
cursor2.execute("SELECT * FROM itens_pedido WHERE pedido_id = " + str(row["id"]))
itens = cursor2.fetchall()
for item in itens:
    cursor3.execute("SELECT nome FROM produtos WHERE id = " + str(item["produto_id"]))
```

**Occurrences:** `models.py:171-201`, `models.py:203-233`, `models.py:239-254` (cinco counts
sequenciais), `models.py:155` (re-busca o preço de um produto já carregado no loop anterior)

**Impact:** `GET /pedidos` com 100 pedidos de 5 itens dispara 601 queries. Com os 10 produtos e 0
pedidos do seed o problema é invisível; ele aparece exatamente quando a aplicação passa a ter uso
real.

**Recommendation:** Uma query com `LEFT JOIN` entre `pedidos`, `itens_pedido` e `produtos`, agrupando
as linhas em memória; e um `GROUP BY status` no lugar dos cinco counts. → `RP-11`

---

### #12 [MEDIUM] Duplicated Validation (AP-13)

**File:** `controllers.py:28-54`

**Description:** `criar_produto` e `atualizar_produto` repetem o mesmo bloco de validação — presença
de `nome`/`preco`/`estoque`, faixas negativas, limites de comprimento. A cópia em `atualizar_produto`
já divergiu: perdeu a checagem de comprimento do nome e a validação de categoria contra a allowlist.

**Evidence:**
```python
if preco < 0:
    return jsonify({"erro": "Preço não pode ser negativo"}), 400
if estoque < 0:
    return jsonify({"erro": "Estoque não pode ser negativo"}), 400
```

**Occurrences:** `controllers.py:28-54` (create), `controllers.py:72-90` (update, já divergente)

**Impact:** A divergência é o bug: `POST /produtos` recusa categoria inválida e nome de 300
caracteres, `PUT /produtos/<id>` aceita ambos. A mesma entidade tem duas regras de validação
diferentes conforme o verbo HTTP.

**Recommendation:** Um validador único por entidade, com modo `partial` para update, levantando
`ValidationError`. → `RP-12`

---

### #13 [MEDIUM] Missing Input Validation (AP-14)

**File:** `controllers.py:118-121`

**Description:** Vários pontos consomem entrada externa sem guarda de tipo. `buscar_produtos` chama
`float()` direto sobre a query string; `criar_pedido` itera `itens` acessando `item["produto_id"]` e
`item["quantidade"]` sem verificar que os itens são dicionários com essas chaves; `criar_usuario` não
valida formato de email nem força de senha, e não trata email duplicado.

**Evidence:**
```python
if preco_min:
    preco_min = float(preco_min)
```

**Occurrences:** `controllers.py:118-121` (`float()` sem guarda), `controllers.py:195-201`
(estrutura de `itens` não validada), `controllers.py:146-165` (email e senha sem formato nem
unicidade), `models.py:139-146` (acesso a chaves do item sem checagem)

**Impact:** `GET /produtos/busca?preco_min=abc` devolve 500 em vez de 400. `POST /pedidos` com
`{"itens": ["x"]}` levanta `TypeError` dentro da camada de dados. Emails duplicados entram sem
constraint, porque a coluna também não é `UNIQUE`.

**Recommendation:** Validação por schema na fronteira, com coerção de tipo antes de qualquer
comparação, e `UNIQUE` na coluna `email`. → `RP-12`

---

### #14 [MEDIUM] Manual Serialization (AP-16)

**File:** `models.py:12-21`

**Description:** A conversão de linha do banco para payload da API é feita campo a campo, à mão, em
oito lugares — dentro da camada de dados. O mesmo objeto é serializado de formas diferentes conforme
a função: `get_todos_usuarios` e `get_usuario_por_id` incluem `senha`, `login_usuario` não.

**Evidence:**
```python
result.append({
    "id": row["id"],
    "nome": row["nome"],
    "descricao": row["descricao"],
    ...
})
```

**Occurrences:** `models.py:12-21`, `:31-40`, `:79-86`, `:95-102`, `:114-119`, `:178-185`,
`:194-199`, `:211-218`, `:226-231`, `:304-313`

**Impact:** Não existe um lugar único que defina o contrato da API, então ele diverge sozinho — é
exatamente por isso que a senha vaza em dois endpoints e não em um terceiro. Adicionar um campo a
produto exige editar quatro funções.

**Recommendation:** Uma camada `serializers/` por entidade, com allowlist de campos públicos, usada
por todos os controllers. Models passam a devolver linhas/objetos de domínio. → `RP-14`

---

### #15 [MEDIUM] Ad-hoc Logging (AP-17)

**File:** `controllers.py:8`

**Description:** Não há configuração de logging no projeto. Eventos de negócio, erros e diagnóstico
saem todos por `print`, no mesmo nível, sem timestamp, sem severidade e sem contexto estruturado.

**Evidence:**
```python
print("Listando " + str(len(produtos)) + " produtos")
```

**Occurrences:** `controllers.py:8`, `:11`, `:57`, `:61`, `:106`, `:161`, `:179`, `:182`, `:208-210`,
`:219`, `:248`, `:250`, `app.py:56`, `app.py:83-86`

**Impact:** Impossível ajustar verbosidade em produção ou filtrar por severidade. `controllers.py:179`
e `:182` registram tentativas de login com o email em texto puro, sem nível `WARNING` e sem
rate limit — um log de auditoria acidental que ninguém consegue consultar.

**Recommendation:** Logger configurado no módulo de middlewares, com nível vindo da config, e
`logger.exception` dentro dos handlers de erro. → `RP-15`

---

### #16 [MEDIUM] Insecure Middleware & Framework Configuration (AP-23)

**File:** `app.py:9`

**Description:** `CORS(app)` sem argumentos habilita `Access-Control-Allow-Origin: *` para todas as
rotas, incluindo `/login`, `/usuarios` e as duas rotas administrativas.

**Evidence:**
```python
CORS(app)
```

**Impact:** Qualquer site na internet pode fazer requisições à API a partir do browser da vítima e ler
a resposta. Combinado com o finding #3, uma página maliciosa consegue extrair a lista de usuários com
senhas via `fetch`.

**Recommendation:** Restringir origens por configuração (`CORS(app, origins=settings.cors_origins)`),
com default restritivo. → `RP-18`

> **Nota de calibração da skill:** no momento em que este relatório foi gerado, o achado não
> correspondia a nenhuma entrada do catálogo — foi identificado por julgamento, não por detection
> signal. A lacuna foi fechada em seguida com a criação de `AP-23 — Insecure Middleware & Framework
> Configuration` e `RP-18 — Harden Middleware Configuration`. A classificação acima já reflete o
> catálogo atualizado. Ver "Observação sobre a skill" no fim deste relatório.

---

### #17 [LOW] Magic Numbers & Magic Strings (AP-19)

**File:** `models.py:256-262`

**Description:** Limiares e percentuais de desconto, faixas de validação e o conjunto de status de
pedido aparecem como literais inline, repetidos entre módulos.

**Evidence:**
```python
if faturamento > 10000:
    desconto = faturamento * 0.1
elif faturamento > 5000:
    desconto = faturamento * 0.05
```

**Occurrences:** `models.py:256-262` (faixas de desconto), `controllers.py:47-52` (limites de nome e
lista de categorias), `controllers.py:242` (lista de status), `models.py:150` (`'pendente'` literal),
`database.py:32` e `:40` (defaults duplicando as mesmas strings)

**Impact:** A lista de status válidos existe em dois lugares (`controllers.py:242` e o `DEFAULT` do
schema) e as categorias em um só, sem constraint no banco — mudar qualquer uma exige encontrar todas
as cópias.

**Recommendation:** `StrEnum` para status e categorias, e as faixas de desconto como estrutura de
dados nomeada junto do model de pedidos. → `RP-16`

---

### #18 [LOW] Dead Code & Unused Imports (AP-21)

**File:** `models.py:2`

**Description:** Imports declarados e nunca referenciados.

**Evidence:**
```python
from database import get_db
import sqlite3
```

**Occurrences:** `models.py:2` (`sqlite3` não usado — o módulo nunca toca no driver diretamente),
`database.py:2` (`os` não usado), `app.py:1` (`request` usado apenas pelo handler admin, que sai do
entry point na refatoração)

**Recommendation:** Remover. → `RP-17`

---

### #19 [LOW] Inconsistent Response Shape & Status Codes (AP-22)

**File:** `controllers.py:9`

**Description:** O envelope de resposta varia entre endpoints. A maioria devolve
`{"dados": ..., "sucesso": true}`, mas `GET /` devolve um objeto plano, `GET /health` usa `status`, e
`buscar_produtos` acrescenta `total` que os outros list endpoints não têm. As chaves misturam
português e inglês (`dados`, `sucesso`, `erro` ao lado de `status`, `database`, `counts`).

**Evidence:**
```python
return jsonify({"dados": produtos, "sucesso": True}), 200
```

**Occurrences:** `controllers.py:9` e demais (envelope padrão), `controllers.py:124` (campo `total`
extra), `controllers.py:276-290` (`/health` com forma própria), `app.py:34-45` (`/` sem envelope)

**Impact:** Cliente não consegue tratar respostas genericamente; cada endpoint exige código próprio de
desempacotamento.

**Recommendation:** Um envelope único definido no serializer e um único formato de erro vindo do
handler central. Qualquer mudança aqui é mudança de contrato e deve ser listada. → `RP-14` + `RP-09`

---

## Deprecated APIs

Nenhuma API deprecated detectada para Flask 3.1.1 / Werkzeug 3.1.8 / Python 3.12.13.

Verificação realizada em quatro frentes, conforme o catálogo:

1. **Boot com warnings habilitados** — `PYTHONWARNINGS=always python -W all` importando `app`:
   nenhum `DeprecationWarning` emitido.
2. **Grep do registry Python** — `utcnow`, `utcfromtimestamp`, `before_first_request`, `flask.escape`,
   `flask.Markup`, `JSONEncoder`, `url_quote`, `distutils`, `imp`, `pkg_resources`,
   `get_event_loop`, `SQLALCHEMY_TRACK_MODIFICATIONS`: nenhuma ocorrência.
3. **Versões resolvidas vs. changelog** — Flask 3.1.1 e Werkzeug 3.1.8 são as versões declaradas em
   `requirements.txt` e as instaladas em `venv/`; nenhuma API removida em 3.x está em uso.
4. **Dependências deprecated** — `flask-cors 5.0.1` é mantido; nenhuma dependência abandonada.

**Runtime warnings capturadas no boot:**
```text
nenhuma
```

> O projeto usa `sqlite3` com a API síncrona da stdlib, que não é deprecated. O
> `check_same_thread=False` do finding #8 é uma flag desaconselhada, não uma API deprecated — está
> classificado como AP-07, não AP-15.

---

## Refactoring Plan Preview

```text
src/
├── config/
│   └── settings.py              # SECRET_KEY, DEBUG, DB_PATH, ADMIN_QUERY_ENABLED, CORS_ORIGINS
├── infra/
│   ├── database.py              # factory de conexão por request (flask.g)
│   └── schema.py                # DDL + FKs, executado na composição
├── models/
│   ├── produto_model.py
│   ├── usuario_model.py
│   └── pedido_model.py          # total, estoque, faixas de desconto
├── controllers/
│   ├── produto_controller.py
│   ├── usuario_controller.py
│   ├── pedido_controller.py
│   ├── relatorio_controller.py
│   └── admin_controller.py      # rotas administrativas atrás de feature flag
├── serializers/
│   ├── produto_serializer.py
│   ├── usuario_serializer.py    # allowlist — sem `senha`
│   └── pedido_serializer.py
├── services/
│   └── notification_service.py
├── schemas/
│   └── validators.py
├── middlewares/
│   ├── error_handler.py         # tipos de erro de domínio + handler central
│   └── logging.py
└── app.py                       # create_app(): composition root
```

| # | Step | Findings resolvidos |
| --- | --- | --- |
| 1 | Config extraction + `.env.example` | #4, #16 |
| 2 | Data access: factory por request, SQL parametrizado, schema com FKs | #2, #8, #9 |
| 3 | Models por entidade, regras de negócio movidas para o domínio | #6, #9, #11, #17 |
| 4 | Controllers finos + service de notificação | #6, #7 |
| 5 | Views/routes: binding puro, rotas admin gated | #1, #6 |
| 6 | Serializers com allowlist | #3, #5, #14, #19 |
| 7 | Middlewares: erro central + logging | #10, #15, #19 |
| 8 | Composition root + limpeza | #18 |
| 9 | Hash de senha | #3 |
| 10 | Validação consolidada | #12, #13 |

**Contract preservation:** os 19 endpoints originais continuam existindo, com os mesmos métodos,
paths e status codes.

**Intentional behaviour changes:**

- `GET /usuarios` e `GET /usuarios/<id>` — o campo `senha` deixa de constar no payload (finding #3).
- `GET /health` — os campos `secret_key`, `debug`, `db_path` e `ambiente` deixam de constar; `status`
  e `database` permanecem (finding #5).
- `POST /admin/query` e `POST /admin/reset-db` — respondem `403` enquanto `ADMIN_QUERY_ENABLED=false`
  (default). Com a flag ligada, o comportamento original é preservado (finding #1).
- `POST /login` — passa a exigir senha com hash. As senhas do seed são re-geradas com hash; senhas
  gravadas antes da refatoração deixam de autenticar (finding #3).
- `PUT /produtos/<id>` — passa a aplicar as mesmas validações de `POST /produtos`, que hoje faltam:
  comprimento do nome e allowlist de categoria. Payloads que hoje são aceitos indevidamente passarão a
  retornar `400` (finding #12).
- `GET /produtos/busca?preco_min=<não-numérico>` — passa a retornar `400` em vez de `500` (finding #13).
- Respostas de erro deixam de conter `str(e)` e passam a devolver mensagem genérica (finding #10).

---

## Accepted / Out of Scope

- **`database.py:56-84` (dados de seed)** — os seeds em si são fixtures de desenvolvimento, não código
  de produção. As senhas em plaintext que eles inserem estão cobertas pelo finding #3; o mecanismo de
  seed não é finding, mas será movido para fora do getter de conexão como parte do passo 2.
- **Nomenclatura em português do domínio** — `produtos`, `criar_pedido`, `faturamento`. É a linguagem
  do domínio e será preservada; traduzir seria churn sem ganho.
- **Ausência de testes automatizados** — real, mas fora do escopo desta skill, que refatora o que
  existe. Registrado abaixo.
- **Ausência de autenticação nas rotas de leitura** — `GET /usuarios` e `GET /pedidos` são públicos.
  Introduzir um sistema de auth é feature nova, não refatoração; o vazamento de senha é resolvido pelo
  finding #3, mas a exposição da listagem permanece.

---

## Post-Refactoring Actions (fora do escopo da skill)

1. **Revogar a `SECRET_KEY` vazada.** Ela está no histórico do git desde `6d1ce62`; removê-la do código
   não a remove do histórico. Gerar uma nova e nunca reutilizar a antiga.
2. **Forçar reset de senha de todos os usuários.** As senhas foram armazenadas em plaintext e devem ser
   consideradas comprometidas — o hash aplicado na refatoração protege o que vier depois, não o que já
   vazou.
3. **Adicionar autenticação e autorização.** As rotas administrativas ficam atrás de feature flag, o
   que fecha o vetor imediato, mas não substitui auth. `GET /usuarios` continua público.
4. **Cobrir com testes.** A refatoração torna as regras testáveis pela primeira vez; a suíte é o passo
   seguinte natural, começando por desconto, estoque e login.
5. **Adicionar `UNIQUE` em `usuarios.email`** com migração dos dados existentes.

---

Total: 19 findings

---

## Refactoring Result

Fase 3 executada e aprovada pelo gate humano em 2026-08-08.

### Estrutura resultante

```text
code-smells-project/
├── .env.example
├── app.py                            # entry point — mantém `python app.py`
└── src/
    ├── app.py                        # composition root: create_app()
    ├── config/settings.py
    ├── domain/
    │   ├── constants.py              # StrEnum de status, faixas de desconto
    │   └── errors.py                 # DomainError e subtipos
    ├── infra/
    │   ├── database.py               # conexão por request via flask.g
    │   ├── schema.py                 # DDL com FKs + seed explícito
    │   └── security.py               # hash de senha (werkzeug)
    ├── models/
    │   ├── produto_model.py
    │   ├── usuario_model.py
    │   ├── pedido_model.py           # transação, reserva de estoque, relatório
    │   └── admin_model.py
    ├── controllers/
    │   ├── produto_controller.py
    │   ├── usuario_controller.py
    │   ├── pedido_controller.py
    │   ├── relatorio_controller.py
    │   ├── admin_controller.py
    │   └── sistema_controller.py
    ├── views/routes.py               # 19 endpoints: método + path -> controller
    ├── serializers/
    │   ├── produto_serializer.py
    │   ├── usuario_serializer.py     # allowlist — `senha` fora do payload
    │   ├── pedido_serializer.py
    │   └── response.py
    ├── schemas/validators.py
    ├── services/notification_service.py
    └── middlewares/
        ├── error_handler.py
        └── logging.py
```

Arquivos removidos: `controllers.py`, `models.py`, `database.py`. 780 linhas em 4 arquivos deram
lugar a 1.357 linhas em 30 arquivos — o aumento é o custo da separação de camadas e dos docstrings
que registram cada decisão.

### Findings resolvidos: 18 completos, 1 parcial

| Severidade | Resolvidos |
| --- | --- |
| CRITICAL | 6/6 |
| HIGH | 4/4 |
| MEDIUM | 6/6 |
| LOW | 2/3 (+1 parcial) |

O finding #19 (envelope de resposta inconsistente) foi resolvido apenas na parte de erro, que agora
tem forma única vinda do handler central. As respostas de sucesso mantêm mais de uma forma — `ok()`
para respostas com dados, `mensagem()` para comandos, e `/` e `/health` com formato próprio — porque
unificá-las quebraria o contrato dos endpoints. A padronização completa exige uma versão nova da API.

### Verificação dos detection signals na árvore refatorada

| Signal | Resultado |
| --- | --- |
| Secrets hardcoded | limpo |
| SQL por concatenação / f-string com valor externo | limpo |
| Campo `senha` em serializer | limpo |
| `global` mutável / `check_same_thread` | limpo |
| `except:` mudo / `str(e)` na resposta | limpo |
| APIs deprecated do registry | limpo |
| `print()` como log | limpo |
| Models/serializers importando Flask | limpo |
| Routes acessando models | limpo |
| Controllers escrevendo SQL | limpo |

Três interpolações em query permanecem (`f"SELECT {CAMPOS} FROM ..."` e `f"DELETE FROM {tabela}"`).
Em todas, o valor interpolado é constante do código — `CAMPOS` é constante de módulo e `tabela` itera
uma tupla literal. Identificadores não podem ser parametrizados por placeholder; o `RP-02` cobre
exatamente esse caso exigindo allowlist literal, que é o que está em uso. Nenhuma entrada externa
alcança esses pontos.

### Validação de comportamento

Baseline capturado **antes** da primeira edição, com 38 probes cobrindo os 19 endpoints mais caminhos
de erro (404, 400, 401, payload inválido, coerção de tipo, estoque insuficiente).

```text
✓ Application boots without errors        (nenhum warning, nenhum traceback)
✓ 19/19 endpoints originais respondem     (mesmos métodos e paths)
✓ 19/38 probes com status e body idênticos
✓ 19/38 probes alterados — todos rastreados a um finding, nenhuma mudança não intencional
✓ Zero anti-patterns remanescentes da auditoria
```

Detalhe dos 19 probes alterados:

| Mudança | Probes | Finding |
| --- | --- | --- |
| `"sucesso": false` acrescentado ao envelope de erro | 10 | #19 |
| Rotas admin respondendo 403 (flag desligada) | 3 | #1 |
| `GET /produtos` após reset bloqueado devolve o catálogo | 1 | #1 (consequência) |
| Campo `senha` removido do payload | 2 | #3 |
| `/health` sem `secret_key`, `debug`, `db_path`, `ambiente` | 1 | #5 |
| `preco_min` não numérico: 500 → 400 | 1 | #13 |
| `DELETE /produtos/1` referenciado por pedido: 200 → 409 | 1 | #9 |
| Item de pedido preserva `produto_nome` em vez de virar `"Desconhecido"` | 1 | #9 (consequência) |

As rotas administrativas foram validadas em uma segunda execução com
`ADMIN_ENDPOINTS_ENABLED=true`: `POST /admin/query` e `POST /admin/reset-db` reproduzem exatamente o
comportamento original, confirmando que a rota foi neutralizada por configuração e não removida.

O login com as credenciais de seed (`admin@loja.com` / `admin123`) continua retornando `200` com o
mesmo payload, o que confirma que a troca de plaintext por hash preservou o fluxo de autenticação.

### Observação sobre a skill — lacuna encontrada e fechada

Esta execução expôs um ponto cego do catálogo. O finding #16 (CORS permissivo) foi identificado por
julgamento, não por detection signal: misconfiguração de segurança em middleware não estava coberta
por AP-01..AP-22. Numa sessão limpa, sem esse julgamento, o achado provavelmente escaparia.

A lacuna foi fechada antes de executar nos projetos 2 e 3:

- **`AP-23 — Insecure Middleware & Framework Configuration`** (MEDIUM, escalando para HIGH/CRITICAL)
  cobre CORS irrestrito ou refletido, wildcard combinado com credentials, debug mode em produção,
  cookies de sessão sem `Secure`/`HttpOnly`/`SameSite`, ausência de security headers, body sem limite
  de tamanho, host allowlist aberta, bind em `0.0.0.0` sem autenticação, verificação de TLS desligada
  e ausência de rate limit em endpoints de autenticação.
- **`RP-18 — Harden Middleware Configuration`** traz o antes/depois em Flask e Express, com a regra de
  verificar pelo header na resposta (`curl -I`) e não pelo código — um header que se acredita estar
  setado e não está é pior que um ausente.

### Delta residual de AP-23 neste projeto

O catálogo foi ampliado **depois** que a Fase 3 deste projeto rodou, e os sinais novos não foram
aplicados retroativamente. Sobre a árvore refatorada, AP-23 hoje ainda apontaria:

| Sinal | Estado |
| --- | --- |
| CORS com origem irrestrita | resolvido — origens vêm da config, default restritivo |
| Debug mode ligado | resolvido — vem da config, default `false` |
| Bind em `0.0.0.0` sem auth | resolvido — default `127.0.0.1` |
| Cookies de sessão sem flags | não se aplica — a API não usa sessão nem cookie |
| Security headers ausentes | **pendente** — não há `X-Content-Type-Options`, `X-Frame-Options` nem `Referrer-Policy` |
| Body sem limite de tamanho | **pendente** — `MAX_CONTENT_LENGTH` não definido |
| Rate limit em `/login` | **pendente** — ausente |

Os três pendentes são de baixo risco de regressão e cabem em poucas linhas no composition root, mas
exigiriam nova rodada de validação contra o baseline. Ficam registrados aqui como decisão consciente,
não como omissão.
