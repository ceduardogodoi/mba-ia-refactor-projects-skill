# code-smells-project

API de E-commerce em Python/Flask — catálogo de produtos, cadastro e login de usuários, criação de
pedidos com baixa de estoque e relatório de vendas.

Este projeto foi a entrada do desafio `refactor-arch` e passou pelas três fases da skill: análise,
auditoria e refatoração para MVC. O relatório da auditoria está em
[`../reports/audit-project-1.md`](../reports/audit-project-1.md).

## Como rodar

```bash
pip install -r requirements.txt
cp .env.example .env      # obrigatório: a aplicação não sobe sem SECRET_KEY
python app.py
```

A aplicação sobe em `http://127.0.0.1:5000`. O banco SQLite (`loja.db`) é criado no primeiro boot,
já com produtos e usuários de exemplo.

Credenciais de seed: `admin@loja.com` / `admin123`.

## Configuração

Toda configuração vem de variáveis de ambiente — nenhum valor sensível está no código. Veja
`.env.example` para a lista completa. Duas merecem atenção:

- **`SECRET_KEY`** é obrigatória e não tem default. A aplicação falha na inicialização se ela estiver
  ausente, o que é intencional: um default de secret é a mesma vulnerabilidade com passos a mais.
- **`ADMIN_ENDPOINTS_ENABLED`** controla `POST /admin/query` e `POST /admin/reset-db`. O default é
  `false`, e nesse estado as duas rotas continuam existindo mas respondem `403`. Ligar significa expor
  execução de SQL arbitrário e destruição de dados.

## Estrutura

```text
app.py                    entry point — carrega config e expõe `app` para WSGI
src/
├── app.py                composition root: create_app()
├── config/               única porta de entrada de configuração
├── domain/               constantes e erros de domínio
├── infra/                conexão por request, schema, hash de senha
├── models/               dados e regras por entidade
├── controllers/          use cases — validam, orquestram, escolhem status code
├── views/routes.py       método + path -> controller
├── serializers/          contrato externo, com allowlist de campos públicos
├── schemas/              validação de entrada
├── services/             colaboradores externos (notificações)
└── middlewares/          tratamento de erro centralizado e logging
```

A direção de dependência é única: `routes → controllers → models → infra`. Models, serializers e
schemas não importam Flask; routes não acessam models; controllers não escrevem SQL.

## Endpoints

Os 19 endpoints originais foram preservados, com os mesmos métodos e paths.

| Método | Path | Descrição |
| --- | --- | --- |
| `GET` | `/` | Índice da API |
| `GET` | `/health` | Status e conectividade do banco |
| `GET` | `/produtos` | Lista produtos |
| `GET` | `/produtos/busca` | Busca por `q`, `categoria`, `preco_min`, `preco_max` |
| `GET` | `/produtos/<id>` | Detalhe do produto |
| `POST` | `/produtos` | Cria produto |
| `PUT` | `/produtos/<id>` | Atualiza produto |
| `DELETE` | `/produtos/<id>` | Remove produto |
| `GET` | `/usuarios` | Lista usuários |
| `GET` | `/usuarios/<id>` | Detalhe do usuário |
| `POST` | `/usuarios` | Cria usuário |
| `POST` | `/login` | Autentica |
| `POST` | `/pedidos` | Cria pedido com baixa de estoque |
| `GET` | `/pedidos` | Lista todos os pedidos |
| `GET` | `/pedidos/usuario/<usuario_id>` | Pedidos de um usuário |
| `PUT` | `/pedidos/<pedido_id>/status` | Atualiza status |
| `GET` | `/relatorios/vendas` | Relatório de vendas |
| `POST` | `/admin/query` | Executa SQL — requer `ADMIN_ENDPOINTS_ENABLED=true` |
| `POST` | `/admin/reset-db` | Limpa o banco — requer `ADMIN_ENDPOINTS_ENABLED=true` |

## Mudanças de comportamento intencionais

A refatoração preservou o contrato, com estas exceções — cada uma exigida por um finding da auditoria:

- `GET /usuarios` e `GET /usuarios/<id>` não retornam mais o campo `senha`.
- `GET /health` não retorna mais `secret_key`, `debug`, `db_path` nem `ambiente`.
- `POST /admin/query` e `POST /admin/reset-db` respondem `403` enquanto a flag estiver desligada.
- Respostas de erro passaram a incluir sempre `"sucesso": false`, e não expõem mais o texto da
  exceção — o detalhe vai para o log.
- `GET /produtos/busca` com `preco_min`/`preco_max` não numérico responde `400` em vez de `500`.
- `DELETE /produtos/<id>` de um produto referenciado por um pedido responde `409` em vez de `200`;
  antes a remoção deixava itens de pedido órfãos.
- `PUT /produtos/<id>` aplica as mesmas validações de `POST /produtos` (comprimento do nome e
  allowlist de categoria), que antes faltavam no update.
- Senhas passaram a ser gravadas com hash. As credenciais de seed continuam as mesmas; senhas
  gravadas antes da refatoração não autenticam mais.

## Pendências fora do escopo da refatoração

- A `SECRET_KEY` original está no histórico do git e precisa ser considerada comprometida.
- As senhas foram armazenadas em plaintext e devem ser resetadas.
- A API não tem autenticação: `GET /usuarios` e `GET /pedidos` continuam públicos.
- Não há testes automatizados. A refatoração tornou as regras testáveis — desconto, estoque e login
  são os pontos de partida naturais.
- `usuarios.email` ainda não tem constraint `UNIQUE`.
