# Arquitetura

O código é organizado em camadas, conforme a [SPEC-ARCH-01](https://github.com/logbuster-app/logbuster-docs/blob/main/docs/specs/transversais/SPEC-ARCH-01-arquitetura-ci-quality-gate.md), RN-02:

```text
main.py              App FastAPI, CORS e registro de routers e handlers de erro
config.py            Configuração por variáveis de ambiente
controllers/         Rotas HTTP: status codes, parâmetros e headers
services/            Regras de negócio
repositories/        Acesso ao banco (SQLAlchemy)
dependencies/        Injeção de dependências (sessão e services)
domain/
  enums.py           Highlight, ReviewInteractionType e ReviewSort
  models/            Tabelas ORM (Review e ReviewInteraction)
  schemas/           Schemas Pydantic de entrada e saída
  errors/            AppError e erros de domínio
utils/
  database.py        Engine, sessão e Base declarativa
  error_handlers.py  Conversão de toda falha para o envelope de erro
alembic/             Migrações do banco
tests/               Testes mockados
```

## Tabelas

**`reviews`**: uma avaliação de filme.

| Coluna | Tipo | Regra |
| --- | --- | --- |
| `id` | UUID | PK, gerado na aplicação |
| `movie_id` | `VARCHAR(12)` | imdbID, `^tt[0-9]{7,10}$` |
| `author_name` | `VARCHAR(50)` | De 2 a 50 caracteres, após `trim` |
| `rating` | `NUMERIC(2,1)` | De 0.5 a 5.0, em passos de 0.5 |
| `content` | `VARCHAR(2000)` | De 10 a 2000 caracteres, após `trim` |
| `is_spoiler` | `BOOLEAN` | Padrão `false` |
| `highlights` | `VARCHAR(32)[]` | No máximo 2 itens (os valores são validados pelo Pydantic) |
| `created_at` | `TIMESTAMPTZ` | Preenchido pelo banco |

**`review_interactions`**: um voto (`like`, `spoiler` ou `well_argued`) de um visitante anônimo (`X-Visitor-Id`) em uma avaliação.
- A unique `(review_id, visitor_id, type)` garante no máximo 1 voto de cada tipo por visitante.
- A FK para `reviews` usa `ON DELETE CASCADE`.
- É gravada pelo `POST /api/v1/reviews/{review_id}/interactions` (`controllers/`, `services/` e `repositories/interaction.py`).
- Os contadores (`counts`) das respostas são calculados a partir desta tabela.

As regras de negócio são validadas no Pydantic, que dá a mensagem de erro amigável, e repetidas em `CHECK` no banco, que é a última linha de defesa.
