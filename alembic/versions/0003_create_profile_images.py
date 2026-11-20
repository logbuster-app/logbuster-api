"""Armazena fotos de perfil e fundos personalizados.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profile_images",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("version", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "kind"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_profile_images_user_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('avatar', 'background')", name="ck_profile_images_kind"
        ),
    )


def downgrade() -> None:
    op.drop_table("profile_images")
