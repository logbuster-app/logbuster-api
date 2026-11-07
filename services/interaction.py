from pydantic import TypeAdapter

from domain.models.interaction import Interaction
from domain.schemas.movies import Identifier, InteractionCreate, InteractionRead
from repositories.interaction import InteractionRepository

_identifier = TypeAdapter(Identifier)


class InteractionService:
    def __init__(self, repository: InteractionRepository) -> None:
        self.repository = repository

    def create(self, movie_id: str, payload: InteractionCreate) -> InteractionRead:
        movie_id = _identifier.validate_python(movie_id)
        payload = InteractionCreate.model_validate(payload)
        interaction = Interaction(movie_id=movie_id, **payload.model_dump())
        return InteractionRead.model_validate(self.repository.create(interaction))
