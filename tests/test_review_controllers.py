from uuid import uuid4

import pytest

from dependencies.services import get_review_service
from dependencies.session import get_session
from domain.enums import ReviewSort
from domain.errors.reviews import ReviewNotFoundError
from domain.schemas.movies import MovieRating
from domain.schemas.reviews import (
    ReviewCounts,
    ReviewListResponse,
    ReviewResponse,
)
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
        ("/api/v1/movies/{movie_id}/reviews", "get"),
        ("/api/v1/reviews/{review_id}", "get"),
        ("/api/v1/movies/{movie_id}/rating", "get"),
    }
    detail = schema["paths"]["/api/v1/reviews/{review_id}"]["get"]
    assert set(detail["responses"]) >= {"200", "400", "404", "422"}
    assert detail["responses"]["404"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
    listing = schema["paths"]["/api/v1/movies/{movie_id}/reviews"]["get"]
    assert set(listing["responses"]) >= {"200", "400", "422"}
    parameters = {(p["name"], p["in"]) for p in listing["parameters"]}
    assert parameters == {
        ("movie_id", "path"),
        ("sort", "query"),
        ("page", "query"),
        ("page_size", "query"),
        ("X-Visitor-Id", "header"),
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
            "Access-Control-Request-Headers": "Content-Type, X-Visitor-Id",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-credentials" not in response.headers
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "x-visitor-id" in allowed and "content-type" in allowed


LIST = f"/api/v1/movies/{MOVIE_ID}/reviews"


def list_response(review, **overrides):
    item = ReviewResponse.from_model(
        review, ReviewCounts(like=4, spoiler=0, well_argued=9), ["well_argued"]
    )
    return ReviewListResponse(
        items=[item], total=1, page=1, page_size=10, sort=ReviewSort.WELL_ARGUED
    ).model_copy(update=overrides)


def test_list_reviews_defaults(client, review_service, review):
    review_service.list.return_value = list_response(review)

    response = client.get(LIST)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "page", "page_size", "sort"}
    assert (body["total"], body["page"], body["page_size"], body["sort"]) == (
        1,
        1,
        10,
        "well_argued",
    )
    assert body["items"][0]["counts"] == {"like": 4, "spoiler": 0, "well_argued": 9}
    assert body["items"][0]["viewer_interactions"] == ["well_argued"]
    review_service.list.assert_called_once_with(
        MOVIE_ID, sort=ReviewSort.WELL_ARGUED, page=1, page_size=10, visitor_id=None
    )


@pytest.mark.parametrize("sort", list(ReviewSort))
def test_list_reviews_forwards_query_and_visitor(client, review_service, review, sort):
    review_service.list.return_value = list_response(
        review, sort=sort, page=2, page_size=50
    )
    response = client.get(
        f"{LIST}?sort={sort}&page=2&page_size=50",
        headers={"X-Visitor-Id": " 550e8400-e29b-41d4-a716-446655440000 "},
    )
    assert response.status_code == 200
    assert response.json()["sort"] == sort
    review_service.list.assert_called_once_with(
        MOVIE_ID,
        sort=sort,
        page=2,
        page_size=50,
        visitor_id="550e8400-e29b-41d4-a716-446655440000",
    )


def test_blank_visitor_header_is_ignored(client, review_service, review):
    review_service.list.return_value = list_response(review)
    client.get(LIST, headers={"X-Visitor-Id": "   "})
    assert review_service.list.call_args.kwargs["visitor_id"] is None


def test_list_empty_movie_returns_200(client, review_service):
    review_service.list.return_value = ReviewListResponse(
        items=[], total=0, page=1, page_size=10, sort=ReviewSort.WELL_ARGUED
    )
    response = client.get("/api/v1/movies/tt9999999/reviews")
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 10,
        "sort": "well_argued",
    }


@pytest.mark.parametrize(
    "query",
    [
        "sort=oldest",
        "sort=WELL_ARGUED",
        "page=0",
        "page=-1",
        "page=abc",
        "page_size=0",
        "page_size=51",
        "page_size=1.5",
    ],
)
def test_invalid_query_returns_400(client, review_service, query):
    error = assert_error(client.get(f"{LIST}?{query}"), 400, "BAD_REQUEST")
    assert error["details"][0]["field"] in {"sort", "page", "page_size"}
    review_service.list.assert_not_called()


def test_too_long_visitor_header_returns_400(client, review_service):
    response = client.get(LIST, headers={"X-Visitor-Id": "x" * 65})
    error = assert_error(response, 400, "BAD_REQUEST")
    assert error["details"][0]["field"] == "X-Visitor-Id"
    review_service.list.assert_not_called()


@pytest.mark.parametrize("movie_id", ["abc", "tt123", "catalog:42", "tt12345678901"])
def test_list_invalid_movie_id_returns_422(client, review_service, movie_id):
    error = assert_error(
        client.get(f"/api/v1/movies/{movie_id}/reviews"), 422, "VALIDATION_ERROR"
    )
    assert error["message"] == "O movie_id deve ser um imdbID válido (ex.: tt0133093)."
    review_service.list.assert_not_called()


def detail_url(review_id):
    return f"{REVIEWS}/{review_id}"


def test_get_review_returns_200_with_full_item(client, review_service, review):
    review_service.get.return_value = ReviewResponse.from_model(
        review, ReviewCounts(like=4, spoiler=0, well_argued=9)
    )

    response = client.get(detail_url(review.id))

    assert response.status_code == 200
    assert response.json() == {
        "id": str(review.id),
        "movie_id": MOVIE_ID,
        "author_name": "Thyago",
        "rating": 4.5,
        "content": CONTENT,
        "is_spoiler": False,
        "highlights": ["direction", "visual_effects"],
        "counts": {"like": 4, "spoiler": 0, "well_argued": 9},
        "viewer_interactions": [],
        "created_at": "2026-11-08T18:30:00Z",
    }
    review_service.get.assert_called_once_with(review.id, visitor_id=None)


def test_get_review_forwards_visitor(client, review_service, review):
    review_service.get.return_value = ReviewResponse.from_model(
        review, viewer_interactions=["like"]
    )
    response = client.get(detail_url(review.id), headers={"X-Visitor-Id": "v1"})
    assert response.json()["viewer_interactions"] == ["like"]
    review_service.get.assert_called_once_with(review.id, visitor_id="v1")


def test_missing_review_returns_404_envelope(client, review_service):
    review_service.get.side_effect = ReviewNotFoundError()
    response = client.get(detail_url(uuid4()))
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Avaliação não encontrada.",
            "details": [],
        }
    }


@pytest.mark.parametrize("review_id", ["invalid", "123", "tt0133093"])
def test_malformed_review_id_returns_422(client, review_service, review_id):
    error = assert_error(client.get(detail_url(review_id)), 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "review_id"
    assert error["message"] == "O review_id deve ser um UUID válido."
    review_service.get.assert_not_called()


def test_get_review_too_long_visitor_returns_400(client, review_service):
    response = client.get(detail_url(uuid4()), headers={"X-Visitor-Id": "x" * 65})
    assert_error(response, 400, "BAD_REQUEST")
    review_service.get.assert_not_called()
