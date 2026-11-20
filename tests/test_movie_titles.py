from unittest.mock import Mock

import pytest

from services import movie_titles
from services.movie_titles import MovieTitleLookup
from services.omdb import MovieNotFound, OmdbClient, OmdbError


@pytest.fixture(autouse=True)
def empty_cache(monkeypatch):
    monkeypatch.setattr(movie_titles, "_titles", {})


def test_returns_title_with_year_and_caches_it():
    omdb = Mock(spec=OmdbClient)
    omdb.get_movie.return_value = {"title": " Matrix ", "year": "1999"}
    lookup = MovieTitleLookup(omdb, timeout=1.5)

    assert lookup("tt0133093") == "Matrix (1999)"
    assert lookup("tt0133093") == "Matrix (1999)"
    omdb.get_movie.assert_called_once_with("tt0133093", timeout=1.5)


def test_title_without_year():
    omdb = Mock(spec=OmdbClient)
    omdb.get_movie.return_value = {"title": "Matrix", "year": None}
    assert MovieTitleLookup(omdb)("tt0133093") == "Matrix"


@pytest.mark.parametrize(
    "outcome",
    [OmdbError(), MovieNotFound(), {"title": ""}, {"title": None}, {}],
)
def test_failures_return_none_without_caching(outcome):
    omdb = Mock(spec=OmdbClient)
    if isinstance(outcome, Exception):
        omdb.get_movie.side_effect = outcome
    else:
        omdb.get_movie.return_value = outcome
    lookup = MovieTitleLookup(omdb)

    assert lookup("tt0133093") is None
    assert lookup("tt0133093") is None
    assert omdb.get_movie.call_count == 2


def test_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(movie_titles, "MAX_CACHED_TITLES", 2)
    omdb = Mock(spec=OmdbClient)
    omdb.get_movie.side_effect = lambda movie_id, timeout: {"title": movie_id}
    lookup = MovieTitleLookup(omdb)

    for movie_id in ("tt0000001", "tt0000002", "tt0000003"):
        lookup(movie_id)

    assert len(movie_titles._titles) <= 2
