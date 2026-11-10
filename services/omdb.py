import httpx

from config import settings


class OmdbError(Exception):
    pass


class MovieNotFound(Exception):
    pass


class TooManyResults(Exception):
    pass


class OmdbClient:
    def search(self, query: str, page: int) -> tuple[list[dict], int]:
        try:
            response = httpx.get(
                settings.omdb_base_url,
                params={
                    "apikey": settings.omdb_api_key,
                    "s": query,
                    "type": "movie",
                    "page": page,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("Response") == "False":
                if data.get("Error") == "Movie not found!":
                    return [], 0
                if data.get("Error") == "Too many results.":
                    raise TooManyResults
                raise OmdbError
            movies = [
                {
                    "id": movie["imdbID"],
                    "title": movie["Title"],
                    "year": movie["Year"],
                    "poster_url": movie.get("Poster")
                    if movie.get("Poster") not in (None, "", "N/A")
                    else None,
                }
                for movie in data["Search"]
            ]
            return movies, int(data["totalResults"])
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise OmdbError from exc

    def get_movie(self, movie_id: str) -> dict:
        try:
            response = httpx.get(
                settings.omdb_base_url,
                params={"apikey": settings.omdb_api_key, "i": movie_id, "plot": "full"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("Response") == "False":
                if data.get("Error") in ("Movie not found!", "Incorrect IMDb ID."):
                    raise MovieNotFound
                raise OmdbError

            def normalized(key: str) -> str | None:
                value = data.get(key)
                return value if value not in (None, "", "N/A") else None

            genre = normalized("Genre")
            return {
                "id": data["imdbID"],
                "title": data["Title"],
                "year": normalized("Year"),
                "runtime": normalized("Runtime"),
                "genres": [item.strip() for item in genre.split(",") if item.strip()]
                if genre
                else [],
                "director": normalized("Director"),
                "actors": normalized("Actors"),
                "plot": normalized("Plot"),
                "poster_url": normalized("Poster"),
            }
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise OmdbError from exc
