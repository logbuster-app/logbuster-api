import pytest
from pydantic import ValidationError

from domain.enums import InteractionType
from domain.schemas.movies import InteractionCreate
from services.interaction import InteractionService


@pytest.mark.parametrize("kind", list(InteractionType))
def test_create_supported_interactions(interaction_repository, interaction, kind):
    interaction.interaction_type = kind
    interaction_repository.create.return_value = interaction
    result = InteractionService(interaction_repository).create(
        "catalog:42", InteractionCreate(user_id="user-1", interaction_type=kind)
    )
    saved = interaction_repository.create.call_args.args[0]
    assert (saved.movie_id, saved.user_id, saved.interaction_type) == (
        "catalog:42",
        "user-1",
        kind,
    )
    assert result.id == interaction.id


@pytest.mark.parametrize("kind", ["dislike", "LIKE", "", None])
def test_reject_unsupported_interaction(interaction_repository, kind):
    payload = InteractionCreate.model_construct(user_id="user-1", interaction_type=kind)
    with pytest.raises(ValidationError):
        InteractionService(interaction_repository).create("catalog:42", payload)
    interaction_repository.create.assert_not_called()


@pytest.mark.parametrize("movie_id", ["", "  ", "x" * 129])
def test_reject_invalid_movie(interaction_repository, movie_id):
    with pytest.raises(ValidationError):
        InteractionService(interaction_repository).create(
            movie_id, InteractionCreate(user_id="user-1", interaction_type="view")
        )
    interaction_repository.create.assert_not_called()


def test_each_interaction_is_an_independent_event(interaction_repository, interaction):
    interaction_repository.create.return_value = interaction
    service = InteractionService(interaction_repository)
    payload = InteractionCreate(user_id="user-1", interaction_type="like")
    service.create("catalog:42", payload)
    service.create("catalog:42", payload)
    assert interaction_repository.create.call_count == 2
    first, second = [
        call.args[0] for call in interaction_repository.create.call_args_list
    ]
    assert first is not second


def test_interaction_propagates_repository_failure(interaction_repository):
    interaction_repository.create.side_effect = RuntimeError("Erro")
    with pytest.raises(RuntimeError):
        InteractionService(interaction_repository).create(
            "catalog:42", InteractionCreate(user_id="user-1", interaction_type="view")
        )
