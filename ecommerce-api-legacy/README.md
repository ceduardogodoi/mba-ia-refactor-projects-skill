# ecommerce-api-legacy

LMS API em Node.js/Express — checkout de matrícula com cobrança, relatório financeiro administrativo
e remoção de usuários.

Este projeto foi entrada do desafio `refactor-arch` e passou pelas três fases da skill: análise,
auditoria e refatoração para MVC. O relatório da auditoria está em
[`../reports/audit-project-2.md`](../reports/audit-project-2.md).

## Como rodar

```bash
npm install
cp .env.example .env      # obrigatório: a aplicação não sobe sem PAYMENT_GATEWAY_KEY
npm start
```

A aplicação sobe em `http://127.0.0.1:3000`. O banco SQLite é em memória por padrão e carrega o seed
automaticamente no boot. Exemplos de requisições estão em `api.http`.

## Configuração

Toda configuração vem de variáveis de ambiente. Veja `.env.example` para a lista completa. Três
merecem atenção:

- **`PAYMENT_GATEWAY_KEY`** é obrigatória e não tem default. A chave que estava hardcoded no código
  (`pk_live_...`) deve ser considerada comprometida e precisa ser revogada.
- **`HOST`** default `127.0.0.1`. O código original chamava `listen(port)` sem host, escutando em
  todas as interfaces — o que expunha na rede local uma API sem autenticação.
- **`DATABASE_FILE`** default `:memory:`, o que recria o banco a cada boot. Aponte para um arquivo
  para ter persistência.

## Estrutura

```text
src/
├── server.js              entry point — só o listen()
├── app.js                 composition root: createApp(), exporta a app sem escutar
├── config/                única porta de entrada de configuração
├── domain/                erros de domínio
├── infra/                 banco promisificado, schema, scrypt, cache, logger
├── models/                dados e regras por entidade
├── services/              cobrança, atrás de interface injetada
├── controllers/           use cases
├── routes/                método + path -> controller
├── serializers/           forma externa do relatório
├── schemas/               validação de entrada
└── middlewares/           erro central, logging, security headers
```

`app.js` monta a aplicação e `server.js` a coloca para escutar. A separação é o que permite testar a
API sem subir porta.

A direção de dependência é única: `routes → controllers → models → infra`. Models, serializers e
schemas não importam Express; routes não acessam models; controllers não escrevem SQL.

## Endpoints

Os 3 endpoints originais foram preservados, com os mesmos métodos e paths. Os nomes de campo do
request (`usr`, `eml`, `pwd`, `c_id`, `card`) também — são contrato público.

| Método | Path | Descrição |
| --- | --- | --- |
| `POST` | `/api/checkout` | Cria matrícula com cobrança; cria o usuário se ainda não existir |
| `GET` | `/api/admin/financial-report` | Receita e alunos por curso |
| `DELETE` | `/api/users/:id` | Remove usuário sem matrículas |

## Mudanças de comportamento intencionais

Cada uma exigida por um finding da auditoria:

- Respostas de erro passaram de texto puro para JSON `{"error": "..."}`, com as mesmas mensagens.
- `POST /api/checkout` com `card` que não seja string de dígitos responde `400`. Antes, um `card`
  numérico **derrubava o processo inteiro** — a exceção era lançada dentro de um callback do sqlite3,
  fora do alcance do Express.
- `POST /api/checkout` passou a exigir `pwd`. Antes, a ausência do campo criava a conta com a senha
  default `"123456"`.
- Senhas passaram a ser gravadas com `scrypt`. A função anterior (`badCrypto`) tinha espaço efetivo de
  12 bits — `badCrypto("senhaforte")` era igual a `badCrypto("sen")`. Hashes antigos não autenticam.
- O log do checkout deixou de conter o número do cartão e a chave do gateway; o cartão aparece
  mascarado (`************4444`).
- Um pagamento recusado não cria mais o usuário. Antes a conta era criada antes da cobrança e ficava
  órfã quando o pagamento falhava.
- `DELETE /api/users/:id` responde `409` quando o usuário tem matrículas e `404` quando não existe.
  Antes respondia `200` incondicionalmente, com uma mensagem que descrevia a própria corrupção que
  estava causando.
- Corpo de requisição acima de `MAX_BODY_SIZE` responde `413`.
- A ordem dos alunos dentro de cada curso no relatório passou a ser explícita (`ORDER BY` da
  matrícula). Antes dependia da ordem de conclusão dos callbacks.

## Pendências fora do escopo da refatoração

- A chave `pk_live_`, a senha do banco e o usuário SMTP estão no histórico do git e precisam ser
  revogados.
- Todas as senhas gravadas com `badCrypto` devem ser consideradas comprometidas.
- Os logs já coletados contêm números de cartão completos e precisam ser expurgados.
- A API não tem autenticação. `GET /api/admin/financial-report` é administrativo e público.
- `POST /api/checkout` não tem rate limit.
- A cobrança continua sendo stub. A interface existe; a integração real, não.
- Não há testes automatizados.
- `sqlite3` está um major atrás; Express 4 está em manutenção.
