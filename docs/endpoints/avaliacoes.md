# Avaliações

Os endpoints do domínio de avaliações. O formato de cada item de avaliação (`ReviewResponse`) é o mesmo em todos eles.

## Item de avaliação (`ReviewResponse`)

```json
{
  "id": "c4f7d9d2-9d4e-4b3a-8f55-1f2e3d4c5b6a",
  "movie_id": "tt0133093",
  "author_name": "Thyago",
  "rating": 4.5,
  "content": "Direção precisa e efeitos visuais que revolucionaram o gênero.",
  "is_spoiler": false,
  "highlights": ["direction", "visual_effects"],
  "counts": { "like": 0, "spoiler": 0, "well_argued": 0 },
  "viewer_interactions": [],
  "created_at": "2026-11-08T18:30:00Z"
}
```

- `counts`: total de votos de cada tipo na avaliação.
- `viewer_interactions`: tipos que o visitante do header `X-Visitor-Id` já marcou (`[]` sem o header).
- `created_at`: sempre em UTC, no formato ISO-8601.

## `POST /api/v1/reviews` — cadastrar avaliação (`BACK-01`)

SPEC: [SPEC-BACK-01](https://github.com/logbuster-app/logbuster-docs/blob/main/docs/specs/back/SPEC-BACK-01-post-cadastro-avaliacao.md)

| Campo | Tipo | Obrigatório | Regra |
| --- | --- | --- | --- |
| `movie_id` | string | sim | imdbID, `^tt[0-9]{7,10}$` (ex.: `tt0133093`) |
| `author_name` | string | sim | De 2 a 50 caracteres, após remover espaços das pontas |
| `rating` | number | sim | De `0.5` a `5.0`, em passos de `0.5` (`4.3`, `0` e `"4.5"` são rejeitados) |
| `content` | string | sim | De 10 a 2000 caracteres, após remover espaços das pontas |
| `is_spoiler` | boolean | não | Padrão `false` |
| `highlights` | string[] | não | De 0 a 2 valores únicos entre `soundtrack`, `cinematography`, `screenplay`, `acting`, `direction` e `visual_effects` |

Campos não listados acima são rejeitados com `422`.

```bash
curl -X POST http://localhost:8000/api/v1/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "movie_id": "tt0133093",
    "author_name": "Thyago",
    "rating": 4.5,
    "content": "Direção precisa e efeitos visuais que revolucionaram o gênero.",
    "is_spoiler": false,
    "highlights": ["direction", "visual_effects"]
  }'
```

**Respostas**
- `201 Created`: o `ReviewResponse` com `id` gerado, `counts` zerados e `viewer_interactions: []`.
- `422 VALIDATION_ERROR`: payload inválido. Nada é salvo. Exemplo com 3 destaques:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Informe no máximo 2 destaques únicos entre: soundtrack, cinematography, screenplay, acting, direction e visual_effects.",
    "details": [{ "field": "highlights", "issue": "List should have at most 2 items after validation, not 3" }]
  }
}
```

## `GET /api/v1/movies/{movie_id}/reviews` — listar avaliações de um filme (`BACK-02`)

SPEC: [SPEC-BACK-02](https://github.com/logbuster-app/logbuster-docs/blob/main/docs/specs/back/SPEC-BACK-02-get-lista-avaliacoes.md)

| Parâmetro | Onde | Padrão | Regra |
| --- | --- | --- | --- |
| `movie_id` | path | — | imdbID (`422` se inválido) |
| `sort` | query | `well_argued` | `well_argued`, `most_liked`, `newest`, `rating_desc` ou `rating_asc` |
| `page` | query | `1` | Inteiro `>= 1` |
| `page_size` | query | `10` | Inteiro de `1` a `50` |
| `X-Visitor-Id` | header | — | Opcional, até 64 caracteres. Preenche `viewer_interactions` |

Query ou header inválidos retornam `400 BAD_REQUEST`.

**Ordenações** (o último critério de desempate é sempre `created_at DESC`):

| `sort` | Critérios |
| --- | --- |
| `well_argued` | Votos "Bem argumentada" ↓, curtidas ↓, mais recente |
| `most_liked` | Curtidas ↓, votos "Bem argumentada" ↓, mais recente |
| `newest` | Mais recente |
| `rating_desc` | Nota ↓, mais recente |
| `rating_asc` | Nota ↑, mais recente |

A ordenação e a paginação acontecem no banco. Os contadores são agregados numa única consulta, e o `total` e o `viewer_interactions` usam no máximo mais duas.

```bash
curl "http://localhost:8000/api/v1/movies/tt0133093/reviews?sort=most_liked&page=1&page_size=10" \
  -H "X-Visitor-Id: 550e8400-e29b-41d4-a716-446655440000"
```

**Resposta `200 OK`**:

```json
{
  "items": [
    {
      "id": "c4f7d9d2-9d4e-4b3a-8f55-1f2e3d4c5b6a",
      "movie_id": "tt0133093",
      "author_name": "Thyago",
      "rating": 4.5,
      "content": "Direção precisa e efeitos visuais que revolucionaram o gênero.",
      "is_spoiler": false,
      "highlights": ["direction", "visual_effects"],
      "counts": { "like": 4, "spoiler": 0, "well_argued": 9 },
      "viewer_interactions": ["well_argued"],
      "created_at": "2026-11-08T18:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10,
  "sort": "most_liked"
}
```

Um filme sem avaliações retorna `200` com `items: []` e `total: 0`, nunca `404`.

## `GET /api/v1/reviews/{review_id}` — consultar avaliação (`BACK-03`)

SPEC: [SPEC-BACK-03](https://github.com/logbuster-app/logbuster-docs/blob/main/docs/specs/back/SPEC-BACK-03-get-avaliacao-especifica.md)

| Parâmetro | Onde | Regra |
| --- | --- | --- |
| `review_id` | path | UUID da avaliação (`422` se malformado) |
| `X-Visitor-Id` | header | Opcional, até 64 caracteres (`400` se maior). Preenche `viewer_interactions` |

```bash
curl http://localhost:8000/api/v1/reviews/c4f7d9d2-9d4e-4b3a-8f55-1f2e3d4c5b6a \
  -H "X-Visitor-Id: 550e8400-e29b-41d4-a716-446655440000"
```

**Respostas**
- `200 OK`: o `ReviewResponse` completo, com os contadores atualizados. É o mesmo formato de item do `POST` e da listagem.
- `404 NOT_FOUND`: não existe avaliação com esse `review_id`.

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Avaliação não encontrada.",
    "details": []
  }
}
```
