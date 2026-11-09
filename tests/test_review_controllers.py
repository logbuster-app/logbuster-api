from uuid import uuid4

import pytest

from dependencies.services import get_review_service
from dependencies.session import get_session
from domain.schemas.movies import MovieRating
from domain.schemas.reviews import ReviewResponse
from main import app

MOVIE_ID = "tt0133093"
REVIEWS = "/api/v1/reviews"
CONTENT = "Direção precisa e efeitos visuais que revolucionaram o gênero."


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["details"], list)
    return body["error"]


def test_create_review_returns_201_with_spec_contract(
    client, review_service, review, review_payload
):
    review_service.create.return_value = ReviewResponse.from_model(review)

    response = client.post(REVIEWS, json=review_payload)

    assert response.status_code == 201
    assert response.json() == {
        "id": str(review.id),
        "movie_id": MOVIE_ID,
        "author_name": "Thyago",
        "rating": 4.5,
        "content": CONTENT,
        "is_spoiler": False,
        "highlights": ["direction", "visual_effects"],
        "counts": {"like": 0, "spoiler": 0, "well_argued": 0},
        "viewer_interactions": [],
        "created_at": "2026-11-08T18:30:00Z",
    }
    (payload,) = review_service.create.call_args.args
    assert payload.rating == 4.5 and payload.movie_id == MOVIE_ID


@pytest.mark.parametrize("rating", [0.5, 1, 3.0, 4.5, 5])
@pytest.mark.parametrize("highlights", [[], ["soundtrack"], ["acting", "direction"]])
def test_create_review_accepts_boundaries(
    client, review_service, review, review_payload, rating, highlights
):
    review_service.create.return_value = ReviewResponse.from_model(review)
    response = client.post(
        REVIEWS, json={**review_payload, "rating": rating, "highlights": highlights}
    )
    assert response.status_code == 201


def test_optional_fields_have_defaults(client, review_service, review, review_payload):
    review_service.create.return_value = ReviewResponse.from_model(review)
    payload = {
        k: v for k, v in review_payload.items() if k not in {"is_spoiler", "highlights"}
    }
    assert client.post(REVIEWS, json=payload).status_code == 201
    (received,) = review_service.create.call_args.args
    assert received.is_spoiler is False and received.highlights == []


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"rating": 0}, "rating"),
        ({"rating": 0.3}, "rating"),
        ({"rating": 4.3}, "rating"),
        ({"rating": 5.5}, "rating"),
        ({"rating": -1}, "rating"),
        ({"rating": "4.5"}, "rating"),
        ({"rating": True}, "rating"),
        ({"rating": None}, "rating"),
        ({"highlights": ["acting", "direction", "soundtrack"]}, "highlights"),
        ({"highlights": ["acting", "acting"]}, "highlights"),
        ({"highlights": ["plot"]}, "highlights"),
        ({"highlights": "acting"}, "highlights"),
        ({"movie_id": "abc"}, "movie_id"),
        ({"movie_id": "tt123"}, "movie_id"),
        ({"movie_id": "tt12345678901"}, "movie_id"),
        ({"movie_id": "nm0133093"}, "movie_id"),
        ({"content": "x" * 9}, "content"),
        ({"content": "   curto   "}, "content"),
        ({"content": "x" * 2001}, "content"),
        ({"author_name": "A"}, "author_name"),
        ({"author_name": "  A  "}, "author_name"),
        ({"author_name": "x" * 51}, "author_name"),
        ({"is_spoiler": "sim"}, "is_spoiler"),
    ],
)
def test_invalid_payload_returns_422_envelope(
    client, review_service, review_payload, changes, field
):
    response = client.post(REVIEWS, json={**review_payload, **changes})
    error = assert_error(response, 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"].split(".")[0] == field
    assert error["message"] != "Os dados enviados são inválidos."
    review_service.create.assert_not_called()


def test_rating_error_message_matches_spec(client, review_service, review_payload):
    response = client.post(REVIEWS, json={**review_payload, "rating": 0.3})
    error = assert_error(response, 422, "VALIDATION_ERROR")
    assert error["message"] == "A nota deve estar entre 0.5 e 5.0 em passos de 0.5."
    assert error["details"] == [
        {"field": "rating", "issue": "Input should be a multiple of 0.5"}
    ]


@pytest.mark.parametrize("field", ["movie_id", "author_name", "rating", "content"])
def test_missing_required_field_returns_422(
    client, review_service, review_payload, field
):
    payload = {k: v for k, v in review_payload.items() if k != field}
    error = assert_error(client.post(REVIEWS, json=payload), 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == field
    review_service.create.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        {"json": {"unexpected": "value"}},
        {"content": "não é json", "headers": {"Content-Type": "application/json"}},
        {},
    ],
)
def test_malformed_body_returns_generic_422(client, review_service, body):
    error = assert_error(client.post(REVIEWS, **body), 422, "VALIDATION_ERROR")
    assert error["details"]
    review_service.create.assert_not_called()


