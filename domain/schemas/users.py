from datetime import UTC, datetime
from typing import Annotated, Literal, Self, get_args
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
)

from domain.models.user import User

DisplayName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=2, max_length=50, pattern=r"^[^\x00]*$"
    ),
]
Bio = Annotated[str, StringConstraints(max_length=160, pattern=r"^[^\x00]*$")]
AvatarId = Literal[
    "avatar-01",
    "avatar-02",
    "avatar-03",
    "avatar-04",
    "avatar-05",
    "avatar-06",
    "avatar-07",
    "avatar-08",
]
AVATAR_IDS = get_args(AvatarId)


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: DisplayName
    email: EmailStr
    password: Annotated[SecretStr, Field(min_length=8, max_length=128)]


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: Annotated[SecretStr, Field(min_length=1, max_length=128)]


class AccessToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserIdentity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(validation_alias="id")
    display_name: str
    created_at: AwareDatetime

    @field_validator("created_at")
    @classmethod
    def timestamp_in_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


def profile_image_url(user_id: UUID, kind: str, version: UUID) -> str:
    return f"/api/v1/users/{user_id}/images/{kind}/{version}"


class ProfileImageLink(BaseModel):
    url: str


class ProfileData(UserIdentity):
    bio: str | None
    avatar_id: AvatarId | None
    avatar_image_url: str | None = None
    background_image_url: str | None = None

    @classmethod
    def from_user(cls, user: User) -> Self:
        urls = {
            f"{image.kind}_image_url": profile_image_url(
                user.id, image.kind, image.version
            )
            for image in user.profile_images
        }
        return cls.model_validate(user).model_copy(update=urls)


class CurrentUser(ProfileData):
    email: str


class Archetype(BaseModel):
    title: str
    description: str


class PublicProfile(ProfileData):
    archetype: Archetype | None = None


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bio: Bio | None = None
    avatar_id: AvatarId | None = None


class AvatarOption(BaseModel):
    id: AvatarId


class AvatarList(BaseModel):
    items: list[AvatarOption]
