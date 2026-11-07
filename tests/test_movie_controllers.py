from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from dependencies.services import get_review_service
from dependencies.session import get_session
from domain.errors.movies import DuplicateReviewError, ReviewNotFoundError
from domain.schemas.movies import InteractionRead, MovieRating, ReviewPage, ReviewRead
from main import app
from utils.database import DatabaseConfigurationError

BASE = "/api/v1/movies/catalog:42"


def test_create_review_returns_public_schema(client, review_service, review):
    review_service.create.return_value = ReviewRead.model_validate(review)
    response = client.post(
        f"{BASE}/reviews",
        json={"user_id": "user-1", "rating": 5, "comment": review.comment},
    )
    assert response.status_code == 201
    result = ReviewRead.model_validate(response.json())
    assert result.id == review.id
    assert result.created_at.utcoffset().total_seconds() == 0
    assert set(response.json()) == {
        "id",
        "movie_id",
        "user_id",
        "rating",
        "comment",
        "created_at",
    }
    movie_id, payload = review_service.create.call_args.args
    assert movie_id == "catalog:42" and payload.rating == 5


def test_duplicate_review_returns_409(client, review_service):
    review_service.create.side_effect = DuplicateReviewError()
    response = client.post(f"{BASE}/reviews", json={"user_id": "user-1", "rating": 5})
    assert response.status_code == 409
    assert response.json() == {"detail": "O usuário já avaliou este filme."}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"user_id": "user-1"},
        {"rating": 3},
        {"user_id": "", "rating": 3},
        {"user_id": "   ", "rating": 3},
        {"user_id": "x" * 129, "rating": 3},
        {"user_id": 1, "rating": 3},
        {"user_id": "u", "rating": 0},
        {"user_id": "u", "rating": 6},
        {"user_id": "u", "rating": 2.5},
        {"user_id": "u", "rating": True},
        {"user_id": "u", "rating": "5"},
        {"user_id": "u", "rating": 3, "comment": "x" * 2001},
        {"user_id": "u", "rating": 3, "unexpected": "value"},
    ],
)
def test_invalid_review_payload_returns_422(client, review_service, payload):
    response = client.post(f"{BASE}/reviews", json=payload)
    assert response.status_code == 422
    review_service.create.assert_not_called()


def test_list_reviews_with_pagination(client, review_service, review):
    review_service.list.return_value = ReviewPage(
        items=[ReviewRead.model_validate(review)], total=9, limit=2, offset=4
    )
    response = client.get(f"{BASE}/reviews?limit=2&offset=4")
    assert response.status_code == 200
    assert ReviewPage.model_validate(response.json()).total == 9
    review_service.list.assert_called_once_with("catalog:42", limit=2, offset=4)


def test_list_empty_movie_returns_empty_page(client, review_service):
    review_service.list.return_value = ReviewPage(items=[], total=0)
    response = client.get(f"{BASE}/reviews")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=101", "offset=-1", "limit=1.5", "offset=abc"]
)
def test_invalid_pagination_returns_422(client, review_service, query):
    assert client.get(f"{BASE}/reviews?{query}").status_code == 422
    review_service.list.assert_not_called()


@pytest.mark.parametrize("movie_id", ["%20%20", "x" * 129])
@pytest.mark.parametrize("suffix", ["reviews", "rating", "interactions"])
def test_invalid_movie_identifier_returns_422(client, movie_id, suffix):
    path = f"/api/v1/movies/{movie_id}/{suffix}"
    response = (
        client.post(path, json={"user_id": "u", "interaction_type": "view"})
        if suffix == "interactions"
        else client.get(path)
    )
    assert response.status_code == 422


def test_get_review_returns_200(client, review_service, review):
    review_service.get.return_value = ReviewRead.model_validate(review)
    response = client.get(f"/api/v1/reviews/{review.id}")
    assert response.status_code == 200
    assert ReviewRead.model_validate(response.json()).id == review.id
    review_service.get.assert_called_once_with(review.id)


def test_missing_review_returns_404(client, review_service):
    review_service.get.side_effect = ReviewNotFoundError()
    response = client.get(f"/api/v1/reviews/{uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Avaliação não encontrada."}


def test_invalid_review_uuid_returns_422(client, review_service):
    assert client.get("/api/v1/reviews/invalid").status_code == 422
    review_service.get.assert_not_called()


