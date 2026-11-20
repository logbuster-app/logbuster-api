from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from utils.database import Base


class ProfileImage(Base):
    __tablename__ = "profile_images"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('avatar', 'background')", name="ck_profile_images_kind"
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_profile_images_user_id"),
        primary_key=True,
    )
    kind: Mapped[str] = mapped_column(String(10), primary_key=True)
    version: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
