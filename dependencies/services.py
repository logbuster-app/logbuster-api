from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from dependencies.session import get_session
from repositories.review import ReviewRepository
from services.review import ReviewService

SessionDep = Annotated[Session, Depends(get_session)]


def get_review_service(session: SessionDep) -> ReviewService:
    return ReviewService(ReviewRepository(session))
