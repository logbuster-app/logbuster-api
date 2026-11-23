from unittest.mock import Mock

import pytest

from services import movie_titles
from services.movie_titles import MovieContext, MovieTitleLookup
from services.omdb import MovieNotFound, OmdbClient, OmdbError


@pytest.fixture(autouse=True)
def empty_cache(monkeypatch):
    monkeypatch.setattr(movie_titles, "_contexts", {})


def omdb_returning(movie):
    omdb = Mock(spec=OmdbClient)
    omdb.get_movie.return_value = movie
    return omdb


def test_context_has_title_year_and_short_synopsis_cached():
    omdb = omdb_returning(
        {"title": " Matrix ", "year": "1999", "plot": " Um hacker descobre a verdade. "}
    )
    lookup = MovieTitleLookup(omdb, timeout=1.5)

    context = lookup.context("tt0133093")

    assert context == MovieContext("Matrix", "1999", "Um hacker descobre a verdade.")
    assert lookup.context("tt0133093") is context
    # CR-02: sinopse curta, com o timeout curto.
    omdb.get_movie.assert_called_once_with("tt0133093", timeout=1.5, plot="short")


def test_default_timeout_is_two_seconds():
    omdb = omdb_returning({"title": "Matrix"})
    MovieTitleLookup(omdb).context("tt0133093")
    assert omdb.get_movie.call_args.kwargs["timeout"] == 2.0


def test_call_returns_label_for_summary():
    omdb = omdb_returning({"title": "Matrix", "year": "1999", "plot": "Premissa."})
    assert MovieTitleLookup(omdb)("tt0133093") == "Matrix (1999)"


@pytest.mark.parametrize("plot", [None, "", "   "])
def test_missing_synopsis_keeps_title(plot):
    omdb = omdb_returning({"title": "Matrix", "year": None, "plot": plot})
    context = MovieTitleLookup(omdb).context("tt0133093")
    assert context == MovieContext("Matrix")
    assert context.label == "Matrix"


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

    assert lookup.context("tt0133093") is None
    assert lookup("tt0133093") is None
    assert omdb.get_movie.call_count == 2


def test_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(movie_titles, "MAX_CACHED_TITLES", 2)
    omdb = Mock(spec=OmdbClient)
    omdb.get_movie.side_effect = lambda movie_id, timeout, plot: {"title": movie_id}
    lookup = MovieTitleLookup(omdb)

    for movie_id in ("tt0000001", "tt0000002", "tt0000003"):
        lookup.context(movie_id)

    assert len(movie_titles._contexts) <= 2
