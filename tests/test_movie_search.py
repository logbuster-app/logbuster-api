from unittest.mock import Mock

import httpx
import pytest

from controllers.movies import get_omdb_client
from dependencies.session import get_session
from main import app
from services.omdb import OmdbClient, OmdbError, TooManyResults


@pytest.fixture
def search_client(client, session):
    omdb = Mock(spec=OmdbClient)
    app.dependency_overrides[get_omdb_client] = lambda: omdb
    app.dependency_overrides[get_session] = lambda: session
    return client, session, omdb


def test_search_enriches_in_one_query(search_client):
    client, session, omdb = search_client
    omdb.search.return_value = (
        [
            {"id": "tt0133093", "title": "Matrix", "year": "1999", "poster_url": None},
            {"id": "tt0234215", "title": "Other", "year": "2000", "poster_url": None},
        ],
        2,
    )
    session.execute.return_value = [("tt0133093", 4.25, 2)]
    response = client.get("/api/v1/movies?q=Matrix")
    assert response.status_code == 200
    assert [
        (item["rating_avg"], item["rating_count"]) for item in response.json()["items"]
    ] == [(4.25, 2), (None, 0)]
    session.execute.assert_called_once()


def test_search_empty_and_failures(search_client):
    client, session, omdb = search_client
    omdb.search.return_value = ([], 0)
    assert client.get("/api/v1/movies?q=none").json()["items"] == []
    session.execute.assert_not_called()
    for error, status in [(OmdbError(), 502), (TooManyResults(), 422)]:
        omdb.search.side_effect = error
        assert client.get("/api/v1/movies?q=matrix").status_code == status
    invalid = client.get("/api/v1/movies?q=%20%20")
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "BAD_REQUEST"
    assert client.get("/api/v1/movies?q=matrix&page=0").status_code == 400


def test_omdb_mapping_and_errors(monkeypatch):
    response = Mock()
    monkeypatch.setattr(httpx, "get", Mock(return_value=response))
    response.json.return_value = {
        "Response": "True",
        "Search": [
            {"imdbID": "tt0133093", "Title": "Matrix", "Year": "1999", "Poster": "N/A"}
        ],
        "totalResults": "1",
    }
    movies, total = OmdbClient().search("Matrix", 1)
    assert total == 1 and movies[0]["poster_url"] is None
    assert httpx.get.call_args.kwargs["params"]["type"] == "movie"
    for message, expected in [
        ("Movie not found!", None),
        ("Too many results.", TooManyResults),
        ("Invalid API key!", OmdbError),
    ]:
        response.json.return_value = {"Response": "False", "Error": message}
        if expected:
            with pytest.raises(expected):
                OmdbClient().search("x", 1)
        else:
            assert OmdbClient().search("x", 1) == ([], 0)
    httpx.get.side_effect = httpx.TimeoutException("secret")
    with pytest.raises(OmdbError):
        OmdbClient().search("x", 1)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_movie_detail_and_errors(search_client):
    from services.omdb import MovieNotFound

    client, session, omdb = search_client
    omdb.get_movie.return_value = {"id": "tt0133093", "title": "Matrix", "genres": []}
    session.execute.return_value = [("tt0133093", 4.5, 2)]
    response = client.get("/api/v1/movies/tt0133093")
    assert response.status_code == 200
    assert response.json()["rating_avg"] == 4.5
    assert response.json()["rating_count"] == 2
    assert client.get("/api/v1/movies/not-an-imdb-id").status_code == 422
    omdb.get_movie.side_effect = MovieNotFound()
    assert client.get("/api/v1/movies/tt0000000").json()["error"]["code"] == "NOT_FOUND"
    omdb.get_movie.side_effect = OmdbError()
    assert client.get("/api/v1/movies/tt0000000").status_code == 502
    assert client.get("/api/v1/movies/wrong/rating").status_code == 422


def test_omdb_detail_normalization_and_not_found(monkeypatch):
    from services.omdb import MovieNotFound

    response = Mock()
    monkeypatch.setattr(httpx, "get", Mock(return_value=response))
    response.json.return_value = {
        "Response": "True",
        "imdbID": "tt0133093",
        "Title": "Matrix",
        "Genre": "Action, Sci-Fi",
        "Year": "N/A",
        "Runtime": "136 min",
        "Poster": "N/A",
    }
    movie = OmdbClient().get_movie("tt0133093")
    assert movie["genres"] == ["Action", "Sci-Fi"]
    assert movie["year"] is None and movie["poster_url"] is None
    assert httpx.get.call_args.kwargs["params"]["plot"] == "full"
    response.json.return_value = {"Response": "False", "Error": "Incorrect IMDb ID."}
    with pytest.raises(MovieNotFound):
        OmdbClient().get_movie("tt0000000")
    response.json.return_value = {"Response": "False", "Error": "Invalid API key!"}
    with pytest.raises(OmdbError):
        OmdbClient().get_movie("tt0000000")


@pytest.mark.parametrize(
    ("path", "field"),
    [
        ("acting/movies?limit=0", "limit"),
        ("acting/movies?limit=21", "limit"),
        ("invalid/movies", "highlight"),
    ],
)
def test_highlight_movies_rejects_invalid_parameters(search_client, path, field):
    client, session, omdb = search_client
    response = client.get(f"/api/v1/highlights/{path}")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["field"] == field
    session.execute.assert_not_called()
    omdb.get_movie.assert_not_called()


@pytest.mark.parametrize("limit", [1, 20])
def test_highlight_movies_returns_empty_ranking(search_client, limit):
    client, session, omdb = search_client
    session.execute.return_value = []

    response = client.get(f"/api/v1/highlights/acting/movies?limit={limit}")

    assert response.status_code == 200
    assert response.json() == {"items": []}
    omdb.get_movie.assert_not_called()


def test_highlight_movies_falls_back_and_caches_only_success(search_client):
    client, session, omdb = search_client
    movie_id = "tt0133093"
    session.execute.return_value = [(movie_id, 4.25, 4, 3)]
    omdb.get_movie.side_effect = [
        OmdbError(),
        {
            "title": "Matrix",
            "year": "1999",
            "poster_url": "https://example.test/poster",
        },
    ]
    path = "/api/v1/highlights/acting/movies"

    response = client.get(path)

    assert response.status_code == 200
    fallback = {
        "id": movie_id,
        "title": movie_id,
        "year": None,
        "poster_url": None,
        "rating_avg": 4.25,
        "rating_count": 4,
        "highlight_count": 3,
    }
    assert response.json() == {"items": [fallback]}
    session.execute.assert_called_once()

    expected = {
        **fallback,
        "title": "Matrix",
        "year": "1999",
        "poster_url": "https://example.test/poster",
    }
    assert client.get(path).json() == {"items": [expected]}
    assert client.get(path).json() == {"items": [expected]}
    assert omdb.get_movie.call_count == 2
    omdb.get_movie.assert_called_with(movie_id, timeout=2.0)
