from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from config import settings
from dependencies.session import get_session
from repositories.interaction import InteractionRepository
from repositories.review import ReviewRepository
from repositories.review_summary import ReviewSummaryRepository
from repositories.user import UserRepository
from services.ai import ChatClient
from services.interaction import InteractionService
from services.movie_titles import MovieTitleLookup
from services.omdb import OmdbClient
from services.review import ReviewService
from services.review_summary import ReviewSummaryService
from services.spoiler import SpoilerCheckService
from services.user import UserService

SessionDep = Annotated[Session, Depends(get_session)]


def get_chat_client() -> ChatClient:
    return ChatClient(
        base_url=settings.ai_base_url,
        api_key=settings.ai_api_key,
        model=settings.ai_model,
        reasoning_effort=settings.ai_reasoning_effort,
    )


def get_title_lookup() -> MovieTitleLookup:
    return MovieTitleLookup(OmdbClient())


ChatClientDep = Annotated[ChatClient, Depends(get_chat_client)]
TitleLookupDep = Annotated[MovieTitleLookup, Depends(get_title_lookup)]


def get_spoiler_check_service(
    chat: ChatClientDep, titles: TitleLookupDep
) -> SpoilerCheckService:
    return SpoilerCheckService(
        chat, titles, timeout=settings.ai_spoiler_timeout_seconds
    )


def get_review_summary_service(
    session: SessionDep, chat: ChatClientDep, titles: TitleLookupDep
) -> ReviewSummaryService:
    spoilers = SpoilerCheckService(
        chat, titles, timeout=settings.ai_spoiler_timeout_seconds
    )
    return ReviewSummaryService(
        ReviewRepository(session),
        ReviewSummaryRepository(session),
        chat,
        title_lookup=titles,
        spoiler_checker=spoilers.check,
        regen_threshold=settings.review_summary_regen_threshold,
        retry_after_seconds=settings.ai_retry_after_seconds,
        timeout=settings.ai_timeout_seconds,
    )


def get_review_service(session: SessionDep) -> ReviewService:
    return ReviewService(ReviewRepository(session))


def get_interaction_service(session: SessionDep) -> InteractionService:
    return InteractionService(ReviewRepository(session), InteractionRepository(session))


def get_user_service(session: SessionDep) -> UserService:
    return UserService(UserRepository(session))
