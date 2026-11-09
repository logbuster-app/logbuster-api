from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, OperationalError

from domain.enums import ReviewInteractionType
from repositories.interaction import InteractionRepository


def compiled(call):
    statement = call.args[0]
    result = statement.compile(dialect=postgresql.dialect())
    return " ".join(str(result).split()), result.params


def test_toggle_removes_existing_vote(session):
    review_id = uuid4()
    session.execute.return_value.first.return_value = (uuid4(),)

    active = InteractionRepository(session).toggle(
        review_id, "v1", ReviewInteractionType.WELL_ARGUED
    )

    assert active is False
    assert session.execute.call_count == 1  # não tenta inserir
    sql, params = compiled(session.execute.call_args_list[0])
    assert sql.startswith("DELETE FROM review_interactions WHERE")
    assert "review_interactions.review_id = %(review_id_1)s" in sql
    assert "review_interactions.visitor_id = %(visitor_id_1)s" in sql
    assert "review_interactions.type = %(type_1)s" in sql
    assert sql.endswith("RETURNING review_interactions.id")
    assert params == {
        "review_id_1": review_id,
        "visitor_id_1": "v1",
        "type_1": ReviewInteractionType.WELL_ARGUED,
    }
    session.commit.assert_called_once()


def test_toggle_inserts_missing_vote_idempotently(session):
    review_id = uuid4()
    deleted, inserted = MagicMock(), MagicMock()
    deleted.first.return_value = None
    session.execute.side_effect = [deleted, inserted]

    active = InteractionRepository(session).toggle(
        review_id, "v1", ReviewInteractionType.LIKE
    )

    assert active is True
    assert session.execute.call_count == 2
    sql, params = compiled(session.execute.call_args_list[1])
    assert sql.startswith("INSERT INTO review_interactions")
    assert sql.endswith(
        "ON CONFLICT ON CONSTRAINT uq_review_interactions_review_visitor_type "
        "DO NOTHING"
    )
    assert params["review_id"] == review_id
    assert params["visitor_id"] == "v1"
    assert params["type"] == ReviewInteractionType.LIKE
    assert params["id"] is not None
    session.commit.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        OperationalError("delete", {}, Exception("Erro")),
        IntegrityError("insert", {}, Exception("fk_review_interactions_review_id")),
    ],
)
@pytest.mark.parametrize("stage", ["execute", "commit"])
def test_toggle_rolls_back_and_propagates_failures(session, stage, error):
    if stage == "execute":
        session.execute.side_effect = error
    else:
        session.execute.return_value.first.return_value = None
        session.commit.side_effect = error
    with pytest.raises(type(error)) as caught:
        InteractionRepository(session).toggle(
            uuid4(), "v1", ReviewInteractionType.SPOILER
        )
    assert caught.value is error
    session.rollback.assert_called_once()
