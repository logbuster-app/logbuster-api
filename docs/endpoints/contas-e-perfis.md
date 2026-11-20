# Contas e perfis

[Back A no Trello](https://trello.com/c/161rtpgG/81-back-a) · [SPEC-BACK-08](https://github.com/logbuster-app/logbuster-docs/blob/main/docs/specs/back/SPEC-BACK-08-auth-perfil-publico.md)

| Método e rota | Entrada | Sucesso |
| --- | --- | --- |
| `POST /api/v1/auth/register` | JSON com `display_name`, `email` e `password` | `201` com `user_id`, `display_name` e `created_at` |
| `POST /api/v1/auth/login` | JSON com `email` e `password` | `200` com `access_token`, `token_type: "bearer"` e `expires_in` em segundos |
| `GET /api/v1/auth/me` | Bearer do titular | `200` com `user_id`, `display_name`, `email`, `created_at`, `bio`, `avatar_id`, `avatar_image_url` e `background_image_url` |
| `GET /api/v1/users/{user_id}` | Público | `200` com o perfil público |
| `GET /api/v1/users/{user_id}/reviews` | Público. `page` a partir de 1, `page_size` de 1 a 50 | `200` com `items`, `total`, `page` e `page_size` |
| `GET /api/v1/avatars` | Público | `200` com `items: [{id}]` |
| `PUT /api/v1/users/me/images/{kind}` | Bearer do titular e conteúdo binário da imagem | `200` com `{url}` |
| `DELETE /api/v1/users/me/images/{kind}` | Bearer do titular | `204` sem corpo |
| `GET /api/v1/users/{user_id}/images/{kind}/{version}` | Público | `200` com o WebP da versão atual ou `404` |
| `PATCH /api/v1/users/me` | Bearer do titular. JSON com `bio` e/ou `avatar_id` | `200` com o perfil atualizado |

## Cadastro e sessão

O nome de exibição tem de 2 a 50 caracteres após remover espaços nas pontas. Contas distintas podem usar o mesmo nome. A senha tem de 8 a 128 caracteres e é armazenada como hash Argon2id. O e-mail é normalizado e comparado sem distinção de maiúsculas e minúsculas. Duplicidade retorna `409 CONFLICT`.

Para obter e verificar tokens, configure `JWT_SECRET` com uma chave aleatória de pelo menos 32 bytes. `JWT_EXPIRES_IN` é um número inteiro positivo em segundos, com padrão de 3600. Em requisições autenticadas, envie `Authorization: Bearer <access_token>`. Credenciais inválidas ou token ausente em rota privada, inválido ou vencido retornam `401 UNAUTHORIZED`.

## Perfil público e histórico

O perfil público contém `user_id`, `display_name`, `created_at`, `bio`, `avatar_id`, `avatar_image_url`, `background_image_url` e `archetype`. O e-mail é retornado só em `/auth/me`. O campo `archetype` é calculado a partir das avaliações da conta e vem `null` com menos de 3. As regras estão em [IA e arquétipo](ia.md).

O titular pode editar bio de até 160 caracteres e escolher um avatar entre `avatar-01` e `avatar-08`. O cliente associa os IDs às ilustrações. Omitir um campo preserva seu valor. Enviar `null` limpa o campo. Corpo inválido retorna `422 VALIDATION_ERROR`.

O histórico usa itens no mesmo [formato das avaliações](avaliacoes.md), com `movie_id` para a ficha do filme e contadores de votos. Inclui apenas avaliações vinculadas à conta e ordena por `created_at DESC, id DESC`. Por padrão, `page=1` e `page_size=10`. Página sem itens retorna lista vazia. Perfil inexistente retorna `404 NOT_FOUND`. Paginação inválida retorna `422 VALIDATION_ERROR`.

## Foto e fundo personalizados

- Use `avatar` para a foto e `background` para o fundo. Cada conta tem no máximo uma imagem de cada tipo. O titular pode enviar, substituir ou remover cada uma de forma independente.
- Envie os bytes diretamente no corpo do `PUT`, com `Content-Type: image/jpeg`, `image/png` ou `image/webp`. A imagem deve ser estática, ter até 8 MiB e no máximo 4096 pixels em cada dimensão.
- A API respeita a orientação da imagem e gera WebP sem metadados, mantendo a proporção. A foto cabe em 512 × 512 e o fundo em 1920 × 1080.
- Use as URLs relativas retornadas no perfil com a origem da API. Uma substituição gera uma nova URL. URLs de versões removidas ou substituídas retornam `404`. O GET público serve `image/webp` e `Cache-Control: no-store`.
- Exiba `avatar_image_url` quando presente e use `avatar_id` como alternativa. Remover a foto recupera a opção fixa. Quando `background_image_url` for `null`, use o fundo padrão do front.
- Envio rejeitado preserva a imagem anterior. Excesso de bytes ou dimensões retorna `413 PAYLOAD_TOO_LARGE`, tipo ausente ou incompatível retorna `415 UNSUPPORTED_MEDIA_TYPE`, e imagem corrompida ou animada retorna `422 VALIDATION_ERROR`. Apenas uma exclusão explícita remove a imagem. Repeti-la retorna `204`.

```bash
curl -X PUT "$API_ORIGIN/api/v1/users/me/images/avatar" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: image/jpeg' \
  --data-binary @foto.jpg
```

## Atualização do banco

Rode `uv run --frozen alembic upgrade head`. A revisão `0002` cria as contas e permite um vínculo opcional das novas avaliações com o usuário. As avaliações anteriores preservam sua autoria anônima, e os votos continuam usando `X-Visitor-Id`.

A revisão `0003` cria o armazenamento das imagens WebP no PostgreSQL. Perfis existentes começam com as duas URLs nulas.