def test_extra_field_is_rejected(client, review_service, review_payload):
    response = client.post(REVIEWS, json={**review_payload, "user_id": "u"})
    error = assert_error(response, 422, "VALIDATION_ERROR")
    assert {"field": "user_id", "issue": "Extra inputs are not permitted"} in error[
        "details"
    ]


def test_controller_real_service_and_mocked_session(
    client, session, review, review_payload
):
    # Exercita a cadeia inteira, isolando somente a sessão de persistência.
    app.dependency_overrides.pop(get_review_service)
    app.dependency_overrides[get_session] = lambda: session

    def populate_defaults(entity):
        entity.id = review.id
        entity.created_at = review.created_at

    session.refresh.side_effect = populate_defaults
    response = client.post(REVIEWS, json=review_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(review.id)
    assert body["rating"] == 4.5
    assert body["counts"] == {"like": 0, "spoiler": 0, "well_argued": 0}
    session.add.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.parametrize("average,count", [(4.67, 3), (0.5, 1), (None, 0)])
def test_movie_rating_response(client, review_service, average, count):
    review_service.rating.return_value = MovieRating(
        movie_id=MOVIE_ID, average_rating=average, reviews_count=count
    )
    response = client.get(f"/api/v1/movies/{MOVIE_ID}/rating")
    assert response.status_code == 200
    assert response.json() == {
        "movie_id": MOVIE_ID,
        "average_rating": average,
        "reviews_count": count,
    }
    review_service.rating.assert_called_once_with(MOVIE_ID)


@pytest.mark.parametrize("movie_id", ["%20%20", "x" * 129])
def test_invalid_rating_movie_identifier_returns_422(client, movie_id):
    response = client.get(f"/api/v1/movies/{movie_id}/rating")
    assert_error(response, 422, "VALIDATION_ERROR")


def test_unknown_route_returns_404_envelope(client):
    error = assert_error(client.get(f"/api/v1/unknown/{uuid4()}"), 404, "NOT_FOUND")
    assert error["message"] == "Recurso não encontrado."


def test_wrong_method_returns_405_envelope(client):
    response = client.put(REVIEWS, json={})
    assert_error(response, 405, "METHOD_NOT_ALLOWED")
    assert "POST" in response.headers["allow"]


def test_docs_and_openapi_document_contract(client):
    assert client.get("/api/docs").status_code == 200
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    operations = {
        (path, method) for path, value in schema["paths"].items() for method in value
    }
    assert operations == {
        ("/api/v1/reviews", "post"),
        ("/api/v1/movies/{movie_id}/rating", "get"),
    }
    post = schema["paths"]["/api/v1/reviews"]["post"]
    assert set(post["responses"]) >= {"201", "422", "500", "503"}
    assert post["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
    rating_schema = schema["components"]["schemas"]["MovieRating"]
    assert {"type": "null"} in rating_schema["properties"]["average_rating"]["anyOf"]


def test_configured_cors_preflight(client):
    response = client.options(
        REVIEWS,
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-credentials" not in response.headers
