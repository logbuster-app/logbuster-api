"""Guarda o resumo da comunidade gerado por IA, um por filme.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_summaries",
        sa.Column("movie_id", sa.String(12), primary_key=True),
        sa.Column("text", sa.String(2000), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviews_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "source_review_ids",
            sa.Text(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "movie_id LIKE 'tt%' AND length(movie_id) BETWEEN 9 AND 12 "
            "AND substr(movie_id, 3) NOT GLOB '*[^0-9]*'",
            name="ck_review_summaries_movie_id",
        ),
        sa.CheckConstraint("reviews_count >= 0", name="ck_review_summaries_count"),
    )


def downgrade() -> None:
    op.drop_table("review_summaries")
