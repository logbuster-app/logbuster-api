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
