"""Cria avaliações e eventos de interação.

Revision ID: 0001
Revises: None
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movie_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.String(2000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("movie_id", "user_id", name="uq_reviews_movie_user"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
        sa.CheckConstraint("length(trim(movie_id)) > 0", name="ck_reviews_movie_id"),
        sa.CheckConstraint("length(trim(user_id)) > 0", name="ck_reviews_user_id"),
    )
    op.create_index(
        "ix_reviews_movie_created_id", "reviews", ["movie_id", "created_at", "id"]
    )
    op.create_table(
        "interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movie_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column(
            "interaction_type",
            sa.Enum(
                "view",
                "like",
                "watchlist",
                "watched",
                name="interaction_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "length(trim(movie_id)) > 0", name="ck_interactions_movie_id"
        ),
        sa.CheckConstraint("length(trim(user_id)) > 0", name="ck_interactions_user_id"),
    )
    op.create_index("ix_interactions_movie_id", "interactions", ["movie_id"])


def downgrade() -> None:
    op.drop_index("ix_interactions_movie_id", table_name="interactions")
    op.drop_table("interactions")
    op.drop_index("ix_reviews_movie_created_id", table_name="reviews")
    op.drop_table("reviews")
