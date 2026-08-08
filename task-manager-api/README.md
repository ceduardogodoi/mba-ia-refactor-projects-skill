# task-manager-api

API de Task Manager em Python/Flask — tarefas com responsável, categoria, prioridade, prazo e tags,
mais relatórios de produtividade por usuário.

Este projeto foi entrada do desafio `refactor-arch` e passou pelas três fases da skill. Diferente dos
outros dois, ele já chegou com alguma separação de pastas — e a auditoria mostrou que ela era nominal:
as rotas faziam o trabalho de controller, model e serializer ao mesmo tempo, enquanto `services/` e
`utils/` somavam 164 linhas que nunca eram executadas. O relatório está em
[`../reports/audit-project-3.md`](../reports/audit-project-3.md).

## Como rodar

```bash
pip install -r requirements.txt
cp .env.example .env      # obrigatório: a aplicação não sobe sem SECRET_KEY
python seed.py            # popula o banco — rode antes do primeiro boot
python app.py
```

A aplicação sobe em `http://127.0.0.1:5000`. Sem o `seed.py`, os endpoints respondem listas vazias.

Credenciais de seed: `joao@email.com` / `1234` (admin), `maria@email.com` / `abcd`,
`pedro@email.com` / `pass`.

## Configuração

Toda configuração vem de variáveis de ambiente. Veja `.env.example` para a lista completa.

- **`SECRET_KEY`** é obrigatória e não tem default. A aplicação falha na inicialização se ela estiver
  ausente — um default de secret é a mesma vulnerabilidade com passos a mais.
- **`DEBUG`** default `false`. O modo debug do Werkzeug expõe um console interativo na página de
  traceback.
- **`NOTIFICATIONS_ENABLED`** default `false`. O `NotificationService` existia no projeto original mas
  nunca era instanciado; ligá-lo faz a aplicação abrir conexões SMTP dentro do request path.

## Estrutura

```text
app.py                     entry point — carrega config e expõe `app` para WSGI
seed.py                    dados iniciais
src/
├── app.py                 composition root: create_app()
├── config/                única porta de entrada de configuração
├── domain/                constantes e erros de domínio
├── infra/                 sessão, utc_now(), PRAGMA foreign_keys, hash de senha
├── models/                dados e regras por entidade
├── repositories/          queries (API 2.0 do SQLAlchemy) e agregações
├── controllers/           use cases
├── views/routes.py        método + path -> controller
├── serializers/           contrato externo, com allowlist de campos
├── schemas/               validação de entrada
├── services/              notificações, com colaboradores injetados
└── middlewares/           erro central, logging, security headers
```

A direção de dependência é única: `routes → controllers → repositories → models → infra`. Models,
repositories e serializers não importam Flask; routes não acessam repositories; controllers não
escrevem query.

## Endpoints

Os 22 endpoints originais foram preservados, com os mesmos métodos e paths.

| Método | Path | Descrição |
| --- | --- | --- |
| `GET` | `/` | Índice da API |
| `GET` | `/health` | Status |
| `GET` | `/tasks` | Lista tasks com nome de usuário e categoria |
| `POST` | `/tasks` | Cria task |
| `GET` | `/tasks/search` | Busca por `q`, `status`, `priority`, `user_id` |
| `GET` | `/tasks/stats` | Contagens e taxa de conclusão |
| `GET` | `/tasks/<id>` | Detalhe da task |
| `PUT` | `/tasks/<id>` | Atualiza task |
| `DELETE` | `/tasks/<id>` | Remove task |
| `GET` | `/users` | Lista usuários com total de tasks |
| `POST` | `/users` | Cria usuário |
| `GET` | `/users/<id>` | Detalhe do usuário com suas tasks |
| `PUT` | `/users/<id>` | Atualiza usuário |
| `DELETE` | `/users/<id>` | Remove usuário e suas tasks |
| `GET` | `/users/<id>/tasks` | Tasks de um usuário |
| `POST` | `/login` | Autentica |
| `GET` | `/reports/summary` | Relatório geral |
| `GET` | `/reports/user/<id>` | Relatório por usuário |
| `GET` | `/categories` | Lista categorias com total de tasks |
| `POST` | `/categories` | Cria categoria |
| `PUT` | `/categories/<id>` | Atualiza categoria |
| `DELETE` | `/categories/<id>` | Remove categoria |

## Mudanças de comportamento intencionais

Cada uma exigida por um finding da auditoria:

- `GET /users/<id>`, `POST /users`, `PUT /users/<id>` e `POST /login` não retornam mais o campo
  `password`. O hash era MD5 sem salt: o valor exposto por `GET /users/1` era
  `81dc9bdb52d04dc20036dbd8313ed055`, o MD5 de `1234`, quebrável por rainbow table.
- `POST /login` não retorna mais `token`. Ele era `fake-jwt-token-<id>`, derivável do id do usuário —
  melhor não existir do que fingir existir enquanto não houver autenticação real.
- Senhas passaram a usar pbkdf2 com salt. Os hashes MD5 anteriores não autenticam mais.
- `POST /tasks`, `PUT /tasks/<id>` e `GET /tasks/search` com `priority` ou `user_id` não numérico
  respondem `400` em vez de `500`. A validação comparava faixa antes de garantir tipo.
- `GET /tasks/<id>` passou a incluir `user_name` e `category_name`, alinhando-se ao `GET /tasks` —
  antes os dois endpoints devolviam formatos diferentes para a mesma entidade.
- Erros inesperados respondem JSON `{"error": "Erro interno"}` em vez de página HTML de 500, e o
  detalhe da exceção vai para o log.
- O servidor escuta em `127.0.0.1` por default, e `DEBUG` vem da config com default `false`.
- Integridade referencial passou a ser aplicada pelo banco (`PRAGMA foreign_keys = ON`). Antes o
  SQLite aceitava qualquer FK inexistente vinda de escrita fora do ORM.

## Pendências fora do escopo da refatoração

- A `SECRET_KEY` e as credenciais de SMTP estão no histórico do git e precisam ser revogadas.
- As senhas MD5 devem ser tratadas como comprometidas — os hashes foram expostos publicamente por
  `GET /users`. Reset obrigatório.
- Não há autenticação: todos os 22 endpoints são públicos, incluindo `DELETE /users/<id>`.
- `users.email` ainda não tem constraint `UNIQUE` — a unicidade é verificada em aplicação.
- O `NotificationService` está desligado por configuração. Ligá-lo exige decidir sobre envio
  assíncrono.
- Não há testes automatizados.
- Datetimes são UTC *naive*. A forma canônica é timezone-aware, mas o SQLite não tem tipo com
  timezone e devolve valores naive mesmo com `DateTime(timezone=True)` — migrar exige um banco com
  suporte real.
