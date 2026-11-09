# LogBuster API

Back-end do LogBuster em FastAPI. Ele guarda as avaliações de filmes e as interações dos leitores e calcula a nota média da comunidade.

As SPECs que definem cada endpoint ficam no repositório [`logbuster-docs`](https://github.com/logbuster-app/logbuster-docs/tree/main/docs/specs). Esta documentação descreve o que já está implementado.

## Stack

| Item | Escolha |
| --- | --- |
| Framework | FastAPI e Pydantic v2 |
| Banco | PostgreSQL 17 (via `compose.yaml`), SQLAlchemy 2.0 e Alembic |
| Ambiente | `mise` e `uv` |
| Testes | pytest com mocks: a suíte não abre banco nem rede |
| Docs | Docsify (esta documentação) e Swagger em `/api/docs` |

## Rodando localmente

O passo a passo completo está no [README do repositório](https://github.com/logbuster-app/logbuster-api#readme). Resumo:

```bash
mise setup                      # instala Python, uv e dependências
cp .env.example .env            # preencha DATABASE_URL e credenciais
docker compose up -d            # sobe o PostgreSQL local
uv run alembic upgrade head     # cria as tabelas
mise start                      # http://localhost:8000/api/docs
mise test                       # testes mockados
```

Exemplo de `DATABASE_URL` para o compose local:

```ini
DATABASE_URL=postgresql+psycopg://logbuster:CHANGE_ME_PASSWORD@localhost:5432/logbuster
```

Para ler esta documentação localmente: `npx docsify-cli serve docs`.

## Endpoints disponíveis

| Card | Método e rota | Status |
| --- | --- | --- |
| `BACK-01` | `POST /api/v1/reviews` | Implementado |
| `BACK-05` | `GET /api/v1/movies/{movie_id}/rating` | Versão inicial (contrato ainda será alinhado à SPEC) |
