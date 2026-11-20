# Padrão de erros

Toda resposta de erro segue o envelope da [SPEC-API-00](https://github.com/logbuster-app/logbuster-docs/blob/main/docs/specs/transversais/SPEC-API-00-contrato-http-e-erros.md), §4.3:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "A nota deve estar entre 0.5 e 5.0 em passos de 0.5.",
    "details": [{ "field": "rating", "issue": "Input should be a multiple of 0.5" }]
  }
}
```

| HTTP | `error.code` | Quando |
| --- | --- | --- |
| `400` | `BAD_REQUEST` | Query string ou header inválido |
| `401` | `UNAUTHORIZED` | Credenciais inválidas ou token ausente em rota privada, inválido ou vencido |
| `404` | `NOT_FOUND` | Recurso inexistente (ex.: `review_id`) ou rota desconhecida |
| `405` | `METHOD_NOT_ALLOWED` | Método HTTP não suportado na rota |
| `409` | `CONFLICT` | E-mail já cadastrado |
| `413` | `PAYLOAD_TOO_LARGE` | Imagem de perfil acima do limite de bytes ou dimensões |
| `415` | `UNSUPPORTED_MEDIA_TYPE` | Tipo de imagem do perfil ausente, não aceito ou incompatível com o arquivo |
| `422` | `VALIDATION_ERROR` | Corpo, parâmetro de path ou paginação do histórico público viola as regras de domínio |
| `500` | `INTERNAL_ERROR` | Erro inesperado (nada interno vaza para o cliente nem para o log) |
| `503` | `SERVICE_UNAVAILABLE` | Banco indisponível ou configuração de banco ou autenticação ausente ou inválida |

- `message` vem em português e se refere ao primeiro campo inválido.
- `details` lista todos os problemas encontrados: `field` é o caminho do campo (ex.: `highlights.2`) e `issue` é a descrição técnica.

## Como lançar um erro de negócio

Herde de `AppError` (`domain/errors/base.py`) e defina `status_code`, `code` e `message`. O handler global (`utils/error_handlers.py`) monta o envelope:

```python
from domain.errors.base import NotFoundError


class ReviewNotFoundError(NotFoundError):
    message = "Avaliação não encontrada."
```
