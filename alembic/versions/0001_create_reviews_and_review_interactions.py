"""Cria avaliações e interações de visitantes em avaliações.

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
        sa.Column("movie_id", sa.String(12), nullable=False),
        sa.Column("author_name", sa.String(50), nullable=False),
        sa.Column("rating", sa.Numeric(2, 1), nullable=False),
        sa.Column("content", sa.String(2000), nullable=False),
        sa.Column(
            "is_spoiler", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "highlights",
            postgresql.ARRAY(sa.String(32)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("movie_id ~ '^tt[0-9]{7,10}$'", name="ck_reviews_movie_id"),
        sa.CheckConstraint(
            "length(trim(author_name)) BETWEEN 2 AND 50", name="ck_reviews_author_name"
        ),
        sa.CheckConstraint(
            "rating >= 0.5 AND rating <= 5.0 AND rating * 2 = floor(rating * 2)",
            name="ck_reviews_rating",
        ),
        sa.CheckConstraint(
            "length(trim(content)) BETWEEN 10 AND 2000", name="ck_reviews_content"
        ),
        sa.CheckConstraint(
            "cardinality(highlights) <= 2", name="ck_reviews_highlights"
        ),
    )
    op.create_index(
        "ix_reviews_movie_created_id", "reviews", ["movie_id", "created_at", "id"]
    )
    op.create_table(
        "review_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visitor_id", sa.String(64), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "like",
                "spoiler",
                "well_argued",
                name="review_interaction_type",
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
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
            name="fk_review_interactions_review_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "review_id",
            "visitor_id",
            "type",
            name="uq_review_interactions_review_visitor_type",
        ),
        sa.CheckConstraint(
            "length(trim(visitor_id)) > 0", name="ck_review_interactions_visitor_id"
        ),
    )


def downgrade() -> None:
    op.drop_table("review_interactions")
    op.drop_index("ix_reviews_movie_created_id", table_name="reviews")
    op.drop_table("reviews")
