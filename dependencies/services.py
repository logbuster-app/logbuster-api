from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from dependencies.session import get_session
from repositories.interaction import InteractionRepository
from repositories.review import ReviewRepository
from services.interaction import InteractionService
from services.review import ReviewService

SessionDep = Annotated[Session, Depends(get_session)]


def get_review_service(session: SessionDep) -> ReviewService:
    return ReviewService(ReviewRepository(session))


def get_interaction_service(session: SessionDep) -> InteractionService:
    return InteractionService(ReviewRepository(session), InteractionRepository(session))
