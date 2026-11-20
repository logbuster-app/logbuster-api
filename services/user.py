from uuid import UUID

from domain.enums import ProfileImageKind
from domain.errors.users import (
    ProfileImageNotFoundError,
    UnauthorizedError,
    UserNotFoundError,
)
from domain.models.user import User
from domain.schemas.users import (
    AccessToken,
    Login,
    ProfileImageLink,
    ProfilePatch,
    Registration,
    profile_image_url,
)
from repositories.user import UserRepository
from utils.profile_images import normalize_profile_image
from utils.security import create_access_token, hash_password, verify_password


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def register(self, payload: Registration) -> User:
        return self.repository.create(
            display_name=payload.display_name,
            email=payload.email.casefold(),
            password_hash=hash_password(payload.password.get_secret_value()),
        )

    def login(self, payload: Login) -> AccessToken:
        user = self.repository.by_email(payload.email.casefold())
        password_hash = user.password_hash if user is not None else None
        password_matches = verify_password(
            password_hash, payload.password.get_secret_value()
        )
        if user is None or not password_matches:
            raise UnauthorizedError("E-mail ou senha inválidos.")
        return create_access_token(user.id)

    def get_profile(self, user_id: UUID) -> User:
        user = self.repository.get(user_id)
        if user is None:
            raise UserNotFoundError()
        return user

    def get_current_user(self, user_id: UUID) -> User:
        user = self.repository.get(user_id)
        if user is None:
            raise UnauthorizedError()
        return user

    def update_profile(self, user_id: UUID, payload: ProfilePatch) -> User:
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            return self.get_current_user(user_id)
        return self.repository.update_profile(user_id, changes)

    def get_profile_image(
        self, user_id: UUID, kind: ProfileImageKind, version: UUID
    ) -> bytes:
        image = self.repository.get_profile_image(user_id, kind, version)
        if image is None:
            raise ProfileImageNotFoundError()
        return image.content

    def replace_profile_image(
        self, user_id: UUID, kind: ProfileImageKind, payload: bytearray, media_type: str
    ) -> ProfileImageLink:
        self.get_current_user(user_id)
        content = normalize_profile_image(payload, media_type, kind)
        version = self.repository.save_profile_image(user_id, kind, content)
        return ProfileImageLink(url=profile_image_url(user_id, kind, version))

    def delete_profile_image(self, user_id: UUID, kind: ProfileImageKind) -> None:
        self.get_current_user(user_id)
        self.repository.delete_profile_image(user_id, kind)
