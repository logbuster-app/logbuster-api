from functools import lru_cache
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
from services.spoiler_scheduler import SpoilerReviewJob, SpoilerReviewScheduler
from services.user import UserService
from utils.database import create_session

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


def build_spoiler_check_service() -> SpoilerCheckService:
    return SpoilerCheckService(
        get_chat_client(),
        get_title_lookup().context,
        timeout=settings.ai_spoiler_timeout_seconds,
    )


@lru_cache(maxsize=1)
def get_spoiler_scheduler() -> SpoilerReviewScheduler:
    """Um pool por processo para a análise pós-publicação (CR-02)."""
    job = SpoilerReviewJob(
        session_factory=create_session,
        repository_factory=ReviewRepository,
        checker_factory=build_spoiler_check_service,
    )
    return SpoilerReviewScheduler(job)


def shutdown_spoiler_scheduler() -> None:
    """Chamado ao desligar a API; só encerra o pool se ele chegou a existir."""
    if get_spoiler_scheduler.cache_info().currsize:
        get_spoiler_scheduler().shutdown()
        get_spoiler_scheduler.cache_clear()


SpoilerSchedulerDep = Annotated[SpoilerReviewScheduler, Depends(get_spoiler_scheduler)]


def get_review_summary_service(
    session: SessionDep, chat: ChatClientDep, titles: TitleLookupDep
) -> ReviewSummaryService:
    spoilers = SpoilerCheckService(
        chat, titles.context, timeout=settings.ai_spoiler_timeout_seconds
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


def get_review_service(
    session: SessionDep, spoiler_scheduler: SpoilerSchedulerDep
) -> ReviewService:
    return ReviewService(ReviewRepository(session), spoiler_scheduler)


def get_interaction_service(session: SessionDep) -> InteractionService:
    return InteractionService(ReviewRepository(session), InteractionRepository(session))


def get_user_service(session: SessionDep) -> UserService:
    return UserService(UserRepository(session))
