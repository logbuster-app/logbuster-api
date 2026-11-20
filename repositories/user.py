from uuid import UUID, uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, undefer

from domain.enums import ProfileImageKind
from domain.errors.users import EmailConflictError, UnauthorizedError
from domain.models.profile_image import ProfileImage
from domain.models.user import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: UUID) -> User | None:
        return self.session.get(User, user_id)

    def by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def create(self, *, display_name: str, email: str, password_hash: str) -> User:
        statement = (
            insert(User)
            .values(display_name=display_name, email=email, password_hash=password_hash)
            .on_conflict_do_nothing(constraint="uq_users_email")
            .returning(User)
        )
        user = self.session.scalars(statement).one_or_none()
        if user is None:
            raise EmailConflictError()
        self.session.commit()
        return user

    def update_profile(self, user_id: UUID, changes: dict[str, str | None]) -> User:
        statement = (
            update(User)
            .where(User.id == user_id)
            .values(**changes)
            .returning(User)
            .execution_options(populate_existing=True)
        )
        user = self.session.scalars(statement).one_or_none()
        if user is None:
            raise UnauthorizedError()
        self.session.commit()
        return user

    def get_profile_image(
        self, user_id: UUID, kind: ProfileImageKind, version: UUID
    ) -> ProfileImage | None:
        statement = (
            select(ProfileImage)
            .options(undefer(ProfileImage.content))
            .where(
                ProfileImage.user_id == user_id,
                ProfileImage.kind == kind,
                ProfileImage.version == version,
            )
        )
        return self.session.scalar(statement)

    def save_profile_image(
        self, user_id: UUID, kind: ProfileImageKind, content: bytes
    ) -> UUID:
        version = uuid4()
        insert_image = insert(ProfileImage).values(
            user_id=user_id, kind=kind, version=version, content=content
        )
        statement = insert_image.on_conflict_do_update(
            index_elements=[ProfileImage.user_id, ProfileImage.kind],
            set_={
                "version": insert_image.excluded.version,
                "content": insert_image.excluded.content,
            },
        )
        self.session.execute(statement)
        self.session.commit()
        return version

    def delete_profile_image(self, user_id: UUID, kind: ProfileImageKind) -> None:
        self.session.execute(
            delete(ProfileImage).where(
                ProfileImage.user_id == user_id, ProfileImage.kind == kind
            )
        )
        self.session.commit()
