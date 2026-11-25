"""Cria contas e adiciona o vínculo opcional das avaliações.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(50), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("bio", sa.String(160), nullable=True),
        sa.Column("avatar_id", sa.String(9), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    with op.batch_alter_table("reviews") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_reviews_user_id",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_reviews_user_created_id", ["user_id", "created_at", "id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("reviews") as batch_op:
        batch_op.drop_index("ix_reviews_user_created_id")
        batch_op.drop_constraint("fk_reviews_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")
    op.drop_table("users")
