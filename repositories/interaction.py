from uuid import UUID, uuid4

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from domain.enums import ReviewInteractionType
from domain.models.review_interaction import ReviewInteraction

UNIQUE_VOTE_CONSTRAINT = "uq_review_interactions_review_visitor_type"


class InteractionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def toggle(
        self, review_id: UUID, visitor_id: str, kind: ReviewInteractionType
    ) -> bool:
        """Alterna o voto `(review_id, visitor_id, type)` e diz se ele ficou ativo.

        O `DELETE ... RETURNING` decide o caminho numa só ida ao banco: se removeu
        um voto, ele fica inativo; senão, insere. O `ON CONFLICT DO NOTHING` torna
        o insert idempotente quando dois cliques simultâneos chegam juntos (os
        dois respondem `active: true` e só um voto é gravado).
        """
        try:
            removed = self.session.execute(
                delete(ReviewInteraction)
                .where(
                    ReviewInteraction.review_id == review_id,
                    ReviewInteraction.visitor_id == visitor_id,
                    ReviewInteraction.type == kind,
                )
                .returning(ReviewInteraction.id)
            ).first()
            if removed is None:
                self.session.execute(
                    insert(ReviewInteraction)
                    .values(
                        id=uuid4(),
                        review_id=review_id,
                        visitor_id=visitor_id,
                        type=kind,
                    )
                    .on_conflict_do_nothing(constraint=UNIQUE_VOTE_CONSTRAINT)
                )
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return removed is None
