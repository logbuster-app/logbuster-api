"""Contexto do filme para a IA, sem tornar a OMDb obrigatória.

A análise de spoiler recebe título, ano e sinopse curta (CR-02). O resumo da
comunidade continua recebendo só o título. A sinopse é a curta (`plot=short`)
porque a completa às vezes conta reviravoltas.
"""

from dataclasses import dataclass

from services.omdb import MovieNotFound, OmdbClient, OmdbError

TITLE_TIMEOUT_SECONDS = 2.0
MAX_CACHED_TITLES = 1_000


@dataclass(frozen=True)
class MovieContext:
    title: str
    year: str | None = None
    synopsis: str | None = None

    @property
    def label(self) -> str:
        return f"{self.title} ({self.year})" if self.year else self.title


# Cache do processo: o contexto do filme não muda e evita uma ida à OMDb por
# análise. Só guarda sucessos, para uma falha passageira não ficar presa.
_contexts: dict[str, MovieContext] = {}


class MovieTitleLookup:
    def __init__(
        self, omdb: OmdbClient, *, timeout: float = TITLE_TIMEOUT_SECONDS
    ) -> None:
        self.omdb = omdb
        self.timeout = timeout

    def context(self, movie_id: str) -> MovieContext | None:
        """Título, ano e sinopse curta, ou `None` se a OMDb falhar ou demorar."""
        if movie_id in _contexts:
            return _contexts[movie_id]
        try:
            movie = self.omdb.get_movie(movie_id, timeout=self.timeout, plot="short")
        except (OmdbError, MovieNotFound):
            return None
        title = movie.get("title")
        if not isinstance(title, str) or not title.strip():
            return None
        synopsis = movie.get("plot")
        context = MovieContext(
            title=title.strip(),
            year=movie.get("year") or None,
            synopsis=synopsis.strip()
            if isinstance(synopsis, str) and synopsis.strip()
            else None,
        )
        if len(_contexts) >= MAX_CACHED_TITLES:
            _contexts.clear()
        _contexts[movie_id] = context
        return context

    def __call__(self, movie_id: str) -> str | None:
        """`"Matrix (1999)"`, usado pelo resumo da comunidade."""
        context = self.context(movie_id)
        return context.label if context else None
