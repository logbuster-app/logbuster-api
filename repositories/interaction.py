from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from domain.models.interaction import Interaction


class InteractionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, interaction: Interaction) -> Interaction:
        try:
            self.session.add(interaction)
            self.session.flush()
            self.session.refresh(interaction)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return interaction
