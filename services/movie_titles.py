"""Título do filme como contexto para a IA, sem tornar a OMDb obrigatória."""

from services.omdb import MovieNotFound, OmdbClient, OmdbError

TITLE_TIMEOUT_SECONDS = 2.0
MAX_CACHED_TITLES = 1_000

# Cache do processo: títulos não mudam e evitam uma ida à OMDb por análise.
_titles: dict[str, str] = {}


class MovieTitleLookup:
    def __init__(
        self, omdb: OmdbClient, *, timeout: float = TITLE_TIMEOUT_SECONDS
    ) -> None:
        self.omdb = omdb
        self.timeout = timeout

    def __call__(self, movie_id: str) -> str | None:
        """`"Matrix (1999)"`, ou `None` se a OMDb falhar ou demorar."""
        if movie_id in _titles:
            return _titles[movie_id]
        try:
            movie = self.omdb.get_movie(movie_id, timeout=self.timeout)
        except (OmdbError, MovieNotFound):
            return None
        title = movie.get("title")
        if not isinstance(title, str) or not title.strip():
            return None
        year = movie.get("year")
        label = f"{title.strip()} ({year})" if year else title.strip()
        if len(_titles) >= MAX_CACHED_TITLES:
            _titles.clear()
        _titles[movie_id] = label
        return label
