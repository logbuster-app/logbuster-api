from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from starlette.concurrency import run_in_threadpool

from dependencies.auth import RequiredUserId
from dependencies.services import get_review_service, get_user_service
from domain.enums import ProfileImageKind
from domain.errors.users import (
    ProfileImageTooLargeError,
    UnsupportedProfileImageTypeError,
)
from domain.schemas.errors import ErrorResponse
from domain.schemas.reviews import UserReviewListQuery, UserReviewListResponse
from domain.schemas.users import (
    AVATAR_IDS,
    AccessToken,
    AvatarList,
    AvatarOption,
    CurrentUser,
    Login,
    ProfileImageLink,
    ProfilePatch,
    PublicProfile,
    Registration,
    UserIdentity,
)
from services.review import ReviewService
from services.user import UserService
from utils.profile_images import IMAGE_FORMATS, MAX_IMAGE_BYTES

router = APIRouter(
    prefix="/api/v1",
    tags=["Contas e perfis"],
    responses={422: {"model": ErrorResponse, "description": "Dados inválidos"}},
)
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]

UNAUTHORIZED_RESPONSE = {
    401: {"model": ErrorResponse, "description": "Autenticação inválida ou ausente"}
}
USER_NOT_FOUND_RESPONSE = {
    404: {"model": ErrorResponse, "description": "Usuário não encontrado"}
}


@router.post(
    "/auth/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserIdentity,
    responses={409: {"model": ErrorResponse, "description": "E-mail já cadastrado"}},
)
def register(payload: Registration, service: UserServiceDep) -> UserIdentity:
    return UserIdentity.model_validate(service.register(payload))


@router.post("/auth/login", response_model=AccessToken, responses=UNAUTHORIZED_RESPONSE)
def login(payload: Login, service: UserServiceDep) -> AccessToken:
    return service.login(payload)


@router.get("/auth/me", response_model=CurrentUser, responses=UNAUTHORIZED_RESPONSE)
def get_session(user_id: RequiredUserId, service: UserServiceDep) -> CurrentUser:
    return CurrentUser.from_user(service.get_current_user(user_id))


@router.get(
    "/users/{user_id}", response_model=PublicProfile, responses=USER_NOT_FOUND_RESPONSE
)
def get_profile(
    user_id: UUID, service: UserServiceDep, reviews: ReviewServiceDep
) -> PublicProfile:
    profile = PublicProfile.from_user(service.get_profile(user_id))
    return profile.model_copy(update={"archetype": reviews.archetype(user_id)})


@router.get(
    "/users/{user_id}/reviews",
    response_model=UserReviewListResponse,
    responses=USER_NOT_FOUND_RESPONSE,
)
def list_user_reviews(
    user_id: UUID,
    query: Annotated[UserReviewListQuery, Query()],
    users: UserServiceDep,
    reviews: ReviewServiceDep,
) -> UserReviewListResponse:
    users.get_profile(user_id)
    return reviews.list_for_user(user_id, query)


@router.get("/avatars", response_model=AvatarList)
def list_avatars() -> AvatarList:
    return AvatarList(items=[AvatarOption(id=avatar_id) for avatar_id in AVATAR_IDS])


@router.patch(
    "/users/me", response_model=PublicProfile, responses=UNAUTHORIZED_RESPONSE
)
def update_profile(
    payload: ProfilePatch,
    user_id: RequiredUserId,
    service: UserServiceDep,
    reviews: ReviewServiceDep,
) -> PublicProfile:
    profile = PublicProfile.from_user(service.update_profile(user_id, payload))
    return profile.model_copy(update={"archetype": reviews.archetype(user_id)})


@router.put(
    "/users/me/images/{kind}",
    response_model=ProfileImageLink,
    responses={
        **UNAUTHORIZED_RESPONSE,
        413: {"model": ErrorResponse, "description": "Imagem acima do limite"},
        415: {"model": ErrorResponse, "description": "Formato de imagem não aceito"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                media_type: {"schema": {"type": "string", "format": "binary"}}
                for media_type in IMAGE_FORMATS
            },
        }
    },
    summary="Enviar ou substituir imagem do perfil",
)
async def replace_profile_image(
    kind: ProfileImageKind,
    user_id: RequiredUserId,
    request: Request,
    service: UserServiceDep,
) -> ProfileImageLink:
    media_type = (
        request.headers.get("Content-Type", "").partition(";")[0].strip().lower()
    )
    if media_type not in IMAGE_FORMATS:
        raise UnsupportedProfileImageTypeError()
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > MAX_IMAGE_BYTES:
            raise ProfileImageTooLargeError()
        payload.extend(chunk)
    return await run_in_threadpool(
        service.replace_profile_image, user_id, kind, payload, media_type
    )


@router.get(
    "/users/{user_id}/images/{kind}/{version}",
    response_class=Response,
    responses={
        200: {
            "content": {
                "image/webp": {"schema": {"type": "string", "format": "binary"}}
            }
        },
        404: {"model": ErrorResponse, "description": "Imagem de perfil não encontrada"},
    },
    summary="Consultar imagem pública do perfil",
)
def get_profile_image(
    user_id: UUID, kind: ProfileImageKind, version: UUID, service: UserServiceDep
) -> Response:
    return Response(
        content=service.get_profile_image(user_id, kind, version),
        media_type="image/webp",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete(
    "/users/me/images/{kind}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=UNAUTHORIZED_RESPONSE,
    summary="Remover imagem do perfil",
)
def delete_profile_image(
    kind: ProfileImageKind, user_id: RequiredUserId, service: UserServiceDep
) -> Response:
    service.delete_profile_image(user_id, kind)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
