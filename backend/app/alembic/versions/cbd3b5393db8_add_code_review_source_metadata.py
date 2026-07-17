"""add code review source metadata

Revision ID: cbd3b5393db8
Revises: 382ae04e7780
Create Date: 2026-07-15 09:14:54.120524

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'cbd3b5393db8'
down_revision = '382ae04e7780'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "code_review_run",
        sa.Column(
            "source_provider",
            sa.String(length=16),
            nullable=True,
        ),
    )

    op.add_column(
        "code_review_run",
        sa.Column(
            "source_url",
            sa.String(length=2048),
            nullable=True,
        ),
    )

    op.add_column(
        "code_review_run",
        sa.Column(
            "source_repository",
            sa.String(length=512),
            nullable=True,
        ),
    )

    op.add_column(
        "code_review_run",
        sa.Column(
            "source_change_number",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "code_review_run",
        sa.Column(
            "source_title",
            sa.String(length=512),
            nullable=True,
        ),
    )

    op.add_column(
        "code_review_run",
        sa.Column(
            "source_author",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "code_review_run",
        sa.Column(
            "source_base_ref",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "code_review_run",
        sa.Column(
            "source_head_ref",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "code_review_run",
        sa.Column(
            "source_base_sha",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "code_review_run",
        sa.Column(
            "source_head_sha",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "code_review_run",
        sa.Column(
            "source_fetched_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_code_review_run_source_provider",
        "code_review_run",
        ["source_provider"],
        unique=False,
    )

    op.create_index(
        "ix_code_review_run_source_repository",
        "code_review_run",
        ["source_repository"],
        unique=False,
    )

    op.create_index(
        "ix_code_review_run_source_change_number",
        "code_review_run",
        ["source_change_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_code_review_run_source_change_number",
        table_name="code_review_run",
    )

    op.drop_index(
        "ix_code_review_run_source_repository",
        table_name="code_review_run",
    )

    op.drop_index(
        "ix_code_review_run_source_provider",
        table_name="code_review_run",
    )

    op.drop_column(
        "code_review_run",
        "source_fetched_at",
    )

    op.drop_column(
        "code_review_run",
        "source_head_sha",
    )

    op.drop_column(
        "code_review_run",
        "source_base_sha",
    )

    op.drop_column(
        "code_review_run",
        "source_head_ref",
    )

    op.drop_column(
        "code_review_run",
        "source_base_ref",
    )

    op.drop_column(
        "code_review_run",
        "source_author",
    )

    op.drop_column(
        "code_review_run",
        "source_title",
    )

    op.drop_column(
        "code_review_run",
        "source_change_number",
    )

    op.drop_column(
        "code_review_run",
        "source_repository",
    )

    op.drop_column(
        "code_review_run",
        "source_url",
    )

    op.drop_column(
        "code_review_run",
        "source_provider",
    )