@pytest.mark.parametrize("average,count", [(4.67, 3), (None, 0)])
def test_movie_rating_response(client, review_service, average, count):
    review_service.rating.return_value = MovieRating(
        movie_id="catalog:42", average_rating=average, reviews_count=count
    )
    response = client.get(f"{BASE}/rating")
    assert response.status_code == 200
    assert response.json() == {
        "movie_id": "catalog:42",
        "average_rating": average,
        "reviews_count": count,
    }
    review_service.rating.assert_called_once_with("catalog:42")


@pytest.mark.parametrize("kind", ["view", "like", "watchlist", "watched"])
def test_create_interaction_returns_201(client, interaction_service, interaction, kind):
    interaction.interaction_type = kind
    interaction_service.create.return_value = InteractionRead.model_validate(
        interaction
    )
    response = client.post(
        f"{BASE}/interactions", json={"user_id": "user-1", "interaction_type": kind}
    )
    assert response.status_code == 201
    result = InteractionRead.model_validate(response.json())
    assert result.interaction_type == kind and result.id == interaction.id
    interaction_service.create.assert_called_once()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"user_id": "u"},
        {"interaction_type": "view"},
        {"user_id": "u", "interaction_type": "dislike"},
        {"user_id": "u", "interaction_type": "LIKE"},
        {"user_id": " ", "interaction_type": "view"},
        {"user_id": "x" * 129, "interaction_type": "view"},
    ],
)
def test_invalid_interaction_returns_422(client, interaction_service, payload):
    assert client.post(f"{BASE}/interactions", json=payload).status_code == 422
    interaction_service.create.assert_not_called()


@pytest.mark.parametrize(
    "error,status,detail",
    [
        (
            OperationalError("select", {}, Exception("SENSITIVE")),
            503,
            "Persistência temporariamente indisponível.",
        ),
        (
            DatabaseConfigurationError("SENSITIVE"),
            503,
            "Persistência temporariamente indisponível.",
        ),
        (RuntimeError("SENSITIVE"), 500, "Erro interno do servidor."),
    ],
)
def test_errors_do_not_expose_internal_details(
    client, review_service, error, status, detail, caplog
):
    review_service.list.side_effect = error
    response = client.get(f"{BASE}/reviews")
    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert "SENSITIVE" not in caplog.text


def test_output_schema_is_enforced(client, review_service):
    review_service.get.return_value = {"id": "invalid"}
    response = client.get(f"/api/v1/reviews/{uuid4()}")
    assert response.status_code == 500
    assert response.json() == {"detail": "Erro interno do servidor."}


def test_controller_real_service_and_mocked_session(client, session, review):
    # Exercita a cadeia inteira, isolando somente a sessão de persistência.
    app.dependency_overrides.pop(get_review_service)
    app.dependency_overrides[get_session] = lambda: session

    def populate_defaults(entity):
        entity.id = review.id
        entity.created_at = review.created_at

    session.refresh.side_effect = populate_defaults
    response = client.post(f"{BASE}/reviews", json={"user_id": "user-1", "rating": 4})
    assert response.status_code == 201
    assert response.json()["rating"] == 4
    session.add.assert_called_once()
    session.commit.assert_called_once()


def test_docs_openapi_routes_and_empty_rating_contract(client):
    assert client.get("/api/docs").status_code == 200
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    operations = {
        (path, method) for path, value in schema["paths"].items() for method in value
    }
    assert operations == {
        ("/api/v1/movies/{movie_id}/reviews", "post"),
        ("/api/v1/movies/{movie_id}/reviews", "get"),
        ("/api/v1/reviews/{review_id}", "get"),
        ("/api/v1/movies/{movie_id}/rating", "get"),
        ("/api/v1/movies/{movie_id}/interactions", "post"),
    }
    rating_schema = schema["components"]["schemas"]["MovieRating"]
    assert {"type": "null"} in rating_schema["properties"]["average_rating"]["anyOf"]
    assert (
        "null"
        in schema["paths"]["/api/v1/movies/{movie_id}/rating"]["get"]["description"]
    )
    assert (
        "409"
        in schema["paths"]["/api/v1/movies/{movie_id}/reviews"]["post"]["responses"]
    )
    assert "404" in schema["paths"]["/api/v1/reviews/{review_id}"]["get"]["responses"]


def test_configured_cors_preflight(client):
    response = client.options(
        f"{BASE}/reviews",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-credentials" not in response.headers
