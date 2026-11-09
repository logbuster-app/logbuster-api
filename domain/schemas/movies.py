from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

Identifier = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]

# imdbID da OMDb, identificador canônico de filme (SPEC-API-00, RN-01).
# [0-9] em vez de \d: o motor de regex do Pydantic aceita dígitos Unicode em \d.
IMDB_ID_PATTERN = r"^tt[0-9]{7,10}$"
ImdbId = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=IMDB_ID_PATTERN)
]


class MovieRating(BaseModel):
    movie_id: Identifier
    average_rating: Annotated[
        float | None,
        Field(
            ge=0.5,
            le=5,
            description="Média arredondada a duas casas decimais; null sem avaliações.",
        ),
    ]
    reviews_count: Annotated[int, Field(ge=0)]
